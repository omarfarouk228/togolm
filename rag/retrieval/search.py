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
from rag.retrieval.enrichment import is_enumeration_query

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

            if has_chunks:
                return _chunk_vector_search(
                    cur,
                    query_vector,
                    category,
                    effective_top_k,
                    min_score,
                    max_chunks_per_document=max_chunks_per_document,
                )
            else:
                return _fulltext_search(cur, question, category, top_k)
    finally:
        conn.close()


def _chunk_vector_search(
    cur,
    query_vector: list[float],
    category: str | None,
    top_k: int,
    min_score: float,
    max_chunks_per_document: int = 1,
) -> list[RetrievedChunk]:
    """Vector search over chunks, joining back to documents for metadata.

    At most ``max_chunks_per_document`` chunks are kept per source URL: 1 by
    default (diversify sources for ordinary fact questions), higher for
    enumeration questions where the full answer lives in one document split
    across several chunks (see ``retrieve``).
    """
    base_sql = """
        SELECT
            d.title, d.url, d.source, d.category, c.content,
            1 - (c.embedding <=> %s::vector) AS score
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
            )
        )
        if len(results) >= top_k:
            break
    return results


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
                    plainto_tsquery('french', %s)) AS score
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
        )
        for row in rows
    ]
