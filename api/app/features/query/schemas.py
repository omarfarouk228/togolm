"""Pydantic request/response models for the query and embed endpoints."""

from pydantic import BaseModel, Field, field_validator, model_validator


class HistoryMessage(BaseModel):
    role: str  # "user" or "assistant"
    content: str


# ~5.3M base64 chars ≈ 4MB raw image. Callers should downscale/compress client-side
# before sending — phone camera photos are routinely 10x this.
_MAX_IMAGE_B64_CHARS = 5_300_000
_ALLOWED_IMAGE_MIME_TYPES = {"image/jpeg", "image/png", "image/webp"}


class ImageAttachment(BaseModel):
    mime_type: str = Field(
        ..., description="One of: " + ", ".join(sorted(_ALLOWED_IMAGE_MIME_TYPES))
    )
    data: str = Field(
        ...,
        min_length=1,
        max_length=_MAX_IMAGE_B64_CHARS,
        description="Base64-encoded image data, no data: prefix",
    )

    @field_validator("mime_type")
    @classmethod
    def _validate_mime_type(cls, value: str) -> str:
        if value not in _ALLOWED_IMAGE_MIME_TYPES:
            raise ValueError(f"Unsupported image mime_type: {value}")
        return value


class QueryRequest(BaseModel):
    # No Field(min_length=...) here: the minimum is conditional on whether an image
    # is attached (see _validate_question below), so it can't be a static constraint.
    question: str = Field(..., max_length=4000)
    category: str | None = None
    language: str = "fr"
    max_tokens: int = Field(3000, ge=50, le=4096)
    history: list[HistoryMessage] = Field(default_factory=list, max_length=20)
    image: ImageAttachment | None = None

    @model_validator(mode="after")
    def _validate_question(self) -> "QueryRequest":
        # A photo carries its own intent, so the typed question may be empty.
        # Without an image, keep the original minimum to reject junk queries.
        if not self.image and len(self.question.strip()) < 3:
            raise ValueError("question must be at least 3 characters")
        return self


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
