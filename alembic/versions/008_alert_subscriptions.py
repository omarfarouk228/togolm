"""Alert subscriptions (procurement and news watch)

Revision ID: 008
Revises: 007
Create Date: 2026-10-25 00:00:00.000000

A subscription is a search (words, optional category) and where to send the
new documents matching it, once a day: an e-mail address (double opt-in:
confirmed through a link before anything else is sent) or a Telegram /
WhatsApp chat (the chat is the confirmation).
"""

from collections.abc import Sequence

from alembic import op

revision: str = "008"
down_revision: str | Sequence[str] | None = "007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS alert_subscriptions (
            id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            channel       VARCHAR(20) NOT NULL
                          CHECK (channel IN ('email', 'telegram', 'whatsapp')),
            target        VARCHAR(320) NOT NULL,
            query         VARCHAR(200) NOT NULL,
            category      VARCHAR(50),
            token         VARCHAR(64) NOT NULL UNIQUE,
            confirmed     BOOLEAN NOT NULL DEFAULT FALSE,
            active        BOOLEAN NOT NULL DEFAULT TRUE,
            created_at    TIMESTAMP NOT NULL DEFAULT NOW(),
            last_sent_at  TIMESTAMP
        )
    """)
    op.execute(
        "CREATE INDEX IF NOT EXISTS alert_subscriptions_target_idx "
        "ON alert_subscriptions (channel, target)"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS alert_subscriptions")
