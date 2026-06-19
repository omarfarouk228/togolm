"""
POST /v1/query        — RAG query endpoint (full response)
POST /v1/query/stream — RAG query endpoint (SSE stream)
POST /v1/embed        — Embedding endpoint
"""

import json
import os
import re
import time

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from api.app.core.auth import APIKeyRecord, get_api_key
from api.app.core.db import get_conn
from api.app.features.query.service import RetrievedChunk, build_answer, retrieve

_GREETINGS_RE = re.compile(
    r"^\s*(hello|hi|hey|bonjour|salut|bonsoir|bonne\s*nuit|good\s*morning|good\s*evening|"
    r"coucou|allo|allô|yo|ok|okay|merci|thanks|thank\s*you|au\s*revoir|bye|bonne\s*journée|"
    r"bonne\s*soirée|slt|bjr|svp|s\'il\s*vous\s*plaît)\s*[!?.,]?\s*$",
    re.IGNORECASE,
)
_MATH_RE = re.compile(r"^\s*[\d\s\+\-\*\/\^\(\)=.,]+\s*$")

# Structural code detection
_ENV_LINE_RE = re.compile(r"^[A-Z][A-Z0-9_]{2,}=", re.MULTILINE)
_CODE_FENCE_RE = re.compile(r"```|\"\"\"")
_CODE_SYNTAX_RE = re.compile(
    r"\bdef \w+\s*\(|\bclass \w+[\s:(]|@router\.|@app\."
    r"|from [\w.]+ import |\basync def \b|\bSELECT\b.{1,60}\bFROM\b"
    r"|\b(?:const|let|var)\s+\w+\s*=|#include\s*<"
    r"|\bimport\s+\w[\w.]*(?:\s*,\s*\w[\w.]*)*\s*$",
    re.IGNORECASE | re.MULTILINE,
)

# Intent-based detection for common off-topic categories
_OFF_TOPIC_INTENT_RE = re.compile(
    r"(?:"
    # code review / debug
    r"(?:penses?-tu|ton avis)\s+(?:sur|de)\s+(?:ce\s+)?(?:code|script|config(?:uration)?|\.env)\b"
    r"|(?:penses?-tu|what do you think)\s+(?:de|of|about)\s+(?:this|ce|mon|le)\s+(?:code|script|programme)\b"
    r"|(?:analyse[rz]?|review|audite[rz]?|debug(?:gue)?|corrige[rz]?)\s+(?:ce|mon|le|cet?)\s+(?:code|script|programme|fichier)"
    r"|que fait\s+(?:ce|mon|le)\s+(?:code|script|programme)\b"
    r"|(?:ce|mon|le)\s+(?:code|script|programme)\s+(?:fait|fais|faisait)\s+quoi\b"
    r"|(?:c'est|c'est)\s+quoi\s+(?:ce|ton|ce\s+bout\s+de)\s+code\b"
    r"|[àa]\s+quoi\s+(?:sert|correspond)\s+(?:ce|mon|le)\s+(?:code|script)\b"
    r"|explique[rz]?\s+(?:ce|mon|le)\s+(?:code|script)\b"
    # cooking / recipes
    r"|\brecette\s+de\b"
    r"|\bcomment\s+cuisiner\b"
    r"|\bcomment\s+pr[eé]parer\s+(?:un|une|le|la|du|des)\b"
    # creative writing unrelated to Togo
    r"|\b[eé]cri[rst][\s-]+(?:moi[\s-]+)?(?:une?\s+)?(?:histoire|po[eè]me|roman|chanson|blague|haïku)\b"
    r"|write\s+(?:me\s+)?(?:a|an)\s+(?:story|poem|song|joke|novel)\b"
    # code generation requests
    r"|\b[eé]cri[rst][\s-]+(?:moi[\s-]+)?(?:une?\s+)?(?:fonction|m[eé]thode|classe|script|programme|composant|requ[eê]te SQL)\b"
    r"|\bg[eé]n[eè]re[rz]?\s+(?:un|une)\s+(?:code|script|fonction|classe|programme)\b"
    r"|write\s+(?:me\s+)?(?:a|an)\s+(?:function|method|class|script|program|component|query)\b"
    # sports scores
    r"|\b(?:score|r[eé]sultat)\s+du\s+match\b"
    # general programming help (not Togo-specific)
    r"|\bcomment\s+(?:coder|programmer|d[eé]bugger)\b"
    # general world knowledge (not Togo-specific)
    r"|\bcombien\s+(?:de\s+)?(?:pays|villes|personnes|habitants|langues|continents)\s+"
    r"(?:y[\s']a[- ]t[- ]il\s+)?(?:dans\s+le\s+monde|au\s+monde|sur\s+(?:terre|la\s+plan[eè]te))\b"
    r"|\bqui\s+est\s+(?:le|la|l[''])\s*(?:pr[eé]sident|premier\s+ministre|roi|reine|chancelier)"
    r"\s+(?:actuel(?:le)?\s+)?(?:de\s+(?:la\s+|l[''])?|du\s+|des\s+)(?!togo\b)\w+"
    r"|\bquelle\s+est\s+la\s+capitale\s+de\s+(?:la\s+|l['']|du\s+|des\s+)?(?!togo\b)\w+"
    r")",
    re.IGNORECASE,
)


