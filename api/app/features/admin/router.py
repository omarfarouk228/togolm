"""
Admin endpoints — auth via POST /v1/admin/login (returns JWT).

Auth:
  POST /v1/admin/login           — validate admin key, get JWT token

Corpus:
  GET  /v1/admin/corpus/stats    — totals, by source / category / language
  GET  /v1/admin/corpus/sources  — per-source doc count and last scrape date
  GET  /v1/admin/corpus/recent   — recently ingested documents

API Keys:
  GET    /v1/admin/keys          — list all keys
  POST   /v1/admin/keys          — create a key with a given plan
  PATCH  /v1/admin/keys/{id}     — update plan or active status
  DELETE /v1/admin/keys/{id}     — hard-delete a key

Queries:
  GET  /v1/admin/queries         — paginated query history
  GET  /v1/admin/queries/stats   — off-topic rate, avg latency, totals

Usage stats:
  GET  /v1/admin/stats           — request counts from Redis

System:
  GET  /v1/admin/health/detailed — DB, Redis, embedding coverage
"""

from fastapi import APIRouter, Header, Query

from db import get_conn
from api.app.features.admin import service
from api.app.features.admin.schemas import (
    AdminLoginRequest,
    AdminLoginResponse,
    ApiKeyItem,
    CreateKeyRequest,
    CreateKeyResponse,
    PatchKeyRequest,
    QueryListResponse,
    RecentDocument,
    SourceStat,
)

router = APIRouter(tags=["Admin"])


def _auth(authorization: str | None, x_admin_key: str | None) -> None:
    service.require_admin(authorization, x_admin_key)


# ── Auth ──────────────────────────────────────────────────────────────────────


@router.post("/admin/login", response_model=AdminLoginResponse)
def login(req: AdminLoginRequest):
    """Exchange the admin key for a 24-hour JWT token."""
    return service.login(req.key)


# ── Corpus ────────────────────────────────────────────────────────────────────


@router.get("/admin/corpus/stats")
def corpus_stats(
    authorization: str | None = Header(default=None),
    x_admin_key: str | None = Header(default=None),
):
    _auth(authorization, x_admin_key)
    conn = get_conn()
    try:
        return service.get_corpus_stats(conn)
    finally:
        conn.close()


@router.get("/admin/corpus/sources", response_model=list[SourceStat])
def corpus_sources(
    authorization: str | None = Header(default=None),
    x_admin_key: str | None = Header(default=None),
):
    _auth(authorization, x_admin_key)
    conn = get_conn()
    try:
        return service.get_corpus_sources(conn)
    finally:
        conn.close()


@router.get("/admin/corpus/recent", response_model=list[RecentDocument])
def corpus_recent(
    limit: int = Query(20, ge=1, le=100),
    authorization: str | None = Header(default=None),
    x_admin_key: str | None = Header(default=None),
):
    _auth(authorization, x_admin_key)
    conn = get_conn()
    try:
        return service.get_recent_documents(conn, limit)
    finally:
        conn.close()


# ── API Keys ──────────────────────────────────────────────────────────────────


@router.get("/admin/keys", response_model=list[ApiKeyItem])
def list_keys(
    plan: str | None = Query(None),
    active_only: bool = Query(False),
    authorization: str | None = Header(default=None),
    x_admin_key: str | None = Header(default=None),
):
    _auth(authorization, x_admin_key)
    conn = get_conn()
    try:
        return service.list_api_keys(conn, plan, active_only)
    finally:
        conn.close()


@router.post("/admin/keys", response_model=CreateKeyResponse, status_code=201)
def create_key(
    req: CreateKeyRequest,
    authorization: str | None = Header(default=None),
    x_admin_key: str | None = Header(default=None),
):
    _auth(authorization, x_admin_key)
    conn = get_conn()
    try:
        return service.create_api_key(conn, req)
    finally:
        conn.close()


@router.patch("/admin/keys/{key_id}", response_model=ApiKeyItem)
def update_key(
    key_id: str,
    req: PatchKeyRequest,
    authorization: str | None = Header(default=None),
    x_admin_key: str | None = Header(default=None),
):
    _auth(authorization, x_admin_key)
    conn = get_conn()
    try:
        return service.update_api_key(conn, key_id, req)
    finally:
        conn.close()


@router.delete("/admin/keys/{key_id}", status_code=204)
def delete_key(
    key_id: str,
    authorization: str | None = Header(default=None),
    x_admin_key: str | None = Header(default=None),
):
    _auth(authorization, x_admin_key)
    conn = get_conn()
    try:
        service.delete_api_key(conn, key_id)
    finally:
        conn.close()


# ── Queries ───────────────────────────────────────────────────────────────────


@router.get("/admin/queries", response_model=QueryListResponse)
def list_queries(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    off_topic_only: bool = Query(False),
    category: str | None = Query(None),
    language: str | None = Query(None),
    latency_min: int | None = Query(None),
    latency_max: int | None = Query(None),
    chunks_min: int | None = Query(None),
    chunks_max: int | None = Query(None),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
    authorization: str | None = Header(default=None),
    x_admin_key: str | None = Header(default=None),
):
    _auth(authorization, x_admin_key)
    conn = get_conn()
    try:
        return service.list_queries(
            conn,
            page,
            page_size,
            off_topic_only,
            category,
            language,
            latency_min,
            latency_max,
            chunks_min,
            chunks_max,
            date_from,
            date_to,
        )
    finally:
        conn.close()


@router.get("/admin/queries/stats")
def query_stats(
    days: int = Query(7, ge=1, le=90),
    authorization: str | None = Header(default=None),
    x_admin_key: str | None = Header(default=None),
):
    _auth(authorization, x_admin_key)
    conn = get_conn()
    try:
        return service.get_query_stats(conn, days)
    finally:
        conn.close()


# ── Usage stats ───────────────────────────────────────────────────────────────


@router.get("/admin/stats")
def get_admin_stats(
    days: int = Query(default=7, ge=1, le=90),
    authorization: str | None = Header(default=None),
    x_admin_key: str | None = Header(default=None),
):
    _auth(authorization, x_admin_key)
    conn = get_conn()
    try:
        return service.get_usage_stats(conn, service.get_redis(), days)
    finally:
        conn.close()


# ── Health ────────────────────────────────────────────────────────────────────


@router.get("/admin/health/detailed")
def health_detailed(
    authorization: str | None = Header(default=None),
    x_admin_key: str | None = Header(default=None),
):
    _auth(authorization, x_admin_key)
    conn = get_conn()
    try:
        return service.get_health(conn, service.get_redis())
    finally:
        conn.close()
