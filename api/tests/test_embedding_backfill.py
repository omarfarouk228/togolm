"""
Tests for the embedding backlog (rag.indexation.backfill) and the ingest-side
guarantee it relies on: vectors from different embedding models must never be
mixed silently.
"""

import subprocess
from unittest.mock import MagicMock, patch

import numpy as np

from rag.indexation import backfill
from rag.indexation.embedder import GEMINI_MODEL_ID, LOCAL_MODEL_ID


def _unit(v):
    v = np.asarray(v, dtype=float)
    return v / np.linalg.norm(v)


class TestClassifyLegacy:
    def test_vector_matching_fresh_local_embedding_is_local(self):
        local = _unit([1.0, 0.0, 0.0])
        other = _unit([0.0, 1.0, 0.0])
        fake_local = MagicMock()
        fake_local.encode.return_value = [local, local]
        with patch.object(backfill, "_local_embedder", return_value=fake_local):
            labels = backfill.classify_legacy([local * 3, other], ["a", "b"])
        assert labels == [LOCAL_MODEL_ID, GEMINI_MODEL_ID]

    def test_accepts_pgvector_objects(self):
        local = _unit([1.0, 0.0])
        stored = MagicMock()
        stored.to_list.return_value = list(local)
        fake_local = MagicMock()
        fake_local.encode.return_value = [local]
        with patch.object(backfill, "_local_embedder", return_value=fake_local):
            assert backfill.classify_legacy([stored], ["a"]) == [LOCAL_MODEL_ID]


class TestProcessBatch:
    def test_legacy_rows_from_canonical_model_are_only_tagged(self):
        canonical = MagicMock(model_id=GEMINI_MODEL_ID)
        rows = [("c1", "texte 1", [0.1]), ("c2", "texte 2", [0.2])]
        with (
            patch.object(
                backfill, "classify_legacy", return_value=[GEMINI_MODEL_ID, LOCAL_MODEL_ID]
            ),
            patch.object(backfill, "execute_batch") as eb,
        ):
            canonical.encode.return_value = [[0.5, 0.5]]
            result = backfill._process_batch(MagicMock(), rows, "legacy", canonical)

        assert result == {"embedded": 1, "tagged": 1}
        canonical.encode.assert_called_once_with(["texte 2"])
        tag_call, embed_call = eb.call_args_list
        assert tag_call.args[2] == [(GEMINI_MODEL_ID, "c1")]
        assert embed_call.args[2][0][1:] == (GEMINI_MODEL_ID, "c2")

    def test_missing_rows_are_embedded_with_canonical_model(self):
        canonical = MagicMock(model_id=GEMINI_MODEL_ID)
        canonical.encode.return_value = [[0.1], [0.2]]
        rows = [("c1", "a", None), ("c2", "b", None)]
        with patch.object(backfill, "execute_batch") as eb:
            result = backfill._process_batch(MagicMock(), rows, "missing", canonical)
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
