from pydantic import BaseModel, EmailStr


class AdminLoginRequest(BaseModel):
    key: str


class AdminLoginResponse(BaseModel):
    token: str
    expires_at: str


class SourceStat(BaseModel):
    source: str
    category: str | None
    doc_count: int
    last_collected: str | None


class RecentDocument(BaseModel):
    id: str
    source: str
    title: str | None
    url: str | None
    category: str | None
    language: str | None
    word_count: int | None
    collected_at: str | None


class ApiKeyItem(BaseModel):
    id: str
    key_prefix: str | None
    owner_name: str | None
    owner_email: str | None
    use_case: str | None
    plan: str
    is_active: bool
    created_at: str | None
    last_used: str | None


class CreateKeyRequest(BaseModel):
    name: str
    email: EmailStr
    use_case: str | None = None
    plan: str = "free"


class CreateKeyResponse(BaseModel):
    api_key: str
    key_prefix: str
    plan: str
    quota_per_day: int


class PatchKeyRequest(BaseModel):
    plan: str | None = None
    is_active: bool | None = None


class QueryItem(BaseModel):
    id: str
    question: str
    language: str | None
    category: str | None
    is_off_topic: bool
    chunks_found: int
    latency_ms: int | None
    api_key_prefix: str | None
    created_at: str | None


class QueryListResponse(BaseModel):
    items: list[QueryItem]
    total: int
    page: int
    page_size: int


class FeedbackSourceItem(BaseModel):
    title: str | None = None
    url: str | None = None


class FeedbackItem(BaseModel):
    id: str
    category: str
    status: str
    question: str
    answer: str
    comment: str | None
    sources: list[FeedbackSourceItem] | None
    language: str | None
    api_key_prefix: str | None
    created_at: str | None


class FeedbackListResponse(BaseModel):
    items: list[FeedbackItem]
    total: int
    page: int
    page_size: int


class PatchFeedbackRequest(BaseModel):
    status: str
