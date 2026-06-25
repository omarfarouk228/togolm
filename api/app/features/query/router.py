"""
POST /v1/query        — RAG query endpoint (full response)
POST /v1/query/stream — RAG query endpoint (SSE stream)
POST /v1/embed        — Embedding endpoint

HTTP layer only: validate, delegate to the query feature modules, shape the
response. Classification, generation, retrieval and logging live elsewhere.
"""

import json
import time

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
from rag.orchestration.classification import is_trivially_off_topic
from rag.orchestration.graph import run_query_graph
from rag.retrieval.enrichment import enrich_query

router = APIRouter(tags=["Query"])

_NO_RESULTS = "Je n'ai pas trouvé de documents pertinents dans le corpus pour cette question."


def _sse(event_type: str, text: str) -> str:
    """Frame a semantic generation event as an SSE data line."""
    return f"data: {json.dumps({'type': event_type, 'text': text})}\n\n"


@router.post("/query", response_model=QueryResponse)
async def query_corpus(
    request: QueryRequest,
    background_tasks: BackgroundTasks,
    api_key: APIKeyRecord | str | None = Depends(get_api_key),
):
    """Query the Togolese corpus via RAG and return an answer with sources."""
    t0 = time.monotonic()

    try:
        result = run_query_graph(
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
    return QueryResponse(
        answer=result.answer,
        sources=[Source(title=c.title, url=c.url, score=round(c.score, 4)) for c in result.chunks],
        model="togolm-rag-v1",
        latency_ms=latency_ms,
    )


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

        off_topic = is_trivially_off_topic(request.question) or (
            generation.route_query(request.question) == "off_topic"
        )
        if off_topic:
            for event_type, text in generation.stream_without_corpus(
                request.question, request.history or []
            ):
                yield _sse(event_type, text)
            latency_ms = int((time.monotonic() - t0) * 1000)
            yield f"data: {json.dumps({'type': 'sources', 'sources': [], 'latency_ms': latency_ms})}\n\n"
            yield "data: [DONE]\n\n"
            log_query(
                request.question, request.language, request.category, True, 0, latency_ms, api_key
            )
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
                    request.question, chunks, request.history or []
                ):
                    yield _sse(event_type, text)
            except Exception:
                events = generation.stream_extractive(chunks) if chunks else iter(
                    [("chunk", _NO_RESULTS)]
                )
                for event_type, text in events:
                    yield _sse(event_type, text)
        elif chunks:
            for event_type, text in generation.stream_extractive(chunks):
                yield _sse(event_type, text)
        else:
            yield _sse("chunk", _NO_RESULTS)

        latency_ms = int((time.monotonic() - t0) * 1000)
        yield f"data: {json.dumps({'type': 'sources', 'sources': sources, 'latency_ms': latency_ms})}\n\n"
        yield "data: [DONE]\n\n"
        log_query(
            request.question,
            request.language,
            enriched.category,
            False,
            len(chunks),
            latency_ms,
            api_key,
        )

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/embed", response_model=EmbedResponse)
async def embed_text(request: EmbedRequest):
    """Generate an embedding vector for the provided text."""
    from rag.indexation.embedder import LocalEmbedder

    try:
        # Always use the local model for real-time inference: no rate limits,
        # no API key required, and the model is pre-baked into the Docker image.
        embedder = LocalEmbedder()
        vector = embedder.encode_one(request.text)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Embedding error: {e}")

    return EmbedResponse(
        embedding=vector,
        model="paraphrase-multilingual-MiniLM-L12-v2",
        token_count=len(request.text.split()),
    )
