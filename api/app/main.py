"""
TogoLM Public API — v1

Endpoints:
  POST /v1/query     — RAG query over the Togolese corpus
  POST /v1/embed     — Generate embeddings via TogoLM
  GET  /v1/categories — List available corpus categories
  GET  /v1/stats     — Public corpus statistics
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.app.routers import corpus, query

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

app.include_router(query.router, prefix="/v1")
app.include_router(corpus.router, prefix="/v1")


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
