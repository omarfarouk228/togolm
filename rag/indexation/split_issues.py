"""
Turn Journal officiel issues stored as one document into one document per act.

Runs on issues already in the database (rag.indexation.journal_officiel does
the splitting): each act is upserted as its own document (url = issue url +
"#<act>"), chunked like any ingested document and left for
rag.indexation.backfill to embed. The issue itself gets status 'split', which
takes it out of retrieval (only 'active' documents are searched) while
keeping it for reference. Re-running is safe: acts are matched by url and
re-chunked only when their text changed.
"""

import json

from db import get_conn
from rag.indexation.chunker import chunk_by_words
from rag.indexation.ingestor import (
    CHUNK_OVERLAP,
    CHUNK_SIZE,
    fetch_existing_document,
    upsert_chunks,
    upsert_document,
)
from rag.indexation.journal_officiel import act_url, split_acts

# An issue is worth splitting when it is long and carries the Journal
# officiel masthead; ordinary jo.gouv.tg pages already hold a single act.
MIN_ISSUE_CHARS = 20_000

_CANDIDATES_SQL = """
    SELECT id, url, title, source, clean_content
    FROM documents
    WHERE status = 'active'
      AND length(clean_content) > %s
      AND left(clean_content, 2000) ILIKE '%%JOURNAL OFFICIEL DE LA REPUBLIQUE TOGOLAISE%%'
"""


def split_issue(cur, issue_id, issue_url: str, issue_title: str, source: str, content: str) -> int:
    """Upsert the acts of one issue; return how many were found (0 = untouched)."""
    acts = split_acts(content)
    if not acts:
        return 0
    for act in acts:
        url = act_url(issue_url, act)
        existing = fetch_existing_document(cur, url)
        doc_id = upsert_document(
            cur,
            {
                "source": source,
                "url": url,
                "category": "legal",
                "subcategory": act.kind.lower(),
                "title": act.title,
                "raw_content": act.text,
                "clean_content": act.text,
                "language": "fr",
                "published_at": act.date,
                "metadata": {
                    "journal_officiel": issue_title,
                    "journal_officiel_url": issue_url,
                    "act_kind": act.kind,
                    "act_number": act.number,
                },
            },
        )
        if existing is None or existing[1] != act.text:
            texts = [c.text for c in chunk_by_words(act.text, doc_id, CHUNK_SIZE, CHUNK_OVERLAP)]
            upsert_chunks(cur, doc_id, texts, [None] * len(texts))  # backfill embeds them
    cur.execute(
        "UPDATE documents SET status = 'split', metadata = coalesce(metadata, '{}'::jsonb) || %s "
        "WHERE id = %s",
        (json.dumps({"split_into_acts": len(acts)}), issue_id),
    )
    return len(acts)


def split_pending_issues() -> dict:
    """Split every active Journal officiel issue still stored as one document."""
    conn = get_conn()
    issues, acts = 0, 0
    try:
        with conn.cursor() as cur:
            cur.execute(_CANDIDATES_SQL, (MIN_ISSUE_CHARS,))
            candidates = cur.fetchall()
        for issue_id, url, title, source, content in candidates:
            with conn.cursor() as cur:
                found = split_issue(cur, issue_id, url, title or "", source, content or "")
            conn.commit()  # one issue per transaction
            if found:
                issues += 1
                acts += found
    finally:
        conn.close()
    return {"candidates": len(candidates), "issues_split": issues, "acts": acts}
