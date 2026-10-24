"""Remove the CI seed document from real corpora

Revision ID: 007
Revises: 006
Create Date: 2026-10-24 00:00:00.000000

Migration 001 inserted a test row ("Loi de finances 2025", url
https://jo.gouv.tg/test-loi-finances-2025) into every database it ran on,
production included. Its single sentence, a made-up 2025 State budget, could be
retrieved and cited to users as an official Journal officiel source. CI now
loads it from api/tests/fixtures/seed.sql after migrating.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "007"
down_revision: str | Sequence[str] | None = "006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SEED_ID = "00000000-0000-0000-0000-000000000001"


def upgrade() -> None:
    op.execute(f"DELETE FROM chunks WHERE document_id = '{SEED_ID}'")
    op.execute(f"DELETE FROM documents WHERE id = '{SEED_ID}'")


def downgrade() -> None:
    # The row was test data; there is nothing worth restoring.
    pass
