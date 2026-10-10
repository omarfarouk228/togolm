"""
Load a batch of Éwé/Kabiyè answers into the native-speaker review queue.

Input: a JSON list of {"question_fr", "answers": {"fr", "ee", "kbp"}} objects
(the shape produced when generating a review batch with the query pipeline).
Each Éwé and Kabiyè answer becomes one item, with the French answer attached
as reference. Re-running is safe: duplicates are skipped.

Usage:
    uv run python scripts/contribute/seed_review_items.py batch.json
"""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from db import get_conn  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description="Seed the language review queue")
    parser.add_argument("file", type=Path)
    args = parser.parse_args()

    batch = json.loads(args.file.read_text())
    added = 0
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            for entry in batch:
                question_fr = entry["question_fr"]
                answers = entry["answers"]
                for language in ("ee", "kbp"):
                    if not answers.get(language):
                        continue
                    cur.execute(
                        """
                        INSERT INTO language_review_items
                            (language, question, question_fr, answer, answer_fr, origin)
                        VALUES (%s, %s, %s, %s, %s, 'seed')
                        ON CONFLICT DO NOTHING
                        """,
                        (
                            language,
                            question_fr,
                            question_fr,
                            answers[language],
                            answers.get("fr"),
                        ),
                    )
                    added += cur.rowcount
        conn.commit()
    finally:
        conn.close()
    print(f"{added} items added")


if __name__ == "__main__":
    main()
