import datetime
import hashlib
import os
import secrets

import jwt
import redis
from fastapi import HTTPException

from api.app.core.rate_limit import PLAN_QUOTAS
from api.app.features.admin.schemas import (
    AdminLoginResponse,
    ApiKeyItem,
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


def get_corpus_stats(conn) -> dict:
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM documents WHERE status = 'active'")
        total_docs = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM chunks")
        total_chunks = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM chunks WHERE embedding IS NOT NULL")
        embedded_chunks = cur.fetchone()[0]

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


def list_api_keys(conn, plan: str | None, active_only: bool) -> list[ApiKeyItem]:
    where = ["1=1"]
    params: list = []
    if plan:
        where.append("plan = %s")
        params.append(plan)
    if active_only:
        where.append("is_active = true")

    with conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT id::text, key_prefix, owner_name, owner_email, use_case,
                   plan, is_active, created_at::text, last_used::text
            FROM api_keys
            WHERE {" AND ".join(where)}
            ORDER BY created_at DESC
        """,
            params,
        )
        return [
            ApiKeyItem(
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
            for r in cur.fetchall()
        ]


def create_api_key(conn, req: CreateKeyRequest) -> CreateKeyResponse:
    if req.plan not in PLAN_QUOTAS:
        raise HTTPException(
            status_code=400, detail=f"Invalid plan. Choose from: {list(PLAN_QUOTAS)}"
        )

    key = _KEY_PREFIX + secrets.token_hex(24)
    key_hash = hashlib.sha256(key.encode()).hexdigest()
    key_prefix = key[:14]

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
            RETURNING id::text, key_prefix, owner_name, owner_email, use_case,
                      plan, is_active, created_at::text, last_used::text
        """,
            params,
        )
        row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="API key not found.")
    conn.commit()

    return ApiKeyItem(
        id=row[0],
        key_prefix=row[1],
        owner_name=row[2],
        owner_email=row[3],
        use_case=row[4],
        plan=row[5],
        is_active=row[6],
        created_at=row[7],
        last_used=row[8],
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
            cur.execute("""
                SELECT
                    (SELECT COUNT(*) FROM documents WHERE status = 'active'),
                    (SELECT COUNT(*) FROM chunks),
                    (SELECT COUNT(*) FROM chunks WHERE embedding IS NOT NULL)
            """)
            total_docs, total_chunks, embedded_chunks = cur.fetchone()
        db_ok = True
    except Exception:
        pass

    redis_ok = False
    try:
        r.ping()
        redis_ok = True
    except Exception:
        pass

    return {
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
