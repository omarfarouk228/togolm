"""
POST /v1/feedback — Report an issue with a generated answer

Unauthenticated and not gated behind the query rate limit: reporting a bad
answer shouldn't cost the visitor part of their daily query quota, and the
payload is a single bounded DB insert (no LLM call), so the abuse surface
is small. Field lengths are capped instead.
"""

import json

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from api.app.core.auth import APIKeyRecord, get_api_key
from db import get_conn

router = APIRouter(tags=["Feedback"])

_CATEGORIES = ("incorrect", "broken_source", "harmful", "other")


class FeedbackSource(BaseModel):
    title: str | None = None
    url: str | None = None


class FeedbackRequest(BaseModel):
    category: str = Field(..., description="One of: incorrect, broken_source, harmful, other")
    question: str = Field(..., min_length=1, max_length=2000)
    answer: str = Field(..., min_length=1, max_length=8000)
    comment: str | None = Field(None, max_length=2000)
    sources: list[FeedbackSource] | None = None
    language: str = Field("fr", max_length=10)


class FeedbackResponse(BaseModel):
    id: str
    message: str


@router.post("/feedback", response_model=FeedbackResponse)
async def submit_feedback(
    body: FeedbackRequest,
    api_key: APIKeyRecord | str | None = Depends(get_api_key),
):
    category = body.category if body.category in _CATEGORIES else "other"

    if isinstance(api_key, APIKeyRecord):
        prefix = api_key.preview
    elif isinstance(api_key, str):
        prefix = api_key[:8] + "..." if len(api_key) > 8 else api_key
    else:
        prefix = None

    sources_json = [s.model_dump() for s in body.sources] if body.sources else None

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO response_feedback
                    (category, comment, question, answer, sources, language, api_key_prefix)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (
                    category,
                    body.comment,
                    body.question,
                    body.answer,
                    json.dumps(sources_json) if sources_json else None,
                    body.language,
                    prefix,
                ),
            )
            feedback_id = cur.fetchone()[0]
        conn.commit()
    finally:
        conn.close()

    return FeedbackResponse(id=str(feedback_id), message="Feedback recorded")
