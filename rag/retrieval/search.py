"""
RAG retrieval service.

Steps:
  1. Embed the question (Gemini RETRIEVAL_QUERY, or the local model)
  2. Rank chunks two ways: cosine similarity in pgvector, and French
     full-text search over documents (fts_vector)
  3. Fuse both rankings with Reciprocal Rank Fusion, return top-k chunks

Generation (LLM) is kept separate in ``generation``; this module only handles
retrieval and returns scored chunks with metadata.
"""

import os
import time
from dataclasses import dataclass

from db import get_conn
from rag.indexation.embedder import get_embedder
from rag.retrieval.enrichment import (
    detect_office_phrase,
    is_enumeration_query,
    is_identity_query,
    normalize_query,
)

_embedder = None

# pgvector's ANN indexes default to very low recall at this corpus size: with
# ivfflat (lists=350) the default probes=1 scans ~1/350 of the vectors, measured
# on prod at 59% recall@10 vs 95.5% with probes=20. Both settings are harmless
# when the other index type is in use.
IVFFLAT_PROBES = int(os.getenv("RAG_IVFFLAT_PROBES", "20"))
HNSW_EF_SEARCH = int(os.getenv("RAG_HNSW_EF_SEARCH", "100"))


def _configure_ann(cur) -> None:
    cur.execute(f"SET ivfflat.probes = {IVFFLAT_PROBES}")
    cur.execute(f"SET hnsw.ef_search = {HNSW_EF_SEARCH}")
    # Keep scanning the HNSW graph when WHERE filters drop candidates, instead
    # of returning fewer than LIMIT rows (pgvector >= 0.8).
    cur.execute("SET hnsw.iterative_scan = relaxed_order")


# ── Hybrid retrieval ─────────────────────────────────────────────────────────
# Pure vector search misses exact identifiers and acronyms (NIF, OTR, RGPH-5,
# CFE...) and anything whose vector is missing or stale. Measured on prod: for
# "Comment obtenir un NIF auprès de l'OTR ?" vector search surfaced no otr.tg
# page, while full-text ranked OTR's NIF page first. Both rankings are fused
# with RRF, which needs no score calibration between the two systems.
RRF_K = 60
FTS_WEIGHT = 0.7  # full-text is noisier on long questions; vector stays primary
FTS_CANDIDATES = 10
# Score given to chunks found by full-text only that have no usable vector, so
# they clear the source-display threshold (api.app.features.query.router).
FTS_ONLY_SCORE = 0.70
# Words present in nearly every document, dropped before even counting them.
FTS_IGNORED_TEXT = "Togo togolais togolaise togolaises République pays"

# Cosine floor for a chunk to reach the model. Calibrated for RETRIEVAL_QUERY
# query embeddings, which score ~0.09 lower than the old symmetric ones.
DEFAULT_MIN_SCORE = 0.55


# Chunks are small (~60 words, sized for the old local embedding model), which
# keeps search precise but gave the model only ~300 words of context for five
# sources. Each retrieved chunk is widened with its neighbours in the same
# document before generation: "small to big" retrieval, no re-embedding needed.
CONTEXT_NEIGHBORS = int(os.getenv("RAG_CONTEXT_NEIGHBORS", "1"))


def _position(row) -> dict:
    """document_id/chunk_index from columns 7-8 of a retrieval row, if present."""
    if len(row) < 9 or row[7] is None:
        return {}
    return {"document_id": str(row[7]), "chunk_index": row[8]}


def _join_overlapping(left: str, right: str, max_overlap_words: int = 30) -> str:
    """Concatenate consecutive chunks, dropping the words they share (the
    chunker repeats the last few words of a chunk at the start of the next)."""
    a, b = left.split(), right.split()
    for n in range(min(max_overlap_words, len(a), len(b)), 0, -1):
        if a[-n:] == b[:n]:
            return " ".join(a + b[n:])
    return f"{left} {right}"


