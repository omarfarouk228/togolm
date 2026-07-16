"""
POST /v1/query        — RAG query endpoint (full response)
POST /v1/query/stream — RAG query endpoint (SSE stream)
POST /v1/embed        — Embedding endpoint

HTTP layer only: validate, delegate to the query feature modules, shape the
response. Classification, generation, retrieval and logging live elsewhere.
"""

import asyncio
import json
import logging
import time
from collections.abc import Iterator

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from fastapi.responses import StreamingResponse

from api.app.core.auth import APIKeyRecord, get_api_key
from api.app.features.query.querylog import log_query
from api.app.features.query.schemas import (
    EmbedRequest,
    EmbedResponse,
    QueryRequest,
    QueryResponse,
    Source,
)
from rag import generation, retrieval
from rag.generation import rewrite_question_with_history
from rag.generation.llm import gemini_available
from rag.indexation.embedder import LocalEmbedder
from rag.orchestration.classification import is_trivially_off_topic
from rag.orchestration.graph import QueryGraphResult, run_query_graph
from rag.retrieval.enrichment import enrich_query

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Query"])

_NO_RESULTS = "Je n'ai pas trouvé de documents pertinents dans le corpus pour cette question."

# Chunks above retrieval min_score (0.62) reach the model as context.
# Only chunks above this higher threshold are shown as sources in the response —
# preventing irrelevant borderline matches from appearing as citations.
_SOURCE_DISPLAY_MIN_SCORE = 0.72

# Module-level embedder cache for the /embed endpoint
_local_embedder: LocalEmbedder | None = None


def _get_local_embedder() -> LocalEmbedder:
    global _local_embedder
    if _local_embedder is None:
        _local_embedder = LocalEmbedder()
    return _local_embedder


def _sse(event_type: str, text: str) -> str:
    """Frame a semantic generation event as an SSE data line."""
    return f"data: {json.dumps({'type': event_type, 'text': text})}\n\n"


def _run_image_query(request: QueryRequest) -> QueryGraphResult:
    """Image branch of /query: understand the image, search the corpus, then fall
    back to a vision-grounded answer when nothing relevant is found (bypasses the
    text-only graph, mirroring how /query/stream already handles its own flow)."""
    image = request.image
    assert image is not None
    search_question = generation.describe_image_question(
        image.mime_type, image.data, request.question
    )
    enriched = enrich_query(search_question, category=request.category)
    chunks = retrieval.retrieve(question=enriched.search_query, category=enriched.category, top_k=5)
    if chunks:
        answer = generation.build_answer_with_image(
            request.question, chunks, image.mime_type, image.data, history=request.history
        )
    else:
        answer = generation.answer_from_image(
            image.mime_type, image.data, request.question, history=request.history
        )
    return QueryGraphResult(
        answer=answer,
        chunks=chunks,
        is_off_topic=False,
        search_question=enriched.search_query,
        search_category=enriched.category,
        added_terms=enriched.added_terms,
    )


@router.post("/query", response_model=QueryResponse)
async def query_corpus(
    request: QueryRequest,
    background_tasks: BackgroundTasks,
    api_key: APIKeyRecord | str | None = Depends(get_api_key),
):
    """Query the Togolese corpus via RAG and return an answer with sources."""
    t0 = time.monotonic()

    try:
        if request.image:
            result = await asyncio.to_thread(_run_image_query, request)
        else:
            result = await asyncio.to_thread(
                run_query_graph,
                question=request.question,
                category=request.category,
                language=request.language,
                history=request.history,
            )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Retrieval error: {e}")

    latency_ms = int((time.monotonic() - t0) * 1000)

    background_tasks.add_task(
        log_query,
        request.question,
        request.language,
        result.search_category,
        result.is_off_topic,
        len(result.chunks),
        latency_ms,
        api_key,
    )
    # Only show chunks that score above the display threshold as sources.
    # Chunks between retrieval min_score and this threshold still reach the model
    # as context but are not presented as citations (they may be borderline matches
    # that the model ignored in favour of general knowledge).
    display_chunks = [c for c in result.chunks if c.score >= _SOURCE_DISPLAY_MIN_SCORE]
    return QueryResponse(
        answer=result.answer,
        sources=[Source(title=c.title, url=c.url, score=round(c.score, 4)) for c in display_chunks],
        model="togolm-rag-v1",
        latency_ms=latency_ms,
    )


