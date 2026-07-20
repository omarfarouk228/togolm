"""
LangChain chat model factory for the query feature.

Centralizes the Gemini key check and the ChatGoogleGenerativeAI configuration so
every generation path shares one place to tune the model, token budgets, and
thinking behaviour.
"""

import os

from langchain_core.runnables import Runnable
from langchain_google_genai import ChatGoogleGenerativeAI

DEFAULT_MODEL = "gemini-2.5-flash"
DEFAULT_FALLBACK_MODEL = "gemini-3-flash-preview"


def gemini_available() -> bool:
    """Return True when a usable Gemini API key is configured."""
    key = os.getenv("GEMINI_API_KEY", "").strip()
    return len(key) > 10


def _primary_model_name() -> str:
    return os.getenv("GEMINI_MODEL", "").strip() or DEFAULT_MODEL


def _fallback_model_name() -> str:
    return os.getenv("GEMINI_FALLBACK_MODEL", "").strip() or DEFAULT_FALLBACK_MODEL


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
        # Gemini 2.5 models default to *dynamic* thinking (an unbounded, variable
        # reasoning budget) when thinking_budget is left unset — it isn't the same
        # as "off". Passing 0 explicitly is required to disable it. Without this,
        # thinking tokens are drawn from the same max_output_tokens ceiling as the
        # visible answer, so a request with a lot of context (e.g. an enumeration
        # question retrieving several chunks) can spend most/all of its budget
        # thinking and cut the visible answer off mid-sentence.
        "thinking_budget": thinking_budget,
    }
    if thinking_budget > 0:
        kwargs["include_thoughts"] = True
    return ChatGoogleGenerativeAI(**kwargs)


def get_chat_model_with_fallback(
    *,
    max_output_tokens: int,
    thinking_budget: int = 0,
    streaming: bool = False,
) -> Runnable:
    """Build the Gemini chat model most call sites should use.

    Tries GEMINI_MODEL (default gemini-2.5-flash) first; if it raises for any
    reason (quota exhausted, model unavailable, transient API error, etc.),
    LangChain's Runnable.with_fallbacks retries once against
    GEMINI_FALLBACK_MODEL (default gemini-3-flash-preview) with the same
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
