"""Voice questions: /v1/transcribe (Éwé and Kabiyè included)."""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from api.app.features.query.schemas import AudioAttachment, TranscribeRequest
from rag.generation.audio import PROMPT, parse_transcription

AUDIO = {"mime_type": "audio/webm;codecs=opus", "data": "AAAA"}


def test_mime_type_is_reduced_to_its_base_type():
    assert AudioAttachment(**AUDIO).mime_type == "audio/webm"


def test_unsupported_audio_type_is_rejected():
    with pytest.raises(ValidationError):
        AudioAttachment(mime_type="video/mp4", data="AAAA")


def test_language_is_normalized():
    assert TranscribeRequest(audio=AUDIO, language="EE").language == "ee"
    assert TranscribeRequest(audio=AUDIO, language="xx").language == "fr"


def test_prompt_forbids_translating_the_transcription():
    # Regression: with "probably Éwé" in the prompt, French speech came back
    # translated into Éwé instead of transcribed.
    assert "ne traduis jamais la transcription" in PROMPT


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (
            '{"langue": "EE", "transcription": "Aleke ma wɔ?", "francais": "Comment faire ?"}',
            {"text": "Aleke ma wɔ?", "translation_fr": "Comment faire ?", "spoken_language": "ee"},
        ),
        (
            '```json\n{"langue": "fr", "transcription": "Bonjour", "francais": "Bonjour"}\n```',
            {"text": "Bonjour", "translation_fr": "Bonjour", "spoken_language": "fr"},
        ),
        ("pas du JSON", {"text": "pas du JSON", "translation_fr": "", "spoken_language": ""}),
    ],
)
def test_parse_transcription(raw, expected):
    assert parse_transcription(raw) == expected


def test_transcribe_endpoint(client: TestClient):
    from api.app.features.query import router as query_router

    result = {"text": "Aleke ma wɔ?", "translation_fr": "Comment faire ?", "spoken_language": "ee"}
    with (
        patch.object(query_router, "gemini_available", return_value=True),
        patch.object(query_router, "transcribe_audio", return_value=result) as t,
    ):
        resp = client.post("/v1/transcribe", json={"audio": AUDIO, "language": "ee"})

    assert resp.status_code == 200
    assert resp.json() == {
        "text": "Aleke ma wɔ?",
        "translation_fr": "Comment faire ?",
        "language": "ee",
        "spoken_language": "ee",
    }
    t.assert_called_once_with("audio/webm", "AAAA", "ee")


def test_empty_transcription_is_a_422(client: TestClient):
    from api.app.features.query import router as query_router

    empty = {"text": "", "translation_fr": "", "spoken_language": ""}
    with (
        patch.object(query_router, "gemini_available", return_value=True),
        patch.object(query_router, "transcribe_audio", return_value=empty),
    ):
        resp = client.post("/v1/transcribe", json={"audio": AUDIO, "language": "ee"})
    assert resp.status_code == 422
