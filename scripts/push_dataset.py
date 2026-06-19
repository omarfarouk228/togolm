"""
Export the TogoLM corpus from PostgreSQL and push it to HuggingFace Hub.

Usage:
    python scripts/push_dataset.py                          # push to default repo
    python scripts/push_dataset.py --repo togolm/togolm-corpus-v1
    python scripts/push_dataset.py --token <HF_TOKEN>       # or set HF_TOKEN env var

Requires: datasets huggingface_hub
    uv pip install datasets huggingface_hub
"""

import argparse
import os
from datetime import date, datetime

import psycopg2
from dotenv import load_dotenv

load_dotenv()

DEFAULT_REPO = "togolm/togolm-corpus-v1"

COLUMNS = [
    "id",
    "source",
    "url",
    "category",
    "subcategory",
    "title",
    "clean_content",
    "word_count",
    "language",
    "published_at",
    "collected_at",
]


def _get_conn():
    return psycopg2.connect(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=int(os.getenv("POSTGRES_PORT", "5432")),
        dbname=os.getenv("POSTGRES_DB", "togolm"),
        user=os.getenv("POSTGRES_USER"),
        password=os.getenv("POSTGRES_PASSWORD") or None,
    )


def _fetch_documents(conn) -> list[dict]:
    sql = f"""
        SELECT {", ".join(COLUMNS)}
        FROM documents
        WHERE status = 'active'
          AND clean_content IS NOT NULL
        ORDER BY source, collected_at DESC
    """
    with conn.cursor() as cur:
        cur.execute(sql)
        cols = [d[0] for d in cur.description]
        rows = cur.fetchall()

    records = []
    for row in rows:
        record = {}
        for col, val in zip(cols, row):
            # Convert non-serializable types to strings
            if isinstance(val, (datetime, date)):
                record[col] = val.isoformat()
            else:
                record[col] = val
        records.append(record)
    return records


def push(repo_id: str = DEFAULT_REPO, token: str | None = None, private: bool = False) -> str:
    try:
        from datasets import Dataset
    except ImportError:
        raise SystemExit("Missing dependency: uv pip install datasets huggingface_hub")

    token = token or os.environ.get("HF_TOKEN")
    if not token:
        raise SystemExit("HuggingFace token required. Set HF_TOKEN env var or pass --token.")

    print("==> Fetching documents from PostgreSQL...")
    conn = _get_conn()
    records = _fetch_documents(conn)
    conn.close()
    print(f"    {len(records)} active documents fetched.")

    print("==> Building HuggingFace Dataset...")
    dataset = Dataset.from_list(records)
    print(f"    {dataset}")

    print(f"==> Pushing to https://huggingface.co/datasets/{repo_id} ...")
    dataset.push_to_hub(
        repo_id,
        token=token,
        private=private,
        commit_message=f"Update corpus — {len(records)} documents",
    )

    url = f"https://huggingface.co/datasets/{repo_id}"
    print(f"\n✅ Dataset published: {url}")
    return url


def main():
    parser = argparse.ArgumentParser(description="Push TogoLM corpus to HuggingFace Hub")
    parser.add_argument(
        "--repo",
        type=str,
        default=DEFAULT_REPO,
        help=f"HuggingFace dataset repo (default: {DEFAULT_REPO})",
    )
    parser.add_argument(
        "--token",
        type=str,
        default=None,
        help="HuggingFace API token (default: HF_TOKEN env var)",
    )
    parser.add_argument(
        "--private",
        action="store_true",
        default=False,
        help="Push as a private dataset",
    )
    args = parser.parse_args()

    push(repo_id=args.repo, token=args.token, private=args.private)


if __name__ == "__main__":
    main()
