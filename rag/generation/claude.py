"""
Claude (Anthropic) as the second LLM provider, behind Gemini.

Gemini failed prod-wide twice (2026-08-31 and 2026-10-10: prepaid credits
depleted, model retired): answers fell back to raw extracts for hours. Claude
is the last link of get_chat_model_with_fallback, from another company, so one
provider's billing or outage no longer takes generation down.

ClaudeChatModel is a minimal LangChain chat model over the official anthropic
SDK, so it slots into the existing prompts, with_fallbacks chains and stream
handling (plain text chunks) unchanged.
"""

import os
import re
from collections.abc import Iterator
from typing import Any

from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, AIMessageChunk, BaseMessage, SystemMessage
from langchain_core.outputs import ChatGeneration, ChatGenerationChunk, ChatResult

from rag.generation.health import record_claude_fallback

DEFAULT_CLAUDE_MODEL = "claude-opus-5-5"
# Thinking can't be turned off on Claude Opus 5.5; low effort keeps it short
# for these short answers. Thinking tokens count against max_tokens, hence the
# headroom over the callers' output budgets (100-2048 tokens).
EFFORT = "low"
THINKING_HEADROOM_TOKENS = 1024
# Fail fast: a slow fallback is what made the Gemini outages look like hangs.
TIMEOUT_S = 30.0
MAX_RETRIES = 1


def claude_available() -> bool:
    return len(os.getenv("ANTHROPIC_API_KEY", "").strip()) > 10


def claude_model_name() -> str:
    return os.getenv("CLAUDE_MODEL", "").strip() or DEFAULT_CLAUDE_MODEL


def _text(content: Any) -> str:
    if isinstance(content, str):
        return content
    parts = []
    for block in content or []:
        if isinstance(block, str):
            parts.append(block)
        elif isinstance(block, dict) and block.get("type") == "text":
            parts.append(block.get("text", ""))
    return "".join(parts)


def _content(content: Any) -> str | list[dict]:
    """Message content for the Messages API. LangChain image parts (data URLs,
    see chains._image_content_block) become base64 image blocks, so questions
    about a photo keep their image when Claude answers them."""
    if isinstance(content, str):
        return content
    blocks: list[dict] = []
    for part in content or []:
        if isinstance(part, str):
            blocks.append({"type": "text", "text": part})
        elif isinstance(part, dict) and part.get("type") == "text" and part.get("text"):
            blocks.append({"type": "text", "text": part["text"]})
        elif isinstance(part, dict) and part.get("type") == "image_url":
            url = (part.get("image_url") or {}).get("url", "")
            match = re.match(r"data:([\w/+.-]+);base64,(.+)", url, re.DOTALL)
            if match:
                blocks.append(
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": match.group(1),
                            "data": match.group(2),
                        },
                    }
                )
    if all(b["type"] == "text" for b in blocks):
        return "".join(b["text"] for b in blocks)
    return blocks


def to_anthropic(messages: list[BaseMessage]) -> tuple[str, list[dict]]:
    """(system prompt, messages) for the Messages API from LangChain messages."""
    system = "\n\n".join(_text(m.content) for m in messages if isinstance(m, SystemMessage))
    turns = []
    for m in messages:
        if isinstance(m, SystemMessage):
            continue
        role = "assistant" if isinstance(m, AIMessage) else "user"
        content = _content(m.content)
        if content:
            turns.append({"role": role, "content": content})
    # The conversation must open with a user turn (history can start with an
    # assistant greeting).
    while turns and turns[0]["role"] != "user":
        turns.pop(0)
    return system, turns


class ClaudeChatModel(BaseChatModel):
    model_name: str = DEFAULT_CLAUDE_MODEL
    max_output_tokens: int = 2048

    @property
    def _llm_type(self) -> str:
        return "anthropic-claude"

    def _client(self):
        import anthropic

        return anthropic.Anthropic(
            api_key=os.environ["ANTHROPIC_API_KEY"], timeout=TIMEOUT_S, max_retries=MAX_RETRIES
        )

    def _request(self, messages: list[BaseMessage]) -> dict:
        system, turns = to_anthropic(messages)
        request = {
            "model": self.model_name,
            "max_tokens": self.max_output_tokens + THINKING_HEADROOM_TOKENS,
            "messages": turns,
            "output_config": {"effort": EFFORT},
        }
        if system:
            request["system"] = system
        return request

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: CallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        response = self._client().messages.create(**self._request(messages))
        record_claude_fallback()
        text = "".join(block.text for block in response.content if block.type == "text")
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content=text))])

    def _stream(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: CallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> Iterator[ChatGenerationChunk]:
        record_claude_fallback()
        with self._client().messages.stream(**self._request(messages)) as stream:
            for text in stream.text_stream:
                chunk = ChatGenerationChunk(message=AIMessageChunk(content=text))
                if run_manager:
                    run_manager.on_llm_new_token(text, chunk=chunk)
                yield chunk


def get_claude_model(*, max_output_tokens: int) -> ClaudeChatModel:
    return ClaudeChatModel(model_name=claude_model_name(), max_output_tokens=max_output_tokens)
