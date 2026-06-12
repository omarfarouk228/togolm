"""
POST /v1/query        — RAG query endpoint (full response)
POST /v1/query/stream — RAG query endpoint (SSE stream)
POST /v1/embed        — Embedding endpoint
"""

import json
import os
import time

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from api.app.services.rag import RetrievedChunk, build_answer, retrieve

router = APIRouter(tags=["Query"])


class QueryRequest(BaseModel):
    question: str = Field(..., min_length=3, max_length=1000)
    category: str | None = None
    language: str = "fr"
    max_tokens: int = Field(500, ge=50, le=2000)


class Source(BaseModel):
    title: str
    url: str | None
    score: float


class QueryResponse(BaseModel):
    answer: str
    sources: list[Source]
    model: str
    latency_ms: int


class EmbedRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=8000)
    model: str = "togolm-embed-v1"


class EmbedResponse(BaseModel):
    embedding: list[float]
    model: str
    token_count: int


@router.post("/query", response_model=QueryResponse)
async def query_corpus(request: QueryRequest):
    """Query the Togolese corpus via RAG and return an answer with sources."""
    t0 = time.monotonic()

    try:
        chunks = retrieve(
            question=request.question,
            category=request.category,
            top_k=5,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Retrieval error: {e}")

    answer = build_answer(request.question, chunks)
    latency_ms = int((time.monotonic() - t0) * 1000)

    return QueryResponse(
        answer=answer,
        sources=[
            Source(title=c.title, url=c.url, score=round(c.score, 4))
            for c in chunks
        ],
        model="togolm-rag-v1",
        latency_ms=latency_ms,
    )


def _stream_gemini(question: str, chunks: list[RetrievedChunk]):
    """Yield SSE data lines from Gemini streaming generation.

    Uses the same system instruction as rag._generate_with_gemini so that
    Gemini falls back to general knowledge when the corpus context is thin —
    instead of returning a useless "the context does not contain…" message.
    """
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    context = "\n\n".join(
        f"[{c.source} — {c.title}]\n{c.content[:600]}" for c in chunks
    )

    system_instruction = (
        "Tu es TogoLM, un assistant IA expert des connaissances togolaises.\n"
        "Tu maîtrises la législation, l'économie, l'éducation, l'histoire et l'actualité du Togo.\n\n"
        "Règles de réponse :\n"
        "1. Si le contexte du corpus contient les informations nécessaires, base ta réponse dessus et indique les sources.\n"
        "2. Si le contexte est insuffisant ou hors-sujet, réponds quand même avec tes connaissances générales sur le Togo "
        "— en précisant en fin de réponse : "
        "\"⚠️ Cette réponse est basée sur mes connaissances générales et non sur le corpus TogoLM.\"\n"
        "3. Réponds toujours dans la langue de la question (français par défaut).\n"
        "4. Ne réponds jamais \"je n'ai pas suffisamment d'informations\" sans fournir une réponse utile."
    )

    corpus_block = context if context else "(aucun document pertinent trouvé dans le corpus)"
    prompt = f"CONTEXTE DU CORPUS TOGOLM :\n{corpus_block}\n\nQUESTION : {question}\n\nRÉPONSE :"

    for chunk in client.models.generate_content_stream(
        model="gemini-2.5-flash",
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=system_instruction,
            max_output_tokens=1000,
        ),
    ):
        if chunk.text:
            yield f"data: {json.dumps({'type': 'chunk', 'text': chunk.text})}\n\n"


def _extractive_stream(chunks: list[RetrievedChunk]):
    """Yield a single SSE data line with the top extractive passage."""
    top = chunks[0]
    excerpt = (
        top.content[:800].rsplit(" ", 1)[0] + "…"
        if len(top.content) > 800
        else top.content
    )
    text = f"{excerpt}\n\n[Source: {top.source}]"
    yield f"data: {json.dumps({'type': 'chunk', 'text': text})}\n\n"


@router.post("/query/stream")
def stream_query(request: QueryRequest):
    """Stream a RAG answer via Server-Sent Events.

    Events (newline-delimited JSON after 'data: '):
      {type: 'chunk',   text: str}
      {type: 'sources', sources: [...], latency_ms: int}
      {type: 'error',   message: str}
    Terminated by: data: [DONE]
    """
    def generate():
        t0 = time.monotonic()

        try:
            chunks = retrieve(question=request.question, category=request.category, top_k=5)
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
            yield "data: [DONE]\n\n"
            return

        sources = [
            {"title": c.title, "url": c.url, "score": round(c.score, 4)}
            for c in chunks
        ]

        gemini_key = os.getenv("GEMINI_API_KEY", "")
        use_gemini = bool(gemini_key) and len(gemini_key) > 10

        if use_gemini:
            # Always call Gemini, even with empty chunks — the system instruction
            # tells it to fall back to general knowledge when context is thin.
            try:
                yield from _stream_gemini(request.question, chunks)
            except Exception:
                if chunks:
                    yield from _extractive_stream(chunks)
                else:
                    no_result = "Aucune information pertinente trouvée dans le corpus TogoLM pour cette question."
                    yield f"data: {json.dumps({'type': 'chunk', 'text': no_result})}\n\n"
        elif chunks:
            yield from _extractive_stream(chunks)
        else:
            no_result = "Aucune information pertinente trouvée dans le corpus TogoLM pour cette question."
            yield f"data: {json.dumps({'type': 'chunk', 'text': no_result})}\n\n"

        latency_ms = int((time.monotonic() - t0) * 1000)
        yield f"data: {json.dumps({'type': 'sources', 'sources': sources, 'latency_ms': latency_ms})}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/embed", response_model=EmbedResponse)
async def embed_text(request: EmbedRequest):
    """Generate an embedding vector for the provided text."""
    from corpus.processors.embedder import LocalEmbedder

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
