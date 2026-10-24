"""
Éwé / Kabiyè Wikipedia passages as wording references.

The model's command of Togo's national languages is uneven. For an answer in
Éwé or Kabiyè, the two passages of that language's Wikipedia (ee/kbp, in the
corpus with language "ee" / "kbp", never used as sources: see
rag.retrieval.search.RETRIEVAL_LANGUAGE) closest to the question are added to
the prompt, as real text to borrow vocabulary and spelling from.

Best-effort: any failure (embedding API, database) returns '' and the answer
is generated without them.
"""

import logging

from db import get_conn
from rag.generation.language_examples import LOCAL_LANGUAGES

logger = logging.getLogger("togolm.generation")

MAX_PASSAGES = 2
MAX_PASSAGE_CHARS = 500
LANGUAGE_NAMES = {"ee": "éwé", "kbp": "kabiyè"}


def reference_block(language: str, question: str) -> str:
    """Prompt section with `language` Wikipedia passages close to `question`, or ''."""
    if language not in LOCAL_LANGUAGES or not question.strip():
        return ""
    try:
        from rag.retrieval.search import _get_embedder

        embedder = _get_embedder()
        vector = embedder.encode_query(question)
        model_id = getattr(embedder, "model_id", None)
        conn = get_conn(vector=True)
        try:
            with conn.cursor() as cur:
                # A few thousand chunks: exact distances on a materialized
                # subset. Through the HNSW index, a filter this selective
                # (<1% of the chunks) would leave nothing to return.
                cur.execute(
                    """
                    WITH candidates AS MATERIALIZED (
                        SELECT d.title, c.content, c.embedding
                        FROM chunks c
                        JOIN documents d ON d.id = c.document_id
                        WHERE d.language = %s
                          AND d.status = 'active'
                          AND c.embedding IS NOT NULL
                          AND (%s::text IS NULL OR c.embedding_model = %s)
                    )
                    SELECT title, content FROM candidates
                    ORDER BY embedding <=> %s::vector
                    LIMIT %s
                    """,
                    (language, model_id, model_id, vector, MAX_PASSAGES),
                )
                rows = cur.fetchall()
        finally:
            conn.close()
    except Exception as e:
        logger.warning("No %s reference passages: %s", language, str(e)[:200])
        return ""
    if not rows:
        return ""

    def cut(text: str) -> str:
        text = " ".join(text.split())
        return text if len(text) <= MAX_PASSAGE_CHARS else text[:MAX_PASSAGE_CHARS] + "…"

    passages = "\n".join(f"- {title} : {cut(content)}" for title, content in rows)
    return (
        f"TEXTES DE RÉFÉRENCE EN {LANGUAGE_NAMES[language].upper()} (extraits de Wikipédia "
        "dans cette langue) : sers-t'en uniquement comme modèle de vocabulaire et "
        "d'orthographe, jamais comme source d'information.\n"
        f"{passages}\n\n"
    )