def _contains_code(q: str) -> bool:
    """Return True when the message body looks like shared source code."""
    if len(_ENV_LINE_RE.findall(q)) >= 3:
        return True
    if _CODE_FENCE_RE.search(q):
        return True
    if len(_CODE_SYNTAX_RE.findall(q)) >= 2:
        return True
    return False


def _is_off_topic(question: str) -> bool:
    """Return True for messages outside TogoLM's domain: greetings, math,
    code dumps, code-review requests, recipes, creative writing, sports."""
    q = question.strip()
    if _GREETINGS_RE.match(q):
        return True
    if _MATH_RE.match(q):
        return True
    if len(q.split()) < 3:
        return True
    if _OFF_TOPIC_INTENT_RE.search(q):
        return True
    if _contains_code(q):
        return True
    return False


def _answer_without_corpus(question: str, history: list) -> str:
    """Call Gemini directly without corpus context for off-topic questions."""
    if not os.getenv("GEMINI_API_KEY"):
        return (
            "Bonjour ! Je suis TogoLM, spécialisé dans les connaissances togolaises. "
            "Posez-moi une question sur le Togo — lois, économie, éducation, actualité…"
        )
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    system_instruction = (
        "Tu es TogoLM, un assistant IA exclusivement spécialisé dans les connaissances togolaises : "
        "lois, économie, éducation, histoire, actualité et culture du Togo.\n\n"
        "RÈGLES ABSOLUES — ne les enfreins jamais :\n"
        "1. Ne génère JAMAIS de code (fonctions, scripts, programmes, classes, etc.).\n"
        "2. Ne fais JAMAIS d'analyse, de revue ou de correction de code.\n"
        "3. Ne rédige pas de contenu créatif sans lien avec le Togo (poèmes, histoires, traductions génériques).\n"
        "4. Pour toute demande hors de ta spécialité, réponds UNIQUEMENT par une phrase courte du type : "
        '"Je suis spécialisé dans les connaissances togolaises. '
        'Posez-moi une question sur le Togo — lois, économie, éducation, histoire…"\n'
        "5. Tu peux répondre brièvement aux salutations avant de rediriger."
    )
    history_block = ""
    if history:
        lines = [
            f"{'Utilisateur' if m.role == 'user' else 'Assistant'}: {m.content[:300]}"
            for m in history[-4:]
        ]
        history_block = "HISTORIQUE:\n" + "\n".join(lines) + "\n\n"
    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=f"{history_block}Question: {question}",
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                max_output_tokens=200,
            ),
        )
        return response.text or ""
    except Exception:
        return (
            "Bonjour ! Je suis TogoLM, spécialisé dans les connaissances togolaises. "
            "Posez-moi une question sur le Togo !"
        )


