import datetime
import hashlib
import json
import os
import secrets

import jwt
import redis
from fastapi import HTTPException

from api.app.core.rate_limit import PLAN_QUOTAS
from api.app.features.admin.schemas import (
    AdminLoginResponse,
    ApiKeyItem,
    ApiKeyListResponse,
    CreateKeyRequest,
    CreateKeyResponse,
    FeedbackItem,
    FeedbackListResponse,
    PatchFeedbackRequest,
    PatchKeyRequest,
    QueryItem,
    QueryListResponse,
    RecentDocument,
    SourceStat,
)

_FEEDBACK_STATUSES = ["open", "reviewed", "dismissed"]

_PLANS = ["anon", "free", "dev", "institution"]
_KEY_PREFIX = "tgolm_"
_TOKEN_TTL_HOURS = 24


def get_redis() -> redis.Redis:
    url = os.getenv("REDIS_URL") or os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
    return redis.from_url(url, decode_responses=True)


def _secret() -> str:
    s = os.getenv("API_SECRET_KEY", "")
    if not s:
        raise HTTPException(status_code=500, detail="API_SECRET_KEY not configured.")
    return s


def login(key: str) -> AdminLoginResponse:
    if key != _secret():
        raise HTTPException(status_code=401, detail="Invalid admin key.")
    expires_at = datetime.datetime.now(datetime.UTC) + datetime.timedelta(hours=_TOKEN_TTL_HOURS)
    token = jwt.encode(
        {"sub": "admin", "exp": expires_at},
        _secret(),
        algorithm="HS256",
    )
    return AdminLoginResponse(token=token, expires_at=expires_at.isoformat())


def require_admin(authorization: str | None, x_admin_key: str | None) -> None:
    """Accept either Bearer JWT token or legacy X-Admin-Key header."""
    # Bearer token (preferred)
    if authorization and authorization.startswith("Bearer "):
        token = authorization.removeprefix("Bearer ")
        try:
            jwt.decode(token, _secret(), algorithms=["HS256"])
            return
        except jwt.ExpiredSignatureError:
            raise HTTPException(status_code=401, detail="Token expired.")
        except jwt.InvalidTokenError:
            raise HTTPException(status_code=401, detail="Invalid token.")

    # Legacy X-Admin-Key (backward compat)
    if x_admin_key and x_admin_key == _secret():
        return

    raise HTTPException(status_code=401, detail="Authentication required.")


# ── Corpus ────────────────────────────────────────────────────────────────────


# Counting the 415k chunks (1.9 GB) takes several seconds on prod and every
# admin page did it on each load: Dashboard, Corpus and Health stayed on their
# loading skeleton for 5+ s. The counts only move with ingestion, so they are
# cached for a few minutes.
_CHUNK_COUNTS_KEY = "togolm:admin:chunk_counts"
_CHUNK_COUNTS_TTL_S = 600


def chunk_counts(conn, r: redis.Redis | None = None) -> tuple[int, int]:
    """(total chunks, chunks with an embedding), cached in Redis."""
    r = r or get_redis()
    try:
        cached = r.get(_CHUNK_COUNTS_KEY)
        if cached:
            total, embedded = json.loads(cached)
            return int(total), int(embedded)
    except Exception:
        pass
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*), COUNT(embedding) FROM chunks")
        total, embedded = cur.fetchone()
    try:
        r.set(_CHUNK_COUNTS_KEY, json.dumps([total, embedded]), ex=_CHUNK_COUNTS_TTL_S)
    except Exception:
        pass
    return int(total), int(embedded)


def get_corpus_stats(conn) -> dict:
    total_chunks, embedded_chunks = chunk_counts(conn)
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM documents WHERE status = 'active'")
        total_docs = cur.fetchone()[0]

        cur.execute("""
            SELECT category, COUNT(*) FROM documents
            WHERE status = 'active' GROUP BY category ORDER BY COUNT(*) DESC
        """)
        by_category = {r[0] or "unknown": r[1] for r in cur.fetchall()}

        cur.execute("""
            SELECT language, COUNT(*) FROM documents
            WHERE status = 'active' GROUP BY language ORDER BY COUNT(*) DESC
        """)
        by_language = {r[0] or "unknown": r[1] for r in cur.fetchall()}

        cur.execute("SELECT COUNT(DISTINCT source) FROM documents WHERE status = 'active'")
        total_sources = cur.fetchone()[0]

    return {
        "total_documents": total_docs,
        "total_chunks": total_chunks,
        "embedded_chunks": embedded_chunks,
        "embedding_coverage_pct": round(embedded_chunks / total_chunks * 100, 1)
        if total_chunks
        else 0,
        "total_sources": total_sources,
        "by_category": by_category,
        "by_language": by_language,
    }


