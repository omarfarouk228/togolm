"""Answer language: French, English and Togo's national languages (Éwé, Kabiyè)."""

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from api.app.features.query.schemas import QueryRequest
from rag.generation import chains
from rag.generation.prompts import RAG_ANSWER_PROMPT, language_instruction


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("fr", "fr"), ("FR-tg", "fr"), ("en_US", "en"), ("ee", "ee"), ("kbp", "kbp"), ("es", "fr")],
)
def test_language_is_normalized(raw, expected):
    assert QueryRequest(question="Question test", language=raw).language == expected


def test_french_needs_no_instruction_and_local_languages_get_one():
    assert language_instruction("fr") == ""
    assert "éwé" in language_instruction("ee")
    assert "kabiyè" in language_instruction("kbp")


def test_answer_prompt_carries_the_language_instruction():
    messages = RAG_ANSWER_PROMPT.format_messages(
        context="ctx", question="q", history=[], language_instruction=language_instruction("ee")
    )
    assert "éwé" in messages[-1].content


class TestQuestionForPipeline:
    def test_french_and_english_questions_are_not_translated(self):
        with patch.object(chains, "get_chat_model_with_fallback") as model:
            assert chains.question_for_pipeline("Qui est le ministre ?", "fr") == (
                "Qui est le ministre ?"
            )
            assert chains.question_for_pipeline("Who is the minister?", "en") == (
                "Who is the minister?"
            )
        model.assert_not_called()

    def test_failure_keeps_the_original_question(self):
        failing = MagicMock(side_effect=RuntimeError("down"))
        with (
            patch.object(chains, "gemini_available", return_value=True),
            patch.object(chains, "get_chat_model_with_fallback", return_value=failing),
        ):
            assert chains.question_for_pipeline("Aleke ma wɔ?", "ee") == "Aleke ma wɔ?"


def test_stream_endpoint_answers_in_requested_language(client: TestClient):
    from api.app.features.query import router as query_router

    captured = {}

    def fake_stream(question, chunks, history, max_output_tokens=2048, language="fr"):
        captured["question"] = question
        captured["language"] = language
        yield ("chunk", "Ŋkɔ")

    with (
        patch.object(query_router.generation, "question_for_pipeline", return_value="Qui ?"),
        patch.object(query_router, "is_trivially_off_topic", return_value=False),
        patch.object(query_router.generation, "route_query", return_value="on_topic"),
        patch.object(query_router.retrieval, "retrieve", return_value=[]),
        patch.object(query_router, "gemini_available", return_value=True),
        patch.object(query_router.generation, "stream_answer", side_effect=fake_stream),
        patch.object(query_router, "log_query"),
    ):
        resp = client.post("/v1/query/stream", json={"question": "Ameka?", "language": "ee"})

    assert resp.status_code == 200
    assert captured == {"question": "Qui ?", "language": "ee"}
