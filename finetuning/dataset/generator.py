"""
Generate Q&A pairs from the TogoLM corpus for supervised fine-tuning.

Reads documents from PostgreSQL, sends each one to Gemini with a generation
prompt, and returns structured Q&A pairs ready for formatting.

Usage:
    uv run python -m finetuning.dataset.generator --limit 50 --out finetuning/datasets/qa_raw.jsonl
    uv run python -m finetuning.dataset.generator --source jo.gouv.tg --pairs-per-doc 5
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


def _generate_pairs(doc: dict, n: int, client, types) -> list[QAPair]:
    """Call Gemini to generate Q&A pairs for one document."""
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

    for attempt in range(3):
        try:
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt,
                config=types.GenerateContentConfig(
                    max_output_tokens=800,
                    temperature=0.7,
                ),
            )
            raw = response.text.strip()
            # Strip markdown code fences if present
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
            raw = raw.strip()

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
            if attempt < 2:
                time.sleep(2)
                continue
            return []
        except Exception as e:
            msg = str(e)
            if "429" in msg or "RESOURCE_EXHAUSTED" in msg:
                wait = 2 ** attempt * 20
                print(f"  [RATE LIMIT] Waiting {wait}s...")
                time.sleep(wait)
            else:
                print(f"  [ERROR] {doc['source']} — {e}")
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

    with open(output, "a", encoding="utf-8") as f:
        for doc in tqdm(docs, desc="Generating"):
            words = len((doc["clean_content"] or "").split())
            if words < MIN_DOC_WORDS:
                continue

            pairs = _generate_pairs(doc, pairs_per_doc, client, types)
            for pair in pairs:
                f.write(json.dumps(asdict(pair), ensure_ascii=False) + "\n")
                total_pairs += 1

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
