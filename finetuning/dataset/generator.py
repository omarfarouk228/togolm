"""
Generate Q&A pairs from the TogoLM corpus for supervised fine-tuning.

Reads documents from PostgreSQL, sends each one to Gemini with a generation
prompt, and returns structured Q&A pairs ready for formatting.

The output file is appended to so interrupted runs can be resumed safely
using --offset N (where N = number of docs already processed).

NOTE FOR FREE-TIER USERS: gemini-2.5-flash is limited to ~20 requests/day
on the free tier. Run incrementally using --limit 20 per day and track
progress with --offset N.

Usage:
    # Paid API key — process a large batch in one run
    python -m finetuning.dataset.generator --source jo.gouv.tg --limit 500

    # Free tier — process 20 docs per day, resuming each time
    python -m finetuning.dataset.generator --source jo.gouv.tg --limit 20 --offset 0
    python -m finetuning.dataset.generator --source jo.gouv.tg --limit 20 --offset 20
    # (script prints the exact --offset to use on quota exhaustion)

    # After all sources: format the dataset
    python -m finetuning.dataset.formatter --format alpaca
"""

import argparse
import json
import os
import time
from dataclasses import asdict, dataclass
from pathlib import Path

import psycopg2
from dotenv import load_dotenv
from tqdm import tqdm

load_dotenv()

PAIRS_PER_DOC = 3   # Q&A pairs to generate per document
MIN_DOC_WORDS = 50  # Skip documents shorter than this

SYSTEM_PROMPT = """Tu es TogoLM, un assistant IA expert des connaissances togolaises.
Tu maîtrises la législation, l'économie, l'éducation, l'histoire et l'actualité du Togo.
Tu réponds toujours en te basant sur les faits fournis dans le contexte."""

GENERATION_PROMPT = """Voici un extrait de document togolais :

SOURCE : {source}
CATÉGORIE : {category}
TITRE : {title}

CONTENU :
{content}

---
Génère exactement {n} paires question-réponse en français basées uniquement sur ce contenu.
Chaque paire doit :
- Poser une question factuelle qu'un citoyen togolais pourrait poser
- Donner une réponse complète et précise basée sur le contenu
- Être indépendante (compréhensible sans lire les autres paires)

Réponds UNIQUEMENT en JSON valide, sans texte autour, avec ce format exact :
[
  {{
    "question": "...",
    "answer": "..."
  }},
  ...
]"""


@dataclass
class QAPair:
    question: str
    answer: str
    source: str
    category: str
    title: str
    doc_id: str


def _get_conn() -> psycopg2.extensions.connection:
    return psycopg2.connect(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=int(os.getenv("POSTGRES_PORT", "5432")),
        dbname=os.getenv("POSTGRES_DB", "togolm"),
        user=os.getenv("POSTGRES_USER"),
        password=os.getenv("POSTGRES_PASSWORD") or None,
    )


def _fetch_documents(
    conn,
    source: str | None,
    category: str | None,
    limit: int,
    offset: int,
) -> list[dict]:
    sql = """
        SELECT id, source, category, title, clean_content
        FROM documents
        WHERE status = 'active'
          AND clean_content IS NOT NULL
          AND LENGTH(clean_content) > 200
    """
    params: list = []
    if source:
        sql += " AND source = %s"
        params.append(source)
    if category:
        sql += " AND category = %s"
        params.append(category)
    sql += " ORDER BY source, id LIMIT %s OFFSET %s"
    params += [limit, offset]

    with conn.cursor() as cur:
        cur.execute(sql, params)
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]


# Model fallback chain — used when a model's daily quota (RPD) is exhausted.
# On the free tier, gemini-2.5-flash is limited to ~20 RPD; on a paid key the
# daily limits are much higher but per-minute limits (RPM) still apply.
_MODELS = ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-2.5-flash-lite"]
_active_model_idx = 0  # tracks which model in _MODELS is currently in use


def _is_rpm_error(msg: str) -> bool:
    """Return True for per-minute rate limits (temporary) vs daily quota (permanent)."""
    low = msg.lower()
    return "per_minute" in low or "per minute" in low or "rate_limit_exceeded" in low