def expand_with_neighbors(cur, chunks: list["RetrievedChunk"], window: int = CONTEXT_NEIGHBORS):
    """Replace each chunk's content with itself plus `window` chunks on each
    side from the same document. Documents contributing several chunks (list
    questions) are left as they are, so their text isn't repeated. Any error
    leaves the chunks unchanged."""
    if window <= 0:
        return chunks
    per_doc: dict[str, int] = {}
    for c in chunks:
        if c.document_id:
            per_doc[c.document_id] = per_doc.get(c.document_id, 0) + 1
    targets = [
        c
        for c in chunks
        if c.document_id and c.chunk_index is not None and per_doc[c.document_id] == 1
    ]
    if not targets:
        return chunks
    try:
        cur.execute(
            """
            SELECT c.document_id, c.chunk_index, c.content
            FROM chunks c
            JOIN unnest(%s::uuid[], %s::int[]) AS w(doc, idx)
              ON c.document_id = w.doc
             AND c.chunk_index BETWEEN w.idx - %s AND w.idx + %s
            """,
            ([c.document_id for c in targets], [c.chunk_index for c in targets], window, window),
        )
        by_doc: dict[str, dict[int, str]] = {}
        for doc_id, idx, content in cur.fetchall():
            by_doc.setdefault(str(doc_id), {})[idx] = content
    except Exception:
        return chunks
    for c in targets:
        pieces = by_doc.get(c.document_id, {})
        text = ""
        for idx in range(c.chunk_index - window, c.chunk_index + window + 1):
            piece = c.content if idx == c.chunk_index else pieces.get(idx)
            if piece:
                text = _join_overlapping(text, piece) if text else piece
        c.content = text or c.content
    return chunks


def _get_embedder():
    global _embedder
    if _embedder is None:
        _embedder = get_embedder()
    return _embedder


@dataclass
class RetrievedChunk:
    title: str
    url: str | None
    source: str
    category: str
    content: str
    score: float
    published_at: str | None = None
    # Position of the chunk in its document, used to add neighbouring chunks
    # to the context (see expand_with_neighbors).
    document_id: str | None = None
    chunk_index: int | None = None


def retrieve(
    question: str,
    category: str | None = None,
    top_k: int = 5,
    min_score: float = DEFAULT_MIN_SCORE,
) -> list[RetrievedChunk]:
    """
    Return the top-k most relevant chunks for the question (hybrid search).
    Falls back to full-text only when the query can't be embedded (embedding
    API down) or no chunk has a vector yet.
    """
    embedder = _get_embedder()
    try:
        query_vector = embedder.encode_query(question)
    except Exception:
        query_vector = None
    model_id = getattr(embedder, "model_id", None)

    # Enumeration questions ("liste des ministres", "composition du...") tend to
    # have their answer spread across several small chunks of one authoritative
    # document: widen the search and allow more than one chunk per document so
    # the model doesn't see just a fragment of the list.
    enumeration = is_enumeration_query(question)
    effective_top_k = max(top_k, 9) if enumeration else top_k
    max_chunks_per_document = 4 if enumeration else 1

    conn = get_conn(vector=True)
    try:
        with conn.cursor() as cur:
            # EXISTS stops at the first row; COUNT(*) scanned ~300k rows on
            # every question (~170 ms on prod).
            cur.execute("SELECT EXISTS (SELECT 1 FROM chunks WHERE embedding IS NOT NULL)")
            has_chunks = bool(cur.fetchone()[0])

            if not has_chunks:
                return _fulltext_search(cur, question, category, top_k)
            if query_vector is None:
                return expand_with_neighbors(
                    cur, _fulltext_chunk_search(cur, question, None, category, top_k, model_id)
                )

            _configure_ann(cur)

            # "Qui est l'actuel président de la République ?"-style questions:
            # pure embedding similarity is unreliable for "who holds office X
            # today", since a short, name-specific article can rank far below
            # generic commentary repeating the same office words. A literal
            # title match on the office, most-recent first, is a much
            # stronger signal here (see enrichment.detect_office_phrase).
            boosted: list[RetrievedChunk] = []
            normalized_question = normalize_query(question)
            if is_identity_query(normalized_question):
                office_phrase = detect_office_phrase(normalized_question)
                if office_phrase:
                    boosted = _office_title_boost(
                        cur, query_vector, office_phrase, category, limit=2, model_id=model_id
                    )

            excluded_urls = {c.url for c in boosted if c.url}
            remaining_top_k = max(effective_top_k - len(boosted), 0)
            if remaining_top_k == 0:
                return expand_with_neighbors(cur, boosted)
            vector_results = _chunk_vector_search(
                cur,
                query_vector,
                category,
                remaining_top_k * 2,
                min_score,
                max_chunks_per_document=max_chunks_per_document,
                excluded_urls=excluded_urls,
                model_id=model_id,
            )
            fts_results = [
                c
                for c in _fulltext_chunk_search(
                    cur, question, query_vector, category, FTS_CANDIDATES, model_id
                )
                if not (c.url and c.url in excluded_urls)
            ]
            fused = fuse_rankings(
                vector_results,
                fts_results,
                top_k=remaining_top_k,
                max_chunks_per_document=max_chunks_per_document,
            )
            return expand_with_neighbors(cur, boosted + fused)
    finally:
        conn.close()


