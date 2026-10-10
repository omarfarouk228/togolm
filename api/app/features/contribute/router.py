"""
Native-speaker contributions for answers in Éwé and Kabiyè.

Public (no account, not counted against the query quota; a per-IP daily cap
on submissions instead):
  GET  /v1/contribute/items?language=ee   — answers waiting for review
  POST /v1/contribute/reviews             — submit one review

Admin:
  GET   /v1/admin/language-reviews        — reviews with their item
  PATCH /v1/admin/language-reviews/{id}   — approve / reject

Only APPROVED reviews are used by generation (rag.generation.language_examples):
this text comes from anonymous visitors and ends up in the model's prompt, so
a human checks it first.
"""

import uuid
from datetime import date

from fastapi import APIRouter, Header, HTTPException, Query, Request
from pydantic import BaseModel, Field

from api.app.core.rate_limit import _get_client_ip, _get_redis
from api.app.features.admin import service as admin_service
from db import get_conn
from rag.generation.language_examples import invalidate_cache

router = APIRouter(tags=["Contribute"])

LANGUAGES = ("ee", "kbp")
RATINGS = ("good", "fix", "bad")
STATUSES = ("pending", "approved", "rejected")
DAILY_REVIEWS_PER_IP = 100


class ReviewItem(BaseModel):
    id: str
    language: str
    question: str
    question_fr: str | None
    answer: str
    answer_fr: str | None
    origin: str
    review_count: int


class ReviewRequest(BaseModel):
    item_id: str = Field(..., min_length=36, max_length=36)
    rating: str = Field(..., description="good | fix | bad")
    correction: str | None = Field(None, max_length=6000)
    comment: str | None = Field(None, max_length=1000)
    reviewer_name: str | None = Field(None, max_length=100)
    reviewer_region: str | None = Field(None, max_length=100)


class ReviewCreated(BaseModel):
    id: str
    message: str


class AdminReview(BaseModel):
    id: str
    item_id: str
    language: str
    question: str
    question_fr: str | None
    answer: str
    rating: str
    correction: str | None
    comment: str | None
    reviewer_name: str | None
    reviewer_region: str | None
    status: str
    created_at: str


class AdminReviewList(BaseModel):
    items: list[AdminReview]
    total: int
    page: int
    page_size: int


class PatchReview(BaseModel):
    status: str = Field(..., description="approved | rejected | pending")


def _require_uuid(value: str, what: str) -> str:
    try:
        return str(uuid.UUID(value))
    except ValueError:
        raise HTTPException(status_code=404, detail=f"Unknown {what}.") from None


def _clean(value: str | None) -> str | None:
    value = (value or "").strip()
    return value or None


@router.get("/contribute/items", response_model=list[ReviewItem])
def list_items(
    language: str = Query(..., description="ee | kbp"),
    limit: int = Query(10, ge=1, le=50),
):
    """Answers to review, least-reviewed first, then newest."""
    if language not in LANGUAGES:
        raise HTTPException(status_code=422, detail="language must be ee or kbp")
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT i.id, i.language, i.question, i.question_fr, i.answer, i.answer_fr,
                       i.origin, COUNT(r.id) AS review_count
                FROM language_review_items i
                LEFT JOIN language_reviews r ON r.item_id = i.id AND r.status <> 'rejected'
                WHERE i.active AND i.language = %s
                GROUP BY i.id
                ORDER BY COUNT(r.id) ASC, i.created_at DESC
                LIMIT %s
                """,
                (language, limit),
            )
            rows = cur.fetchall()
    finally:
        conn.close()
    return [
        ReviewItem(
            id=str(r[0]),
            language=r[1],
            question=r[2],
            question_fr=r[3],
            answer=r[4],
            answer_fr=r[5],
            origin=r[6],
            review_count=r[7],
        )
        for r in rows
    ]


@router.post("/contribute/reviews", response_model=ReviewCreated)
def submit_review(body: ReviewRequest, request: Request):
    if body.rating not in RATINGS:
        raise HTTPException(status_code=422, detail="rating must be good, fix or bad")
    item_id = _require_uuid(body.item_id, "item")

    try:
        key = f"contrib:{_get_client_ip(request)}:{date.today().isoformat()}"
        redis = _get_redis()
        count = redis.incr(key)
        if count == 1:
            redis.expire(key, 86_400)
        if count > DAILY_REVIEWS_PER_IP:
            raise HTTPException(status_code=429, detail="Daily contribution limit reached.")
    except HTTPException:
        raise
    except Exception:
        pass  # Redis down: accept the review rather than lose it

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM language_review_items WHERE id = %s", (item_id,))
            if cur.fetchone() is None:
                raise HTTPException(status_code=404, detail="Unknown item.")
            cur.execute(
                """
                INSERT INTO language_reviews
                    (item_id, rating, correction, comment, reviewer_name, reviewer_region)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (
                    item_id,
                    body.rating,
                    _clean(body.correction),
                    _clean(body.comment),
                    _clean(body.reviewer_name),
                    _clean(body.reviewer_region),
                ),
            )
            review_id = cur.fetchone()[0]
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    return ReviewCreated(id=str(review_id), message="Review recorded")


