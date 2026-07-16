"""Add response_feedback table

Revision ID: 002
Revises: 001
Create Date: 2026-07-16 00:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

revision: str = "002"
down_revision: str | Sequence[str] | None = "001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS response_feedback (
            id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            category       VARCHAR(30) NOT NULL
                           CHECK (category IN ('incorrect', 'broken_source', 'harmful', 'other')),
            comment        TEXT,
            question       TEXT NOT NULL,
            answer         TEXT NOT NULL,
            sources        JSONB,
            language       VARCHAR(10) DEFAULT 'fr',
            api_key_prefix VARCHAR(20),
            status         VARCHAR(20) NOT NULL DEFAULT 'open'
                           CHECK (status IN ('open', 'reviewed', 'dismissed')),
            created_at     TIMESTAMP DEFAULT NOW()
        )
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS response_feedback_created_at_idx
            ON response_feedback (created_at DESC)
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS response_feedback_status_idx
            ON response_feedback (status)
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS response_feedback CASCADE")
