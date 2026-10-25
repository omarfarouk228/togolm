"""
POST /v1/auth/register  — Request a free API key (shown once)
GET  /v1/auth/me        — Current key info and daily usage
"""

import datetime
import hashlib
import hmac
import os
import secrets

import redis
from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, EmailStr

from api.app.core.auth import APIKeyRecord, get_api_key
from api.app.core.rate_limit import PLAN_QUOTAS
from db import get_conn

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
    # End of a paid plan (payments, 010); None for free keys and fixed plans.
    plan_expires_at: datetime.datetime | None = None


class RotateResponse(BaseModel):
    api_key: str
    key_prefix: str
    message: str


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

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT plan_expires_at FROM api_keys WHERE id = %s", (api_key.id,))
            row = cur.fetchone()
    finally:
        conn.close()

    return MeResponse(
        name=api_key.owner_name,
        email=api_key.owner_email,
        plan=plan,
        key_prefix=api_key.preview,
        requests_today=used,
        quota_per_day=quota,
        remaining_today=max(0, quota - used),
        plan_expires_at=row[0] if row else None,
    )


@router.post("/auth/keys/rotate", response_model=RotateResponse)
def rotate_key(api_key: APIKeyRecord | str | None = Depends(get_api_key)):
    """Revoke this key and issue its replacement on the same account.

    The old key stops working at once (a leaked key is useless after this);
    the plan, its end date and the usage history stay, since they hang on the
    account row, not on the key. The new key is shown once.
    """
    if not isinstance(api_key, APIKeyRecord):
        raise HTTPException(status_code=401, detail="X-API-Key header required")
    key = _generate_key()
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE api_keys SET key_hash = %s, key_prefix = %s
                WHERE id = %s AND is_active = TRUE
                """,
                (_hash_key(key), key[:14], api_key.id),
            )
            if cur.rowcount != 1:
                raise HTTPException(status_code=401, detail="Invalid API key")
        conn.commit()
    finally:
        conn.close()
    return RotateResponse(
        api_key=key,
        key_prefix=key[:14] + "...",
        message="The previous key no longer works. Save this one: it is shown only once.",
    )


@router.get("/auth/usage")
def usage(
    days: int = Query(30, ge=1, le=90),
    api_key: APIKeyRecord | str | None = Depends(get_api_key),
):
    """Questions asked with this key per day (POST /v1/query and /v1/query/stream),
    for the integrator's dashboard. Counted since 2026-10-25 (migration 009)."""
    if not isinstance(api_key, APIKeyRecord):
        raise HTTPException(status_code=401, detail="X-API-Key header required")
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT DATE(created_at), COUNT(*),
                       COUNT(*) FILTER (WHERE is_off_topic),
                       percentile_cont(0.5) WITHIN GROUP (ORDER BY latency_ms)
                FROM user_queries
                WHERE api_key_id = %s AND created_at >= CURRENT_DATE - %s
                GROUP BY 1
                """,
                (api_key.id, days - 1),
            )
            rows = {r[0].isoformat(): r for r in cur.fetchall()}
    finally:
        conn.close()
    today = datetime.date.today()
    series = []
    for i in range(days - 1, -1, -1):
        day = (today - datetime.timedelta(days=i)).isoformat()
        r = rows.get(day)
        series.append(
            {
                "date": day,
                "questions": int(r[1]) if r else 0,
                "off_topic": int(r[2]) if r else 0,
                "latency_p50_ms": int(r[3]) if r and r[3] is not None else None,
            }
        )
    return {
        "plan": api_key.plan,
        "quota_per_day": PLAN_QUOTAS.get(api_key.plan, PLAN_QUOTAS["free"]),
        "days": series,
    }


class ClaimRequest(BaseModel):
    email: EmailStr


@router.post("/auth/keys/claim", response_model=RotateResponse, include_in_schema=False)
def claim_key(body: ClaimRequest, x_internal_token: str | None = Header(None)):
    """Issue a new key for an e-mail whose ownership the website has verified
    (Google or magic-link sign-in), when that address already had a key from the
    registration form that the account can't read back. Only the website calls
    this, with INTERNAL_API_TOKEN; the old key stops working, the plan stays."""
    expected = os.getenv("INTERNAL_API_TOKEN", "")
    if not expected:
        raise HTTPException(status_code=503, detail="Key claim is not configured")
    if not x_internal_token or not hmac.compare_digest(x_internal_token, expected):
        raise HTTPException(status_code=403, detail="Forbidden")
    key = _generate_key()
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE api_keys SET key_hash = %s, key_prefix = %s
                WHERE lower(owner_email) = lower(%s) AND is_active = TRUE
                """,
                (_hash_key(key), key[:14], str(body.email)),
            )
            if cur.rowcount != 1:
                raise HTTPException(status_code=404, detail="No active key for this e-mail")
        conn.commit()
    finally:
        conn.close()
    return RotateResponse(
        api_key=key,
        key_prefix=key[:14] + "...",
        message="New key issued; the previous one no longer works.",
    )
