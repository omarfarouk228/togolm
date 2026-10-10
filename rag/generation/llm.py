"""
LangChain chat model factory for the query feature.

Centralizes the Gemini key check and the ChatGoogleGenerativeAI configuration so
every generation path shares one place to tune the model, token budgets, and
thinking behaviour.
"""

import logging
import os

from langchain_core.runnables import Runnable
from langchain_google_genai import ChatGoogleGenerativeAI

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "gemini-3.8-flash"
DEFAULT_FALLBACK_MODEL = "gemini-3.5-flash"

# Models Google no longer serves to this project's API key, mapped to their
# replacement, so a stale GEMINI_MODEL in the deployment environment can't
# take generation down. On 2026-10-10 every answer fell back to raw extracts:
# "gemini-2.5-flash is no longer available to new users" (404).
RETIRED_MODELS = {
    "gemini-2.5-flash": "gemini-3.8-flash",
}


def gemini_available() -> bool:
    """Return True when a usable Gemini API key is configured."""
    key = os.getenv("GEMINI_API_KEY", "").strip()
    return len(key) > 10


def _resolve(name: str) -> str:
    replacement = RETIRED_MODELS.get(name)
    if replacement:
        logger.warning("Gemini model %s is retired, using %s instead", name, replacement)
        return replacement
    return name


def _primary_model_name() -> str:
    return _resolve(os.getenv("GEMINI_MODEL", "").strip() or DEFAULT_MODEL)


def _fallback_model_name() -> str:
    return _resolve(os.getenv("GEMINI_FALLBACK_MODEL", "").strip() or DEFAULT_FALLBACK_MODEL)


def thinking_settings(model_name: str, thinking_budget: int = 0) -> dict:
    """Thinking parameters for ChatGoogleGenerativeAI, per model generation.

    Gemini 2.x takes a token budget, where 0 means off (left unset it thinks
    dynamically and can eat the visible answer's token budget). Gemini 3.x
    takes a level instead and can't fully turn thinking off: "minimal" is the
    closest, "low" when the caller wants reasoning streamed.
    """
    if model_name.startswith("gemini-2"):
        settings: dict = {"thinking_budget": thinking_budget}
        if thinking_budget > 0:
            settings["include_thoughts"] = True
        return settings
    if thinking_budget > 0:
        return {"thinking_config": {"thinking_level": "LOW", "include_thoughts": True}}
    return {"thinking_config": {"thinking_level": "MINIMAL"}}


def has_distinct_fallback_model() -> bool:
    """True when the configured fallback model differs from the primary one.

    Callers that can't use get_chat_model_with_fallback directly (e.g. because
    they need with_structured_output, unavailable on the wrapped Runnable) use
    this to decide whether building a second model + .with_fallbacks() is
    worthwhile, rather than retrying against an identical model.
    """
    return _fallback_model_name() != _primary_model_name()


def get_chat_model(
    *,
    max_output_tokens: int,
    thinking_budget: int = 0,
    streaming: bool = False,
    use_fallback_model: bool = False,
) -> ChatGoogleGenerativeAI:
    """Build a single configured Gemini chat model (no automatic fallback).

    The model name is read from GEMINI_MODEL (or GEMINI_FALLBACK_MODEL when
    use_fallback_model=True) on every call — not frozen at import time — so
    ops can swap either via the environment without a redeploy, and tests can
    monkeypatch per-case. Most callers should use get_chat_model_with_fallback
    instead; this one exists for call sites that need chat-model-specific
    methods (e.g. with_structured_output) and build their own fallback chain
    manually (see route_query).

    When thinking_budget > 0 the model emits reasoning tokens, surfaced by
    LangChain as ``thinking`` content blocks so callers can stream them apart
    from the answer.
    """
    model_name = _fallback_model_name() if use_fallback_model else _primary_model_name()
    kwargs: dict = {
        "model": model_name,
        "google_api_key": os.environ["GEMINI_API_KEY"],
        "max_output_tokens": max_output_tokens,
        "streaming": streaming,
        # Thinking left on draws from the same max_output_tokens ceiling as the
        # visible answer and can cut it off mid-sentence on context-heavy
        # requests, so it is kept off (2.x) or minimal (3.x) by default.
        **thinking_settings(model_name, thinking_budget),
    }
    return ChatGoogleGenerativeAI(**kwargs)


def get_chat_model_with_fallback(
    *,
    max_output_tokens: int,
    thinking_budget: int = 0,
    streaming: bool = False,
) -> Runnable:
    """Build the Gemini chat model most call sites should use.

    Tries GEMINI_MODEL (default gemini-3.8-flash) first; if it raises for any
    reason (quota exhausted, model unavailable, transient API error, etc.),
    LangChain's Runnable.with_fallbacks retries once against
    GEMINI_FALLBACK_MODEL (default gemini-3.5-flash) with the same
    generation params. Note: for streaming, the fallback only kicks in if the
    failure happens before any token has been yielded — a mid-stream failure
    can't be safely retried without duplicating output already sent.
    """
    primary = get_chat_model(
        max_output_tokens=max_output_tokens, thinking_budget=thinking_budget, streaming=streaming
    )
    if _fallback_model_name() == _primary_model_name():
        return primary
    fallback = get_chat_model(
        max_output_tokens=max_output_tokens,
        thinking_budget=thinking_budget,
        streaming=streaming,
        use_fallback_model=True,
    )
    return primary.with_fallbacks([fallback])
