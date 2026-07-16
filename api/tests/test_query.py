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
from api.app.main import app
from rag.retrieval import RetrievedChunk

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
            patch("rag.retrieval.retrieve", return_value=[FAKE_CHUNK]),
            patch("rag.generation.build_answer", return_value="Réponse test"),
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
            patch("rag.retrieval.retrieve", return_value=[FAKE_CHUNK]),
            patch("rag.generation.build_answer", return_value="OK"),
        ):
            resp = client.post("/v1/query", json={"question": "Régime politique du Togo ?"})
        sources = resp.json()["sources"]
        assert len(sources) == 1
        assert sources[0]["title"] == FAKE_CHUNK.title
        assert sources[0]["url"] == FAKE_CHUNK.url
        assert 0 <= sources[0]["score"] <= 1

    def test_query_is_enriched_before_retrieval(self):
        with (
            patch("rag.retrieval.retrieve", return_value=[FAKE_CHUNK]) as mock_r,
            patch("rag.generation.build_answer", return_value="OK"),
        ):
            resp = client.post("/v1/query", json={"question": "Quels impots OTR au Togo ?"})

        assert resp.status_code == 200
        kwargs = mock_r.call_args.kwargs
        assert "office togolais des recettes" in kwargs["question"]
        assert kwargs["category"] == "economy"

    def test_empty_corpus_returns_answer(self):
        with patch("rag.retrieval.retrieve", return_value=[]):
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
        with (
            patch("rag.generation.route_query", return_value="on_topic"),
            patch("rag.retrieval.retrieve", side_effect=Exception("DB error")),
        ):
            resp = client.post("/v1/query", json={"question": "Question valide ?"})
        assert resp.status_code == 500


FAKE_IMAGE = {"mime_type": "image/jpeg", "data": "ZmFrZS1pbWFnZS1ieXRlcw=="}


