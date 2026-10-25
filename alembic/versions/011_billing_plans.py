"""Paid plan prices, edited from the admin

Revision ID: 011
Revises: 010
Create Date: 2026-10-25 00:00:00.000000

Prices are a business decision that changes without a release: they live
here, edited on the admin's Billing page (PUT /v1/admin/billing/plans), not
in an environment variable. Seeded inactive and unpriced: nothing is for sale
until a price is set and the plan switched on.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "011"
down_revision: str | Sequence[str] | None = "010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS billing_plans (
            plan          VARCHAR(20) PRIMARY KEY,
            label         VARCHAR(60) NOT NULL,
            monthly_fcfa  INTEGER CHECK (monthly_fcfa IS NULL OR monthly_fcfa > 0),
            active        BOOLEAN NOT NULL DEFAULT FALSE,
            updated_at    TIMESTAMP NOT NULL DEFAULT NOW()
        )
    """)
    op.execute("""
        INSERT INTO billing_plans (plan, label) VALUES
            ('dev', 'Développeur'), ('institution', 'Institution')
        ON CONFLICT DO NOTHING
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS billing_plans")
