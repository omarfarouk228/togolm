"""
Unit tests for rag.generation.llm — the Gemini chat model factory.

No real API calls: ChatGoogleGenerativeAI accepts any string as an API key at
construction time (it's only validated on the first real request), so these
tests just inspect the constructed Runnable's configuration.
"""

from langchain_core.runnables.fallbacks import RunnableWithFallbacks
from langchain_google_genai import ChatGoogleGenerativeAI

from rag.generation.llm import (
    DEFAULT_FALLBACK_MODEL,
    DEFAULT_MODEL,
    get_chat_model,
    get_chat_model_with_fallback,
    has_distinct_fallback_model,
)


class TestGetChatModel:
    def test_defaults_to_default_model(self, monkeypatch):
        monkeypatch.setenv("GEMINI_API_KEY", "AQ.fake-key")
        monkeypatch.delenv("GEMINI_MODEL", raising=False)
        model = get_chat_model(max_output_tokens=100)
        assert model.model == DEFAULT_MODEL

    def test_reads_model_from_env(self, monkeypatch):
        monkeypatch.setenv("GEMINI_API_KEY", "AQ.fake-key")
        monkeypatch.setenv("GEMINI_MODEL", "gemini-2.0-flash")
        model = get_chat_model(max_output_tokens=100)
        assert model.model == "gemini-2.0-flash"

    def test_use_fallback_model_defaults_to_default_fallback(self, monkeypatch):
        monkeypatch.setenv("GEMINI_API_KEY", "AQ.fake-key")
        monkeypatch.delenv("GEMINI_FALLBACK_MODEL", raising=False)
        model = get_chat_model(max_output_tokens=100, use_fallback_model=True)
        assert model.model == DEFAULT_FALLBACK_MODEL

    def test_use_fallback_model_reads_env(self, monkeypatch):
        monkeypatch.setenv("GEMINI_API_KEY", "AQ.fake-key")
        monkeypatch.setenv("GEMINI_FALLBACK_MODEL", "gemini-3-pro-preview")
        model = get_chat_model(max_output_tokens=100, use_fallback_model=True)
        assert model.model == "gemini-3-pro-preview"

    def test_thinking_disabled_by_default(self, monkeypatch):
        # Regression: Gemini 2.5 defaults to *dynamic* (unbounded) thinking when
        # thinking_budget is left unset, not thinking=off. Left unset, thinking
        # tokens draw from the same max_output_tokens ceiling as the visible
        # answer and can silently truncate it for context-heavy requests. Every
        # answer-generation call site in this codebase relies on the default
        # (none pass thinking_budget), so the factory must send 0 explicitly.
        monkeypatch.setenv("GEMINI_API_KEY", "AQ.fake-key")
        model = get_chat_model(max_output_tokens=100)
        assert model.thinking_budget == 0

    def test_thinking_enabled_when_budget_requested(self, monkeypatch):
        monkeypatch.setenv("GEMINI_API_KEY", "AQ.fake-key")
        model = get_chat_model(max_output_tokens=100, thinking_budget=500)
        assert model.thinking_budget == 500
        assert model.include_thoughts is True


class TestHasDistinctFallbackModel:
    def test_true_by_default(self, monkeypatch):
        monkeypatch.delenv("GEMINI_MODEL", raising=False)
        monkeypatch.delenv("GEMINI_FALLBACK_MODEL", raising=False)
        assert has_distinct_fallback_model() is True

    def test_false_when_explicitly_equal(self, monkeypatch):
        monkeypatch.setenv("GEMINI_MODEL", "gemini-2.0-flash")
        monkeypatch.setenv("GEMINI_FALLBACK_MODEL", "gemini-2.0-flash")
        assert has_distinct_fallback_model() is False


class TestGetChatModelWithFallback:
    def test_wraps_primary_and_fallback_models(self, monkeypatch):
        monkeypatch.setenv("GEMINI_API_KEY", "AQ.fake-key")
        monkeypatch.delenv("GEMINI_MODEL", raising=False)
        monkeypatch.delenv("GEMINI_FALLBACK_MODEL", raising=False)
        runnable = get_chat_model_with_fallback(max_output_tokens=100)
        assert isinstance(runnable, RunnableWithFallbacks)
        assert runnable.runnable.model == DEFAULT_MODEL
        assert [f.model for f in runnable.fallbacks] == [DEFAULT_FALLBACK_MODEL]

    def test_skips_fallback_wrapping_when_models_identical(self, monkeypatch):
        monkeypatch.setenv("GEMINI_API_KEY", "AQ.fake-key")
        monkeypatch.setenv("GEMINI_MODEL", "gemini-2.0-flash")
        monkeypatch.setenv("GEMINI_FALLBACK_MODEL", "gemini-2.0-flash")
        model = get_chat_model_with_fallback(max_output_tokens=100)
        assert isinstance(model, ChatGoogleGenerativeAI)
        assert not isinstance(model, RunnableWithFallbacks)
