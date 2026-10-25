"""Payments (PayGate Global) and paid plan expiry

Revision ID: 010
Revises: 009
Create Date: 2026-10-25 00:00:00.000000

payments: one row per checkout (mobile money through PayGate Global), keyed
by our own identifier, sent to PayGate and used to check the payment status.
api_keys.plan_expires_at: end of a paid plan; past it the key counts as
"free" (api.app.core.auth), with no job to run. NULL for plans set by hand.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "010"
down_revision: str | Sequence[str] | None = "009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TABLE api_keys ADD COLUMN IF NOT EXISTS plan_expires_at TIMESTAMP")
    op.execute("""
        CREATE TABLE IF NOT EXISTS payments (
            id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            identifier        VARCHAR(40) NOT NULL UNIQUE,
            api_key_id        UUID NOT NULL REFERENCES api_keys(id) ON DELETE CASCADE,
            plan              VARCHAR(20) NOT NULL,
            months            INTEGER NOT NULL CHECK (months BETWEEN 1 AND 12),
            amount            INTEGER NOT NULL,
            network           VARCHAR(10) NOT NULL,
            status            VARCHAR(12) NOT NULL DEFAULT 'pending' CHECK (
                status IN ('pending', 'paid', 'expired', 'cancelled', 'failed')
            ),
            tx_reference      VARCHAR(64),
            payment_reference VARCHAR(64),
            payment_method    VARCHAR(20),
            created_at        TIMESTAMP NOT NULL DEFAULT NOW(),
            paid_at           TIMESTAMP
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS payments_api_key_idx ON payments (api_key_id)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS payments")
    op.execute("ALTER TABLE api_keys DROP COLUMN IF EXISTS plan_expires_at")
