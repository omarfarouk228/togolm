"""
API Key authentication for TogoLM API.

Flow:
    1. No key provided      → anonymous access (rate-limited by IP)
    2. Key provided         → SHA-256 hash → lookup in api_keys table
    3. Found in DB          → return APIKeyRecord (carries plan info)
    4. Not in DB            → check API_KEYS env var (dev/CI fallback)
    5. Not anywhere         → 401 Unauthorized

The plain-text key is NEVER stored — only its SHA-256 hash.

Environment (fallback only):
    API_KEYS — comma-separated raw keys accepted without a DB record.
               Leave empty in production. Useful for local dev / CI.
"""

import hashlib
import os
from dataclasses import dataclass
from typing import Optional

from fastapi import Header, HTTPException

from api.app.db import get_conn


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class APIKeyRecord:
    """Validated API key with owner metadata and plan."""
    id: str
    owner_name: str | None
    owner_email: str | None
    plan: str          # free | dev | institution
    preview: str       # first 8 chars + "..." for safe logging


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------

def _hash_key(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


def _lookup_db(key: str) -> APIKeyRecord | None:
    """
    Look up key in api_keys table (by hash) and update last_used.
    Returns None if not found or DB is unavailable.
    """
    key_hash = _hash_key(key)
    try:
        conn = get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE api_keys
                    SET last_used = NOW()
                    WHERE key_hash = %s AND is_active = TRUE
                    RETURNING id::text, owner_name, owner_email, plan
                    """,
                    (key_hash,),
                )
                row = cur.fetchone()
            conn.commit()
        finally:
            conn.close()

        if row:
            return APIKeyRecord(
                id=row[0],
                owner_name=row[1],
                owner_email=row[2],
                plan=row[3],
                preview=key[:8] + "...",
            )
    except Exception:
        # DB unavailable — fall through to env fallback
        pass
    return None


def _check_env_fallback(key: str) -> bool:
    """
    Dev/CI fallback: accept keys listed in API_KEYS env var.
    If API_KEYS is empty, accept any key (local dev mode).
    """
    raw = os.getenv("API_KEYS", "")
    valid_keys = {k.strip() for k in raw.split(",") if k.strip()}
    return (not valid_keys) or (key in valid_keys)


# ---------------------------------------------------------------------------
# FastAPI dependency
# ---------------------------------------------------------------------------

async def get_api_key(
    x_api_key: Optional[str] = Header(None),
) -> Optional[APIKeyRecord | str]:
    """
    FastAPI dependency — extracts and validates X-API-Key header.

    Returns:
        APIKeyRecord  — key found in DB (full metadata + plan)
        str           — key accepted via env fallback (dev mode)
        None          — no key provided (anonymous)

    Raises:
        HTTPException 401 — key provided but not recognised anywhere
    """
    if x_api_key is None:
        return None  # anonymous

    if not x_api_key.strip():
        raise HTTPException(status_code=401, detail="Invalid API key")

    # 1. DB lookup (production path)
    record = _lookup_db(x_api_key)
    if record:
        return record

    # 2. Env fallback (dev / CI)
    if _check_env_fallback(x_api_key):
        return x_api_key  # plain string — rate limiter defaults to "dev" plan

    raise HTTPException(status_code=401, detail="Invalid API key")
