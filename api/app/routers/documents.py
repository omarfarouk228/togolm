"""
GET /v1/documents         — Paginated document list with filtering
GET /v1/documents/{id}    — Single document with its chunks
GET /v1/search            — Full-text keyword search
"""

from typing import Literal

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

    sql_where = "WHERE d.status = 'active'"
    params: list = []
    if source:
        sql_where += " AND d.source = %s"
        params.append(source)
    if category:
        sql_where += " AND d.category = %s"
        params.append(category)
    if language:
        sql_where += " AND d.language = %s"
        params.append(language)

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                f"SELECT COUNT(*) FROM documents d {sql_where}",
                params,
            )
            total = cur.fetchone()[0]

            cur.execute(
                f"""
                SELECT d.id, d.source, d.url, d.category, d.subcategory,
                       d.title, d.language, d.published_at,
                       array_length(string_to_array(d.clean_content, ' '), 1) AS word_count,
                       COUNT(c.id) AS chunk_count
                FROM documents d
                LEFT JOIN chunks c ON c.document_id = d.id
                {sql_where}
                GROUP BY d.id
                ORDER BY d.collected_at DESC
                LIMIT %s OFFSET %s
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

    chunks = [
        ChunkOut(chunk_index=c[0], content=c[1], word_count=c[2])
        for c in chunk_rows
    ]

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
    """Full-text keyword search over the corpus."""
    # Build tsquery — join words with AND so results match all terms
    words = [w.strip() for w in q.split() if len(w.strip()) > 1]
    if not words:
        raise HTTPException(status_code=400, detail="Query too short")

    tsquery = " & ".join(words)

    sql_where = "WHERE status = 'active'"
    params: list = [tsquery, tsquery]
    if source:
        sql_where += " AND source = %s"
        params.append(source)
    if category:
        sql_where += " AND category = %s"
        params.append(category)

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            try:
                cur.execute(
                    f"""
                    SELECT
                        id, source, url, title, clean_content,
                        ts_rank(
                            to_tsvector('french', coalesce(title,'') || ' ' || coalesce(clean_content,'')),
                            to_tsquery('french', %s)
                        ) AS score
                    FROM documents
                    {sql_where}
                      AND to_tsvector('french', coalesce(title,'') || ' ' || coalesce(clean_content,''))
                          @@ to_tsquery('french', %s)
                    ORDER BY score DESC
                    LIMIT %s
                    """,
                    params + [limit],
                )
                rows = cur.fetchall()
            except psycopg2.Error:
                conn.rollback()
                # tsquery syntax error — fall back to ILIKE
                cur.execute(
                    f"""
                    SELECT id, source, url, title, clean_content, 0.5
                    FROM documents
                    {sql_where.replace('%s', '%s').replace('to_tsquery', '')}
                      AND (title ILIKE %s OR clean_content ILIKE %s)
                    LIMIT %s
                    """,
                    (f"%{q}%", f"%{q}%", limit)
                    + tuple(p for p in (source, category) if p),
                )
                rows = cur.fetchall()

            # COUNT uses only one tsquery placeholder + filter params
            count_params: list = [tsquery]
            if source:
                count_params.append(source)
            if category:
                count_params.append(category)
            try:
                cur.execute(
                    f"""
                    SELECT COUNT(*) FROM documents
                    {sql_where}
                      AND to_tsvector('french', coalesce(title,'') || ' ' || coalesce(clean_content,''))
                          @@ to_tsquery('french', %s)
                    """,
                    count_params,
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
            excerpt = ("…" if start > 0 else "") + content[start:idx + 200].strip() + "…"
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
