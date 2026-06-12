"""
GET /v1/admin/stats — API usage statistics (admin-only)

Protected by X-Admin-Key header matching the API_SECRET_KEY environment variable.
Stats are read from Redis counters written by the rate_limit middleware.
"""

import datetime
import os

import redis
from fastapi import APIRouter, Header, HTTPException, Query

from api.app.db import get_conn

router = APIRouter(tags=["Admin"])

_PLANS = ["anon", "free", "dev", "institution"]
_STATS_TTL = 35 * 86_400


def _get_redis() -> redis.Redis:
    url = os.getenv("REDIS_URL") or os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
    return redis.from_url(url, decode_responses=True)


def _require_admin(x_admin_key: str | None) -> None:
    secret = os.getenv("API_SECRET_KEY", "")
    if not secret or x_admin_key != secret:
        raise HTTPException(status_code=401, detail="Invalid or missing X-Admin-Key.")


@router.get("/admin/stats")
def get_admin_stats(
    days: int = Query(default=7, ge=1, le=90, description="Number of past days to include"),
    x_admin_key: str | None = Header(default=None),
):
    """
    Return API usage statistics for the last N days.

    Requires X-Admin-Key header matching API_SECRET_KEY.
    """
    _require_admin(x_admin_key)

    today = datetime.date.today()
    dates = [(today - datetime.timedelta(days=i)).isoformat() for i in range(days - 1, -1, -1)]

    # Fetch all counters in a single pipeline
    r = _get_redis()
    pipe = r.pipeline()
    for date in dates:
        pipe.get(f"stats:req:{date}")
        pipe.get(f"stats:rl_hit:{date}")
        for plan in _PLANS:
            pipe.get(f"stats:req:{date}:{plan}")

    results = pipe.execute()

    # Parse pipeline results
    by_day = []
    total_requests = 0
    total_rl_hits = 0
    idx = 0

    for date in dates:
        day_total = int(results[idx] or 0)
        day_rl_hits = int(results[idx + 1] or 0)
        idx += 2

        by_plan: dict[str, int] = {}
        for plan in _PLANS:
            by_plan[plan] = int(results[idx] or 0)
            idx += 1

        total_requests += day_total
        total_rl_hits += day_rl_hits
        by_day.append(
            {
                "date": date,
                "total": day_total,
                "rate_limit_hits": day_rl_hits,
                "by_plan": by_plan,
            }
        )

    # Active API keys from the database
    keys_by_plan: dict[str, int] = {p: 0 for p in _PLANS if p != "anon"}
    total_keys = 0
    try:
        conn = get_conn()
        with conn.cursor() as cur:
            cur.execute("SELECT plan, COUNT(*) FROM api_keys WHERE is_active = true GROUP BY plan")
            for plan, count in cur.fetchall():
                keys_by_plan[plan] = int(count)
                total_keys += int(count)
        conn.close()
    except Exception:
        pass  # DB unavailable — return partial stats

    return {
        "period_days": days,
        "total_requests": total_requests,
        "total_rate_limit_hits": total_rl_hits,
        "rate_limit_hit_rate": (
            round(total_rl_hits / total_requests * 100, 1) if total_requests else 0
        ),
        "by_day": by_day,
        "active_api_keys": {
            "total": total_keys,
            "by_plan": keys_by_plan,
        },
    }
