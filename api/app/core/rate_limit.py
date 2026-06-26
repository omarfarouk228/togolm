"""
Redis-based rate limiting for TogoLM API.

Quotas per 24-hour window:
    anonymous    :    20 req  (identified by client IP)
    free plan    :   200 req  (identified by key ID)
    dev plan     : 1 000 req  (identified by key ID)
    institution  : 100 000 req (identified by key ID — effectively unlimited)

Uses Redis INCR + EXPIRE (atomic, safe across multiple Uvicorn workers).
Fails open: if Redis is unavailable, requests are allowed through.

Stats counters written on every request (35-day TTL):
    stats:req:{YYYY-MM-DD}          — total requests
    stats:req:{YYYY-MM-DD}:{plan}   — requests by plan
    stats:rl_hit:{YYYY-MM-DD}       — rate-limit 429s

Environment:
    REDIS_URL           — Redis connection URL (takes priority)
    CELERY_BROKER_URL   — reused as Redis URL if REDIS_URL is not set
"""

import datetime
import os

import redis
from fastapi import Depends, HTTPException, Request

from api.app.core.auth import APIKeyRecord, get_api_key

# Limits: plan → (max_requests, window_in_seconds)
_LIMITS: dict[str, tuple[int, int]] = {
    "anon": (20, 86_400),
    "free": (200, 86_400),
    "dev": (1_000, 86_400),
    "institution": (100_000, 86_400),
}

PLAN_QUOTAS: dict[str, int] = {k: v[0] for k, v in _LIMITS.items()}

_STATS_TTL = 35 * 86_400  # keep 35 days of stats

# Module-level singleton — one ConnectionPool shared across all workers in the process
_redis_client: redis.Redis | None = None


def _get_redis() -> redis.Redis:
    global _redis_client
    if _redis_client is None:
        url = os.getenv("REDIS_URL") or os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
        _redis_client = redis.from_url(url, decode_responses=True)
    return _redis_client


def _get_client_ip(request: Request) -> str:
    # X-Real-IP is set by Nginx ($remote_addr) and cannot be forged by the client.
    # In production this is the authoritative source; prefer it over X-Forwarded-For.
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip.strip()
    # Fallback for dev/non-Nginx environments: use the leftmost X-Forwarded-For entry.
    # This is the original client IP as reported by the first proxy.
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
    Also records daily stats counters for the /v1/admin/stats endpoint.

    Raises:
        HTTPException 429 — rate limit exceeded
    """
    if isinstance(api_key, APIKeyRecord):
        plan = api_key.plan
        identifier = api_key.id
    elif isinstance(api_key, str):
        plan = "dev"
        identifier = api_key
    else:
        plan = "anon"
        identifier = _get_client_ip(request)

    max_req, window = _LIMITS.get(plan, _LIMITS["dev"])
    redis_key = f"rl:{plan}:{identifier}"
    today = datetime.date.today().isoformat()

    try:
        r = _get_redis()

        # Rate limit check
        count = r.incr(redis_key)
        if count == 1:
            r.expire(redis_key, window)

        # Stats counters — pipeline to keep it one round-trip
        pipe = r.pipeline()
        pipe.incr(f"stats:req:{today}")
        pipe.expire(f"stats:req:{today}", _STATS_TTL)
        pipe.incr(f"stats:req:{today}:{plan}")
        pipe.expire(f"stats:req:{today}:{plan}", _STATS_TTL)
        pipe.execute()

        if count > max_req:
            # Record the 429 separately
            r.incr(f"stats:rl_hit:{today}")
            r.expire(f"stats:rl_hit:{today}", _STATS_TTL)
            raise HTTPException(
                status_code=429,
                detail=f"Rate limit exceeded ({max_req} requests/24 h for plan '{plan}').",
                headers={"Retry-After": str(window)},
            )
    except HTTPException:
        raise
    except Exception:
        pass  # Redis down → fail open
