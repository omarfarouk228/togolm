"""Shared infrastructure: PostgreSQL connection factory."""

from db.connection import get_conn

__all__ = ["get_conn"]
