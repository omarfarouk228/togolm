"""Native-speaker reviews of answers in Éwé and Kabiyè

Revision ID: 005
Revises: 004
Create Date: 2026-10-10 00:00:00.000000

language_review_items: answers TogoLM gave in a national language, queued
for review (seeded sets, and real chat answers captured automatically).
language_reviews: one native speaker's verdict on an item (rating, optional
corrected wording). Approved corrections are fed back into generation as
examples of validated wording (rag.generation.language_examples).
"""

from collections.abc import Sequence

from alembic import op

revision: str = "005"
down_revision: str | Sequence[str] | None = "004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS language_review_items (
            id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            language    VARCHAR(10) NOT NULL CHECK (language IN ('ee', 'kbp')),
            question    TEXT NOT NULL,
            question_fr TEXT,
            answer      TEXT NOT NULL,
            answer_fr   TEXT,
            origin      VARCHAR(10) NOT NULL DEFAULT 'seed' CHECK (origin IN ('seed', 'live')),
            active      BOOLEAN NOT NULL DEFAULT TRUE,
            created_at  TIMESTAMP NOT NULL DEFAULT NOW()
        )
    """)
    op.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS language_review_items_dedup_idx
            ON language_review_items (language, md5(question || '|' || answer))
    """)
    op.execute("""
        CREATE TABLE IF NOT EXISTS language_reviews (
            id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            item_id         UUID NOT NULL REFERENCES language_review_items(id) ON DELETE CASCADE,
            rating          VARCHAR(10) NOT NULL CHECK (rating IN ('good', 'fix', 'bad')),
            correction      TEXT,
            comment         TEXT,
            reviewer_name   VARCHAR(100),
            reviewer_region VARCHAR(100),
            status          VARCHAR(20) NOT NULL DEFAULT 'pending'
                            CHECK (status IN ('pending', 'approved', 'rejected')),
            created_at      TIMESTAMP NOT NULL DEFAULT NOW(),
            reviewed_at     TIMESTAMP
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS language_reviews_item_idx ON language_reviews (item_id)")
    op.execute("""
        CREATE INDEX IF NOT EXISTS language_reviews_status_idx
            ON language_reviews (status, created_at DESC)
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS language_reviews")
    op.execute("DROP TABLE IF EXISTS language_review_items")
