"""
Drain the embedding backlog by hand (missing, legacy and stale-model vectors).

Same logic as the corpus.tasks.embed_pending_chunks Celery task, which runs it
every 15 minutes in production; see rag.indexation.backfill for details.
Safe to interrupt and re-run.

Usage:
    uv run python scripts/corpus/embed_missing.py --status
    uv run python scripts/corpus/embed_missing.py --limit 5000
"""

import argparse
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent.parent
load_dotenv(ROOT / ".env")
sys.path.insert(0, str(ROOT))

from rag.indexation.backfill import embed_pending, pending_counts  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description="Backfill chunk embeddings")
    parser.add_argument("--limit", type=int, default=4000, help="Max chunks to handle")
    parser.add_argument("--status", action="store_true", help="Only print the backlog size")
    args = parser.parse_args()

    print(f"Backlog: {pending_counts()}")
    if args.status:
        return
    print(embed_pending(max_chunks=args.limit))
    print(f"Backlog: {pending_counts()}")


if __name__ == "__main__":
    main()