def _stream_image_query(
    request: QueryRequest, api_key: APIKeyRecord | str | None, t0: float
) -> Iterator[str]:
    """Image branch of /query/stream: understand the image, search the corpus, then
    fall back to a vision-grounded answer when nothing relevant is found."""
    image = request.image
    assert image is not None
    search_question = generation.describe_image_question(
        image.mime_type, image.data, request.question
    )
    enriched = enrich_query(search_question, category=request.category)

    try:
        chunks = retrieval.retrieve(
            question=enriched.search_query, category=enriched.category, top_k=5
        )
    except Exception as e:
        yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
        yield "data: [DONE]\n\n"
        return

    sources = [{"title": c.title, "url": c.url, "score": round(c.score, 4)} for c in chunks]

    if gemini_available():
        try:
            events = (
                generation.stream_answer_with_image(
                    request.question,
                    chunks,
                    image.mime_type,
                    image.data,
                    request.history or [],
                    max_output_tokens=request.max_tokens,
                )
                if chunks
                else generation.stream_answer_from_image(
                    image.mime_type,
                    image.data,
                    request.question,
                    request.history or [],
                    max_output_tokens=request.max_tokens,
                )
            )
            for event_type, text in events:
                yield _sse(event_type, text)
        except Exception:
            events = (
                generation.stream_extractive(chunks) if chunks else iter([("chunk", _NO_RESULTS)])
            )
            for event_type, text in events:
                yield _sse(event_type, text)
    elif chunks:
        for event_type, text in generation.stream_extractive(chunks):
            yield _sse(event_type, text)
    else:
        yield _sse("chunk", _NO_RESULTS)

    latency_ms = int((time.monotonic() - t0) * 1000)
    log_query(
        request.question,
        request.language,
        enriched.category,
        False,
        len(chunks),
        latency_ms,
        api_key,
    )
    display_sources = [s for s in sources if s["score"] >= _SOURCE_DISPLAY_MIN_SCORE]
    yield f"data: {json.dumps({'type': 'sources', 'sources': display_sources, 'latency_ms': latency_ms})}\n\n"
    yield "data: [DONE]\n\n"


@router.post("/query/stream")
def stream_query(
    request: QueryRequest,
    api_key: APIKeyRecord | str | None = Depends(get_api_key),
):
    """Stream a RAG answer via Server-Sent Events.

    Events (newline-delimited JSON after 'data: '):
      {type: 'thinking', text: str}
      {type: 'chunk',    text: str}
      {type: 'sources',  sources: [...], latency_ms: int}
      {type: 'error',    message: str}
    Terminated by: data: [DONE]
    """

    def generate():
        t0 = time.monotonic()

        if request.image:
            yield from _stream_image_query(request, api_key, t0)
            return

        off_topic = is_trivially_off_topic(request.question) or (
            generation.route_query(request.question) == "off_topic"
        )
        if off_topic:
            for event_type, text in generation.stream_without_corpus(
                request.question, request.history or []
            ):
                yield _sse(event_type, text)
            latency_ms = int((time.monotonic() - t0) * 1000)
            log_query(
                request.question, request.language, request.category, True, 0, latency_ms, api_key
            )
            yield f"data: {json.dumps({'type': 'sources', 'sources': [], 'latency_ms': latency_ms})}\n\n"
            yield "data: [DONE]\n\n"
            return

        # Rewrite the question using conversation history so the vector search
        # operates on a standalone, fully-resolved query instead of a pronoun-laden follow-up.
        search_question = request.question
        if request.history:
            search_question = rewrite_question_with_history(request.question, request.history)
        enriched = enrich_query(search_question, category=request.category)

        try:
            chunks = retrieval.retrieve(
                question=enriched.search_query, category=enriched.category, top_k=5
            )
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
            yield "data: [DONE]\n\n"
            return

        sources = [{"title": c.title, "url": c.url, "score": round(c.score, 4)} for c in chunks]

        if gemini_available():
            try:
                for event_type, text in generation.stream_answer(
                    request.question,
                    chunks,
                    request.history or [],
                    max_output_tokens=request.max_tokens,
                ):
                    yield _sse(event_type, text)
            except Exception:
                events = (
                    generation.stream_extractive(chunks)
                    if chunks
                    else iter([("chunk", _NO_RESULTS)])
                )
                for event_type, text in events:
                    yield _sse(event_type, text)
        elif chunks:
            for event_type, text in generation.stream_extractive(chunks):
                yield _sse(event_type, text)
        else:
            yield _sse("chunk", _NO_RESULTS)

        latency_ms = int((time.monotonic() - t0) * 1000)
        log_query(
            request.question,
            request.language,
            enriched.category,
            False,
            len(chunks),
            latency_ms,
            api_key,
        )
        display_sources = [s for s in sources if s["score"] >= _SOURCE_DISPLAY_MIN_SCORE]
        yield f"data: {json.dumps({'type': 'sources', 'sources': display_sources, 'latency_ms': latency_ms})}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/embed", response_model=EmbedResponse)
async def embed_text(request: EmbedRequest):
    """Generate an embedding vector for the provided text."""
    try:
        # Always use the local model for real-time inference: no rate limits,
        # no API key required, and the model is pre-baked into the Docker image.
        vector = await asyncio.to_thread(_get_local_embedder().encode_one, request.text)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Embedding error: {e}")

    return EmbedResponse(
        embedding=vector,
        model="paraphrase-multilingual-MiniLM-L12-v2",
        token_count=len(request.text.split()),
    )
