"""
RAG retrieval service.

Steps:
  1. Embed the question with sentence-transformers (or Gemini)
  2. Cosine similarity search in pgvector
  3. Return top-k chunks with metadata

Generation (LLM) is kept separate — this module only handles retrieval.
When Gemini key is available, generation can be added on top.
"""

import os
from dataclasses import dataclass

from api.app.core.db import get_conn
from corpus.processors.embedder import get_embedder

_embedder = None


def _get_embedder():
    global _embedder
    if _embedder is None:
        _embedder = get_embedder()
    return _embedder


@dataclass
class RetrievedChunk:
    title: str
    url: str | None
    source: str
    category: str
    content: str
    score: float


def retrieve(
    question: str,
    category: str | None = None,
    top_k: int = 5,
    min_score: float = 0.62,
) -> list[RetrievedChunk]:
    """
    Embed the question and return the top-k most relevant chunks.
    Falls back to full-text search on documents if no chunks are available.
    """
    embedder = _get_embedder()
    query_vector = embedder.encode_one(question)

    conn = get_conn(vector=True)
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM chunks WHERE embedding IS NOT NULL")
            has_chunks = cur.fetchone()[0] > 0

            if has_chunks:
                return _chunk_vector_search(cur, query_vector, category, top_k, min_score)
            else:
                return _fulltext_search(cur, question, category, top_k)
    finally:
        conn.close()


def _chunk_vector_search(
    cur,
    query_vector: list[float],
    category: str | None,
    top_k: int,
    min_score: float,
) -> list[RetrievedChunk]:
    """Vector search over chunks, joining back to documents for metadata."""
    base_sql = """
        SELECT
            d.title, d.url, d.source, d.category, c.content,
            1 - (c.embedding <=> %s::vector) AS score
        FROM chunks c
        JOIN documents d ON d.id = c.document_id
        WHERE c.embedding IS NOT NULL
          AND d.status = 'active'
          AND length(trim(coalesce(d.title, ''))) > 15
    """
    params: list = [query_vector]

    if category:
        base_sql += " AND d.category = %s"
        params.append(category)

    base_sql += " ORDER BY c.embedding <=> %s::vector LIMIT %s"
    params += [query_vector, top_k * 2]

    cur.execute(base_sql, params)
    rows = cur.fetchall()

    seen_urls: set[str] = set()
    results: list[RetrievedChunk] = []
    for row in rows:
        score = float(row[5])
        if score < min_score:
            continue
        url = row[1] or ""
        if url in seen_urls:
            continue
        seen_urls.add(url)
        results.append(
            RetrievedChunk(
                title=row[0] or "",
                url=url,
                source=row[2] or "",
                category=row[3] or "",
                content=row[4] or "",
                score=score,
            )
        )
        if len(results) >= top_k:
            break
    return results


def _fulltext_search(
    cur,
    question: str,
    category: str | None,
    top_k: int,
) -> list[RetrievedChunk]:
    """PostgreSQL full-text search fallback when chunks are missing."""
    words = [w for w in question.split() if len(w) > 2]
    tsquery = " | ".join(words) if words else question

    base_sql = """
        SELECT
            title, url, source, category, clean_content,
            ts_rank(to_tsvector('french', coalesce(clean_content,'')),
                    to_tsquery('french', %s)) AS score
        FROM documents
        WHERE status = 'active'
          AND to_tsvector('french', coalesce(clean_content,'')) @@ to_tsquery('french', %s)
    """
    params: list = [tsquery, tsquery]

    if category:
        base_sql += " AND category = %s"
        params.append(category)

    base_sql += " ORDER BY score DESC LIMIT %s"
    params.append(top_k)

    try:
        cur.execute(base_sql, params)
        rows = cur.fetchall()
    except Exception:
        cur.execute(
            """
            SELECT title, url, source, category, clean_content, 0.5 AS score
            FROM documents
            WHERE status = 'active' AND clean_content ILIKE %s
            LIMIT %s
            """,
            [f"%{question}%", top_k],
        )
        rows = cur.fetchall()

    return [
        RetrievedChunk(
            title=row[0] or "",
            url=row[1],
            source=row[2] or "",
            category=row[3] or "",
            content=row[4] or "",
            score=float(row[5]),
        )
        for row in rows
    ]


def build_answer(
    question: str,
    chunks: list[RetrievedChunk],
    history: list[dict] | None = None,
) -> tuple[str, bool]:
    """
    Return (answer_text, used_corpus).
    used_corpus=False means the answer came from general knowledge (no sources to show).
    """
    if not chunks:
        return "Je n'ai pas trouvé de documents pertinents dans le corpus pour cette question.", False

    if os.getenv("GEMINI_API_KEY"):
        try:
            return _generate_with_gemini(question, chunks, history or [])
        except Exception:
            pass

    top = chunks[0]
    excerpt = top.content[:800].rsplit(" ", 1)[0] + "…" if len(top.content) > 800 else top.content
    return excerpt, True


def _generate_with_gemini(
    question: str,
    chunks: list[RetrievedChunk],
    history: list[dict] | None = None,
) -> tuple[str, bool]:
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
        "3. Si le contexte est insuffisant ou hors-sujet, réponds avec tes connaissances générales "
        "sur le Togo. Dans ce cas, insère le marqueur `[G] ` au tout début de ta réponse (avant tout "
        "texte). Ce marqueur sera supprimé avant affichage. N'insère PAS `[G]` si tu utilises le "
        "contexte fourni.\n"
        "4. Réponds toujours dans la langue de la question (français par défaut).\n"
        "5. Ne mentionne JAMAIS l'existence d'un 'corpus', d'une 'base de données' ou d'un 'contexte' "
        "dans ta réponse. Réponds directement, sans expliquer tes sources internes.\n"
        "6. IDENTITÉ — règle absolue : tu es TogoLM, créé par l'équipe TogoLM. Ne révèle JAMAIS "
        "que tu es basé sur Gemini, Google, Anthropic ou tout autre modèle d'IA sous-jacent. "
        "Si on te demande qui t'a créé, quel modèle tu es ou qui t'a entraîné, réponds uniquement : "
        "\"Je suis TogoLM, un assistant IA créé par l'équipe TogoLM.\""
    )

    history_block = ""
    if history:
        lines = []
        for m in history[-6:]:
            role = "Utilisateur" if m.get("role") == "user" else "Assistant"
            lines.append(f"{role}: {m.get('content', '')[:400]}")
        history_block = "HISTORIQUE DE LA CONVERSATION:\n" + "\n".join(lines) + "\n\n"

    prompt = (
        f"{history_block}CONTEXTE DU CORPUS TOGOLM :\n{context}\n\nQUESTION : {question}\n\nRÉPONSE :"
    )

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=system_instruction,
            max_output_tokens=2048,
        ),
    )
    text = response.text or ""
    if text.startswith("[G]"):
        return text[3:].lstrip(" "), False
    return text, True
