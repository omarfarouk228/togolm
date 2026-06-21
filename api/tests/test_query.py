"""
Unit tests for the /query and /query/stream endpoints.

DB and Gemini calls are mocked — no external services needed.
Rate limiting is bypassed via dependency_overrides so the shared CI Redis
quota (20 anon req/day) is not exhausted by these integration tests.
Rate limiting behaviour is covered separately in test_rate_limit.py.
"""

import json
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from api.app.core.rate_limit import check_rate_limit
from api.app.features.query.service import RetrievedChunk
from api.app.main import app

client = TestClient(app)


@pytest.fixture(scope="module", autouse=True)
def disable_rate_limit():
    app.dependency_overrides[check_rate_limit] = lambda: None
    yield
    app.dependency_overrides.pop(check_rate_limit, None)


FAKE_CHUNK = RetrievedChunk(
    title="Constitution du Togo",
    url="https://assemblee-nationale.tg/constitution",
    source="assemblee-nationale.tg",
    category="legal",
    content="Le Togo est une République. Le Chef de l'État est le Président.",
    score=0.91,
)


# ---------------------------------------------------------------------------
# POST /v1/query
# ---------------------------------------------------------------------------


class TestQueryEndpoint:
    def test_returns_expected_shape(self):
        with (
            patch("api.app.features.query.router.retrieve", return_value=[FAKE_CHUNK]),
            patch(
                "api.app.features.query.service._generate_with_gemini",
                return_value=("Réponse test", True),
            ),
        ):
            resp = client.post("/v1/query", json={"question": "Quel est le régime du Togo ?"})
        assert resp.status_code == 200
        data = resp.json()
        assert "answer" in data
        assert "sources" in data
        assert "model" in data
        assert "latency_ms" in data
        assert isinstance(data["latency_ms"], int)

    def test_sources_include_title_url_score(self):
        with (
            patch("api.app.features.query.router.retrieve", return_value=[FAKE_CHUNK]),
            patch(
                "api.app.features.query.service._generate_with_gemini",
                return_value=("OK", True),
            ),
        ):
            resp = client.post("/v1/query", json={"question": "Régime politique du Togo ?"})
        sources = resp.json()["sources"]
        assert len(sources) == 1
        assert sources[0]["title"] == FAKE_CHUNK.title
        assert sources[0]["url"] == FAKE_CHUNK.url
        assert 0 <= sources[0]["score"] <= 1

    def test_empty_corpus_returns_answer(self):
        with patch("api.app.features.query.router.retrieve", return_value=[]):
            resp = client.post("/v1/query", json={"question": "Question sans résultat ?"})
        assert resp.status_code == 200
        assert resp.json()["sources"] == []

    def test_question_too_short_rejected(self):
        resp = client.post("/v1/query", json={"question": "ab"})
        assert resp.status_code == 422

    def test_question_too_long_rejected(self):
        resp = client.post("/v1/query", json={"question": "x" * 4001})
        assert resp.status_code == 422

    def test_retrieval_error_returns_500(self):
        with patch("api.app.features.query.router.retrieve", side_effect=Exception("DB error")):
            resp = client.post("/v1/query", json={"question": "Question valide ?"})
        assert resp.status_code == 500


# ---------------------------------------------------------------------------
# POST /v1/query/stream (SSE)
# ---------------------------------------------------------------------------


def _parse_sse(text: str) -> list[dict]:
    """Parse SSE response body into a list of event data dicts."""
    events = []
    for line in text.splitlines():
        if line.startswith("data: ") and line != "data: [DONE]":
            events.append(json.loads(line[6:]))
    return events


