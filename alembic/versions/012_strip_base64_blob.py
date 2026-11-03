"""Strip the inline base64 image stored in one edusup.gouv.tg article

Revision ID: 012
Revises: 011
Create Date: 2026-11-03 00:00:00.000000

One article (edusup.gouv.tg, "Réunion annuelle et 10ème forum de dialogue
politique...") was ingested with a 1.95 M-character base64 image in its text,
before clean_document stripped such blobs. Its chunk blocked the embedding
backlog (tokens-per-minute quota) and would have sent ~2 MB of base64 to the
model if ever retrieved. A scan in prod on 2026-11-03 found this single chunk
and document, so they are targeted by id: a full-table regex scan took ~40 s,
too long for a migration run at API start-up.

The chunk's embedding is cleared so the backfill re-embeds the cleaned text.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "012"
down_revision: str | Sequence[str] | None = "011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_CHUNK_ID = "ead20ff2-d468-4a85-a6ba-e67c6c161292"
_BLOB = r"[A-Za-z0-9+/]{200,}={0,2}"


def upgrade() -> None:
    # No-op on databases that don't hold this chunk (dev, CI).
    op.execute(f"""
        UPDATE documents
        SET clean_content = regexp_replace(clean_content, '{_BLOB}', ' ', 'g'),
            raw_content = regexp_replace(raw_content, '{_BLOB}', ' ', 'g')
        WHERE id = (SELECT document_id FROM chunks WHERE id = '{_CHUNK_ID}')
    """)
    op.execute(f"""
        UPDATE chunks
        SET content = regexp_replace(content, '{_BLOB}', ' ', 'g'),
            embedding = NULL,
            embedding_model = NULL
        WHERE id = '{_CHUNK_ID}'
    """)


def downgrade() -> None:
    # The stripped base64 is not restored: it was never readable text.
    pass
