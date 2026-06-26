"""
LangChain chat model factory for the query feature.

Centralizes the Gemini key check and the ChatGoogleGenerativeAI configuration so
every generation path shares one place to tune the model, token budgets, and
thinking behaviour.
"""

import os

from langchain_google_genai import ChatGoogleGenerativeAI

DEFAULT_MODEL = "gemini-2.5-flash"


def gemini_available() -> bool:
    """Return True when a usable Gemini API key is configured."""
    key = os.getenv("GEMINI_API_KEY", "").strip()
    return len(key) > 10


def get_chat_model(
    *,
    max_output_tokens: int,
    thinking_budget: int = 0,
    streaming: bool = False,
) -> ChatGoogleGenerativeAI:
    """Build a configured Gemini chat model.

    When thinking_budget > 0 the model emits reasoning tokens, surfaced by
    LangChain as ``thinking`` content blocks so callers can stream them apart
    from the answer.
    """
    return ChatGoogleGenerativeAI(
        model=DEFAULT_MODEL,
        google_api_key=os.environ["GEMINI_API_KEY"],
        max_output_tokens=max_output_tokens,
        thinking_budget=thinking_budget,
        include_thoughts=thinking_budget > 0,
        streaming=streaming,
    )
