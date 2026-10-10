"""Pydantic request/response models for the query and embed endpoints."""

from pydantic import BaseModel, Field, field_validator, model_validator


def normalize_language(v: str | None) -> str:
    """'fr', 'en', 'ee' (Éwé) or 'kbp' (Kabiyè); region tags like 'fr-TG'
    are reduced to the base language, anything else falls back to 'fr'."""
    from rag.generation.prompts import SUPPORTED_LANGUAGES

    base = (v or "fr").strip().lower().replace("_", "-").split("-")[0]
    return base if base in SUPPORTED_LANGUAGES else "fr"


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

    @field_validator("language")
    @classmethod
    def _normalize_language(cls, v: str) -> str:
        return normalize_language(v)

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


# ~2.8M base64 chars ≈ 2MB of audio: about 2 minutes of browser Opus/AAC,
# far more than a spoken question needs.
_MAX_AUDIO_B64_CHARS = 2_800_000
_ALLOWED_AUDIO_MIME_TYPES = {
    "audio/webm",  # Chrome, Edge, Firefox, Android (Opus)
    "audio/ogg",
    "audio/mp4",  # Safari, iOS (AAC)
    "audio/aac",
    "audio/mpeg",
    "audio/wav",
}


class AudioAttachment(BaseModel):
    mime_type: str = Field(..., description="Audio type from MediaRecorder, e.g. audio/webm")
    data: str = Field(
        ...,
        min_length=1,
        max_length=_MAX_AUDIO_B64_CHARS,
        description="Base64-encoded audio data, no data: prefix",
    )

    @field_validator("mime_type")
    @classmethod
    def _validate_mime_type(cls, value: str) -> str:
        # MediaRecorder reports codecs too ("audio/webm;codecs=opus").
        base = value.split(";")[0].strip().lower()
        if base not in _ALLOWED_AUDIO_MIME_TYPES:
            raise ValueError(f"Unsupported audio mime_type: {value}")
        return base


class TranscribeRequest(BaseModel):
    audio: AudioAttachment
    language: str = "fr"

    @field_validator("language")
    @classmethod
    def _normalize_language(cls, v: str) -> str:
        return normalize_language(v)


class TranscribeResponse(BaseModel):
    text: str = Field(..., description="What was said, in the language spoken")
    translation_fr: str = Field(..., description="French translation of the text")
    language: str = Field(..., description="Language the client asked for")
    spoken_language: str = Field(
        "", description="Language the model heard: fr, ee, kbp, en, autre, or empty"
    )
