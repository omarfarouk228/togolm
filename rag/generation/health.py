"""
Generation health: did the last call to the LLM succeed?

When every Gemini call fails (exhausted credits, retired model, outage) the
API still answers, with raw extracts from the sources, so nothing looks down:
on 2026-10-10 that went unnoticed until a user saw it. Each answer generation
records its outcome here (Redis, best-effort); GET /health/generation reports
"degraded" when the latest outcome is a failure, and the uptime workflow
opens an outage issue on it. Failures are also logged, with their cause.
"""

import logging
import os
import time
from datetime import UTC, datetime

import redis

logger = logging.getLogger("togolm.generation")

_LAST_OK = "togolm:gen:last_ok"
_LAST_ERROR = "togolm:gen:last_error"
_LAST_ERROR_CAUSE = "togolm:gen:last_error_cause"
_client: redis.Redis | None = None


def _redis() -> redis.Redis:
    global _client
    if _client is None:
        url = os.getenv("REDIS_URL") or os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
        _client = redis.from_url(url, decode_responses=True, socket_timeout=2)
    return _client


def short_cause(exc: BaseException) -> str:
    """'402 RESOURCE_EXHAUSTED', '404 NOT_FOUND'... or the exception class."""
    text = str(exc)
    for status in ("RESOURCE_EXHAUSTED", "NOT_FOUND", "PERMISSION_DENIED", "UNAVAILABLE",
                   "DEADLINE_EXCEEDED", "INVALID_ARGUMENT", "UNAUTHENTICATED"):  # fmt: skip
        if status in text:
            code = next(
                (w for w in text.replace(":", " ").split() if w.isdigit() and len(w) == 3), ""
            )
            return f"{code} {status}".strip()
    return type(exc).__name__


def record_success() -> None:
    try:
        _redis().set(_LAST_OK, time.time())
    except Exception:
        pass


def record_failure(exc: BaseException) -> None:
    cause = short_cause(exc)
    logger.warning("Answer generation failed (%s): %s", cause, str(exc)[:300])
    try:
        pipe = _redis().pipeline()
        pipe.set(_LAST_ERROR, time.time())
        pipe.set(_LAST_ERROR_CAUSE, cause)
        pipe.execute()
    except Exception:
        pass


def status() -> dict:
    """{"status": "ok" | "degraded" | "unknown", "last_ok", "last_error", "cause"}."""

    def iso(ts):
        return datetime.fromtimestamp(float(ts), UTC).isoformat(timespec="seconds") if ts else None

    try:
        r = _redis()
        last_ok, last_error, cause = r.get(_LAST_OK), r.get(_LAST_ERROR), r.get(_LAST_ERROR_CAUSE)
    except Exception:
        return {"status": "unknown", "last_ok": None, "last_error": None, "cause": None}
    if last_error and (not last_ok or float(last_error) > float(last_ok)):
        state = "degraded"
    elif last_ok:
        state = "ok"
    else:
        state = "unknown"
    return {
        "status": state,
        "last_ok": iso(last_ok),
        "last_error": iso(last_error),
        "cause": cause if state == "degraded" else None,
    }