def _stream_without_corpus(question: str, history: list):
    """Stream a Gemini response without corpus context for off-topic questions."""
    if not os.getenv("GEMINI_API_KEY"):
        msg = (
            "Bonjour ! Je suis TogoLM, spécialisé dans les connaissances togolaises. "
            "Posez-moi une question sur le Togo — lois, économie, éducation, actualité…"
        )
        yield f"data: {json.dumps({'type': 'chunk', 'text': msg})}\n\n"
        return
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    system_instruction = (
        "Tu es TogoLM, un assistant IA exclusivement spécialisé dans les connaissances togolaises : "
        "lois, économie, éducation, histoire, actualité et culture du Togo.\n\n"
        "RÈGLES ABSOLUES — ne les enfreins jamais :\n"
        "1. Ne génère JAMAIS de code (fonctions, scripts, programmes, classes, etc.).\n"
        "2. Ne fais JAMAIS d'analyse, de revue ou de correction de code.\n"
        "3. Ne rédige pas de contenu créatif sans lien avec le Togo (poèmes, histoires, traductions génériques).\n"
        "4. Pour toute demande hors de ta spécialité, réponds UNIQUEMENT par une phrase courte du type : "
        '"Je suis spécialisé dans les connaissances togolaises. '
        'Posez-moi une question sur le Togo — lois, économie, éducation, histoire…"\n'
        "5. Tu peux répondre brièvement aux salutations avant de rediriger."
    )
    history_block = ""
    if history:
        lines = [
            f"{'Utilisateur' if m.role == 'user' else 'Assistant'}: {m.content[:300]}"
            for m in history[-4:]
        ]
        history_block = "HISTORIQUE:\n" + "\n".join(lines) + "\n\n"
    try:
        for chunk in client.models.generate_content_stream(
            model="gemini-2.5-flash",
            contents=f"{history_block}Question: {question}",
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                max_output_tokens=200,
                thinking_config=types.ThinkingConfig(thinking_budget=0),
            ),
        ):
            if chunk.text:
                yield f"data: {json.dumps({'type': 'chunk', 'text': chunk.text})}\n\n"
    except Exception:
        msg = "Bonjour ! Je suis TogoLM, spécialisé dans les connaissances togolaises."
        yield f"data: {json.dumps({'type': 'chunk', 'text': msg})}\n\n"


