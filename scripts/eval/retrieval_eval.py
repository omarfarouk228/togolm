"""
Retrieval quality check against the real corpus (see rag.evaluation.retrieval).

Pipelines (--pipeline):
    api       question enriched like the query API does (default)
    filtered  same, but the inferred category is applied as a hard filter
    raw       the question as typed, no enrichment

Usage:
    uv run python scripts/eval/retrieval_eval.py [--pipeline api] [--top-k 5] [--verbose]
"""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from rag.evaluation.retrieval import DEFAULT_CASES, evaluate, load_cases  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description="Evaluate retrieval hit rate")
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--file", default=str(DEFAULT_CASES))
    parser.add_argument("--pipeline", choices=["api", "filtered", "raw"], default="api")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    report = evaluate(load_cases(Path(args.file)), pipeline=args.pipeline, top_k=args.top_k)
    for r in report["results"]:
        mark = f"#{r['rank']}" if r["rank"] else "miss"
        print(f"{mark:>5}  {r['latency_ms']:6d} ms  {r['question']}")
        if args.verbose:
            for url in r["top_urls"]:
                print(f"         {url}")
    print(
        f"\n[{report['pipeline']}] hit@{report['top_k']}: {report['hits']}/{report['cases']} "
        f"({report['hit_rate']:.0%})  MRR: {report['mrr']:.3f}  "
        f"latency p50: {report['latency_p50_ms']} ms  max: {report['latency_max_ms']} ms"
    )


if __name__ == "__main__":
    main()
