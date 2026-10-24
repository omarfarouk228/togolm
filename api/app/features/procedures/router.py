"""
GET /v1/procedures       — Administrative procedures, searchable (fiches démarches)
GET /v1/procedures/{id}  — One procedure as a structured card

Public and read-only, like the corpus stats: browsing procedures must not use
up a visitor's daily question quota.
"""

import uuid

from fastapi import APIRouter, HTTPException, Query

from db import get_conn
from rag.procedures import PROCEDURE_SOURCES, procedure_card

router = APIRouter(tags=["Procedures"])


def _rows(
    where: str, params: list, limit: int, offset: int, order: str, order_params: tuple = ()
) -> list[tuple]:
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT id::text, title, url, source, clean_content
                FROM documents
                WHERE status = 'active' AND source = ANY(%s) {where}
                ORDER BY {order}
                LIMIT %s OFFSET %s
                """,
                [list(PROCEDURE_SOURCES), *params, *order_params, limit, offset],
            )
            return cur.fetchall()
    finally:
        conn.close()


def card_for_url(url: str) -> dict | None:
    """The procedure card of a document URL, if it is a procedure."""
    rows = _rows("AND url = %s", [url], 1, 0, "id")
    return procedure_card(*rows[0]) if rows else None


@router.get("/procedures")
def list_procedures(
    q: str | None = Query(None, max_length=200, description="Search words"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """Procedures matching `q` (all words first, like /v1/search), else A to Z."""
    if q and q.strip():
        tsquery = "websearch_to_tsquery('french', %s)"
        rows = _rows(
            f"AND fts_vector @@ {tsquery}",
            [q],
            limit,
            offset,
            f"ts_rank(fts_vector, {tsquery}) DESC",
            (q,),
        )
        if not rows and offset == 0:
            rows = _rows("AND title ILIKE %s", [f"%{q.strip()}%"], limit, 0, "title")
    else:
        rows = _rows("", [], limit, offset, "title")
    items = []
    for row in rows:
        card = procedure_card(*row)
        if card:
            items.append(
                {
                    k: card.get(k)
                    for k in ("id", "title", "url", "source", "summary", "cost", "duration")
                }
            )
    return {"items": items, "limit": limit, "offset": offset}


@router.get("/procedures/{procedure_id}")
def get_procedure(procedure_id: str):
    try:
        uuid.UUID(procedure_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Procedure not found") from None
    rows = _rows("AND id = %s", [procedure_id], 1, 0, "id")
    card = procedure_card(*rows[0]) if rows else None
    if not card:
        raise HTTPException(status_code=404, detail="Procedure not found")
    return card
