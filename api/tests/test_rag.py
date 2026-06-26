"""
Unit tests for api.app.services.rag

All DB and embedder calls are mocked — no real PostgreSQL needed.
"""

from unittest.mock import MagicMock, patch

from rag.generation import build_answer
from rag.retrieval import RetrievedChunk, retrieve

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_chunk(**kwargs) -> RetrievedChunk:
    defaults = dict(
        title="Test doc",
        url="https://example.tg/doc",
        source="test.tg",
        category="legal",
        content="Contenu de test pour le corpus togolais.",
        score=0.85,
    )
    return RetrievedChunk(**(defaults | kwargs))


# ---------------------------------------------------------------------------
# build_answer — pure logic, no DB
# ---------------------------------------------------------------------------


class TestBuildAnswer:
    def test_empty_chunks_returns_no_result_message(self):
        answer, used_corpus = build_answer("Quelle est la capitale du Togo ?", [])
        assert "pertinents" in answer
        assert used_corpus is False

    def test_extractive_fallback_when_no_gemini_key(self, monkeypatch):
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        chunk = make_chunk(content="Lomé est la capitale du Togo.")
        answer, used_corpus = build_answer("Quelle est la capitale ?", [chunk])
        assert "Lomé" in answer
        assert used_corpus is True

    def test_extractive_fallback_returns_content(self, monkeypatch):
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        chunk = make_chunk(content="Contenu de test pour le corpus togolais.")
        answer, used_corpus = build_answer("question ?", [chunk])
        assert "Contenu de test" in answer
        assert used_corpus is True

    def test_long_content_is_truncated(self, monkeypatch, fake_chunk_long):
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        answer, used_corpus = build_answer("question ?", [fake_chunk_long])
        assert len(answer) < 1000
        assert "…" in answer

    def test_short_content_not_truncated(self, monkeypatch):
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        short = "Court texte."
        chunk = make_chunk(content=short)
        answer, _ = build_answer("question ?", [chunk])
        assert short in answer
        assert "…" not in answer

    def test_gemini_called_when_key_present(self, monkeypatch):
        monkeypatch.setenv("GEMINI_API_KEY", "AQ.fake-key-for-test")
        chunk = make_chunk()
        with patch(
            "rag.generation.chains._generate_answer", return_value="Réponse Gemini"
        ) as mock_gemini:
            answer, used_corpus = build_answer("question ?", [chunk])
        mock_gemini.assert_called_once()
        assert answer == "Réponse Gemini"
        assert used_corpus is True

    def test_gemini_exception_falls_back_to_extractive(self, monkeypatch):
        monkeypatch.setenv("GEMINI_API_KEY", "AQ.fake-key-for-test")
        chunk = make_chunk(content="Texte de secours.")
        with patch(
            "rag.generation.chains._generate_answer",
            side_effect=Exception("API error"),
        ):
            answer, used_corpus = build_answer("question ?", [chunk])
        assert "Texte de secours" in answer
        assert used_corpus is True


# ---------------------------------------------------------------------------
# retrieve — mocked DB + embedder
# ---------------------------------------------------------------------------


class TestRetrieve:
    def _mock_conn(self, rows: list, chunk_count: int = 1):
        """Build a mock psycopg2 connection that returns given rows."""
        mock_cur = MagicMock()
        mock_cur.__enter__ = lambda s: s
        mock_cur.__exit__ = MagicMock(return_value=False)
        # First fetchone → chunk count
        mock_cur.fetchone.return_value = (chunk_count,)
        mock_cur.fetchall.return_value = rows
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cur
        mock_conn.__enter__ = lambda s: s
        mock_conn.__exit__ = MagicMock(return_value=False)
        return mock_conn

    def test_returns_retrieved_chunks(self):
        row = ("Titre doc", "https://test.tg", "test.tg", "legal", "Contenu.", 0.9)
        mock_conn = self._mock_conn([row], chunk_count=1)

        with (
            patch("rag.retrieval.search.get_conn", return_value=mock_conn),
            patch("rag.retrieval.search._get_embedder") as mock_emb,
        ):
            mock_emb.return_value.encode_one.return_value = [0.1] * 384
            result = retrieve("question de test", top_k=1)

        assert len(result) == 1
        assert result[0].title == "Titre doc"
        assert result[0].score == 0.9

    def test_filters_low_score_chunks(self):
        # Score below min_score=0.3 → filtered out
        row = ("Titre", "https://test.tg", "test.tg", "legal", "Contenu.", 0.1)
        mock_conn = self._mock_conn([row], chunk_count=1)

        with (
            patch("rag.retrieval.search.get_conn", return_value=mock_conn),
            patch("rag.retrieval.search._get_embedder") as mock_emb,
        ):
            mock_emb.return_value.encode_one.return_value = [0.1] * 384
            result = retrieve("question", top_k=5)

        assert result == []

    def test_falls_back_to_fulltext_when_no_chunks(self):
        row = ("Titre FT", "https://test.tg", "test.tg", "legal", "Contenu FT.", 0.5)
        mock_conn = self._mock_conn([row], chunk_count=0)

        with (
            patch("rag.retrieval.search.get_conn", return_value=mock_conn),
            patch("rag.retrieval.search._get_embedder") as mock_emb,
        ):
            mock_emb.return_value.encode_one.return_value = [0.1] * 384
            result = retrieve("question")

        assert len(result) == 1
        assert result[0].title == "Titre FT"
