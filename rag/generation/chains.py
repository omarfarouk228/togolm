"""
LangChain generation layer for the query feature.

Every LLM call lives here, built as LCEL chains over a single ChatGoogleGenerativeAI
model and the versioned prompts in ``prompts``. Retrieval and HTTP concerns stay
out of this module.

Streaming helpers yield ``(event_type, text)`` tuples — ``"chunk"`` for answer
tokens and ``"thinking"`` for reasoning tokens — leaving SSE framing to the route.
"""

from collections.abc import Iterator
from typing import Any, Literal

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_core.output_parsers import StrOutputParser
from pydantic import BaseModel, Field

from rag.generation.llm import gemini_available, get_chat_model
from rag.generation.prompts import (
    IMAGE_ANSWER_SYSTEM,
    IMAGE_UNDERSTANDING_SYSTEM,
    OFF_TOPIC_PROMPT,
    RAG_ANSWER_PROMPT,
    REWRITE_PROMPT,
    ROUTER_PROMPT,
)

History = list[Any]
Intent = Literal["on_topic", "off_topic"]

# Canned replies used when Gemini is unavailable or a call fails.
OFF_TOPIC_GREETING = (
    "Bonjour ! Je suis TogoLM, spécialisé dans les connaissances togolaises. "
    "Posez-moi une question sur le Togo — lois, économie, éducation, actualité…"
)
OFF_TOPIC_FALLBACK = (
    "Bonjour ! Je suis TogoLM, spécialisé dans les connaissances togolaises. "
    "Posez-moi une question sur le Togo !"
)
STREAM_OFF_TOPIC_FALLBACK = (
    "Bonjour ! Je suis TogoLM, spécialisé dans les connaissances togolaises."
)
NO_CORPUS_ANSWER = "Je n'ai pas trouvé de documents pertinents dans le corpus pour cette question."


# --- Routing (agentic intent classification) ----------------------------------


class QueryRoute(BaseModel):
    """Structured routing decision for an incoming message."""

    intent: Intent = Field(description="on_topic if related to Togo, else off_topic")
    reason: str = Field(default="", description="Short justification, for observability")


def route_query(question: str) -> Intent:
    """Classify a non-trivial message as on/off topic via a structured LLM call.

    Fails open: if Gemini is unavailable or the call fails, returns 'on_topic' so a
    genuine question is never wrongly redirected.
    """
    if not gemini_available():
        return "on_topic"
    model = get_chat_model(max_output_tokens=100).with_structured_output(QueryRoute)
    try:
        result = (ROUTER_PROMPT | model).invoke({"question": question})
        return result.intent
    except Exception:
        return "on_topic"


# --- Shared helpers -----------------------------------------------------------


def _role_content(message: Any) -> tuple[str, str]:
    if isinstance(message, dict):
        return str(message.get("role", "")), str(message.get("content", ""))
    return str(getattr(message, "role", "")), str(getattr(message, "content", ""))


def _history_messages(history: History, limit: int, truncate: int) -> list[BaseMessage]:
    """Convert raw history into alternating LangChain messages (truncated)."""
    messages: list[BaseMessage] = []
    for item in history[-limit:]:
        role, content = _role_content(item)
        content = content[:truncate]
        messages.append(HumanMessage(content) if role == "user" else AIMessage(content))
    return messages


def _history_text(history: History, limit: int = 4, truncate: int = 300) -> str:
    lines = []
    for item in history[-limit:]:
        role, content = _role_content(item)
        speaker = "Utilisateur" if role == "user" else "Assistant"
        lines.append(f"{speaker}: {content[:truncate]}")
    return "\n".join(lines)


def _format_context(chunks: list[Any]) -> str:
    context = "\n\n".join(f"[{c.source} — {c.title}]\n{c.content[:600]}" for c in chunks)
    return context or "(aucun document disponible)"


def extractive_answer(chunks: list[Any]) -> str:
    """Surface the top passage with attribution when no LLM is used."""
    top = chunks[0]
    excerpt = top.content[:800].rsplit(" ", 1)[0] + "…" if len(top.content) > 800 else top.content
    return f"{excerpt}\n\n[Source: {top.source}]"


def _iter_chunk_events(chunk: Any) -> Iterator[tuple[str, str]]:
    """Map a streamed AIMessageChunk to (event_type, text) tuples."""
    content = chunk.content
    if isinstance(content, str):
        if content:
            yield ("chunk", content)
        return
    if isinstance(content, list):
        for block in content:
            if isinstance(block, str):
                if block:
                    yield ("chunk", block)
            elif isinstance(block, dict):
                btype = block.get("type")
                if btype in ("thinking", "reasoning"):
                    text = block.get("thinking") or block.get("reasoning")
                    if text:
                        yield ("thinking", text)
                elif btype == "text":
                    text = block.get("text")
                    if text:
                        yield ("chunk", text)


# --- Non-streaming generation -------------------------------------------------


def build_answer(
    question: str, chunks: list[Any], history: History | None = None, max_output_tokens: int = 2048
) -> str:
    """Assemble an answer from retrieved chunks (graph answer_builder).

    When chunks is empty, Gemini answers from general knowledge (no sources will
    be shown by the caller). Falls back to extractive or NO_CORPUS_ANSWER only
    when Gemini is unavailable.
    """
    if gemini_available():
        try:
            return _generate_answer(question, chunks, history or [], max_output_tokens)
        except Exception:
            pass
    if not chunks:
        return NO_CORPUS_ANSWER
    return extractive_answer(chunks)


