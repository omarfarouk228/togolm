"""Pydantic request/response models for the query and embed endpoints."""

from pydantic import BaseModel, Field


class HistoryMessage(BaseModel):
    role: str  # "user" or "assistant"
    content: str


class QueryRequest(BaseModel):
    question: str = Field(..., min_length=3, max_length=4000)
    category: str | None = None
    language: str = "fr"
    max_tokens: int = Field(1500, ge=50, le=2000)
    history: list[HistoryMessage] = Field(default_factory=list, max_length=20)


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
