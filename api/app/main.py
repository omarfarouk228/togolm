"""
TogoLM Public API — v1

Endpoints:
  POST /v1/query            — RAG query over the Togolese corpus
  POST /v1/embed            — Generate embeddings via TogoLM
  GET  /v1/categories       — List available corpus categories
  GET  /v1/stats            — Public corpus statistics
  GET  /v1/documents        — Paginated document list
  GET  /v1/documents/{id}   — Single document with chunks
  GET  /v1/search           — Full-text keyword search
"""

from dotenv import load_dotenv

load_dotenv()  # must run before any module that reads os.getenv()

from fastapi import Depends, FastAPI  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402

from api.app.rate_limit import check_rate_limit  # noqa: E402
from api.app.routers import admin, auth, corpus, documents, query  # noqa: E402

app = FastAPI(
    title="TogoLM API",
    description="The first open-source AI API for Togo",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Restrict in production
    allow_methods=["*"],
    allow_headers=["*"],
)

_security = [Depends(check_rate_limit)]

app.include_router(admin.router, prefix="/v1")  # protected by X-Admin-Key, no rate limit
app.include_router(auth.router, prefix="/v1")  # no rate limit on register/me
app.include_router(query.router, prefix="/v1", dependencies=_security)
app.include_router(corpus.router, prefix="/v1", dependencies=_security)
app.include_router(documents.router, prefix="/v1", dependencies=_security)


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
