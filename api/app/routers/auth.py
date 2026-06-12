"""
POST /v1/auth/register  — Request a free API key (shown once)
GET  /v1/auth/me        — Current key info and daily usage
"""

import hashlib
import os
import secrets

import redis
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr

from api.app.auth import APIKeyRecord, get_api_key
from api.app.db import get_conn
from api.app.rate_limit import PLAN_QUOTAS

router = APIRouter(tags=["Auth"])

_KEY_PREFIX = "tgolm_"


def _generate_key() -> str:
    return _KEY_PREFIX + secrets.token_hex(24)


def _hash_key(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


def _get_redis() -> redis.Redis:
    url = os.getenv("REDIS_URL") or os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
    return redis.from_url(url, decode_responses=True)


def _redis_usage(plan: str, key_id: str) -> int:
    try:
        count = _get_redis().get(f"rl:{plan}:{key_id}")
        return int(count) if count else 0
    except Exception:
        return 0


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------


class RegisterRequest(BaseModel):
    name: str
    email: EmailStr
    use_case: str | None = None


class RegisterResponse(BaseModel):
    api_key: str
    key_prefix: str
    plan: str
    quota_per_day: int
    message: str


class MeResponse(BaseModel):
    name: str | None
    email: str | None
    plan: str
    key_prefix: str
    requests_today: int
    quota_per_day: int
    remaining_today: int


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/auth/register", response_model=RegisterResponse)
def register(req: RegisterRequest):
    """Create a free API key. The plain-text key is shown once — save it immediately."""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id FROM api_keys WHERE owner_email = %s",
                (req.email,),
            )
            if cur.fetchone():
                raise HTTPException(
                    status_code=409,
                    detail="An API key already exists for this email address.",
                )

        key = _generate_key()
        key_hash = _hash_key(key)
        key_prefix = key[:14]  # "tgolm_" + first 8 hex chars

        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO api_keys (key_hash, key_prefix, owner_name, owner_email, use_case, plan)
                VALUES (%s, %s, %s, %s, %s, 'free')
                """,
                (key_hash, key_prefix, req.name, req.email, req.use_case),
            )
        conn.commit()
    finally:
        conn.close()

    return RegisterResponse(
        api_key=key,
        key_prefix=key_prefix + "...",
        plan="free",
        quota_per_day=PLAN_QUOTAS["free"],
        message="Save your API key — it will only be shown once.",
    )


@router.get("/auth/me", response_model=MeResponse)
def me(api_key: APIKeyRecord | str | None = Depends(get_api_key)):
    """Return usage stats for the authenticated key."""
    if api_key is None:
        raise HTTPException(status_code=401, detail="X-API-Key header required")

    if isinstance(api_key, str):
        quota = PLAN_QUOTAS["dev"]
        return MeResponse(
            name="Dev",
            email=None,
            plan="dev",
            key_prefix=api_key[:8] + "...",
            requests_today=_redis_usage("dev", api_key),
            quota_per_day=quota,
            remaining_today=quota,
        )

    plan = api_key.plan
    quota = PLAN_QUOTAS.get(plan, PLAN_QUOTAS["free"])
    used = _redis_usage(plan, api_key.id)

    return MeResponse(
        name=api_key.owner_name,
        email=api_key.owner_email,
        plan=plan,
        key_prefix=api_key.preview,
        requests_today=used,
        quota_per_day=quota,
        remaining_today=max(0, quota - used),
    )