@router.get("/admin/language-reviews", response_model=AdminReviewList)
def admin_list_reviews(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: str | None = Query(None),
    language: str | None = Query(None),
    authorization: str | None = Header(default=None),
    x_admin_key: str | None = Header(default=None),
):
    admin_service.require_admin(authorization, x_admin_key)
    where, params = ["TRUE"], []
    if status in STATUSES:
        where.append("r.status = %s")
        params.append(status)
    if language in LANGUAGES:
        where.append("i.language = %s")
        params.append(language)
    clause = " AND ".join(where)
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                f"""SELECT COUNT(*) FROM language_reviews r
                    JOIN language_review_items i ON i.id = r.item_id WHERE {clause}""",
                params,
            )
            total = cur.fetchone()[0]
            cur.execute(
                f"""
                SELECT r.id, r.item_id, i.language, i.question, i.question_fr, i.answer,
                       r.rating, r.correction, r.comment, r.reviewer_name, r.reviewer_region,
                       r.status, r.created_at
                FROM language_reviews r
                JOIN language_review_items i ON i.id = r.item_id
                WHERE {clause}
                ORDER BY r.created_at DESC
                LIMIT %s OFFSET %s
                """,
                [*params, page_size, (page - 1) * page_size],
            )
            rows = cur.fetchall()
    finally:
        conn.close()
    return AdminReviewList(
        items=[
            AdminReview(
                id=str(r[0]),
                item_id=str(r[1]),
                language=r[2],
                question=r[3],
                question_fr=r[4],
                answer=r[5],
                rating=r[6],
                correction=r[7],
                comment=r[8],
                reviewer_name=r[9],
                reviewer_region=r[10],
                status=r[11],
                created_at=str(r[12]),
            )
            for r in rows
        ],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.patch("/admin/language-reviews/{review_id}")
def admin_update_review(
    review_id: str,
    body: PatchReview,
    authorization: str | None = Header(default=None),
    x_admin_key: str | None = Header(default=None),
):
    admin_service.require_admin(authorization, x_admin_key)
    review_id = _require_uuid(review_id, "review")
    if body.status not in STATUSES:
        raise HTTPException(status_code=422, detail="status must be approved, rejected or pending")
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE language_reviews
                SET status = %s, reviewed_at = CASE WHEN %s = 'pending' THEN NULL ELSE NOW() END
                WHERE id = %s
                RETURNING id, status
                """,
                (body.status, body.status, review_id),
            )
            row = cur.fetchone()
        conn.commit()
    finally:
        conn.close()
    if row is None:
        raise HTTPException(status_code=404, detail="Review not found.")
    invalidate_cache()  # approved wording is used by generation right away
    return {"id": str(row[0]), "status": row[1]}
