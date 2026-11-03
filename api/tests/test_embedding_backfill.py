"""
Tests for the embedding backlog (rag.indexation.backfill) and the ingest-side
guarantee it relies on: vectors from different embedding models must never be
mixed silently.
"""

import subprocess
from unittest.mock import MagicMock, patch

from rag.indexation import backfill
from rag.indexation.embedder import GEMINI_MODEL_ID


class TestProcessBatch:
    def test_legacy_rows_are_re_embedded_without_the_local_model(self):
        """Legacy vectors are re-embedded with the canonical model, never
        classified with the local model (that loaded torch into the worker)."""
        canonical = MagicMock(model_id=GEMINI_MODEL_ID)
        canonical.encode.return_value = [[0.5], [0.6]]
        rows = [("c1", "texte 1", [0.1]), ("c2", "texte 2", [0.2])]
        with patch.object(backfill, "execute_batch") as eb:
            result = backfill._process_batch(MagicMock(), rows, canonical)
        assert result == {"embedded": 2, "tagged": 0}
        canonical.encode.assert_called_once_with(["texte 1", "texte 2"])
        assert [r[1:] for r in eb.call_args.args[2]] == [
            (GEMINI_MODEL_ID, "c1"),
            (GEMINI_MODEL_ID, "c2"),
        ]
        assert not hasattr(backfill, "_local_embedder")

    def test_missing_rows_are_embedded_with_canonical_model(self):
        canonical = MagicMock(model_id=GEMINI_MODEL_ID)
        canonical.encode.return_value = [[0.1], [0.2]]
        rows = [("c1", "a", None), ("c2", "b", None)]
        with patch.object(backfill, "execute_batch") as eb:
            result = backfill._process_batch(MagicMock(), rows, canonical)
        assert result == {"embedded": 2, "tagged": 0}
        assert [r[2] for r in eb.call_args.args[2]] == ["c1", "c2"]


class TestEmbedPending:
    def _conn(self, batches):
        cur = MagicMock()
        cur.__enter__ = lambda s: s
        cur.__exit__ = MagicMock(return_value=False)
        cur.fetchall.side_effect = batches
        conn = MagicMock()
        conn.cursor.return_value = cur
        return conn

    def test_embedding_error_stops_run_and_rolls_back(self):
        canonical = MagicMock(model_id=GEMINI_MODEL_ID)
        canonical.encode.side_effect = RuntimeError("429 RESOURCE_EXHAUSTED")
        conn = self._conn([[("c1", "a", None)]])
        with (
            patch.object(backfill, "_canonical_embedder", return_value=canonical),
            patch.object(backfill, "get_conn", return_value=conn),
        ):
            result = backfill.embed_pending(max_chunks=10)
        assert result["stopped"].startswith("embedding error")
        conn.rollback.assert_called_once()
        conn.close.assert_called_once()

    def test_stops_when_backlog_is_empty(self):
        canonical = MagicMock(model_id=GEMINI_MODEL_ID)
        conn = self._conn([[], [], []])
        with (
            patch.object(backfill, "_canonical_embedder", return_value=canonical),
            patch.object(backfill, "get_conn", return_value=conn),
        ):
            result = backfill.embed_pending(max_chunks=10)
        assert result["stopped"] == "done"
        assert result["embedded"] == 0


class TestIngestNoSilentModelFallback:
    def test_embed_batch_returns_none_instead_of_switching_models(self):
        from rag.indexation import ingestor

        failing = MagicMock(model_id=GEMINI_MODEL_ID)
        failing.encode.side_effect = RuntimeError("429 RESOURCE_EXHAUSTED")
        with (
            patch.object(ingestor, "_embedder", failing),
            patch.object(ingestor.time, "sleep"),
        ):
            vectors, model_id = ingestor.embed_batch(["a"])
        assert vectors is None
        assert model_id == GEMINI_MODEL_ID


class TestRunSpiderTimeout:
    def test_timeout_returns_serializable_result(self, tmp_path):
        from corpus import tasks

        with (
            patch.object(tasks, "DATASETS_DIR", tmp_path),
            patch.object(
                tasks.subprocess, "run", side_effect=subprocess.TimeoutExpired("scrapy", 1)
            ),
        ):
            result = tasks.run_spider.run("togofirst")
        assert result == {
            "spider": "togofirst",
            "success": False,
            "timed_out": True,
            "output_kb": 0,
        }


class TestProjectOnPath:
    def test_root_is_added_back_after_celery_removed_it(self, monkeypatch):
        # celery -A only keeps the project root on sys.path while loading the
        # app; embed_pending_chunks must restore it before importing rag.
        import sys

        from corpus import tasks

        monkeypatch.setattr(sys, "path", [p for p in sys.path if p != str(tasks.ROOT)])
        tasks._ensure_project_on_path()
        assert sys.path[0] == str(tasks.ROOT)


def test_gemini_embedder_sets_a_request_timeout(monkeypatch):
    from unittest.mock import patch as _patch

    from rag.indexation import embedder

    monkeypatch.setenv("GEMINI_API_KEY", "test-key-123456")
    with _patch("google.genai.Client") as client:
        embedder.GeminiEmbedder()
    options = client.call_args.kwargs["http_options"]
    assert options.timeout == embedder.EMBED_TIMEOUT_MS


def test_gemini_embedder_caps_each_input(monkeypatch):
    """One oversized text must not exceed the tokens-per-minute quota alone."""
    from rag.indexation import embedder

    monkeypatch.setenv("GEMINI_API_KEY", "fake")
    gem = embedder.GeminiEmbedder.__new__(embedder.GeminiEmbedder)
    gem._client = MagicMock()
    gem._types = MagicMock()
    gem._client.models.embed_content.return_value = MagicMock(
        embeddings=[MagicMock(values=[0.1]), MagicMock(values=[0.2])]
    )
    gem.encode(["court", "x" * 2_000_000])
    sent = gem._client.models.embed_content.call_args.kwargs["contents"]
    assert sent[0] == "court"
    assert len(sent[1]) == embedder.MAX_EMBED_CHARS


def test_clean_document_drops_inline_base64_images():
    from rag.indexation.cleaner import clean_document

    blob = "iVBORw0KGgoAAAANSUhEUgAA" * 5_000
    raw = f"Réunion annuelle à Lomé. <img src=data:image/png;base64,{blob}> Fin du texte."
    cleaned = clean_document(raw + " Autre bloc " + "QUJD" * 100)
    assert "Réunion annuelle à Lomé." in cleaned
    assert "Fin du texte." in cleaned
    assert "base64" not in cleaned
    assert len(cleaned) < 200
