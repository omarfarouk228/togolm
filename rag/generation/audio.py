"""
Speech-to-text for voice questions, including Éwé and Kabiyè.

Browsers' built-in dictation (Web Speech API) has no Éwé or Kabiyè model, so
the chat sends the recording here instead and Gemini, which understands
audio, transcribes it. The transcription is returned in the language spoken
(standard orthography) together with a French translation.
"""

import base64
import json
import os

from rag.generation.llm import _fallback_model_name, _primary_model_name

LANGUAGE_NAMES = {
    "fr": "français",
    "en": "anglais",
    "ee": "éwé (Èʋegbe)",
    "kbp": "kabiyè (Kabɩyɛ)",
}

ORTHOGRAPHY_HINTS = {
    "ee": "Si la personne parle éwé, utilise l'orthographe standard (ɖ, ɛ, ƒ, ɣ, ŋ, ɔ, ʋ).",
    "kbp": "Si la personne parle kabiyè, utilise l'orthographe standard (ɖ, ɛ, ɩ, ŋ, ɔ, ʊ).",
}

PROMPT = (
    "Transcris fidèlement cet enregistrement d'une question posée à TogoLM, un "
    "assistant sur le Togo. Écris EXACTEMENT ce que la personne dit, dans la "
    "langue qu'elle parle réellement : ne traduis jamais la transcription. "
    "La personne a choisi de parler en {language}, mais elle peut aussi parler "
    "français ou mélanger les deux (noms d'institutions, de lieux, sigles). "
    "{orthography} N'invente rien : si un passage est inaudible, écris [inaudible]. "
    "Réponds UNIQUEMENT avec un objet JSON de la forme "
    '{{"langue": "<code de la langue réellement parlée : fr, ee, kbp, en ou autre>", '
    '"transcription": "<texte exact dans la langue parlée>", '
    '"francais": "<traduction française fidèle>"}}.'
)


# A stalled call must not hold the request open forever.
TRANSCRIBE_TIMEOUT_MS = 30_000


class TranscriptionError(Exception):
    """Raised when no model could transcribe the recording."""


def transcribe_audio(mime_type: str, data_b64: str, language: str) -> dict:
    """Return {"text", "translation_fr", "spoken_language"} for the recording."""
    from google import genai
    from google.genai import types

    client = genai.Client(
        api_key=os.environ["GEMINI_API_KEY"],
        http_options=types.HttpOptions(timeout=TRANSCRIBE_TIMEOUT_MS),
    )
    prompt = PROMPT.format(
        language=LANGUAGE_NAMES.get(language, "français"),
        orthography=ORTHOGRAPHY_HINTS.get(language, ""),
    )
    contents = [
        types.Part.from_bytes(data=base64.b64decode(data_b64), mime_type=mime_type),
        prompt,
    ]
    config = types.GenerateContentConfig(
        response_mime_type="application/json",
        temperature=0,
        max_output_tokens=1024,
        thinking_config=types.ThinkingConfig(thinking_budget=0),
    )

    last_error: Exception | None = None
    models = [_primary_model_name()]
    if _fallback_model_name() not in models:
        models.append(_fallback_model_name())
    for model in models:
        try:
            response = client.models.generate_content(model=model, contents=contents, config=config)
            return parse_transcription(response.text or "")
        except Exception as e:  # try the fallback model
            last_error = e
    raise TranscriptionError(str(last_error))


def parse_transcription(raw: str) -> dict:
    """Parse the model's JSON answer; tolerate code fences or plain text."""
    text = raw.strip()
    if text.startswith("```"):
        text = text.strip("`").removeprefix("json").strip()
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return {"text": text, "translation_fr": "", "spoken_language": ""}
    if not isinstance(payload, dict):
        return {"text": str(payload), "translation_fr": "", "spoken_language": ""}
    return {
        "text": str(payload.get("transcription", "")).strip(),
        "translation_fr": str(payload.get("francais", "")).strip(),
        "spoken_language": str(payload.get("langue", "")).strip().lower(),
    }
