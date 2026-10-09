"""
Retrieval quality check against the real corpus.

For each question in evals/retrieval_queries.jsonl, run rag.retrieval.retrieve
and count a hit when a returned chunk's URL or title matches the expected
pattern. Reports hit@k, MRR and latency. Read-only; needs DB access and, in
production, the Gemini key used for query embeddings.

Pipelines (--pipeline):
    api       question enriched like the query API does (default)
    filtered  same, but the inferred category is applied as a hard filter
    raw       the question as typed, no enrichment

Usage:
    uv run python scripts/eval/retrieval_eval.py [--pipeline api] [--top-k 5] [--verbose]
"""

import argparse
import json
import re
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from rag.retrieval import retrieve  # noqa: E402
from rag.retrieval.enrichment import enrich_query  # noqa: E402


def run_retrieval(question: str, pipeline: str, top_k: int):
    if pipeline == "raw":
        return retrieve(question, top_k=top_k)
    enriched = enrich_query(question)
    category = enriched.category if pipeline == "filtered" else None
    return retrieve(enriched.search_query, category=category, top_k=top_k)


def main():
    parser = argparse.ArgumentParser(description="Evaluate retrieval hit rate")
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--file", default=str(ROOT / "evals" / "retrieval_queries.jsonl"))
    parser.add_argument("--pipeline", choices=["api", "filtered", "raw"], default="api")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    cases = [json.loads(line) for line in Path(args.file).read_text().splitlines() if line.strip()]
    hits, reciprocal_ranks, latencies = 0, [], []
    for case in cases:
        pattern = re.compile(case["expect"], re.IGNORECASE)
        started = time.perf_counter()
        chunks = run_retrieval(case["question"], args.pipeline, args.top_k)
        latencies.append((time.perf_counter() - started) * 1000)
        rank = next(
            (i for i, c in enumerate(chunks, 1) if pattern.search(f"{c.url or ''} {c.title}")),
            None,
        )
        hits += rank is not None
        reciprocal_ranks.append(1 / rank if rank else 0.0)
        mark = f"#{rank}" if rank else "miss"
        print(f"{mark:>5}  {latencies[-1]:6.0f} ms  {case['question']}")
        if args.verbose:
            for c in chunks:
                print(f"         {c.score:.3f} {c.url}")
        time.sleep(0.5)  # stay under the embedding API rate limit

    n = len(cases)
    print(
        f"\n[{args.pipeline}] hit@{args.top_k}: {hits}/{n} ({hits / n:.0%})  "
        f"MRR: {statistics.mean(reciprocal_ranks):.3f}  "
        f"latency p50: {statistics.median(latencies):.0f} ms  max: {max(latencies):.0f} ms"
    )


if __name__ == "__main__":
    main()
