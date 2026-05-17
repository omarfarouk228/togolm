"""
RAG retrieval service.

Steps:
  1. Embed the question with sentence-transformers (or Gemini)
  2. Cosine similarity search in pgvector
  3. Return top-k chunks with metadata

Generation (LLM) is kept separate — this module only handles retrieval.
When Gemini key is available, generation can be added on top.
"""

import os
from dataclasses import dataclass

import psycopg2
from pgvector.psycopg2 import register_vector

from corpus.processors.embedder import get_embedder

_embedder = None


def _get_embedder():
    global _embedder
    if _embedder is None:
        _embedder = get_embedder()
    return _embedder


def _get_conn():
    password = os.getenv("POSTGRES_PASSWORD") or None
    conn = psycopg2.connect(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=int(os.getenv("POSTGRES_PORT", "5432")),
        dbname=os.getenv("POSTGRES_DB", "togolm"),
        user=os.getenv("POSTGRES_USER"),
        password=password,
    )
    register_vector(conn)
    return conn


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
    min_score: float = 0.3,
) -> list[RetrievedChunk]:
    """
    Embed the question and return the top-k most relevant chunks.
    Falls back to full-text search on documents if no chunks are available.
    """
    embedder = _get_embedder()
    query_vector = embedder.encode_one(question)

    conn = _get_conn()
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
    """
    params: list = [query_vector]

    if category:
        base_sql += " AND d.category = %s"
        params.append(category)

    base_sql += " ORDER BY c.embedding <=> %s::vector LIMIT %s"
    params += [query_vector, top_k]

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
        if float(row[5]) >= min_score
    ]


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


def build_answer(question: str, chunks: list[RetrievedChunk]) -> str:
    """
    Assemble an answer from retrieved chunks.
    Without a generation model, we surface the most relevant passage.
    When Gemini key is set, this can be replaced by a proper LLM call.
    """
    if not chunks:
        return "No relevant information found in the TogoLM corpus for this question."

    if os.getenv("GEMINI_API_KEY"):
        try:
            return _generate_with_gemini(question, chunks)
        except Exception:
            pass  # Fall through to extractive answer

    # Extractive fallback: return the top passage with attribution
    top = chunks[0]
    excerpt = top.content[:800].rsplit(" ", 1)[0] + "…" if len(top.content) > 800 else top.content
    return f"{excerpt}\n\n[Source: {top.source}]"


def _generate_with_gemini(question: str, chunks: list[RetrievedChunk]) -> str:
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

    context = "\n\n".join(
        f"[{c.source} — {c.title}]\n{c.content[:600]}" for c in chunks
    )

    prompt = f"""You are TogoLM, an AI assistant specialized in Togolese knowledge.
Answer the following question based only on the provided context.
If the context does not contain enough information, say so clearly.
Answer in the same language as the question.

CONTEXT:
{context}

QUESTION: {question}

ANSWER:"""

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
        config=types.GenerateContentConfig(max_output_tokens=1000),
    )
    return response.text
