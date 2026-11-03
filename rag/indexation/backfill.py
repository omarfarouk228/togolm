"""
Embedding backlog, drained straight from PostgreSQL.

Three kinds of chunks need work, handled in this order:
  1. missing   — embedding IS NULL (inserted with --no-embed, or the embedding
                 API was down at ingest time). Newest documents first.
  2. legacy    — embedding set but embedding_model IS NULL: written before the
                 column existed, by either Gemini or the local fallback model.
                 They are simply re-embedded with the canonical model. Telling
                 the two apart with the local model loaded torch into the worker
                 (~1.5 GB of RAM on a saturated host) to save re-embedding a
                 few thousand short chunks.
  3. stale     — embedding_model set but not the canonical model (e.g. after
                 switching models).

Each call is bounded (max_chunks, deadline_s) and commits per batch, so it is
safe to interrupt and is meant to be called repeatedly (see
corpus.tasks.embed_pending_chunks). An embedding API error ends the run early;
the next run picks up where this one stopped.
"""

import time

import numpy as np
from psycopg2.extras import execute_batch

from db import get_conn
from rag.indexation.embedder import get_embedder

BATCH_SIZE = 20

_canonical = None


def _canonical_embedder():
    global _canonical
    if _canonical is None:
        _canonical = get_embedder()
    return _canonical


_MISSING_SQL = """
    SELECT c.id, c.content, NULL
    FROM chunks c
    JOIN documents d ON d.id = c.document_id
    WHERE c.embedding IS NULL AND d.status = 'active'
    ORDER BY d.collected_at DESC NULLS LAST
    LIMIT %s
    FOR UPDATE OF c SKIP LOCKED
"""

_LEGACY_SQL = """
    SELECT id, content, embedding
    FROM chunks
    WHERE embedding IS NOT NULL AND embedding_model IS NULL
    LIMIT %s
    FOR UPDATE SKIP LOCKED
"""

_STALE_SQL = """
    SELECT id, content, NULL
    FROM chunks
    WHERE embedding IS NOT NULL
      AND embedding_model IS NOT NULL
      AND embedding_model <> %s
    LIMIT %s
    FOR UPDATE SKIP LOCKED
"""


def _process_batch(cur, rows, canonical) -> dict:
    """Embed one batch of (id, content, _) rows with the canonical model."""
    ids = [r[0] for r in rows]
    texts = [r[1] for r in rows]
    embedded = 0
    for i in range(0, len(texts), BATCH_SIZE):
        batch_ids = ids[i : i + BATCH_SIZE]
        vectors = canonical.encode(texts[i : i + BATCH_SIZE])
        execute_batch(
            cur,
            "UPDATE chunks SET embedding = %s, embedding_model = %s WHERE id = %s",
            [(np.asarray(v), canonical.model_id, cid) for v, cid in zip(vectors, batch_ids)],
        )
        embedded += len(batch_ids)
    return {"embedded": embedded, "tagged": 0}


def embed_pending(max_chunks: int = 4000, deadline_s: float | None = None) -> dict:
    """Work through the backlog until max_chunks rows are handled, the
    deadline passes, the backlog is empty, or the embedding API fails."""
    canonical = _canonical_embedder()
    started = time.monotonic()
    stats = {"model": canonical.model_id, "embedded": 0, "tagged": 0, "stopped": "done"}
    by_kind = {"missing": 0, "legacy": 0, "stale": 0}

    conn = get_conn(vector=True)
    try:
        for kind in ("missing", "legacy", "stale"):
            while True:
                handled = stats["embedded"] + stats["tagged"]
                if handled >= max_chunks:
                    stats["stopped"] = "max_chunks"
                    return {**stats, "by_kind": by_kind}
                if deadline_s is not None and time.monotonic() - started > deadline_s:
                    stats["stopped"] = "deadline"
                    return {**stats, "by_kind": by_kind}

                limit = min(BATCH_SIZE, max_chunks - handled)
                with conn.cursor() as cur:
                    if kind == "missing":
                        cur.execute(_MISSING_SQL, (limit,))
                    elif kind == "legacy":
                        cur.execute(_LEGACY_SQL, (limit,))
                    else:
                        cur.execute(_STALE_SQL, (canonical.model_id, limit))
                    rows = cur.fetchall()
                    if not rows:
                        conn.commit()
                        break
                    try:
                        result = _process_batch(cur, rows, canonical)
                    except Exception as e:  # embedding API down / rate limited
                        conn.rollback()
                        stats["stopped"] = f"embedding error: {str(e)[:200]}"
                        return {**stats, "by_kind": by_kind}
                conn.commit()
                stats["embedded"] += result["embedded"]
                stats["tagged"] += result["tagged"]
                by_kind[kind] += len(rows)
        return {**stats, "by_kind": by_kind}
    finally:
        conn.close()


def pending_counts() -> dict:
    """Backlog size per kind, for monitoring (admin health endpoint, CLI)."""
    canonical_id = _canonical_embedder().model_id
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    COUNT(*) FILTER (WHERE embedding IS NULL),
                    COUNT(*) FILTER (WHERE embedding IS NOT NULL AND embedding_model IS NULL),
                    COUNT(*) FILTER (WHERE embedding_model IS NOT NULL AND embedding_model <> %s)
                FROM chunks
                """,
                (canonical_id,),
            )
            missing, legacy, stale = cur.fetchone()
        return {"missing": missing, "legacy": legacy, "stale": stale}
    finally:
        conn.close()
