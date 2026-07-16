"""
GET /v1/categories       — List corpus categories
GET /v1/stats            — Public corpus statistics
GET /v1/documents/recent — Small fixed-size list of recent documents for display
"""

from fastapi import APIRouter, Query
from pydantic import BaseModel

from db import get_conn

router = APIRouter(tags=["Corpus"])

RECENT_DOCUMENTS_MAX_LIMIT = 12

CATEGORIES = [
    "administrative",
    "legal",
    "education",
    "economy",
    "health",
    "agriculture",
    "politics",
    "press",
]


class CategoryResponse(BaseModel):
    categories: list[str]
    total: int


class SourceStat(BaseModel):
    source: str
    documents: int
    chunks: int


class RecentDocument(BaseModel):
    id: str
    source: str
    url: str | None
    title: str | None
    category: str | None


class RecentDocumentsResponse(BaseModel):
    documents: list[RecentDocument]


class StatsResponse(BaseModel):
    model_config = {"protected_namespaces": ()}

    total_documents: int
    total_chunks: int
    languages: list[str]
    categories: list[str]
    sources: list[SourceStat]
    last_updated: str | None
    model_version: str


@router.get("/categories", response_model=CategoryResponse)
async def list_categories():
    """Return the list of available corpus categories."""
    return CategoryResponse(categories=CATEGORIES, total=len(CATEGORIES))


@router.get("/stats", response_model=StatsResponse)
async def corpus_stats():
    """Return live statistics about the corpus from PostgreSQL."""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM documents WHERE status = 'active'")
            total_docs = cur.fetchone()[0]

            cur.execute("SELECT COUNT(*) FROM chunks WHERE embedding IS NOT NULL")
            total_chunks = cur.fetchone()[0]

            cur.execute("SELECT DISTINCT language FROM documents WHERE status = 'active'")
            languages = [row[0] for row in cur.fetchall() if row[0]]

            cur.execute(
                "SELECT MAX(GREATEST(collected_at, updated_at)) FROM documents WHERE status = 'active'"
            )
            last_updated = cur.fetchone()[0]

            cur.execute(
                """
                SELECT d.source, COUNT(DISTINCT d.id), COUNT(c.id)
                FROM documents d
                LEFT JOIN chunks c ON c.document_id = d.id
                WHERE d.status = 'active'
                GROUP BY d.source
                ORDER BY COUNT(DISTINCT d.id) DESC
                """
            )
            source_rows = cur.fetchall()
    finally:
        conn.close()

    sources = [
        SourceStat(source=row[0], documents=row[1], chunks=row[2] or 0) for row in source_rows
    ]

    return StatsResponse(
        total_documents=total_docs,
        total_chunks=total_chunks,
        languages=sorted(languages) or ["fr"],
        categories=CATEGORIES,
        sources=sources,
        last_updated=last_updated.isoformat() if last_updated else None,
        model_version="togolm-embed-v1",
    )


@router.get("/documents/recent", response_model=RecentDocumentsResponse)
async def recent_documents(limit: int = Query(6, ge=1, le=RECENT_DOCUMENTS_MAX_LIMIT)):
    """Small, unauthenticated, non-rate-limited feed of recent documents for display
    (homepage, marketing surfaces). Not paginated or filterable — use GET /v1/documents
    for browsing, which stays behind the rate limit."""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, source, url, title, category
                FROM documents
                WHERE status = 'active'
                ORDER BY collected_at DESC
                LIMIT %s
                """,
                (limit,),
            )
            rows = cur.fetchall()
    finally:
        conn.close()

    return RecentDocumentsResponse(
        documents=[
            RecentDocument(id=str(row[0]), source=row[1] or "", url=row[2], title=row[3], category=row[4])
            for row in rows
        ]
    )
