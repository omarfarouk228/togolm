"""
Shared PostgreSQL connection factory.

Usage:
    from api.app.db import get_conn

    conn = get_conn()          # standard connection
    conn = get_conn(vector=True)  # with pgvector registered (for RAG)
"""

import os

import psycopg2
from pgvector.psycopg2 import register_vector


def get_conn(vector: bool = False) -> psycopg2.extensions.connection:
    """
    Open and return a psycopg2 connection using environment variables.

    Args:
        vector: If True, registers the pgvector type on the connection.
                Required for routes that use embedding similarity search.
    """
    conn = psycopg2.connect(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=int(os.getenv("POSTGRES_PORT", "5432")),
        dbname=os.getenv("POSTGRES_DB", "togolm"),
        user=os.getenv("POSTGRES_USER"),
        password=os.getenv("POSTGRES_PASSWORD") or None,
    )
    if vector:
        register_vector(conn)
    return conn