def get_corpus_sources(conn) -> list[SourceStat]:
    with conn.cursor() as cur:
        cur.execute("""
            SELECT source, category, COUNT(*) AS doc_count,
                   MAX(collected_at)::text AS last_collected
            FROM documents
            WHERE status = 'active'
            GROUP BY source, category
            ORDER BY doc_count DESC
        """)
        return [
            SourceStat(source=r[0], category=r[1], doc_count=r[2], last_collected=r[3])
            for r in cur.fetchall()
        ]


def get_recent_documents(conn, limit: int) -> list[RecentDocument]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id::text, source, title, url, category, language,
                   word_count, collected_at::text
            FROM documents
            WHERE status = 'active'
            ORDER BY collected_at DESC
            LIMIT %s
        """,
            (limit,),
        )
        return [
            RecentDocument(
                id=r[0],
                source=r[1],
                title=r[2],
                url=r[3],
                category=r[4],
                language=r[5],
                word_count=r[6],
                collected_at=r[7],
            )
            for r in cur.fetchall()
        ]


# ── API Keys ──────────────────────────────────────────────────────────────────


_KEY_COLUMNS = """id::text, key_prefix, owner_name, owner_email, use_case,
                   plan, is_active, created_at::text, last_used::text"""


def _key_item(r) -> ApiKeyItem:
    return ApiKeyItem(
        id=r[0],
        key_prefix=r[1],
        owner_name=r[2],
        owner_email=r[3],
        use_case=r[4],
        plan=r[5],
        is_active=r[6],
        created_at=r[7],
        last_used=r[8],
    )


def _new_key() -> tuple[str, str, str]:
    """Return (plain key, sha256 hash, display prefix) for a fresh key."""
    key = _KEY_PREFIX + secrets.token_hex(24)
    return key, hashlib.sha256(key.encode()).hexdigest(), key[:14]


def list_api_keys(
    conn, page: int, page_size: int, plan: str | None, active_only: bool
) -> ApiKeyListResponse:
    offset = (page - 1) * page_size
    where = ["1=1"]
    params: list = []
    if plan:
        where.append("plan = %s")
        params.append(plan)
    if active_only:
        where.append("is_active = true")
    clause = " AND ".join(where)

    with conn.cursor() as cur:
        cur.execute(f"SELECT COUNT(*) FROM api_keys WHERE {clause}", params)
        total = cur.fetchone()[0]
        cur.execute(
            f"""
            SELECT {_KEY_COLUMNS}
            FROM api_keys
            WHERE {clause}
            ORDER BY created_at DESC
            LIMIT %s OFFSET %s
        """,
            params + [page_size, offset],
        )
        items = [_key_item(r) for r in cur.fetchall()]
    return ApiKeyListResponse(items=items, total=total, page=page, page_size=page_size)


def create_api_key(conn, req: CreateKeyRequest) -> CreateKeyResponse:
    if req.plan not in PLAN_QUOTAS:
        raise HTTPException(
            status_code=400, detail=f"Invalid plan. Choose from: {list(PLAN_QUOTAS)}"
        )

    key, key_hash, key_prefix = _new_key()

    with conn.cursor() as cur:
        cur.execute("SELECT id FROM api_keys WHERE owner_email = %s", (req.email,))
        if cur.fetchone():
            raise HTTPException(status_code=409, detail="An API key already exists for this email.")
        cur.execute(
            """
            INSERT INTO api_keys (key_hash, key_prefix, owner_name, owner_email, use_case, plan)
            VALUES (%s, %s, %s, %s, %s, %s)
        """,
            (key_hash, key_prefix, req.name, req.email, req.use_case, req.plan),
        )
    conn.commit()

    return CreateKeyResponse(
        api_key=key,
        key_prefix=key_prefix + "...",
        plan=req.plan,
        quota_per_day=PLAN_QUOTAS[req.plan],
    )


def update_api_key(conn, key_id: str, req: PatchKeyRequest) -> ApiKeyItem:
    if req.plan is not None and req.plan not in PLAN_QUOTAS:
        raise HTTPException(
            status_code=400, detail=f"Invalid plan. Choose from: {list(PLAN_QUOTAS)}"
        )

    sets = []
    params: list = []
    if req.plan is not None:
        sets.append("plan = %s")
        params.append(req.plan)
    if req.is_active is not None:
        sets.append("is_active = %s")
        params.append(req.is_active)
    if not sets:
        raise HTTPException(status_code=400, detail="Nothing to update.")

    params.append(key_id)
    with conn.cursor() as cur:
        cur.execute(
            f"""
            UPDATE api_keys SET {", ".join(sets)}
            WHERE id::text = %s
            RETURNING {_KEY_COLUMNS}
        """,
            params,
        )
        row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="API key not found.")
    conn.commit()

    return _key_item(row)


def reset_api_key(conn, key_id: str) -> CreateKeyResponse:
    """Replace a key's secret. The old key stops working at once; the record
    (owner, plan, quota counter keyed by id) is kept."""
    key, key_hash, key_prefix = _new_key()
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE api_keys SET key_hash = %s, key_prefix = %s, last_used = NULL
            WHERE id::text = %s
            RETURNING plan
        """,
            (key_hash, key_prefix, key_id),
        )
        row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="API key not found.")
    conn.commit()

    return CreateKeyResponse(
        api_key=key,
        key_prefix=key_prefix + "...",
        plan=row[0],
        quota_per_day=PLAN_QUOTAS.get(row[0], 0),
    )