def _generate_pairs(doc: dict, n: int, client, types) -> list[QAPair]:
    """Call Gemini to generate Q&A pairs for one document.

    Handles two kinds of 429 errors differently:
    - RPM (per-minute rate limit): waits with exponential backoff, retries same model.
    - RPD (daily quota exhausted): switches to next model in the fallback chain.
    """
    global _active_model_idx

    content = doc["clean_content"]
    # Use first 2000 words to stay within context limits and avoid long docs
    words = content.split()
    if len(words) > 2000:
        content = " ".join(words[:2000])

    prompt = GENERATION_PROMPT.format(
        source=doc["source"],
        category=doc["category"] or "général",
        title=doc["title"] or "",
        content=content,
        n=n,
    )

    for attempt in range(5):
        model = _MODELS[_active_model_idx]
        try:
            response = client.models.generate_content(
                model=model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    max_output_tokens=2048,
                    temperature=0.7,
                ),
            )
            # Guard: safety filter may leave response.text None or raise
            try:
                raw = response.text
            except Exception:
                raw = None

            if not raw:
                # Blocked by safety filter or empty response
                finish = getattr(response, "candidates", None)
                reason = (
                    finish[0].finish_reason if finish else "unknown"
                ) if finish else "no candidates"
                print(f"  [BLOCKED] doc {doc['id']} — finish_reason: {reason}")
                return []

            raw = raw.strip()

            # Strip markdown code fences if present
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
            raw = raw.strip()

            # Try to extract a JSON array if model added preamble text
            if not raw.startswith("["):
                start = raw.find("[")
                end = raw.rfind("]")
                if start != -1 and end != -1:
                    raw = raw[start : end + 1]

            pairs_data = json.loads(raw)
            return [
                QAPair(
                    question=p["question"].strip(),
                    answer=p["answer"].strip(),
                    source=doc["source"],
                    category=doc["category"] or "",
                    title=doc["title"] or "",
                    doc_id=str(doc["id"]),
                )
                for p in pairs_data
                if p.get("question") and p.get("answer")
            ]
        except json.JSONDecodeError:
            if attempt < 4:
                time.sleep(2)
                continue
            # Print a sample of what the model returned so we can diagnose
            preview = repr(raw[:200]) if raw else "<empty>"
            print(f"  [WARN] JSON parse failed for doc {doc['id']} — response: {preview}")
            return []
        except Exception as e:
            msg = str(e)
            if "429" in msg or "RESOURCE_EXHAUSTED" in msg:
                if _is_rpm_error(msg):
                    # Temporary per-minute rate limit — back off and retry same model
                    wait = min(30 * (attempt + 1), 120)
                    print(f"  [RPM] {model} rate limit — waiting {wait}s (attempt {attempt + 1}/5)...")
                    time.sleep(wait)
                    continue
                else:
                    # Daily quota exhausted — switch to next model in fallback chain
                    if _active_model_idx + 1 < len(_MODELS):
                        _active_model_idx += 1
                        next_model = _MODELS[_active_model_idx]
                        print(f"  [QUOTA] {model} daily quota hit — switching to {next_model}")
                        continue
                    # All models exhausted — raise so caller can handle
                    raise RuntimeError("QUOTA_EXHAUSTED: all Gemini models at daily quota")
            else:
                print(f"  [ERROR] {doc['source']} — {type(e).__name__}: {e}")
                return []
    return []


def generate(
    limit: int = 100,
    offset: int = 0,
    source: str | None = None,
    category: str | None = None,
    pairs_per_doc: int = PAIRS_PER_DOC,
    output: Path = Path("finetuning/datasets/qa_raw.jsonl"),
) -> int:
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

    conn = _get_conn()
    docs = _fetch_documents(conn, source, category, limit, offset)
    conn.close()

    print(f"Generating {pairs_per_doc} Q&A pairs for {len(docs)} documents...")

    output.parent.mkdir(parents=True, exist_ok=True)
    total_pairs = 0
    processed_docs = 0  # docs actually attempted (used to compute next --offset)

    with open(output, "a", encoding="utf-8") as f:
        for doc in tqdm(docs, desc="Generating"):
            words = len((doc["clean_content"] or "").split())
            if words < MIN_DOC_WORDS:
                processed_docs += 1  # count even skipped docs so offset stays aligned
                continue

            try:
                pairs = _generate_pairs(doc, pairs_per_doc, client, types)
            except RuntimeError as e:
                if "QUOTA_EXHAUSTED" in str(e):
                    next_offset = offset + processed_docs
                    print(
                        f"\n[QUOTA EXHAUSTED] Daily Gemini quota reached after "
                        f"{total_pairs} pairs from {processed_docs} docs.\n"
                        f"Resume tomorrow with:\n"
                        f"  python -m finetuning.dataset.generator"
                        f" --offset {next_offset}"
                        + (f" --source {source}" if source else "")
                        + (f" --category {category}" if category else "")
                        + f" --limit {limit}"
                    )
                    break
                raise

            for pair in pairs:
                f.write(json.dumps(asdict(pair), ensure_ascii=False) + "\n")
                total_pairs += 1
            if pairs:
                f.flush()  # Persist to disk immediately, don't wait for buffer

            processed_docs += 1
            time.sleep(0.3)  # Rate limit headroom

    print(f"Done: {total_pairs} Q&A pairs written to {output}")
    return total_pairs


def main():
    parser = argparse.ArgumentParser(description="Generate Q&A pairs from TogoLM corpus")
    parser.add_argument("--limit", type=int, default=100, help="Max documents to process")
    parser.add_argument("--offset", type=int, default=0, help="Skip first N documents")
    parser.add_argument("--source", type=str, default=None, help="Filter by source domain")
    parser.add_argument("--category", type=str, default=None, help="Filter by category")
    parser.add_argument("--pairs-per-doc", type=int, default=PAIRS_PER_DOC)
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("finetuning/datasets/qa_raw.jsonl"),
        help="Output JSONL file",
    )
    args = parser.parse_args()

    generate(
        limit=args.limit,
        offset=args.offset,
        source=args.source,
        category=args.category,
        pairs_per_doc=args.pairs_per_doc,
        output=args.out,
    )


if __name__ == "__main__":
    main()
