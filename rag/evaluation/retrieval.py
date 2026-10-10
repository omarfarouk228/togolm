"""
Retrieval quality check against the real corpus.

Each case in evals/retrieval_queries.jsonl is a real question plus a regex
that a relevant source's URL or title must match. The question goes through
the same enrichment as the query API, then rag.retrieval.retrieve; a case is
a hit when a returned chunk matches. Reports hit@k, MRR and latency.

Used by scripts/eval/retrieval_eval.py (by hand) and by the weekly
corpus.tasks.run_retrieval_eval task, whose results the admin shows.
"""

import json
import re
import statistics
import time
from datetime import UTC, datetime
from pathlib import Path

from rag.retrieval import retrieve
from rag.retrieval.enrichment import enrich_query

ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_CASES = ROOT / "evals" / "retrieval_queries.jsonl"
# Below this hit rate a run is flagged as a regression (measured 100% when
# retrieval v2 shipped on 2026-10-09).
REGRESSION_HIT_RATE = 0.8


def load_cases(path: Path = DEFAULT_CASES) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def run_retrieval(question: str, pipeline: str, top_k: int):
    if pipeline == "raw":
        return retrieve(question, top_k=top_k)
    enriched = enrich_query(question)
    category = enriched.category if pipeline == "filtered" else None
    return retrieve(enriched.search_query, category=category, top_k=top_k)


def evaluate(
    cases: list[dict], pipeline: str = "api", top_k: int = 5, pause_s: float = 0.5
) -> dict:
    """Run every case; return aggregate metrics plus per-case results."""
    results, latencies, reciprocal_ranks = [], [], []
    for case in cases:
        pattern = re.compile(case["expect"], re.IGNORECASE)
        started = time.perf_counter()
        chunks = run_retrieval(case["question"], pipeline, top_k)
        latency_ms = (time.perf_counter() - started) * 1000
        rank = next(
            (i for i, c in enumerate(chunks, 1) if pattern.search(f"{c.url or ''} {c.title}")),
            None,
        )
        latencies.append(latency_ms)
        reciprocal_ranks.append(1 / rank if rank else 0.0)
        results.append(
            {
                "question": case["question"],
                "rank": rank,
                "latency_ms": round(latency_ms),
                "top_urls": [c.url for c in chunks[:3]],
            }
        )
        if pause_s:
            time.sleep(pause_s)  # stay under the embedding API rate limit

    hits = sum(1 for r in results if r["rank"])
    n = len(results) or 1
    hit_rate = hits / n
    return {
        "ran_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "pipeline": pipeline,
        "top_k": top_k,
        "cases": len(results),
        "hits": hits,
        "hit_rate": round(hit_rate, 3),
        "mrr": round(statistics.mean(reciprocal_ranks), 3) if reciprocal_ranks else 0.0,
        "latency_p50_ms": round(statistics.median(latencies)) if latencies else 0,
        "latency_max_ms": round(max(latencies)) if latencies else 0,
        "regression": hit_rate < REGRESSION_HIT_RATE,
        "results": results,
    }