def _log_query(
    question: str,
    language: str,
    category: str | None,
    is_off_topic: bool,
    chunks_found: int,
    latency_ms: int,
    api_key: APIKeyRecord | str | None,
) -> None:
    """Persist a query log record — called in background, never raises."""
    if isinstance(api_key, APIKeyRecord):
        prefix = api_key.preview
    elif isinstance(api_key, str):
        prefix = api_key[:8] + "..." if len(api_key) > 8 else api_key
    else:
        prefix = None

    try:
        conn = get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO user_queries
                        (question, language, category, is_off_topic, chunks_found, latency_ms, api_key_prefix)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """,
                    (question, language, category, is_off_topic, chunks_found, latency_ms, prefix),
                )
            conn.commit()
        finally:
            conn.close()
    except Exception:
        pass  # logging must never break the main flow


router = APIRouter(tags=["Query"])


class HistoryMessage(BaseModel):
    role: str  # "user" or "assistant"
    content: str


class QueryRequest(BaseModel):
    question: str = Field(..., min_length=3, max_length=4000)
    category: str | None = None
    language: str = "fr"
    max_tokens: int = Field(500, ge=50, le=2000)
    history: list[HistoryMessage] = []


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


def rewrite_question_with_history(question: str, history: list[HistoryMessage]) -> str:
    """Rewrite a follow-up question as a standalone search query.

    Resolves all pronouns and implicit references using the conversation history.
    Falls back to the original question if Gemini is unavailable or the call fails.
    """
    if not history or not os.getenv("GEMINI_API_KEY"):
        return question

    from google import genai
    from google.genai import types

    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    history_text = "\n".join(
        f"{'Utilisateur' if m.role == 'user' else 'Assistant'}: {m.content[:300]}"
        for m in history[-4:]
    )
    prompt = (
        f"Historique de conversation:\n{history_text}\n\n"
        f"Nouvelle question: {question}\n\n"
        "Reformule cette question en une requête de recherche autonome et complète, "
        "en remplaçant tous les pronoms et références implicites par les entités explicites du contexte. "
        "Réponds UNIQUEMENT avec la requête reformulée, sans guillemets ni explication."
    )
    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(max_output_tokens=150),
        )
        rewritten = (response.text or "").strip()
        return rewritten if rewritten else question
    except Exception:
        return question


@router.post("/query", response_model=QueryResponse)
async def query_corpus(
    request: QueryRequest,
    background_tasks: BackgroundTasks,
    api_key: APIKeyRecord | str | None = Depends(get_api_key),
):
    """Query the Togolese corpus via RAG and return an answer with sources."""
    t0 = time.monotonic()

    if _is_off_topic(request.question):
        answer = _answer_without_corpus(request.question, request.history)
        latency_ms = int((time.monotonic() - t0) * 1000)
        background_tasks.add_task(
            _log_query,
            request.question,
            request.language,
            request.category,
            True,
            0,
            latency_ms,
            api_key,
        )
        return QueryResponse(
            answer=answer, sources=[], model="togolm-rag-v1", latency_ms=latency_ms
        )

    search_question = request.question
    if request.history:
        search_question = rewrite_question_with_history(request.question, request.history)

    try:
        chunks = retrieve(
            question=search_question,
            category=request.category,
            top_k=5,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Retrieval error: {e}")

    history_dicts = [{"role": m.role, "content": m.content} for m in request.history]
    answer = build_answer(request.question, chunks, history=history_dicts)
    latency_ms = int((time.monotonic() - t0) * 1000)

    background_tasks.add_task(
        _log_query,
        request.question,
        request.language,
        request.category,
        False,
        len(chunks),
        latency_ms,
        api_key,
    )
    return QueryResponse(
        answer=answer,
        sources=[Source(title=c.title, url=c.url, score=round(c.score, 4)) for c in chunks],
        model="togolm-rag-v1",
        latency_ms=latency_ms,
    )


def _stream_gemini(
    question: str,
    chunks: list[RetrievedChunk],
    history: list[HistoryMessage] | None = None,
):
    """Yield SSE data lines from Gemini streaming generation.

    Emits three event types:
      thinking — model reasoning tokens (thought=True parts)
      chunk    — answer tokens
    """
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    context = "\n\n".join(f"[{c.source} — {c.title}]\n{c.content[:600]}" for c in chunks)

    system_instruction = (
        "Tu es TogoLM, un assistant IA expert des connaissances togolaises.\n"
        "Tu maîtrises la législation, l'économie, l'éducation, l'histoire et l'actualité du Togo.\n\n"
        "Règles de réponse :\n"
        "1. Si le contexte fourni contient les informations nécessaires, base ta réponse dessus.\n"
        "2. Ne mets JAMAIS de citations inline dans le texte (pas de [source], pas de [domaine — titre]). "
        "Les sources sont affichées séparément par l'interface.\n"
        "3. Si le contexte est insuffisant ou hors-sujet, réponds quand même avec tes connaissances générales sur le Togo.\n"
        "4. Réponds toujours dans la langue de la question (français par défaut).\n"
        "5. Ne réponds jamais 'je n'ai pas suffisamment d'informations' sans fournir une réponse utile.\n"
        "6. Ne mentionne JAMAIS l'existence d'un 'corpus', d'une 'base de données' ou d'un 'contexte' "
        "dans ta réponse. Réponds directement, sans expliquer tes sources internes."
    )

    corpus_block = context if context else "(aucun document disponible)"

    history_block = ""
    if history:
        lines = []
        for m in history[-6:]:
            role = "Utilisateur" if m.role == "user" else "Assistant"
            lines.append(f"{role}: {m.content[:400]}")
        history_block = "HISTORIQUE DE LA CONVERSATION:\n" + "\n".join(lines) + "\n\n"

    prompt = f"{history_block}CONTEXTE :\n{corpus_block}\n\nQUESTION : {question}\n\nRÉPONSE :"

    for chunk in client.models.generate_content_stream(
        model="gemini-2.5-flash",
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=system_instruction,
            max_output_tokens=2048,
            thinking_config=types.ThinkingConfig(thinking_budget=2048),
        ),
    ):
        if not (
            chunk.candidates and chunk.candidates[0].content and chunk.candidates[0].content.parts
        ):
            continue
        for part in chunk.candidates[0].content.parts:
            if getattr(part, "thought", False) and part.text:
                yield f"data: {json.dumps({'type': 'thinking', 'text': part.text})}\n\n"
            elif part.text:
                yield f"data: {json.dumps({'type': 'chunk', 'text': part.text})}\n\n"


def _extractive_stream(chunks: list[RetrievedChunk]):
    """Yield a single SSE data line with the top extractive passage."""
    top = chunks[0]
    excerpt = top.content[:800].rsplit(" ", 1)[0] + "…" if len(top.content) > 800 else top.content
    text = f"{excerpt}\n\n[Source: {top.source}]"
    yield f"data: {json.dumps({'type': 'chunk', 'text': text})}\n\n"


@router.post("/query/stream")
def stream_query(
    request: QueryRequest,
    api_key: APIKeyRecord | str | None = Depends(get_api_key),
):
    """Stream a RAG answer via Server-Sent Events.

    Events (newline-delimited JSON after 'data: '):
      {type: 'chunk',   text: str}
      {type: 'sources', sources: [...], latency_ms: int}
      {type: 'error',   message: str}
    Terminated by: data: [DONE]
    """

    def generate():
        t0 = time.monotonic()

        if _is_off_topic(request.question):
            yield from _stream_without_corpus(request.question, request.history or [])
            latency_ms = int((time.monotonic() - t0) * 1000)
            yield f"data: {json.dumps({'type': 'sources', 'sources': [], 'latency_ms': latency_ms})}\n\n"
            yield "data: [DONE]\n\n"
            _log_query(
                request.question, request.language, request.category, True, 0, latency_ms, api_key
            )
            return

        # Rewrite the question using conversation history so the vector search
        # operates on a standalone, fully-resolved query instead of a pronoun-laden follow-up.
        search_question = request.question
        if request.history:
            search_question = rewrite_question_with_history(request.question, request.history)

        try:
            chunks = retrieve(question=search_question, category=request.category, top_k=5)
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
            yield "data: [DONE]\n\n"
            return

        sources = [{"title": c.title, "url": c.url, "score": round(c.score, 4)} for c in chunks]

        gemini_key = os.getenv("GEMINI_API_KEY", "")
        use_gemini = bool(gemini_key) and len(gemini_key) > 10

        if use_gemini:
            try:
                yield from _stream_gemini(request.question, chunks, request.history or [])
            except Exception:
                if chunks:
                    yield from _extractive_stream(chunks)
                else:
                    no_result = "Je n'ai pas trouvé de documents pertinents dans le corpus pour cette question."
                    yield f"data: {json.dumps({'type': 'chunk', 'text': no_result})}\n\n"
        elif chunks:
            yield from _extractive_stream(chunks)
        else:
            no_result = (
                "Je n'ai pas trouvé de documents pertinents dans le corpus pour cette question."
            )
            yield f"data: {json.dumps({'type': 'chunk', 'text': no_result})}\n\n"

        latency_ms = int((time.monotonic() - t0) * 1000)
        yield f"data: {json.dumps({'type': 'sources', 'sources': sources, 'latency_ms': latency_ms})}\n\n"
        yield "data: [DONE]\n\n"
        _log_query(
            request.question,
            request.language,
            request.category,
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
