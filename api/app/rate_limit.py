"""
Redis-based rate limiting for TogoLM API.

Quotas per 24-hour window:
    anonymous    :    100 req  (identified by client IP)
    free plan    :    100 req  (identified by key ID)
    dev plan     :  1 000 req  (identified by key ID)
    institution  : 100 000 req (identified by key ID — effectively unlimited)

Uses Redis INCR + EXPIRE (atomic, safe across multiple Uvicorn workers).
Fails open: if Redis is unavailable, requests are allowed through.

Environment:
    REDIS_URL           — Redis connection URL (takes priority)
    CELERY_BROKER_URL   — reused as Redis URL if REDIS_URL is not set
"""

import os

import redis
from fastapi import Depends, HTTPException, Request

from api.app.auth import APIKeyRecord, get_api_key

# Limits: plan → (max_requests, window_in_seconds)
_LIMITS: dict[str, tuple[int, int]] = {
    "anon":        (100,     86_400),
    "free":        (100,     86_400),
    "dev":         (1_000,   86_400),
    "institution": (100_000, 86_400),
}


def _get_redis() -> redis.Redis:
    url = os.getenv("REDIS_URL") or os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
    return redis.from_url(url, decode_responses=True)


def _get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


async def check_rate_limit(
    request: Request,
    api_key: APIKeyRecord | str | None = Depends(get_api_key),
) -> None:
    """
    FastAPI dependency — enforces per-plan rate limits via Redis.

    Must be injected AFTER get_api_key so the key is already validated.

    Raises:
        HTTPException 429 — rate limit exceeded
    """
    if isinstance(api_key, APIKeyRecord):
        plan       = api_key.plan
        identifier = api_key.id
    elif isinstance(api_key, str):
        # env-fallback key: treat as "dev" plan
        plan       = "dev"
        identifier = api_key
    else:
        # anonymous
        plan       = "anon"
        identifier = _get_client_ip(request)

    max_req, window = _LIMITS.get(plan, _LIMITS["dev"])
    redis_key = f"rl:{plan}:{identifier}"

    try:
        r = _get_redis()
        count = r.incr(redis_key)
        if count == 1:
            r.expire(redis_key, window)

        if count > max_req:
            raise HTTPException(
                status_code=429,
                detail=f"Rate limit exceeded ({max_req} requests/24 h for plan '{plan}').",
                headers={"Retry-After": str(window)},
            )
    except HTTPException:
        raise
    except Exception:
        pass  # Redis down → fail open
