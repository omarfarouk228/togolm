"""Log the API key id with each question

Revision ID: 009
Revises: 008
Create Date: 2026-10-25 00:00:00.000000

user_queries.api_key_prefix keeps the first 8 characters of a key: "tgolm_"
and 2 random ones, shared by several of the 137 keys of 2026-10. Per-key
usage history (GET /v1/auth/usage) needs the key itself.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "009"
down_revision: str | Sequence[str] | None = "008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TABLE user_queries ADD COLUMN IF NOT EXISTS api_key_id UUID")
    op.execute(
        "CREATE INDEX IF NOT EXISTS user_queries_api_key_id_idx "
        "ON user_queries (api_key_id, created_at)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS user_queries_api_key_id_idx")
    op.execute("ALTER TABLE user_queries DROP COLUMN IF EXISTS api_key_id")