class TestImageQuery:
    """POST /v1/query with an attached image (vision-assisted RAG)."""

    def test_empty_question_allowed_with_image(self):
        with (
            patch("rag.generation.describe_image_question", return_value="requête dérivée"),
            patch("rag.retrieval.retrieve", return_value=[FAKE_CHUNK]),
            patch("rag.generation.build_answer_with_image", return_value="Réponse"),
        ):
            resp = client.post("/v1/query", json={"question": "", "image": FAKE_IMAGE})
        assert resp.status_code == 200

    def test_empty_question_rejected_without_image(self):
        resp = client.post("/v1/query", json={"question": ""})
        assert resp.status_code == 422

    def test_invalid_mime_type_rejected(self):
        resp = client.post(
            "/v1/query",
            json={
                "question": "Question valide ?",
                "image": {"mime_type": "image/gif", "data": "xx"},
            },
        )
        assert resp.status_code == 422

    def test_uses_corpus_when_retrieval_succeeds(self):
        with (
            patch(
                "rag.generation.describe_image_question", return_value="requête dérivée"
            ) as mock_d,
            patch("rag.retrieval.retrieve", return_value=[FAKE_CHUNK]),
            patch(
                "rag.generation.build_answer_with_image", return_value="Reponse RAG"
            ) as mock_build,
            patch("rag.generation.answer_from_image") as mock_vision,
        ):
            resp = client.post(
                "/v1/query", json={"question": "Que dit ce document ?", "image": FAKE_IMAGE}
            )
        assert resp.status_code == 200
        assert resp.json()["answer"] == "Reponse RAG"
        mock_d.assert_called_once()
        mock_build.assert_called_once()
        # The image must still reach the answer step even though corpus chunks
        # were found — a query derived from an unrelated image can coincidentally
        # match chunks, and only the image lets the model notice the mismatch.
        args, kwargs = mock_build.call_args
        assert FAKE_IMAGE["mime_type"] in args or FAKE_IMAGE["mime_type"] in kwargs.values()
        assert FAKE_IMAGE["data"] in args or FAKE_IMAGE["data"] in kwargs.values()
        mock_vision.assert_not_called()

    def test_falls_back_to_vision_when_corpus_empty(self):
        with (
            patch("rag.generation.describe_image_question", return_value="requête dérivée"),
            patch("rag.retrieval.retrieve", return_value=[]),
            patch("rag.generation.build_answer_with_image") as mock_build,
            patch("rag.generation.answer_from_image", return_value="Reponse vision") as mock_vision,
        ):
            resp = client.post(
                "/v1/query", json={"question": "Que dit ce document ?", "image": FAKE_IMAGE}
            )
        assert resp.status_code == 200
        assert resp.json()["answer"] == "Reponse vision"
        assert resp.json()["sources"] == []
        mock_vision.assert_called_once()
        mock_build.assert_not_called()


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
            patch("rag.retrieval.retrieve", return_value=[FAKE_CHUNK]),
            patch("rag.generation.stream_answer", return_value=iter([])),
        ):
            resp = client.post("/v1/query/stream", json={"question": "Question stream ?"})
        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers["content-type"]

    def test_stream_ends_with_done(self):
        with (
            patch("rag.retrieval.retrieve", return_value=[FAKE_CHUNK]),
            patch("rag.generation.stream_answer", return_value=iter([])),
        ):
            resp = client.post("/v1/query/stream", json={"question": "Question stream ?"})
        assert "data: [DONE]" in resp.text

    def test_stream_includes_sources_event(self):
        with (
            patch("rag.retrieval.retrieve", return_value=[FAKE_CHUNK]),
            patch("rag.generation.stream_answer", return_value=iter([])),
        ):
            resp = client.post("/v1/query/stream", json={"question": "Question stream ?"})
        events = _parse_sse(resp.text)
        sources_events = [e for e in events if e.get("type") == "sources"]
        assert len(sources_events) == 1
        assert "latency_ms" in sources_events[0]

    def test_stream_uses_gemini_when_key_set(self, monkeypatch):
        monkeypatch.setenv("GEMINI_API_KEY", "AQ.fake-key")
        with (
            patch("rag.generation.route_query", return_value="on_topic"),
            patch("rag.retrieval.retrieve", return_value=[FAKE_CHUNK]),
            patch(
                "rag.generation.stream_answer", return_value=iter([("chunk", "Réponse Gemini")])
            ) as mock_g,
        ):
            resp = client.post("/v1/query/stream", json={"question": "Question Gemini ?"})
        mock_g.assert_called_once()
        # SSE body is JSON — accented chars are unicode-escaped
        assert "R\\u00e9ponse Gemini" in resp.text or "Réponse Gemini" in resp.text

    def test_stream_extractive_fallback_when_no_key(self, monkeypatch):
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        with patch("rag.retrieval.retrieve", return_value=[FAKE_CHUNK]):
            resp = client.post("/v1/query/stream", json={"question": "Question extractive ?"})
        events = _parse_sse(resp.text)
        chunk_events = [e for e in events if e.get("type") == "chunk"]
        assert len(chunk_events) >= 1
        # Extractive mode includes source attribution
        combined = " ".join(e["text"] for e in chunk_events)
        assert "assemblee-nationale.tg" in combined

    def test_stream_no_results_message(self, monkeypatch):
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        with patch("rag.retrieval.retrieve", return_value=[]):
            resp = client.post("/v1/query/stream", json={"question": "Question sans résultat ?"})
        events = _parse_sse(resp.text)
        chunk_events = [e for e in events if e.get("type") == "chunk"]
        assert len(chunk_events) == 1
        assert "trouvé de documents pertinents" in chunk_events[0]["text"]

    def test_stream_retrieval_error_yields_error_event(self):
        with (
            patch("rag.generation.route_query", return_value="on_topic"),
            patch("rag.retrieval.retrieve", side_effect=Exception("DB down")),
        ):
            resp = client.post("/v1/query/stream", json={"question": "Question erreur ?"})
        events = _parse_sse(resp.text)
        error_events = [e for e in events if e.get("type") == "error"]
        assert len(error_events) == 1
        assert "DB down" in error_events[0]["message"]