def _generate_answer(
    question: str, chunks: list[Any], history: History, max_output_tokens: int = 2048
) -> str:
    chain = (
        RAG_ANSWER_PROMPT | get_chat_model(max_output_tokens=max_output_tokens) | StrOutputParser()
    )
    return chain.invoke(
        {
            "context": _format_context(chunks),
            "question": question,
            "history": _history_messages(history, limit=6, truncate=400),
        }
    )


def answer_without_corpus(question: str, history: History) -> str:
    """Answer an off-topic message without corpus context (graph off_topic_node)."""
    if not gemini_available():
        return OFF_TOPIC_GREETING
    chain = OFF_TOPIC_PROMPT | get_chat_model(max_output_tokens=200) | StrOutputParser()
    try:
        return (
            chain.invoke(
                {"question": question, "history": _history_messages(history, limit=4, truncate=300)}
            )
            or ""
        )
    except Exception:
        return OFF_TOPIC_FALLBACK


def rewrite_question_with_history(question: str, history: History) -> str:
    """Rewrite a follow-up as a standalone search query, resolving references.

    Falls back to the original question when Gemini is unavailable or the call fails.
    """
    if not history or not gemini_available():
        return question
    chain = REWRITE_PROMPT | get_chat_model(max_output_tokens=150) | StrOutputParser()
    try:
        rewritten = chain.invoke(
            {"history_text": _history_text(history), "question": question}
        ).strip()
        return rewritten or question
    except Exception:
        return question


# --- Image-grounded generation -------------------------------------------------


def _image_content_block(mime_type: str, data: str) -> dict[str, Any]:
    return {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{data}"}}


def describe_image_question(mime_type: str, data: str, question: str) -> str:
    """Turn an attached image (+ optional typed question) into a standalone search query.

    Falls back to the raw question when Gemini is unavailable or the call fails, so
    retrieval still runs on whatever text the user typed.
    """
    fallback = question.strip() or "Décris cette image."
    if not gemini_available():
        return fallback
    try:
        text = question.strip() or "Que puis-je savoir sur cette image ?"
        content: list[Any] = [_image_content_block(mime_type, data), {"type": "text", "text": text}]
        messages = [SystemMessage(IMAGE_UNDERSTANDING_SYSTEM), HumanMessage(content=content)]
        result = get_chat_model(max_output_tokens=150).invoke(messages)
        rewritten = str(result.content).strip()
        return rewritten or fallback
    except Exception:
        return fallback


def answer_from_image(
    mime_type: str,
    data: str,
    question: str,
    history: History | None = None,
    max_output_tokens: int = 2048,
) -> str:
    """Answer directly from the image when corpus retrieval found nothing."""
    if gemini_available():
        try:
            messages = _image_answer_messages(mime_type, data, question, history or [])
            model = get_chat_model(max_output_tokens=max_output_tokens)
            return str(model.invoke(messages).content) or NO_CORPUS_ANSWER
        except Exception:
            pass
    return NO_CORPUS_ANSWER


def _image_answer_messages(
    mime_type: str, data: str, question: str, history: History
) -> list[BaseMessage]:
    text = question.strip() or "Décris cette image et explique ce qu'elle représente."
    content: list[Any] = [_image_content_block(mime_type, data), {"type": "text", "text": text}]
    return [
        SystemMessage(IMAGE_ANSWER_SYSTEM),
        *_history_messages(history, limit=6, truncate=400),
        HumanMessage(content=content),
    ]


# --- Streaming generation -----------------------------------------------------


def stream_answer(
    question: str, chunks: list[Any], history: History | None = None, max_output_tokens: int = 2048
) -> Iterator[tuple[str, str]]:
    """Stream a RAG answer. Raises on LLM failure so the caller can fall back."""
    history_msgs = _history_messages(history or [], limit=6, truncate=400)
    messages = RAG_ANSWER_PROMPT.format_messages(
        context=_format_context(chunks),
        question=question,
        history=history_msgs,
    )
    model = get_chat_model(max_output_tokens=max_output_tokens, streaming=True)
    for chunk in model.stream(messages):
        yield from _iter_chunk_events(chunk)


def stream_without_corpus(
    question: str, history: History | None = None
) -> Iterator[tuple[str, str]]:
    """Stream an off-topic reply, handling missing key and failures internally."""
    if not gemini_available():
        yield ("chunk", OFF_TOPIC_GREETING)
        return
    model = get_chat_model(max_output_tokens=200, streaming=True)
    messages = OFF_TOPIC_PROMPT.format_messages(
        question=question,
        history=_history_messages(history or [], limit=4, truncate=300),
    )
    try:
        for chunk in model.stream(messages):
            yield from _iter_chunk_events(chunk)
    except Exception:
        yield ("chunk", STREAM_OFF_TOPIC_FALLBACK)


def stream_extractive(chunks: list[Any]) -> Iterator[tuple[str, str]]:
    """Yield the top extractive passage as a single chunk event."""
    yield ("chunk", extractive_answer(chunks))


def stream_answer_from_image(
    mime_type: str,
    data: str,
    question: str,
    history: History | None = None,
    max_output_tokens: int = 2048,
) -> Iterator[tuple[str, str]]:
    """Stream an answer grounded directly on the image. Raises on LLM failure so the
    caller can fall back, matching stream_answer's contract."""
    messages = _image_answer_messages(mime_type, data, question, history or [])
    model = get_chat_model(max_output_tokens=max_output_tokens, streaming=True)
    for chunk in model.stream(messages):
        yield from _iter_chunk_events(chunk)
