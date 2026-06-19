# ── Base image ─────────────────────────────────────────────────────────────
FROM python:3.11-slim AS base

WORKDIR /app

# System deps: build essentials + psycopg2 native
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# ── Dependency layer ────────────────────────────────────────────────────────
FROM base AS deps

# Copy only dependency manifests so Docker cache is invalidated only when
# they change, not on every code edit.
COPY pyproject.toml uv.lock* ./

# Install uv for fast installs, then install all project dependencies.
RUN pip install --no-cache-dir uv && \
    uv pip install --system --no-cache .

# Pre-download the embedding model (bakes it into the image so cold starts
# don't need internet access to download ~120 MB model weights).
RUN python -c "\
from sentence_transformers import SentenceTransformer; \
SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')"

# ── Production image ────────────────────────────────────────────────────────
FROM deps AS production

# Copy application code (excludes everything in .dockerignore)
COPY api/      ./api/
COPY corpus/   ./corpus/
COPY alembic/  ./alembic/
COPY scripts/  ./scripts/
COPY alembic.ini ./alembic.ini

# Non-root user for security
RUN useradd --create-home --shell /bin/bash app && \
    mkdir -p /app/corpus/datasets && \
    chown -R app:app /app
USER app

# Health check (calls the /health endpoint every 30s)
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

EXPOSE 8000

CMD ["sh", "-c", "alembic upgrade head && uvicorn api.app.main:app --host 0.0.0.0 --port 8000 --workers 2 --log-level info"]