def fuse_rankings(
    vector_results: list[RetrievedChunk],
    fts_results: list[RetrievedChunk],
    top_k: int,
    max_chunks_per_document: int = 1,
) -> list[RetrievedChunk]:
    """Reciprocal Rank Fusion of the vector and full-text rankings.

    A chunk's fused score is sum(weight / (RRF_K + rank)) over the lists it
    appears in. With one chunk per document, both lists are matched by URL, so
    a document found by both systems ranks first even if the two picked
    different chunks of it (the vector system's chunk is kept).
    """

    def key(c: RetrievedChunk):
        if c.url and max_chunks_per_document == 1:
            return c.url
        return (c.url, c.content)

    fused: dict = {}
    for weight, ranking in ((1.0, vector_results), (FTS_WEIGHT, fts_results)):
        for rank, chunk in enumerate(ranking, start=1):
            k = key(chunk)
            entry = fused.setdefault(k, [0.0, chunk])
            entry[0] += weight / (RRF_K + rank)

    ordered = sorted(fused.values(), key=lambda e: e[0], reverse=True)
    per_doc: dict[str, int] = {}
    results: list[RetrievedChunk] = []
    for _, chunk in ordered:
        if chunk.url:
            n = per_doc.get(chunk.url, 0)
            if n >= max_chunks_per_document:
                continue
            per_doc[chunk.url] = n + 1
        results.append(chunk)
        if len(results) >= top_k:
            break
    return results


# Lexemes found in more than this share of documents are dropped from the
# full-text query: OR-ing a very common word ("obtenir", "document") makes
# Postgres rank tens of thousands of documents (5-7 s measured on prod) while
# barely changing the result. Document frequencies are cached per process.
FTS_MAX_DOC_SHARE = 0.03
FTS_DF_CACHE_TTL_S = 6 * 3600
_df_cache: dict[str, tuple[int, float]] = {}
_doc_total: tuple[int, float] | None = None


def _build_or_tsquery(cur, question: str) -> str | None:
    """OR-tsquery of the question's discriminating French lexemes, or None."""
    global _doc_total
    now = time.monotonic()
    cur.execute(
        """
        SELECT DISTINCT lexeme FROM unnest(to_tsvector('french', %s))
        WHERE length(lexeme) > 1
          AND lexeme <> ALL (tsvector_to_array(to_tsvector('french', %s)))
        """,
        (question, FTS_IGNORED_TEXT),
    )
    lexemes = [r[0] for r in cur.fetchall()]
    if not lexemes:
        return None

    if _doc_total is None or now - _doc_total[1] > FTS_DF_CACHE_TTL_S:
        cur.execute("SELECT reltuples::bigint FROM pg_class WHERE relname = 'documents'")
        row = cur.fetchone()
        _doc_total = (max(int(row[0]) if row else 0, 1), now)

    missing = [
        lx for lx in lexemes if lx not in _df_cache or now - _df_cache[lx][1] > FTS_DF_CACHE_TTL_S
    ]
    if missing:
        cur.execute(
            """
            SELECT lx, (
                SELECT count(*) FROM documents WHERE fts_vector @@ quote_literal(lx)::tsquery
            )
            FROM unnest(%s::text[]) AS lx
            """,
            (missing,),
        )
        for lx, df in cur.fetchall():
            _df_cache[lx] = (int(df), now)

    max_df = FTS_MAX_DOC_SHARE * _doc_total[0]
    by_rarity = sorted(lexemes, key=lambda lx: _df_cache[lx][0])
    kept = [lx for lx in by_rarity if 0 < _df_cache[lx][0] <= max_df]
    if not kept:
        # Only common words: the two rarest still beat no full-text signal.
        kept = [lx for lx in by_rarity if _df_cache[lx][0] > 0][:2]
    if not kept:
        return None
    return " | ".join("'" + lx.replace("'", "''") + "'" for lx in kept)


