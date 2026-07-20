"""
RAG retrieval service.

Steps:
  1. Embed the question with sentence-transformers (or Gemini)
  2. Cosine similarity search in pgvector
  3. Return top-k chunks with metadata

Generation (LLM) is kept separate in ``generation``; this module only handles
retrieval and returns scored chunks with metadata.
"""

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


def retrieve(
    question: str,
    category: str | None = None,
    top_k: int = 5,
    min_score: float = 0.62,
) -> list[RetrievedChunk]:
    """
    Embed the question and return the top-k most relevant chunks.
    Falls back to full-text search on documents if no chunks are available.
    """
    embedder = _get_embedder()
    query_vector = embedder.encode_one(question)

    # Enumeration questions ("liste des ministres", "composition du...") tend to
    # have their answer spread across several small chunks of one authoritative
    # document — widen the search and allow more than one chunk per document so
    # the model doesn't see just a fragment of the list.
    enumeration = is_enumeration_query(question)
    effective_top_k = max(top_k, 9) if enumeration else top_k
    max_chunks_per_document = 4 if enumeration else 1

    conn = get_conn(vector=True)
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM chunks WHERE embedding IS NOT NULL")
            has_chunks = cur.fetchone()[0] > 0

            if not has_chunks:
                return _fulltext_search(cur, question, category, top_k)

            # "Qui est l'actuel président de la République ?"-style questions:
            # pure embedding similarity is unreliable for "who holds office X
            # today", since a short, name-specific article can rank far below
            # generic commentary repeating the same office words. A literal
            # title match on the office, most-recent first, is a much
            # stronger signal here — see enrichment.detect_office_phrase.
            boosted: list[RetrievedChunk] = []
            normalized_question = normalize_query(question)
            if is_identity_query(normalized_question):
                office_phrase = detect_office_phrase(normalized_question)
                if office_phrase:
                    boosted = _office_title_boost(
                        cur, query_vector, office_phrase, category, limit=2
                    )

            excluded_urls = {c.url for c in boosted if c.url}
            remaining_top_k = max(effective_top_k - len(boosted), 0)
            vector_results = _chunk_vector_search(
                cur,
                query_vector,
                category,
                remaining_top_k,
                min_score,
                max_chunks_per_document=max_chunks_per_document,
                excluded_urls=excluded_urls,
            )
            return boosted + vector_results
    finally:
        conn.close()


def _chunk_vector_search(
    cur,
    query_vector: list[float],
    category: str | None,
    top_k: int,
    min_score: float,
    max_chunks_per_document: int = 1,
    excluded_urls: set[str] | None = None,
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
            d.published_at
        FROM chunks c
        JOIN documents d ON d.id = c.document_id
        WHERE c.embedding IS NOT NULL
          AND d.status = 'active'
          AND length(trim(coalesce(d.title, ''))) > 15
    """
    params: list = [query_vector]

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
) -> list[RetrievedChunk]:
    """Surface the most recently published document(s) whose title literally
    names the office asked about (see enrichment.detect_office_phrase),
    one chunk per document. Ordered by publish date, not embedding score:
    for "who holds office X today", recency of the title match beats
    semantic similarity, which can't tell a pre-reform mention of an office
    from a current one.
    """
    sql = """
        SELECT title, url, source, category, content, published_at, score
        FROM (
            SELECT DISTINCT ON (d.id)
                d.title, d.url, d.source, d.category, c.content, d.published_at,
                1 - (c.embedding <=> %s::vector) AS score
            FROM documents d
            JOIN chunks c ON c.document_id = d.id
            WHERE d.status = 'active'
              AND c.embedding IS NOT NULL
              AND length(trim(coalesce(d.title, ''))) > 15
              AND d.title ILIKE %s
    """
    params: list = [query_vector, f"%{title_phrase}%"]

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
