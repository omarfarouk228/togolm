# ── Stage 1: build deps ───────────────────────────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install uv for fast dependency resolution
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

COPY pyproject.toml .

# Install torch CPU-only first to avoid pulling the 3 GB CUDA variant
RUN uv venv /opt/venv && \
    /opt/venv/bin/pip install --no-cache-dir \
        torch --index-url https://download.pytorch.org/whl/cpu

# Install the rest of the project deps (core only, no finetuning extras)
RUN /opt/venv/bin/pip install --no-cache-dir \
    fastapi \
    "uvicorn[standard]" \
    pydantic \
    python-dotenv \
    psycopg2-binary \
    pgvector \
    sqlalchemy \
    "google-genai>=2.3.0" \
    "sentence-transformers>=5.5.0" \
    tqdm \
    python-slugify


# ── Stage 2: runtime ──────────────────────────────────────────────────────────
FROM python:3.11-slim AS runtime

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /opt/venv /opt/venv

# Copy only what the API needs
COPY api/ api/

# Runtime env — secrets (POSTGRES_*, GEMINI_API_KEY, REDIS_URL) must be
# injected by Coolify. API_KEYS is a dev/CI fallback only — leave unset in prod.
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONPATH="/app" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    API_ENV=production

EXPOSE 8000

CMD ["uvicorn", "api.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
