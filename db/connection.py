"""
Shared PostgreSQL connection factory with pooling.

Usage (unchanged from before — existing conn.close() calls work correctly):
    from db import get_conn

    conn = get_conn()           # standard connection
    conn = get_conn(vector=True)  # with pgvector registered (for RAG)
    conn.close()                # returns to pool instead of destroying the socket

All callers retain their existing try/finally conn.close() pattern.
For new code, the conn_ctx() context manager is more ergonomic.
"""

import os
import threading
from contextlib import contextmanager

import psycopg2.pool
from pgvector.psycopg2 import register_vector

_pool: psycopg2.pool.ThreadedConnectionPool | None = None
_pool_lock = threading.Lock()


def _get_pool() -> psycopg2.pool.ThreadedConnectionPool:
    global _pool
    if _pool is not None:
        return _pool
    with _pool_lock:
        if _pool is None:
            _pool = psycopg2.pool.ThreadedConnectionPool(
                minconn=2,
                maxconn=10,
                host=os.getenv("POSTGRES_HOST", "localhost"),
                port=int(os.getenv("POSTGRES_PORT", "5432")),
                dbname=os.getenv("POSTGRES_DB", "togolm"),
                user=os.getenv("POSTGRES_USER"),
                password=os.getenv("POSTGRES_PASSWORD") or None,
            )
    return _pool


class _PooledConn:
    """Proxy that intercepts close() to return the connection to the pool."""

    def __init__(self, conn, pool: psycopg2.pool.ThreadedConnectionPool) -> None:
        self._conn = conn
        self._pool = pool

    def close(self) -> None:
        self._pool.putconn(self._conn)

    def __getattr__(self, name: str):
        return getattr(self._conn, name)


def get_conn(vector: bool = False) -> psycopg2.extensions.connection:
    """
    Borrow a connection from the pool.

    The returned object behaves like a standard psycopg2 connection.
    Calling .close() returns it to the pool; it does not close the socket.
    """
    pool = _get_pool()
    conn = pool.getconn()
    if vector:
        register_vector(conn)
    return _PooledConn(conn, pool)  # type: ignore[return-value]


@contextmanager
def conn_ctx(vector: bool = False):
    """Context manager — borrows and automatically returns a pooled connection."""
    conn = get_conn(vector=vector)
    try:
        yield conn
    finally:
        conn.close()