def delete_api_key(conn, key_id: str) -> None:
    with conn.cursor() as cur:
        cur.execute("DELETE FROM api_keys WHERE id::text = %s RETURNING id", (key_id,))
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="API key not found.")
    conn.commit()


# ── Queries ───────────────────────────────────────────────────────────────────


def list_queries(
    conn,
    page: int,
    page_size: int,
    off_topic_only: bool,
    category: str | None = None,
    language: str | None = None,
    latency_min: int | None = None,
    latency_max: int | None = None,
    chunks_min: int | None = None,
    chunks_max: int | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
) -> QueryListResponse:
    offset = (page - 1) * page_size
    conditions: list[str] = []
    params: list = []

    if off_topic_only:
        conditions.append("is_off_topic = true")
    if category:
        conditions.append("category = %s")
        params.append(category)
    if language:
        conditions.append("language = %s")
        params.append(language)
    if latency_min is not None:
        conditions.append("latency_ms >= %s")
        params.append(latency_min)
    if latency_max is not None:
        conditions.append("latency_ms <= %s")
        params.append(latency_max)
    if chunks_min is not None:
        conditions.append("chunks_found >= %s")
        params.append(chunks_min)
    if chunks_max is not None:
        conditions.append("chunks_found <= %s")
        params.append(chunks_max)
    if date_from:
        conditions.append("created_at >= %s")
        params.append(date_from)
    if date_to:
        conditions.append("created_at <= %s")
        params.append(date_to + " 23:59:59")

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""

    with conn.cursor() as cur:
        cur.execute(f"SELECT COUNT(*) FROM user_queries {where}", params)
        total = cur.fetchone()[0]
        cur.execute(
            f"""
            SELECT id::text, question, language, category, is_off_topic,
                   chunks_found, latency_ms, api_key_prefix, created_at::text
            FROM user_queries
            {where}
            ORDER BY created_at DESC
            LIMIT %s OFFSET %s
        """,
            params + [page_size, offset],
        )
        items = [
            QueryItem(
                id=r[0],
                question=r[1],
                language=r[2],
                category=r[3],
                is_off_topic=r[4],
                chunks_found=r[5],
                latency_ms=r[6],
                api_key_prefix=r[7],
                created_at=r[8],
            )
            for r in cur.fetchall()
        ]
    return QueryListResponse(items=items, total=total, page=page, page_size=page_size)


