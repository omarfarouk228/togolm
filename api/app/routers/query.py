"""
POST /v1/query  — RAG query endpoint
POST /v1/embed  — Embedding endpoint
"""

import time

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from api.app.services.rag import build_answer, retrieve

router = APIRouter(tags=["Query"])


class QueryRequest(BaseModel):
    question: str = Field(..., min_length=3, max_length=1000)
    category: str | None = None
    language: str = "fr"
    max_tokens: int = Field(500, ge=50, le=2000)


class Source(BaseModel):
    title: str
    url: str | None
    score: float


class QueryResponse(BaseModel):
    answer: str
    sources: list[Source]
    model: str
    latency_ms: int


class EmbedRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=8000)
    model: str = "togolm-embed-v1"


class EmbedResponse(BaseModel):
    embedding: list[float]
    model: str
    token_count: int


@router.post("/query", response_model=QueryResponse)
async def query_corpus(request: QueryRequest):
    """Query the Togolese corpus via RAG and return an answer with sources."""
    t0 = time.monotonic()

    try:
        chunks = retrieve(
            question=request.question,
            category=request.category,
            top_k=5,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Retrieval error: {e}")

    answer = build_answer(request.question, chunks)
    latency_ms = int((time.monotonic() - t0) * 1000)

    return QueryResponse(
        answer=answer,
        sources=[
            Source(title=c.title, url=c.url, score=round(c.score, 4))
            for c in chunks
        ],
        model="togolm-rag-v1",
        latency_ms=latency_ms,
    )


@router.post("/embed", response_model=EmbedResponse)
async def embed_text(request: EmbedRequest):
    """Generate an embedding vector for the provided text."""
    from corpus.processors.embedder import get_embedder

    try:
        embedder = get_embedder()
        vector = embedder.encode_one(request.text)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Embedding error: {e}")

    return EmbedResponse(
        embedding=vector,
        model="paraphrase-multilingual-MiniLM-L12-v2",
        token_count=len(request.text.split()),
    )
