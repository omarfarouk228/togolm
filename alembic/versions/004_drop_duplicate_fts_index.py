"""Drop the duplicate GIN index on documents.fts_vector

Revision ID: 004
Revises: 003
Create Date: 2026-10-09 00:00:00.000000

Prod has two identical GIN indexes on documents.fts_vector:
documents_fts_idx (created by 001) and documents_fts_gin_idx (created by hand).
Full-text search is now part of every query (hybrid retrieval), and every
document write pays for both. Keep the one the migrations own.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "004"
down_revision: str | Sequence[str] | None = "003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE INDEX IF NOT EXISTS documents_fts_idx ON documents USING gin (fts_vector)")
    op.execute("DROP INDEX IF EXISTS documents_fts_gin_idx")


def downgrade() -> None:
    pass  # the dropped index was an exact duplicate; nothing to restore