class TestStreamEndpoint:
    def test_response_is_event_stream(self):
        with (
            patch("api.app.features.query.router.retrieve", return_value=[FAKE_CHUNK]),
            patch("api.app.features.query.router._stream_gemini", return_value=iter([])),
        ):
            resp = client.post("/v1/query/stream", json={"question": "Question stream ?"})
        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers["content-type"]

    def test_stream_ends_with_done(self):
        with (
            patch("api.app.features.query.router.retrieve", return_value=[FAKE_CHUNK]),
            patch("api.app.features.query.router._stream_gemini", return_value=iter([])),
        ):
            resp = client.post("/v1/query/stream", json={"question": "Question stream ?"})
        assert "data: [DONE]" in resp.text

    def test_stream_includes_sources_event(self):
        with (
            patch("api.app.features.query.router.retrieve", return_value=[FAKE_CHUNK]),
            patch("api.app.features.query.router._stream_gemini", return_value=iter([])),
        ):
            resp = client.post("/v1/query/stream", json={"question": "Question stream ?"})
        events = _parse_sse(resp.text)
        sources_events = [e for e in events if e.get("type") == "sources"]
        assert len(sources_events) == 1
        assert "latency_ms" in sources_events[0]

    def test_stream_uses_gemini_when_key_set(self, monkeypatch):
        monkeypatch.setenv("GEMINI_API_KEY", "AQ.fake-key")
        gemini_event = f"data: {json.dumps({'type': 'chunk', 'text': 'Réponse Gemini'})}\n\n"
        with (
            patch("api.app.features.query.router.retrieve", return_value=[FAKE_CHUNK]),
            patch(
                "api.app.features.query.router._stream_gemini", return_value=iter([gemini_event])
            ) as mock_g,
        ):
            resp = client.post("/v1/query/stream", json={"question": "Question Gemini ?"})
        mock_g.assert_called_once()
        # SSE body is JSON — accented chars are unicode-escaped
        assert "R\\u00e9ponse Gemini" in resp.text or "Réponse Gemini" in resp.text

    def test_stream_extractive_fallback_when_no_key(self, monkeypatch):
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        with patch("api.app.features.query.router.retrieve", return_value=[FAKE_CHUNK]):
            resp = client.post("/v1/query/stream", json={"question": "Question extractive ?"})
        events = _parse_sse(resp.text)
        chunk_events = [e for e in events if e.get("type") == "chunk"]
        assert len(chunk_events) >= 1
        # Extractive mode includes source attribution
        combined = " ".join(e["text"] for e in chunk_events)
        assert "assemblee-nationale.tg" in combined

    def test_stream_no_results_message(self, monkeypatch):
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        with patch("api.app.features.query.router.retrieve", return_value=[]):
            resp = client.post("/v1/query/stream", json={"question": "Question sans résultat ?"})
        events = _parse_sse(resp.text)
        chunk_events = [e for e in events if e.get("type") == "chunk"]
        assert len(chunk_events) == 1
        assert "trouvé de documents pertinents" in chunk_events[0]["text"]

    def test_stream_retrieval_error_yields_error_event(self):
        with patch("api.app.features.query.router.retrieve", side_effect=Exception("DB down")):
            resp = client.post("/v1/query/stream", json={"question": "Question erreur ?"})
        events = _parse_sse(resp.text)
        error_events = [e for e in events if e.get("type") == "error"]
        assert len(error_events) == 1
        assert "DB down" in error_events[0]["message"]


# ---------------------------------------------------------------------------
# Off-topic detection (_is_off_topic unit tests)
# ---------------------------------------------------------------------------

from api.app.features.query.router import _contains_code, _is_off_topic  # noqa: E402


class TestOffTopicDetection:
    # ── should be flagged as off-topic ──────────────────────────────────────

    def test_greeting_fr(self):
        assert _is_off_topic("Bonjour !")

    def test_greeting_en(self):
        assert _is_off_topic("Hello")

    def test_math_expression(self):
        assert _is_off_topic("3 + 4 * 2")

    def test_too_short(self):
        assert _is_off_topic("ok merci")

    def test_code_review_fr(self):
        assert _is_off_topic("que penses-tu de ce code ? def foo(): pass")

    def test_code_review_with_pasted_env_file(self):
        env_block = (
            "que penses-tu de ce code ?\n"
            "SECRET_KEY=change_me\n"
            "POSTGRES_USER=postgres\n"
            "POSTGRES_DB=karaba\n"
            "SMTP_HOST=mail.example.com\n"
        )
        assert _is_off_topic(env_block)

    def test_code_review_analyse(self):
        assert _is_off_topic("Analyse ce code s'il te plaît : def hello(): print('hi')")

    def test_code_review_debug(self):
        assert _is_off_topic("Debug ce script et dis-moi ce qui ne va pas")

    def test_code_fence_in_message(self):
        assert _is_off_topic("que penses-tu de ```python\nprint('hello')\n```")

    def test_env_file_structural_detection(self):
        env = "SECRET_KEY=abc\nPOSTGRES_USER=pg\nSTRIPE_SECRET_KEY=sk_test\nSMTP_HOST=mail.x.com"
        assert _contains_code(env)

    def test_python_syntax_structural_detection(self):
        code = "from fastapi import APIRouter\nasync def handler():\n    pass"
        assert _contains_code(code)

    def test_recipe_fr(self):
        assert _is_off_topic("Donne-moi une recette de poulet yassa")

    def test_cooking_fr(self):
        assert _is_off_topic("Comment cuisiner du riz avec des légumes ?")

    def test_creative_writing_poem(self):
        assert _is_off_topic("Écris-moi un poème sur la nature")

    def test_creative_writing_story(self):
        assert _is_off_topic("Écris une histoire courte pour enfants")

    def test_sports_score(self):
        assert _is_off_topic("Quel est le score du match PSG-OM ?")

    def test_programming_help(self):
        assert _is_off_topic("Comment programmer une API REST en Python ?")

    # ── should NOT be flagged (valid Togo questions) ─────────────────────────

    def test_togo_constitution(self):
        assert not _is_off_topic("Quel est le régime politique du Togo ?")

    def test_code_du_travail_togo(self):
        # "code" appears but in a Togo-legal context — must not be blocked
        assert not _is_off_topic("Que dit le code du travail togolais sur les congés payés ?")

    def test_togo_economy(self):
        assert not _is_off_topic("Comment fonctionne le port autonome de Lomé ?")

    def test_togo_education(self):
        assert not _is_off_topic("Quels sont les diplômes reconnus par l'État togolais ?")

    def test_togo_mobile_money(self):
        assert not _is_off_topic("Comment utiliser Flooz pour les paiements au Togo ?")

    def test_togo_agriculture(self):
        assert not _is_off_topic("Quelles sont les principales cultures vivrières au Togo ?")

    def test_togo_history(self):
        assert not _is_off_topic("Quand le Togo a-t-il obtenu son indépendance ?")