def get_query_stats(conn, days: int) -> dict:
    since = datetime.date.today() - datetime.timedelta(days=days)
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM user_queries")
        (total_all_time,) = cur.fetchone()

        cur.execute(
            """
            SELECT COUNT(*),
                   COUNT(*) FILTER (WHERE is_off_topic),
                   ROUND(AVG(latency_ms)) AS avg_latency,
                   ROUND(AVG(chunks_found), 1) AS avg_chunks
            FROM user_queries WHERE created_at >= %s
        """,
            (since,),
        )
        total, off_topic, avg_latency, avg_chunks = cur.fetchone()

        cur.execute(
            """
            SELECT question, COUNT(*) AS n
            FROM user_queries
            WHERE created_at >= %s AND is_off_topic = false
            GROUP BY question ORDER BY n DESC LIMIT 10
        """,
            (since,),
        )
        top_questions = [{"question": r[0], "count": r[1]} for r in cur.fetchall()]

        cur.execute(
            """
            SELECT DATE(created_at) AS day, COUNT(*) AS n
            FROM user_queries WHERE created_at >= %s
            GROUP BY day ORDER BY day
        """,
            (since,),
        )
        by_day = [{"date": str(r[0]), "count": r[1]} for r in cur.fetchall()]

    total = total or 0
    return {
        "period_days": days,
        "total_queries": total_all_time or 0,
        "period_queries": total,
        "off_topic_count": off_topic or 0,
        "off_topic_rate_pct": round((off_topic or 0) / total * 100, 1) if total else 0,
        "avg_latency_ms": int(avg_latency) if avg_latency else None,
        "avg_chunks_found": float(avg_chunks) if avg_chunks else None,
        "top_questions": top_questions,
        "by_day": by_day,
    }


# ── Usage stats ───────────────────────────────────────────────────────────────


def get_usage_stats(conn, r: redis.Redis, days: int) -> dict:
    today = datetime.date.today()
    dates = [(today - datetime.timedelta(days=i)).isoformat() for i in range(days - 1, -1, -1)]

    pipe = r.pipeline()
    for date in dates:
        pipe.get(f"stats:req:{date}")
        pipe.get(f"stats:rl_hit:{date}")
        for plan in _PLANS:
            pipe.get(f"stats:req:{date}:{plan}")
    results = pipe.execute()

    by_day = []
    total_requests = total_rl_hits = 0
    idx = 0
    for date in dates:
        day_total = int(results[idx] or 0)
        day_rl_hits = int(results[idx + 1] or 0)
        idx += 2
        by_plan = {plan: int(results[idx + i] or 0) for i, plan in enumerate(_PLANS)}
        idx += len(_PLANS)
        total_requests += day_total
        total_rl_hits += day_rl_hits
        by_day.append(
            {"date": date, "total": day_total, "rate_limit_hits": day_rl_hits, "by_plan": by_plan}
        )

    keys_by_plan: dict[str, int] = {p: 0 for p in _PLANS if p != "anon"}
    total_keys = 0
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT plan, COUNT(*) FROM api_keys WHERE is_active = true GROUP BY plan")
            for plan, count in cur.fetchall():
                keys_by_plan[plan] = int(count)
                total_keys += int(count)
    except Exception:
        pass

    requests_today = by_day[-1]["total"] if by_day else 0

    return {
        "period_days": days,
        "total_requests": total_requests,
        "requests_today": requests_today,
        "total_rate_limit_hits": total_rl_hits,
        "rate_limit_hit_rate": round(total_rl_hits / total_requests * 100, 1)
        if total_requests
        else 0,
        "by_day": by_day,
        "active_api_keys": {"total": total_keys, "by_plan": keys_by_plan},
    }


# ── Health ────────────────────────────────────────────────────────────────────