def _fulltext_chunk_search(
    cur,
    question: str,
    query_vector: list[float] | None,
    category: str | None,
    limit: int,
    model_id: str | None,
) -> list[RetrievedChunk]:
    """Full-text ranking of documents (indexed fts_vector), one chunk each.

    The query ORs the question's discriminating lexemes (see _build_or_tsquery)
    so long natural-language questions still match; ts_rank_cd puts documents
    matching more of them first. For each document, the chunk sharing the most
    lexemes with the question is returned. Its score is its cosine similarity
    when it has a vector from the canonical model, else FTS_ONLY_SCORE. Low
    cosine scores are NOT filtered out here: the lexical match is the signal,
    and a stale vector (legacy model) must not hide an exact-term hit.
    """
    tsquery = _build_or_tsquery(cur, question)
    if tsquery is None:
        return []

    sql = """
        WITH q AS (SELECT %(tsquery)s::tsquery AS tsq),
        docs AS (
            SELECT d.id, d.title, d.url, d.source, d.category, d.published_at,
                   ts_rank_cd(d.fts_vector, q.tsq, 32) AS rank
            FROM documents d, q
            WHERE d.fts_vector @@ q.tsq
              AND d.status = 'active'
              AND length(trim(coalesce(d.title, ''))) > 15
              {category_filter}
            ORDER BY rank DESC
            LIMIT %(limit)s
        )
        SELECT docs.title, docs.url, docs.source, docs.category, best.content,
               best.score, docs.published_at, docs.id, best.chunk_index
        FROM docs
        CROSS JOIN q
        CROSS JOIN LATERAL (
            SELECT c.content, c.chunk_index,
                   CASE
                       WHEN %(vector)s::vector IS NOT NULL
                        AND c.embedding IS NOT NULL
                        {model_filter}
                       THEN 1 - (c.embedding <=> %(vector)s::vector)
                   END AS score
            FROM chunks c
            WHERE c.document_id = docs.id
            ORDER BY ts_rank_cd(to_tsvector('french', c.content), q.tsq) DESC, c.chunk_index
            LIMIT 1
        ) best
        ORDER BY docs.rank DESC
    """
    params = {"tsquery": tsquery, "limit": limit, "vector": query_vector, "model_id": model_id}
    category_filter = ""
    if category:
        category_filter = "AND d.category = %(category)s"
        params["category"] = category
    model_filter = ""
    if model_id:
        model_filter = "AND (c.embedding_model IS NULL OR c.embedding_model = %(model_id)s)"
    cur.execute(sql.format(category_filter=category_filter, model_filter=model_filter), params)

    return [
        RetrievedChunk(
            title=row[0] or "",
            url=row[1],
            source=row[2] or "",
            category=row[3] or "",
            content=row[4] or "",
            score=float(row[5]) if row[5] is not None else FTS_ONLY_SCORE,
            published_at=str(row[6]) if row[6] else None,
            **_position(row),
        )
        for row in cur.fetchall()
    ]


def _chunk_vector_search(
    cur,
    query_vector: list[float],
    category: str | None,
    top_k: int,
    min_score: float,
    max_chunks_per_document: int = 1,
    excluded_urls: set[str] | None = None,
    model_id: str | None = None,
) -> list[RetrievedChunk]:
    """Vector search over chunks, joining back to documents for metadata.

    At most ``max_chunks_per_document`` chunks are kept per source URL: 1 by
    default (diversify sources for ordinary fact questions), higher for
    enumeration questions where the full answer lives in one document split
    across several chunks (see ``retrieve``). ``excluded_urls`` skips
    documents already surfaced by ``_office_title_boost`` so they aren't
    duplicated in the fill.
    """
    if top_k <= 0:
        return []

    base_sql = """
        SELECT
            d.title, d.url, d.source, d.category, c.content,
            1 - (c.embedding <=> %s::vector) AS score,
            d.published_at, c.document_id, c.chunk_index
        FROM chunks c
        JOIN documents d ON d.id = c.document_id
        WHERE c.embedding IS NOT NULL
          AND d.status = 'active'
          AND length(trim(coalesce(d.title, ''))) > 15
    """
    params: list = [query_vector]

    if model_id:
        # Skip vectors known to come from another model (meaningless scores);
        # untagged legacy vectors stay searchable until the backfill sorts them.
        base_sql += " AND (c.embedding_model IS NULL OR c.embedding_model = %s)"
        params.append(model_id)

    if category:
        base_sql += " AND d.category = %s"
        params.append(category)

    # Fetch extra candidates so there's enough headroom to pull several chunks
    # from the same top document when max_chunks_per_document > 1.
    base_sql += " ORDER BY c.embedding <=> %s::vector LIMIT %s"
    params += [query_vector, top_k * 4]

    cur.execute(base_sql, params)
    rows = cur.fetchall()

    doc_chunk_counts: dict[str, int] = {}
    results: list[RetrievedChunk] = []
    for row in rows:
        score = float(row[5])
        if score < min_score:
            continue
        url = row[1]
        if url and excluded_urls and url in excluded_urls:
            continue
        # Only cap documents that have a URL; null-URL docs are always distinct
        if url:
            count = doc_chunk_counts.get(url, 0)
            if count >= max_chunks_per_document:
                continue
            doc_chunk_counts[url] = count + 1
        results.append(
            RetrievedChunk(
                title=row[0] or "",
                url=url,
                source=row[2] or "",
                category=row[3] or "",
                content=row[4] or "",
                score=score,
                published_at=str(row[6]) if row[6] else None,
                **_position(row),
            )
        )
        if len(results) >= top_k:
            break
    return results


