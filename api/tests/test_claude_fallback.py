"""Claude as the second LLM provider, behind Gemini."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from rag.generation import claude, llm
from rag.generation.chains import _iter_chunk_events


def test_messages_are_converted_for_the_messages_api():
    system, turns = claude.to_anthropic(
        [
            SystemMessage("Tu es TogoLM."),
            AIMessage("Bonjour !"),  # history may open with an assistant turn
            HumanMessage("Quel est le budget 2026 ?"),
            AIMessage("2 400 milliards."),
            HumanMessage(
                content=[
                    {"type": "image_url", "image_url": {"url": "data:image/png;base64,iVBOR"}},
                    {"type": "text", "text": "Qu'est-ce que c'est ?"},
                ]
            ),
        ]
    )
    assert system == "Tu es TogoLM."
    assert [t["role"] for t in turns] == ["user", "assistant", "user"]
    assert turns[0]["content"] == "Quel est le budget 2026 ?"
    image, text = turns[2]["content"]
    assert image == {
        "type": "image",
        "source": {"type": "base64", "media_type": "image/png", "data": "iVBOR"},
    }
    assert text == {"type": "text", "text": "Qu'est-ce que c'est ?"}


def _fake_client(text="Réponse de Claude"):
    client = MagicMock()
    client.messages.create.return_value = SimpleNamespace(
        content=[SimpleNamespace(type="thinking"), SimpleNamespace(type="text", text=text)]
    )
    stream = MagicMock()
    stream.__enter__.return_value.text_stream = iter(["Répon", "se"])
    client.messages.stream.return_value = stream
    return client


def test_claude_answers_and_records_the_fallback(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test-key-1234")
    model = claude.get_claude_model(max_output_tokens=200)
    client = _fake_client()
    with (
        patch.object(claude.ClaudeChatModel, "_client", return_value=client),
        patch.object(claude, "record_claude_fallback") as recorded,
    ):
        answer = model.invoke([SystemMessage("Règles"), HumanMessage("Question ?")])
        events = [
            e for chunk in model.stream([HumanMessage("Q")]) for e in _iter_chunk_events(chunk)
        ]

    assert answer.content == "Réponse de Claude"
    assert events == [("chunk", "Répon"), ("chunk", "se")]
    assert recorded.call_count == 2
    request = client.messages.create.call_args.kwargs
    assert request["model"] == "claude-opus-5-5"
    assert request["system"] == "Règles"
    assert request["output_config"] == {"effort": "low"}
    assert request["max_tokens"] == 200 + claude.THINKING_HEADROOM_TOKENS


@pytest.fixture
def keys(monkeypatch):
    def set_keys(gemini: bool, anthropic: bool):
        for name, on in (("GEMINI_API_KEY", gemini), ("ANTHROPIC_API_KEY", anthropic)):
            if on:
                monkeypatch.setenv(name, "key-for-tests-1234567")
            else:
                monkeypatch.delenv(name, raising=False)
        monkeypatch.delenv("GEMINI_MODEL", raising=False)
        monkeypatch.delenv("GEMINI_FALLBACK_MODEL", raising=False)

    return set_keys


def _chain_types(runnable) -> list[str]:
    links = (
        [runnable.runnable, *runnable.fallbacks] if hasattr(runnable, "fallbacks") else [runnable]
    )
    return [type(link).__name__ for link in links]


def test_chain_is_gemini_then_gemini_fallback_then_claude(keys):
    keys(gemini=True, anthropic=True)
    chain = llm.get_chat_model_with_fallback(max_output_tokens=100)
    assert _chain_types(chain) == [
        "ChatGoogleGenerativeAI",
        "ChatGoogleGenerativeAI",
        "ClaudeChatModel",
    ]
    assert chain.runnable.max_retries == 1


def test_chain_without_one_provider(keys):
    keys(gemini=False, anthropic=True)
    assert llm.llm_available()
    assert _chain_types(llm.get_chat_model_with_fallback(max_output_tokens=100)) == [
        "ClaudeChatModel"
    ]
    keys(gemini=True, anthropic=False)
    assert "ClaudeChatModel" not in _chain_types(
        llm.get_chat_model_with_fallback(max_output_tokens=100)
    )
    keys(gemini=False, anthropic=False)
    assert not llm.llm_available()
    with pytest.raises(RuntimeError):
        llm.get_chat_model_with_fallback(max_output_tokens=100)