def get_health(conn, r: redis.Redis) -> dict:
    db_ok = False
    total_docs = total_chunks = embedded_chunks = 0
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM documents WHERE status = 'active'")
            total_docs = cur.fetchone()[0]
        total_chunks, embedded_chunks = chunk_counts(conn, r)
        db_ok = True
    except Exception:
        pass

    redis_ok = False
    try:
        r.ping()
        redis_ok = True
    except Exception:
        pass

    # Chunks still waiting on rag.indexation.backfill (missing vector, untagged
    # legacy vector, or vector from a non-canonical model).
    embedding_backlog = None
    try:
        from rag.indexation.backfill import pending_counts

        embedding_backlog = pending_counts()
    except Exception:
        pass

    return {
        "embedding_backlog": embedding_backlog,
        "database": {
            "status": "ok" if db_ok else "error",
            "details": {
                "total_documents": total_docs,
                "total_chunks": total_chunks,
                "embedded_chunks": embedded_chunks,
            }
            if db_ok
            else None,
        },
        "redis": {"status": "ok" if redis_ok else "error"},
        "chunks_with_embeddings": embedded_chunks,
        "total_chunks": total_chunks,
        "embedding_coverage": round(embedded_chunks / total_chunks * 100, 1) if total_chunks else 0,
    }


def list_feedback(
    conn,
    page: int,
    page_size: int,
    status: str | None = None,
    category: str | None = None,
) -> FeedbackListResponse:
    offset = (page - 1) * page_size
    conditions: list[str] = []
    params: list = []

    if status:
        conditions.append("status = %s")
        params.append(status)
    if category:
        conditions.append("category = %s")
        params.append(category)

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""

    with conn.cursor() as cur:
        cur.execute(f"SELECT COUNT(*) FROM response_feedback {where}", params)
        total = cur.fetchone()[0]
        cur.execute(
            f"""
            SELECT id::text, category, status, question, answer, comment,
                   sources, language, api_key_prefix, created_at::text
            FROM response_feedback
            {where}
            ORDER BY created_at DESC
            LIMIT %s OFFSET %s
        """,
            params + [page_size, offset],
        )
        items = [
            FeedbackItem(
                id=r[0],
                category=r[1],
                status=r[2],
                question=r[3],
                answer=r[4],
                comment=r[5],
                sources=r[6],
                language=r[7],
                api_key_prefix=r[8],
                created_at=r[9],
            )
            for r in cur.fetchall()
        ]
    return FeedbackListResponse(items=items, total=total, page=page, page_size=page_size)


