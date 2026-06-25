"""Background persistence of query logs. Best-effort: never raises."""

from api.app.core.auth import APIKeyRecord
from db import get_conn


def log_query(
    question: str,
    language: str,
    category: str | None,
    is_off_topic: bool,
    chunks_found: int,
    latency_ms: int,
    api_key: APIKeyRecord | str | None,
) -> None:
    """Persist a query log record — called in background, never raises."""
    if isinstance(api_key, APIKeyRecord):
        prefix = api_key.preview
    elif isinstance(api_key, str):
        prefix = api_key[:8] + "..." if len(api_key) > 8 else api_key
    else:
        prefix = None

    try:
        conn = get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO user_queries
                        (question, language, category, is_off_topic, chunks_found, latency_ms, api_key_prefix)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """,
                    (question, language, category, is_off_topic, chunks_found, latency_ms, prefix),
                )
            conn.commit()
        finally:
            conn.close()
    except Exception:
        pass  # logging must never break the main flow
