"""
GET /v1/documents         — Paginated document list with filtering
GET /v1/documents/{id}    — Single document with its chunks
GET /v1/search            — Full-text keyword search
"""

import psycopg2
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from api.app.db import get_conn

router = APIRouter(tags=["Documents"])


class ChunkOut(BaseModel):
    chunk_index: int
    content: str
    word_count: int | None


class DocumentSummary(BaseModel):
    id: str
    source: str
    url: str | None
    category: str | None
    subcategory: str | None
    title: str | None
    language: str | None
    published_at: str | None
    word_count: int | None
    chunk_count: int


class DocumentDetail(DocumentSummary):
    clean_content: str | None
    chunks: list[ChunkOut]


class DocumentListResponse(BaseModel):
    documents: list[DocumentSummary]
    total: int
    page: int
    page_size: int
    pages: int


class SearchResult(BaseModel):
    id: str
    source: str
    url: str | None
    title: str | None
    excerpt: str
    score: float
    category: str | None


class SearchResponse(BaseModel):
    results: list[SearchResult]
    total: int
    query: str


@router.get("/documents", response_model=DocumentListResponse)
def list_documents(
    source: str | None = Query(None, description="Filter by source domain"),
    category: str | None = Query(None, description="Filter by category"),
    language: str | None = Query(None, description="Filter by language code"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """List corpus documents with optional filtering and pagination."""
    offset = (page - 1) * page_size

    where_clauses = ["d.status = 'active'"]
    params: list = []
    if source:
        where_clauses.append("d.source = %s")
        params.append(source)
    if category:
        where_clauses.append("d.category = %s")
        params.append(category)
    if language:
        where_clauses.append("d.language = %s")
        params.append(language)

    sql_where = "WHERE " + " AND ".join(where_clauses)

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                f"SELECT COUNT(*) FROM documents d {sql_where}",
                params,
            )
            total = cur.fetchone()[0]

            # Paginate first (cheap), then count chunks only for the returned page.
            # The old JOIN+GROUP BY scanned all chunks before applying LIMIT.
            cur.execute(
                f"""
                WITH paged AS (
                    SELECT d.id, d.source, d.url, d.category, d.subcategory,
                           d.title, d.language, d.published_at, d.word_count,
                           d.collected_at
                    FROM documents d
                    {sql_where}
                    ORDER BY d.collected_at DESC
                    LIMIT %s OFFSET %s
                )
                SELECT p.id, p.source, p.url, p.category, p.subcategory,
                       p.title, p.language, p.published_at, p.word_count,
                       COALESCE(cc.n, 0) AS chunk_count
                FROM paged p
                LEFT JOIN (
                    SELECT document_id, COUNT(*) AS n
                    FROM chunks
                    WHERE document_id IN (SELECT id FROM paged)
                    GROUP BY document_id
                ) cc ON cc.document_id = p.id
                ORDER BY p.collected_at DESC
                """,
                params + [page_size, offset],
            )
            rows = cur.fetchall()
    finally:
        conn.close()

    docs = [
        DocumentSummary(
            id=str(row[0]),
            source=row[1] or "",
            url=row[2],
            category=row[3],
            subcategory=row[4],
            title=row[5],
            language=row[6],
            published_at=row[7].isoformat() if row[7] else None,
            word_count=row[8],
            chunk_count=row[9] or 0,
        )
        for row in rows
    ]

    return DocumentListResponse(
        documents=docs,
        total=total,
        page=page,
        page_size=page_size,
        pages=(total + page_size - 1) // page_size,
    )


@router.get("/documents/{doc_id}", response_model=DocumentDetail)
def get_document(doc_id: str):
    """Fetch a single document with its text chunks."""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT d.id, d.source, d.url, d.category, d.subcategory,
                       d.title, d.language, d.published_at,
                       array_length(string_to_array(d.clean_content, ' '), 1),
                       d.clean_content
                FROM documents d
                WHERE d.id = %s AND d.status = 'active'
                """,
                (doc_id,),
            )
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Document not found")

            cur.execute(
                """
                SELECT chunk_index, content, word_count
                FROM chunks
                WHERE document_id = %s
                ORDER BY chunk_index
                """,
                (doc_id,),
            )
            chunk_rows = cur.fetchall()
    finally:
        conn.close()

    chunks = [ChunkOut(chunk_index=c[0], content=c[1], word_count=c[2]) for c in chunk_rows]

    return DocumentDetail(
        id=str(row[0]),
        source=row[1] or "",
        url=row[2],
        category=row[3],
        subcategory=row[4],
        title=row[5],
        language=row[6],
        published_at=row[7].isoformat() if row[7] else None,
        word_count=row[8],
        chunk_count=len(chunks),
        clean_content=row[9],
        chunks=chunks,
    )


@router.get("/search", response_model=SearchResponse)
def search_documents(
    q: str = Query(..., min_length=2, max_length=500, description="Search query"),
    source: str | None = Query(None),
    category: str | None = Query(None),
    limit: int = Query(10, ge=1, le=50),
):
    """Full-text keyword search over the corpus.

    Uses the pre-computed fts_vector column with a GIN index for fast search.
    Falls back to ILIKE if the tsquery syntax is invalid.
    """
    # Build tsquery — OR between words so partial queries still return results
    words = [w.strip() for w in q.split() if len(w.strip()) > 1]
    if not words:
        raise HTTPException(status_code=400, detail="Query too short")

    tsquery = " | ".join(words)

    filters = ["status = 'active'", "fts_vector IS NOT NULL"]
    filter_params: list = []
    if source:
        filters.append("source = %s")
        filter_params.append(source)
    if category:
        filters.append("category = %s")
        filter_params.append(category)
    where_clause = "WHERE " + " AND ".join(filters)

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            try:
                # Main search — uses the GIN index on fts_vector (fast)
                cur.execute(
                    f"""
                    SELECT
                        id, source, url, title, clean_content,
                        ts_rank(fts_vector, to_tsquery('french', %s)) AS score
                    FROM documents
                    {where_clause}
                      AND fts_vector @@ to_tsquery('french', %s)
                    ORDER BY score DESC
                    LIMIT %s
                    """,
                    [tsquery] + filter_params + [tsquery, limit],
                )
                rows = cur.fetchall()
            except psycopg2.Error:
                conn.rollback()
                # tsquery syntax error (e.g. single special char) — fall back to ILIKE on title
                cur.execute(
                    f"""
                    SELECT id, source, url, title, clean_content, 0.5
                    FROM documents
                    {where_clause}
                      AND (title ILIKE %s OR clean_content ILIKE %s)
                    LIMIT %s
                    """,
                    filter_params + [f"%{q}%", f"%{q}%", limit],
                )
                rows = cur.fetchall()

            try:
                cur.execute(
                    f"""
                    SELECT COUNT(*) FROM documents
                    {where_clause}
                      AND fts_vector @@ to_tsquery('french', %s)
                    """,
                    filter_params + [tsquery],
                )
                total = cur.fetchone()[0]
            except Exception:
                conn.rollback()
                total = len(rows)
    finally:
        conn.close()

    results = []
    for row in rows:
        content = row[4] or ""
        # Extract a short excerpt around the first match
        q_lower = q.lower()
        idx = content.lower().find(q_lower.split()[0])
        if idx >= 0:
            start = max(0, idx - 100)
            excerpt = ("…" if start > 0 else "") + content[start : idx + 200].strip() + "…"
        else:
            excerpt = content[:200] + "…" if len(content) > 200 else content

        results.append(
            SearchResult(
                id=str(row[0]),
                source=row[1] or "",
                url=row[2],
                title=row[3],
                excerpt=excerpt,
                score=round(float(row[5]), 4),
                category=None,
            )
        )

    return SearchResponse(results=results, total=total, query=q)
