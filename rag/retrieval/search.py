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

    conn = get_conn(vector=True)
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM chunks WHERE embedding IS NOT NULL")
            has_chunks = cur.fetchone()[0] > 0

            if has_chunks:
                return _chunk_vector_search(cur, query_vector, category, top_k, min_score)
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
) -> list[RetrievedChunk]:
    """Vector search over chunks, joining back to documents for metadata."""
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

    base_sql += " ORDER BY c.embedding <=> %s::vector LIMIT %s"
    params += [query_vector, top_k * 2]

    cur.execute(base_sql, params)
    rows = cur.fetchall()

    seen_urls: set[str] = set()
    results: list[RetrievedChunk] = []
    for row in rows:
        score = float(row[5])
        if score < min_score:
            continue
        url = row[1] or ""
        if url in seen_urls:
            continue
        seen_urls.add(url)
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
    words = [w for w in question.split() if len(w) > 2]
    tsquery = " | ".join(words) if words else question

    base_sql = """
        SELECT
            title, url, source, category, clean_content,
            ts_rank(to_tsvector('french', coalesce(clean_content,'')),
                    to_tsquery('french', %s)) AS score
        FROM documents
        WHERE status = 'active'
          AND to_tsvector('french', coalesce(clean_content,'')) @@ to_tsquery('french', %s)
    """
    params: list = [tsquery, tsquery]

    if category:
        base_sql += " AND category = %s"
        params.append(category)

    base_sql += " ORDER BY score DESC LIMIT %s"
    params.append(top_k)

    try:
        cur.execute(base_sql, params)
        rows = cur.fetchall()
    except Exception:
        cur.execute(
            """
            SELECT title, url, source, category, clean_content, 0.5 AS score
            FROM documents
            WHERE status = 'active' AND clean_content ILIKE %s
            LIMIT %s
            """,
            [f"%{question}%", top_k],
        )
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
