"""Give the Journal officiel special issues a real title

Revision ID: 006
Revises: 005
Create Date: 2026-10-10 00:00:00.000000

Special issues of the Journal officiel were stored under the title
"NUMERO SPECIAL" (the first line of the PDF), which says nothing about them
in the sources shown to users. Rename them from their header, e.g.
"Journal officiel de la République togolaise n° 13 bis (numéro spécial) du
02 mars 2026". New ones get the same title at ingest
(rag.indexation.titles).
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "006"
down_revision: str | Sequence[str] | None = "005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    from rag.indexation.titles import journal_officiel_title

    conn = op.get_bind()
    rows = conn.execute(
        sa.text(
            "SELECT id, left(clean_content, 600) FROM documents "
            "WHERE lower(trim(title)) IN ('numero special', 'numéro spécial')"
        )
    ).fetchall()
    for doc_id, head in rows:
        title = journal_officiel_title(head or "")
        if title:
            conn.execute(
                sa.text("UPDATE documents SET title = :title WHERE id = :id"),
                {"title": title, "id": doc_id},
            )


def downgrade() -> None:
    op.execute(
        "UPDATE documents SET title = 'NUMERO SPECIAL' "
        "WHERE title LIKE 'Journal officiel de la République togolaise n° % (numéro spécial) du %'"
    )
