"""Tag each chunk vector with the model that produced it

Revision ID: 003
Revises: 002
Create Date: 2026-10-09 00:00:00.000000

Queries are embedded with one model, but past ingest runs silently fell back
to a different local model whenever the Gemini quota ran out, so the chunks
table mixes vectors from two incompatible spaces. embedding_model records
which model produced each vector (NULL = written before this column existed;
rag.indexation.backfill classifies and fixes those).
"""

from collections.abc import Sequence

from alembic import op

revision: str = "003"
down_revision: str | Sequence[str] | None = "002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TABLE chunks ADD COLUMN IF NOT EXISTS embedding_model VARCHAR(64)")
    # Backlog lookups (missing or untagged vectors) stay cheap as the table grows.
    op.execute("""
        CREATE INDEX IF NOT EXISTS chunks_embedding_pending_idx
            ON chunks (document_id) WHERE embedding_model IS NULL
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS chunks_embedding_pending_idx")
    op.execute("ALTER TABLE chunks DROP COLUMN IF EXISTS embedding_model")
