"""
Backfill embeddings for documents that have no embedded chunks yet.

Reads directly from PostgreSQL — no need to re-ingest JSONL files.
Safe to interrupt and re-run: already-embedded docs are skipped.

Usage:
    uv run python scripts/embed_missing.py
    uv run python scripts/embed_missing.py --source jo.gouv.tg
    uv run python scripts/embed_missing.py --limit 500
"""

import argparse
import os
import sys
import time
from pathlib import Path

import psycopg2
from dotenv import load_dotenv
from pgvector.psycopg2 import register_vector
from tqdm import tqdm

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")
sys.path.insert(0, str(ROOT))

from rag.indexation.chunker import chunk_by_words  # noqa: E402
from rag.indexation.embedder import get_embedder, max_chunk_words  # noqa: E402

EMBED_BATCH_SIZE = 20
# Must match the ingestor: sized to the embedding model's token window so chunks
# are never silently truncated (see rag.indexation.embedder.max_chunk_words).
CHUNK_SIZE = max_chunk_words()
CHUNK_OVERLAP = max(1, CHUNK_SIZE // 8)


def get_connection():
    conn = psycopg2.connect(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=int(os.getenv("POSTGRES_PORT", "5432")),
        dbname=os.getenv("POSTGRES_DB", "togolm"),
        user=os.getenv("POSTGRES_USER"),
        password=os.getenv("POSTGRES_PASSWORD"),
    )
    register_vector(conn)
    return conn


def fetch_unembedded(conn, source=None, limit=None) -> list[tuple]:
    """Return (id, clean_content, source) for docs with no embedded chunks."""
    where = [
        "d.status = 'active'",
        "d.clean_content IS NOT NULL",
        "length(d.clean_content) > 100",
        "NOT EXISTS (SELECT 1 FROM chunks c WHERE c.document_id = d.id AND c.embedding IS NOT NULL)",
    ]
    params = []
    if source:
        where.append("d.source = %s")
        params.append(source)

    sql = f"""
        SELECT d.id, d.clean_content, d.source
        FROM documents d
        WHERE {" AND ".join(where)}
        ORDER BY d.source, d.id
    """
    if limit:
        sql += f" LIMIT {int(limit)}"

    with conn.cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchall()


def embed_doc(conn, embedder, doc_id: str, clean_content: str):
    """Chunk + embed one document, replace its chunks in DB."""
    chunks = chunk_by_words(clean_content, doc_id, chunk_size=CHUNK_SIZE, overlap=CHUNK_OVERLAP)
    chunk_texts = [c.text for c in chunks]
    if not chunk_texts:
        return 0

    # Embed in batches with retry/fallback handled by embed_batch
    embeddings = []
    for i in range(0, len(chunk_texts), EMBED_BATCH_SIZE):
        batch = chunk_texts[i : i + EMBED_BATCH_SIZE]
        for attempt in range(4):
            try:
                batch_embs = embedder.encode(batch)
                embeddings.extend(batch_embs)
                break
            except Exception as e:
                msg = str(e)
                if "429" in msg or "RESOURCE_EXHAUSTED" in msg:
                    wait = 2**attempt * 15
                    if attempt < 3:
                        tqdm.write(f"  [RATE LIMIT] wait {wait}s…")
                        time.sleep(wait)
                    else:
                        tqdm.write("  [RATE LIMIT] switching to local model")
                        from rag.indexation.embedder import LocalEmbedder

                        embedder.__class__ = LocalEmbedder
                        embedder._model = None
                        batch_embs = embedder.encode(batch)
                        embeddings.extend(batch_embs)
                else:
                    raise

    with conn.cursor() as cur:
        cur.execute("DELETE FROM chunks WHERE document_id = %s", (doc_id,))
        for idx, (text, emb) in enumerate(zip(chunk_texts, embeddings)):
            cur.execute(
                """
                INSERT INTO chunks (document_id, chunk_index, content, word_count, embedding)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (doc_id, idx, text, len(text.split()), emb),
            )
    conn.commit()
    return len(chunk_texts)


def main():
    parser = argparse.ArgumentParser(description="Backfill embeddings for un-embedded docs")
    parser.add_argument("--source", help="Only embed docs from this source")
    parser.add_argument("--limit", type=int, help="Max number of docs to process")
    args = parser.parse_args()

    conn = get_connection()
    embedder = get_embedder()
    embedder_name = type(embedder).__name__

    print(f"Embedder: {embedder_name}")
    print("Fetching un-embedded documents…")

    docs = fetch_unembedded(conn, source=args.source, limit=args.limit)
    print(f"Found {len(docs):,} documents to embed\n")

    if not docs:
        print("Nothing to do.")
        conn.close()
        return

    total_chunks = 0
    errors = 0
    start = time.time()

    for doc_id, clean_content, source in tqdm(docs, desc="Embedding", unit="doc"):
        try:
            n = embed_doc(conn, embedder, doc_id, clean_content)
            total_chunks += n
        except Exception as e:
            errors += 1
            tqdm.write(f"  [ERROR] {source} doc {doc_id}: {e}")

    elapsed = time.time() - start
    print(f"\nDone in {elapsed / 60:.1f} min")
    print(f"   Docs processed : {len(docs):,}")
    print(f"   Chunks created : {total_chunks:,}")
    print(f"   Errors         : {errors}")
    conn.close()


if __name__ == "__main__":
    main()
