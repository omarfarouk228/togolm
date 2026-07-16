"""
TogoLM Public API — v1

Endpoints:
  POST /v1/query            — RAG query over the Togolese corpus
  POST /v1/embed            — Generate embeddings via TogoLM
  GET  /v1/categories       — List available corpus categories
  GET  /v1/stats            — Public corpus statistics
  GET  /v1/documents/recent — Small fixed-size recent-documents feed (no rate limit)
  GET  /v1/documents        — Paginated document list
  GET  /v1/documents/{id}   — Single document with chunks
  GET  /v1/search           — Full-text keyword search
"""

import os

from dotenv import load_dotenv

load_dotenv()  # must run before any module that reads os.getenv()

from fastapi import Depends, FastAPI  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402

from api.app.core.rate_limit import check_rate_limit  # noqa: E402
from api.app.features.admin.router import router as admin_router  # noqa: E402
from api.app.features.auth.router import router as auth_router  # noqa: E402
from api.app.features.corpus.router import router as corpus_router  # noqa: E402
from api.app.features.documents.router import router as documents_router  # noqa: E402
from api.app.features.query.router import router as query_router  # noqa: E402

app = FastAPI(
    title="TogoLM API",
    description="The first open-source AI API for Togo",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

_cors_origins_raw = os.getenv("CORS_ORIGINS", "")
_allowed_origins = [o.strip() for o in _cors_origins_raw.split(",") if o.strip()] or ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

_security = [Depends(check_rate_limit)]

app.include_router(admin_router, prefix="/v1")  # protected by X-Admin-Key, no rate limit
app.include_router(auth_router, prefix="/v1")  # no rate limit on register/me
app.include_router(corpus_router, prefix="/v1")  # public read-only stats, no rate limit
app.include_router(query_router, prefix="/v1", dependencies=_security)
app.include_router(documents_router, prefix="/v1", dependencies=_security)


@app.get("/", include_in_schema=False)
def root():
    return {
        "name": "TogoLM API",
        "version": "0.1.0",
        "docs": "/docs",
        "status": "ok",
    }


@app.get("/health", include_in_schema=False)
def health():
    return {"status": "ok"}
