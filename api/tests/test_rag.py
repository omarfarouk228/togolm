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
    def test_empty_chunks_calls_gemini_for_general_knowledge(self, monkeypatch):
        monkeypatch.setenv("GEMINI_API_KEY", "AQ.fake-key-for-test")
        with patch(
            "rag.generation.chains._generate_answer", return_value="Lomé est la capitale du Togo."
        ) as mock_gemini:
            answer = build_answer("Quelle est la capitale du Togo ?", [])
        mock_gemini.assert_called_once()
        assert "Lomé" in answer

    def test_empty_chunks_no_gemini_returns_no_result_message(self, monkeypatch):
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        answer = build_answer("Quelle est la capitale du Togo ?", [])
        assert "pertinents" in answer

    def test_extractive_fallback_when_no_gemini_key(self, monkeypatch):
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        chunk = make_chunk(content="Lomé est la capitale du Togo.")
        answer = build_answer("Quelle est la capitale ?", [chunk])
        assert "Lomé" in answer

    def test_extractive_fallback_returns_content(self, monkeypatch):
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        chunk = make_chunk(content="Contenu de test pour le corpus togolais.")
        answer = build_answer("question ?", [chunk])
        assert "Contenu de test" in answer

    def test_long_content_is_truncated(self, monkeypatch, fake_chunk_long):
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        answer = build_answer("question ?", [fake_chunk_long])
        assert len(answer) < 1000
        assert "…" in answer

    def test_short_content_not_truncated(self, monkeypatch):
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        short = "Court texte."
        chunk = make_chunk(content=short)
        answer = build_answer("question ?", [chunk])
        assert short in answer
        assert "…" not in answer

    def test_gemini_called_when_key_present(self, monkeypatch):
        monkeypatch.setenv("GEMINI_API_KEY", "AQ.fake-key-for-test")
        chunk = make_chunk()
        with patch(
            "rag.generation.chains._generate_answer", return_value="Réponse Gemini"
        ) as mock_gemini:
            answer = build_answer("question ?", [chunk])
        mock_gemini.assert_called_once()
        assert answer == "Réponse Gemini"

    def test_gemini_exception_falls_back_to_extractive(self, monkeypatch):
        monkeypatch.setenv("GEMINI_API_KEY", "AQ.fake-key-for-test")
        chunk = make_chunk(content="Texte de secours.")
        with patch(
            "rag.generation.chains._generate_answer",
            side_effect=Exception("API error"),
        ):
            answer = build_answer("question ?", [chunk])
        assert "Texte de secours" in answer


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
        row = ("Titre doc", "https://test.tg", "test.tg", "legal", "Contenu.", 0.9, "2026-01-01")
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
        # Score 0.1 is well below min_score=0.62 → filtered out
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
        row = ("Titre FT", "https://test.tg", "test.tg", "legal", "Contenu FT.", 0.5, "2026-01-01")
        mock_conn = self._mock_conn([row], chunk_count=0)

        with (
            patch("rag.retrieval.search.get_conn", return_value=mock_conn),
            patch("rag.retrieval.search._get_embedder") as mock_emb,
        ):
            mock_emb.return_value.encode_one.return_value = [0.1] * 384
            result = retrieve("question")

        assert len(result) == 1
        assert result[0].title == "Titre FT"

    def test_ordinary_question_keeps_one_chunk_per_document(self):
        # Same document URL twice — the second chunk must be dropped for a
        # plain fact question (source diversification stays the default).
        rows = [
            (
                "Article gouvernement",
                "https://presidence.tg/a",
                "presidence.tg",
                "politics",
                "Chunk 1.",
                0.9,
                "2026-01-01",
            ),
            (
                "Article gouvernement",
                "https://presidence.tg/a",
                "presidence.tg",
                "politics",
                "Chunk 2.",
                0.85,
                "2026-01-01",
            ),
        ]
        mock_conn = self._mock_conn(rows, chunk_count=2)

        with (
            patch("rag.retrieval.search.get_conn", return_value=mock_conn),
            patch("rag.retrieval.search._get_embedder") as mock_emb,
        ):
            mock_emb.return_value.encode_one.return_value = [0.1] * 384
            result = retrieve("Qui dirige ce ministère ?", top_k=5)

        assert len(result) == 1

    def test_enumeration_question_keeps_multiple_chunks_from_same_document(self):
        # A "liste des ministres"-style query needs several chunks of the one
        # authoritative document (the roster is split across small chunks).
        rows = [
            (
                "Composition du gouvernement",
                "https://presidence.tg/gouvernement",
                "presidence.tg",
                "politics",
                f"Chunk {i}.",
                0.9 - i * 0.01,
                "2026-01-01",
            )
            for i in range(4)
        ]
        mock_conn = self._mock_conn(rows, chunk_count=len(rows))

        with (
            patch("rag.retrieval.search.get_conn", return_value=mock_conn),
            patch("rag.retrieval.search._get_embedder") as mock_emb,
        ):
            mock_emb.return_value.encode_one.return_value = [0.1] * 384
            result = retrieve("liste des ministres du gouvernement togolais", top_k=9)

        assert len(result) == 4

    def test_identity_query_prepends_office_title_boost(self):
        # "qui est l'actuel président de la République ?" — regression found
        # live 2026-07-20: the correct officeholder article ranked hundreds of
        # positions below generic commentary on pure embedding similarity.
        # The office-title boost query must run first (most recent title
        # match), then the ordinary vector search fills the rest, excluding
        # whatever the boost already surfaced.
        boost_row = (
            "Le Président de la République honore les citoyens les plus méritants",
            "https://presidence.gouv.tg/a",
            "presidence.gouv.tg",
            "politics",
            "Le Président de la République, Jean-Lucien Savi de Tové, a décerné...",
            "2026-04-29",
            0.77,
        )
        fill_row = (
            "Faure Gnassingbé",
            "https://fr.wikipedia.org/wiki/Faure_Gnassingbe",
            "fr.wikipedia.org",
            "politics",
            "Faure Gnassingbé est...",
            0.85,
            None,
        )

        mock_cur = MagicMock()
        mock_cur.__enter__ = lambda s: s
        mock_cur.__exit__ = MagicMock(return_value=False)
        mock_cur.fetchone.return_value = (1,)
        mock_cur.fetchall.side_effect = [[boost_row], [fill_row]]
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cur
        mock_conn.__enter__ = lambda s: s
        mock_conn.__exit__ = MagicMock(return_value=False)

        with (
            patch("rag.retrieval.search.get_conn", return_value=mock_conn),
            patch("rag.retrieval.search._get_embedder") as mock_emb,
        ):
            mock_emb.return_value.encode_one.return_value = [0.1] * 384
            result = retrieve("qui est l'actuel président de la République ?", top_k=5)

        assert len(result) == 2
        assert (
            result[0].title
            == "Le Président de la République honore les citoyens les plus méritants"
        )
        assert result[0].published_at == "2026-04-29"
        assert result[1].title == "Faure Gnassingbé"

    def test_non_identity_query_skips_office_title_boost(self):
        # No known office named in the question — must fall straight through
        # to the ordinary vector search with a single execute() call.
        row = ("Titre doc", "https://test.tg", "test.tg", "legal", "Contenu.", 0.9, None)
        mock_conn = self._mock_conn([row], chunk_count=1)

        with (
            patch("rag.retrieval.search.get_conn", return_value=mock_conn),
            patch("rag.retrieval.search._get_embedder") as mock_emb,
        ):
            mock_emb.return_value.encode_one.return_value = [0.1] * 384
            result = retrieve("quel est le budget de l'Etat togolais ?", top_k=5)

        assert len(result) == 1
        assert result[0].title == "Titre doc"