def _office_title_boost(
    cur,
    query_vector: list[float],
    title_phrase: str,
    category: str | None,
    limit: int,
    model_id: str | None = None,
) -> list[RetrievedChunk]:
    """Surface the most recently published document(s) whose title literally
    names the office asked about (see enrichment.detect_office_phrase),
    one chunk per document. Ordered by publish date, not embedding score:
    for "who holds office X today", recency of the title match beats
    semantic similarity, which can't tell a pre-reform mention of an office
    from a current one.
    """
    sql = """
        SELECT title, url, source, category, content, published_at, score,
               document_id, chunk_index
        FROM (
            SELECT DISTINCT ON (d.id)
                d.title, d.url, d.source, d.category, c.content, d.published_at,
                1 - (c.embedding <=> %s::vector) AS score,
                d.id AS document_id, c.chunk_index
            FROM documents d
            JOIN chunks c ON c.document_id = d.id
            WHERE d.status = 'active'
              AND c.embedding IS NOT NULL
              AND length(trim(coalesce(d.title, ''))) > 15
              AND d.title ILIKE %s
    """
    params: list = [query_vector, f"%{title_phrase}%"]

    if model_id:
        sql += " AND (c.embedding_model IS NULL OR c.embedding_model = %s)"
        params.append(model_id)

    if category:
        sql += " AND d.category = %s"
        params.append(category)

    sql += """
            ORDER BY d.id, c.chunk_index ASC
        ) ranked
        ORDER BY published_at DESC NULLS LAST
        LIMIT %s
    """
    params.append(limit)

    cur.execute(sql, params)
    return [
        RetrievedChunk(
            title=row[0] or "",
            url=row[1],
            source=row[2] or "",
            category=row[3] or "",
            content=row[4] or "",
            published_at=str(row[5]) if row[5] else None,
            score=float(row[6]),
            **_position(row),
        )
        for row in cur.fetchall()
    ]


def _fulltext_search(
    cur,
    question: str,
    category: str | None,
    top_k: int,
) -> list[RetrievedChunk]:
    """PostgreSQL full-text search fallback when chunks are missing."""
    # plainto_tsquery handles arbitrary text safely (no syntax errors from apostrophes etc.)
    base_sql = """
        SELECT
            title, url, source, category, clean_content,
            ts_rank(to_tsvector('french', coalesce(clean_content,'')),
                    plainto_tsquery('french', %s)) AS score,
            published_at
        FROM documents
        WHERE status = 'active'
          AND to_tsvector('french', coalesce(clean_content,'')) @@ plainto_tsquery('french', %s)
    """
    params: list = [question, question]

    if category:
        base_sql += " AND category = %s"
        params.append(category)

    base_sql += " ORDER BY score DESC LIMIT %s"
    params.append(top_k)

    cur.execute(base_sql, params)
    rows = cur.fetchall()

    return [
        RetrievedChunk(
            title=row[0] or "",
            url=row[1],
            source=row[2] or "",
            category=row[3] or "",
            content=row[4] or "",
            score=float(row[5]),
            published_at=str(row[6]) if row[6] else None,
        )
        for row in rows
    ]
