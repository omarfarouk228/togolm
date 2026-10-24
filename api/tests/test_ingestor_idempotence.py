"""
Unit tests for the ingestor's unchanged-content skip.

Without this, `ingest_datasets` deletes and rebuilds every chunk (wiping
embeddings) on every run regardless of whether the source content changed —
combined with the pipeline's timeouts, a run interrupted mid-way permanently
loses embeddings that already existed. These tests lock the two building
blocks that make re-ingestion skip untouched, already-indexed documents.
"""

from unittest.mock import MagicMock

from rag.indexation.ingestor import fetch_existing_document, needs_reindex


class TestFetchExistingDocument:
    def test_returns_none_for_empty_url(self):
        assert fetch_existing_document(MagicMock(), "") is None

    def test_returns_id_and_content_when_found(self):
        cur = MagicMock()
        cur.fetchone.return_value = ("doc-1", "contenu existant")
        assert fetch_existing_document(cur, "https://test.tg/a") == ("doc-1", "contenu existant")

    def test_returns_none_when_not_found(self):
        cur = MagicMock()
        cur.fetchone.return_value = None
        assert fetch_existing_document(cur, "https://test.tg/a") is None


class TestNeedsReindex:
    def test_true_when_no_chunks_exist(self):
        cur = MagicMock()
        cur.fetchone.return_value = (0,)
        assert needs_reindex(cur, "doc-1", embed=True) is True

    def test_false_when_embed_disabled_and_chunks_already_exist(self):
        # --no-embed runs only care whether text rows exist, not embeddings.
        cur = MagicMock()
        cur.fetchone.return_value = (5,)
        assert needs_reindex(cur, "doc-1", embed=False) is False

    def test_true_when_some_chunks_missing_embedding(self):
        cur = MagicMock()
        cur.fetchone.side_effect = [(5,), (2,)]  # total, then missing-embedding count
        assert needs_reindex(cur, "doc-1", embed=True) is True

    def test_false_when_all_chunks_already_embedded(self):
        cur = MagicMock()
        cur.fetchone.side_effect = [(5,), (0,)]
        assert needs_reindex(cur, "doc-1", embed=True) is False


def test_reingest_fills_a_missing_date_and_never_erases_one():
    import uuid

    from db import get_conn
    from rag.indexation.ingestor import upsert_document

    url = f"https://example.tg/article-{uuid.uuid4()}"
    doc = {"source": "example.tg", "url": url, "title": "Article de test", "category": "press"}
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            upsert_document(cur, {**doc, "raw_content": "v1", "clean_content": "v1"})
            upsert_document(
                cur,
                {
                    **doc,
                    "raw_content": "v2",
                    "clean_content": "v2",
                    "published_at": "23 octobre 2026",
                },
            )
            upsert_document(cur, {**doc, "raw_content": "v3", "clean_content": "v3"})
            cur.execute("SELECT published_at::text FROM documents WHERE url = %s", (url,))
            assert cur.fetchone()[0] == "2026-10-23"
            cur.execute("DELETE FROM documents WHERE url = %s", (url,))
        conn.commit()
    finally:
        conn.close()