class TestImageStreamQuery:
    """POST /v1/query/stream with an attached image bypasses the off-topic guard
    entirely and routes through the vision-assisted flow."""

    def test_uses_corpus_when_retrieval_succeeds(self, monkeypatch):
        monkeypatch.setenv("GEMINI_API_KEY", "AQ.fake-key")
        with (
            patch("rag.generation.describe_image_question", return_value="requête dérivée"),
            patch("rag.retrieval.retrieve", return_value=[FAKE_CHUNK]),
            patch(
                "rag.generation.stream_answer_with_image",
                return_value=iter([("chunk", "Reponse RAG")]),
            ) as mock_stream,
            patch("rag.generation.stream_answer_from_image") as mock_vision,
        ):
            resp = client.post(
                "/v1/query/stream", json={"question": "Que dit ce document ?", "image": FAKE_IMAGE}
            )
        assert "Reponse RAG" in resp.text
        mock_stream.assert_called_once()
        # The image must reach the streaming answer step too, for the same reason
        # as the non-streaming path (see build_answer_with_image).
        args, kwargs = mock_stream.call_args
        assert FAKE_IMAGE["mime_type"] in args or FAKE_IMAGE["mime_type"] in kwargs.values()
        mock_vision.assert_not_called()

    def test_falls_back_to_vision_when_corpus_empty(self, monkeypatch):
        monkeypatch.setenv("GEMINI_API_KEY", "AQ.fake-key")
        with (
            patch("rag.generation.describe_image_question", return_value="requête dérivée"),
            patch("rag.retrieval.retrieve", return_value=[]),
            patch(
                "rag.generation.stream_answer_from_image",
                return_value=iter([("chunk", "Reponse vision")]),
            ) as mock_vision,
        ):
            resp = client.post(
                "/v1/query/stream", json={"question": "Que dit ce document ?", "image": FAKE_IMAGE}
            )
        assert "Reponse vision" in resp.text
        mock_vision.assert_called_once()

    def test_skips_off_topic_guard(self, monkeypatch):
        # A trivially off-topic question (e.g. a greeting) still runs the vision
        # flow when an image is attached, instead of the canned redirect reply.
        monkeypatch.setenv("GEMINI_API_KEY", "AQ.fake-key")
        with (
            patch("rag.generation.describe_image_question", return_value="requête dérivée"),
            patch("rag.retrieval.retrieve", return_value=[FAKE_CHUNK]),
            patch(
                "rag.generation.stream_answer_with_image",
                return_value=iter([("chunk", "Reponse RAG")]),
            ),
            patch("rag.generation.stream_without_corpus") as mock_off_topic,
        ):
            resp = client.post("/v1/query/stream", json={"question": "salut", "image": FAKE_IMAGE})
        assert "Reponse RAG" in resp.text
        mock_off_topic.assert_not_called()


# ---------------------------------------------------------------------------
# Routing: deterministic micro-guard + agentic router fail-open
# ---------------------------------------------------------------------------

from rag.generation import route_query  # noqa: E402
from rag.orchestration.classification import is_trivially_off_topic  # noqa: E402


class TestTrivialGuard:
    """The micro-guard only catches obvious cases for free. Everything else is
    deferred to the LLM router (returns False here), whose decision quality is an
    eval concern, not a unit-test one."""

    # ── trivially off-topic (handled without any LLM call) ───────────────────

    def test_greeting_fr(self):
        assert is_trivially_off_topic("Bonjour !")

    def test_greeting_en(self):
        assert is_trivially_off_topic("Hello")

    def test_math_expression(self):
        assert is_trivially_off_topic("3 + 4 * 2")

    def test_too_short(self):
        assert is_trivially_off_topic("ok merci")

    # ── NOT trivial: deferred to the router, guard must not pre-judge ─────────

    def test_recipe_deferred_to_router(self):
        assert not is_trivially_off_topic("Donne-moi une recette de poulet yassa")

    def test_code_request_deferred_to_router(self):
        assert not is_trivially_off_topic("Écris une fonction Python qui trie une liste")

    def test_togo_question_not_trivial(self):
        assert not is_trivially_off_topic("Quel est le régime politique du Togo ?")

    def test_togo_legal_code_not_trivial(self):
        assert not is_trivially_off_topic("Que dit le code du travail togolais ?")


class TestRouterFailOpen:
    def test_returns_on_topic_without_gemini_key(self, monkeypatch):
        # No key → no LLM call → never wrongly redirect a real question.
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        assert route_query("Quel est le régime politique du Togo ?") == "on_topic"