def update_feedback_status(conn, feedback_id: str, req: PatchFeedbackRequest) -> FeedbackItem:
    if req.status not in _FEEDBACK_STATUSES:
        raise HTTPException(
            status_code=400, detail=f"Invalid status. Choose from: {_FEEDBACK_STATUSES}"
        )

    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE response_feedback SET status = %s
            WHERE id::text = %s
            RETURNING id::text, category, status, question, answer, comment,
                      sources, language, api_key_prefix, created_at::text
        """,
            (req.status, feedback_id),
        )
        row = cur.fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Feedback not found")
        conn.commit()

    return FeedbackItem(
        id=row[0],
        category=row[1],
        status=row[2],
        question=row[3],
        answer=row[4],
        comment=row[5],
        sources=row[6],
        language=row[7],
        api_key_prefix=row[8],
        created_at=row[9],
    )


# ── Overview ──────────────────────────────────────────────────────────────────

# Sources crawled daily by corpus.tasks.run_news_spiders; the others only by
# the weekly full crawl.
_DAILY_SOURCES = {
    "icilome.com",
    "togoactualite.com",
    "togofirst.com",
    "lomeinfos.com",
    "letogolais.com",
    "savoirnews.net",
    "republicoftogo.com",
    "presidence.gouv.tg",
}
_STALE_AFTER_DAYS = {"daily": 3, "weekly": 14}
CRAWL_RESULTS_KEY = "togolm:crawl:spiders"


def _traffic(cur, days: int) -> list[dict]:
    cur.execute(
        """
        SELECT DATE(created_at) AS day,
               COUNT(*),
               percentile_cont(0.5) WITHIN GROUP (ORDER BY latency_ms),
               percentile_cont(0.9) WITHIN GROUP (ORDER BY latency_ms),
               COUNT(*) FILTER (WHERE is_off_topic),
               COUNT(*) FILTER (WHERE chunks_found = 0 AND NOT is_off_topic),
               COUNT(*) FILTER (WHERE api_key_prefix IS NOT NULL)
        FROM user_queries
        WHERE created_at >= CURRENT_DATE - %s
        GROUP BY day ORDER BY day
        """,
        (days - 1,),
    )
    rows = {r[0].isoformat(): r for r in cur.fetchall()}
    today = datetime.date.today()
    out = []
    for i in range(days - 1, -1, -1):
        day = (today - datetime.timedelta(days=i)).isoformat()
        r = rows.get(day)
        out.append(
            {
                "date": day,
                "queries": int(r[1]) if r else 0,
                "latency_p50_ms": int(r[2]) if r and r[2] is not None else None,
                "latency_p90_ms": int(r[3]) if r and r[3] is not None else None,
                "off_topic": int(r[4]) if r else 0,
                "no_sources": int(r[5]) if r else 0,
                "with_key": int(r[6]) if r else 0,
            }
        )
    return out


def _sources(cur) -> list[dict]:
    cur.execute(
        """
        SELECT source, MODE() WITHIN GROUP (ORDER BY category), COUNT(*),
               MAX(collected_at), MAX(published_at),
               COUNT(*) FILTER (WHERE published_at IS NULL)
        FROM documents
        WHERE status = 'active'
        GROUP BY source
        ORDER BY COUNT(*) DESC
        """
    )
    now = datetime.datetime.now()
    out = []
    for source, category, docs, collected, published, undated in cur.fetchall():
        schedule = "daily" if source in _DAILY_SOURCES else "weekly"
        age = (now - collected).days if collected else None
        out.append(
            {
                "source": source,
                "category": category,
                "documents": int(docs),
                "schedule": schedule,
                "last_collected": collected.isoformat(timespec="minutes") if collected else None,
                "last_published": published.isoformat() if published else None,
                "days_since_collected": age,
                "undated_pct": round(undated * 100 / docs) if docs else 0,
                "stale": age is None or age > _STALE_AFTER_DAYS[schedule],
            }
        )
    return out


def _crawls(r: redis.Redis) -> list[dict]:
    try:
        raw = r.hgetall(CRAWL_RESULTS_KEY)
    except Exception:
        return []
    runs = []
    for value in raw.values():
        try:
            runs.append(json.loads(value))
        except ValueError:
            continue
    return sorted(runs, key=lambda run: run.get("finished_at") or "", reverse=True)


def _latest_eval(r: redis.Redis) -> dict | None:
    from corpus.tasks import EVAL_HISTORY_KEY

    try:
        raw = r.lindex(EVAL_HISTORY_KEY, 0)
    except Exception:
        return None
    if not raw:
        return None
    run = json.loads(raw)
    return {k: v for k, v in run.items() if k != "results"}


def get_overview(conn, r: redis.Redis, days: int = 14) -> dict:
    """Everything the admin home page needs in one call: what needs attention
    (generation down, stale sources, failed crawls, reports and reviews to
    handle) and how the service is used (queries, latency)."""
    from rag.generation.health import status as generation_status

    total_chunks, embedded_chunks = chunk_counts(conn, r)
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM documents WHERE status = 'active'")
        total_docs = cur.fetchone()[0]
        traffic = _traffic(cur, days)
        sources = _sources(cur)
        cur.execute("SELECT COUNT(*) FROM response_feedback WHERE status = 'open'")
        open_feedback = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM language_reviews WHERE status = 'pending'")
        pending_reviews = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM api_keys WHERE is_active")
        active_keys = cur.fetchone()[0]

    usage = get_usage_stats(conn, r, days)
    rate_limited = {d["date"]: d["rate_limit_hits"] for d in usage["by_day"]}
    requests = {d["date"]: d["total"] for d in usage["by_day"]}
    for day in traffic:
        day["requests"] = requests.get(day["date"], 0)
        day["rate_limited"] = rate_limited.get(day["date"], 0)

    return {
        "generated_at": datetime.datetime.now(datetime.UTC).isoformat(timespec="seconds"),
        "generation": generation_status(),
        "corpus": {
            "documents": total_docs,
            "chunks": total_chunks,
            "embedded_chunks": embedded_chunks,
            "sources": len(sources),
        },
        "traffic": traffic,
        "sources": sources,
        "crawls": _crawls(r),
        "retrieval_eval": _latest_eval(r),
        "todo": {
            "open_feedback": int(open_feedback),
            "pending_reviews": int(pending_reviews),
        },
        "active_api_keys": int(active_keys),
    }
