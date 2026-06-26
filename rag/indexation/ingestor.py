"""
Ingest scraped JSONL documents into PostgreSQL + pgvector.

Usage:
    uv run python -m rag.indexation.ingestor corpus/datasets/service_public.jsonl
    uv run python -m rag.indexation.ingestor corpus/datasets/*.jsonl --no-embed
"""

import argparse
import json
import os
import re
import time
from pathlib import Path

import psycopg2
from dotenv import load_dotenv
from pgvector.psycopg2 import register_vector
from tqdm import tqdm

from rag.indexation.chunker import chunk_by_words
from rag.indexation.cleaner import clean_document, is_useful
from rag.indexation.embedder import get_embedder, max_chunk_words

load_dotenv(Path(__file__).resolve().parents[2] / ".env")

EMBED_BATCH_SIZE = 20
# Sized to the embedding model's token window so chunks are never silently
# truncated at embed time (see rag.indexation.embedder.max_chunk_words).
CHUNK_SIZE = max_chunk_words()  # words per chunk
CHUNK_OVERLAP = max(1, CHUNK_SIZE // 8)  # ~12% overlap between consecutive chunks

# Module-level embedder cache — avoids re-instantiating (and re-checking Gemini quota) per batch
_embedder = None

FR_MONTHS = {
    "janvier": "01",
    "février": "02",
    "mars": "03",
    "avril": "04",
    "mai": "05",
    "juin": "06",
    "juillet": "07",
    "août": "08",
    "septembre": "09",
    "octobre": "10",
    "novembre": "11",
    "décembre": "12",
}
FR_DATE_RE = re.compile(r"(\d{1,2})\s+(" + "|".join(FR_MONTHS) + r")\s+(\d{4})", re.IGNORECASE)


def normalize_date(raw: str | None) -> str | None:
    """Convert any date string to ISO YYYY-MM-DD, or return None."""
    if not raw:
        return None
    raw = raw.strip()
    # Already ISO
    if re.match(r"^\d{4}-\d{2}-\d{2}$", raw):
        return raw
    # French long format: "28 avril 2025"
    m = FR_DATE_RE.search(raw)
    if m:
        d, month_fr, y = m.group(1), m.group(2).lower(), m.group(3)
        return f"{y}-{FR_MONTHS[month_fr]}-{d.zfill(2)}"
    # ISO-like with time: "2026-04-29T..." → truncate
    if re.match(r"^\d{4}-\d{2}-\d{2}T", raw):
        return raw[:10]
    return None


def get_connection() -> psycopg2.extensions.connection:
    password = os.getenv("POSTGRES_PASSWORD") or None
    conn = psycopg2.connect(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=int(os.getenv("POSTGRES_PORT", "5432")),
        dbname=os.getenv("POSTGRES_DB", "togolm"),
        user=os.getenv("POSTGRES_USER"),
        password=password,
    )
    register_vector(conn)
    return conn


def embed_batch(texts: list[str]) -> list[list[float]]:
    """
    Embed a batch of texts.
    Uses a module-level cached embedder to avoid re-checking Gemini quota every batch.
    Retries with exponential backoff on rate limit; permanently falls back to
    sentence-transformers if Gemini quota is exhausted for the rest of the run.
    """
    global _embedder
    if _embedder is None:
        _embedder = get_embedder()

    for attempt in range(4):
        try:
            return _embedder.encode(texts)
        except Exception as e:
            msg = str(e)
            is_rate_limit = "429" in msg or "RESOURCE_EXHAUSTED" in msg
            is_transient = "503" in msg or "UNAVAILABLE" in msg or "502" in msg or "500" in msg
            if is_rate_limit or is_transient:
                wait = 2**attempt * 15  # 15s, 30s, 60s, 120s
                if attempt < 3:
                    label = "RATE LIMIT" if is_rate_limit else "TRANSIENT ERROR"
                    print(f"  [{label}] Waiting {wait}s before retry {attempt + 1}/3...")
                    time.sleep(wait)
                else:
                    print(
                        "  [GEMINI UNAVAILABLE] Switching to local model for this run"
                    )
                    from rag.indexation.embedder import LocalEmbedder

                    _embedder = LocalEmbedder()
                    return _embedder.encode(texts)
            else:
                raise
    return _embedder.encode(texts)


def upsert_document(cur, doc: dict) -> str:
    """Insert or update a document row, return its UUID."""
    clean = doc.get("clean_content", "")
    cur.execute(
        """
        INSERT INTO documents
            (source, url, category, subcategory, title,
             raw_content, clean_content, language, word_count,
             published_at, metadata, status)
        VALUES
            (%(source)s, %(url)s, %(category)s, %(subcategory)s, %(title)s,
             %(raw_content)s, %(clean_content)s, %(language)s, %(word_count)s,
             %(published_at)s, %(metadata)s, 'active')
        ON CONFLICT (url) DO UPDATE SET
            title         = EXCLUDED.title,
            raw_content   = EXCLUDED.raw_content,
            clean_content = EXCLUDED.clean_content,
            word_count    = EXCLUDED.word_count,
            metadata      = EXCLUDED.metadata,
            updated_at    = NOW()
        RETURNING id
        """,
        {
            "source": doc.get("source", ""),
            "url": doc.get("url", ""),
            "category": doc.get("category", ""),
            "subcategory": doc.get("subcategory", ""),
            "title": doc.get("title", ""),
            "raw_content": doc.get("raw_content", ""),
            "clean_content": clean,
            "language": doc.get("language", "fr"),
            "word_count": len(clean.split()) if clean else 0,
            "published_at": normalize_date(doc.get("published_at")),
            "metadata": json.dumps(doc.get("metadata", {})),
        },
    )
    return cur.fetchone()[0]


def upsert_chunks(
    cur, document_id: str, chunks_text: list[str], embeddings: list[list[float] | None]
) -> None:
    """Delete existing chunks for a document, then insert fresh ones."""
    cur.execute("DELETE FROM chunks WHERE document_id = %s", (document_id,))
    for idx, (text, emb) in enumerate(zip(chunks_text, embeddings)):
        cur.execute(
            """
            INSERT INTO chunks (document_id, chunk_index, content, word_count, embedding)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (document_id, idx, text, len(text.split()), emb),
        )


def process_file(jsonl_path: Path, embed: bool, conn) -> tuple[int, int, int]:
    """
    Process one JSONL file.
    Returns (total, inserted, skipped) counts.
    """
    with open(jsonl_path, encoding="utf-8") as f:
        raw_docs = [json.loads(line) for line in f if line.strip()]

    total = len(raw_docs)
    inserted = 0
    skipped = 0

    # Clean all documents first
    cleaned_docs = []
    for doc in raw_docs:
        clean = clean_document(doc.get("raw_content", ""))
        if not is_useful(clean):
            skipped += 1
            continue
        doc["clean_content"] = clean
        cleaned_docs.append(doc)

    if not cleaned_docs:
        return total, 0, skipped

    with conn.cursor() as cur:
        for doc in tqdm(cleaned_docs, desc=jsonl_path.name):
            doc_id = upsert_document(cur, doc)

            # Split into chunks
            raw_chunks = chunk_by_words(
                doc["clean_content"],
                doc_id,
                chunk_size=CHUNK_SIZE,
                overlap=CHUNK_OVERLAP,
            )
            chunk_texts = [c.text for c in raw_chunks]

            chunk_embeddings: list[list[float] | None] = [None] * len(chunk_texts)
            if embed and chunk_texts:
                for i in range(0, len(chunk_texts), EMBED_BATCH_SIZE):
                    batch = chunk_texts[i : i + EMBED_BATCH_SIZE]
                    batch_embs = embed_batch(batch)
                    for j, emb in enumerate(batch_embs):
                        chunk_embeddings[i + j] = emb
                    if i + EMBED_BATCH_SIZE < len(chunk_texts):
                        time.sleep(0.5)  # Rate limit headroom

            upsert_chunks(cur, doc_id, chunk_texts, chunk_embeddings)
            inserted += 1
            conn.commit()  # commit per-document so partial progress survives crashes

    return total, inserted, skipped


def main():
    parser = argparse.ArgumentParser(description="Ingest scraped JSONL into PostgreSQL + pgvector")
    parser.add_argument("files", nargs="+", type=Path, help="JSONL files to ingest")
    parser.add_argument(
        "--no-embed",
        action="store_true",
        help="Skip embedding generation (insert text only, useful without Gemini API key)",
    )
    args = parser.parse_args()

    conn = get_connection()
    print(
        f"Connected to PostgreSQL — {'embeddings ON' if not args.no_embed else 'embeddings OFF'}\n"
    )

    total_all = inserted_all = skipped_all = 0

    failed_files = []
    for path in args.files:
        if not path.exists():
            print(f"[SKIP] {path} not found")
            continue
        print(f"Processing {path}...")
        try:
            t, i, s = process_file(path, embed=not args.no_embed, conn=conn)
            print(f"  Done: {i} inserted, {s} skipped (below min length), {t} total\n")
            total_all += t
            inserted_all += i
            skipped_all += s
        except Exception as exc:
            conn.rollback()
            print(f"  [ERROR] {path.name} failed: {exc}\n")
            failed_files.append(path.name)

    if failed_files:
        print(f"Failed files ({len(failed_files)}): {', '.join(failed_files)}")

    conn.close()
    print(f"Summary: {inserted_all}/{total_all} documents ingested ({skipped_all} skipped)")


if __name__ == "__main__":
    main()
