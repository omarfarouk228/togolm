"""
DeepEval smoke tests for TogoLM RAG grounding.

Run explicitly with:
    deepeval test run evals/test_rag_deepeval.py
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

GOLDENS_PATH = Path(__file__).parent / "goldens" / "rag_smoke.jsonl"

pytestmark = pytest.mark.skipif(
    not os.getenv("OPENAI_API_KEY"),
    reason="DeepEval judge metrics require OPENAI_API_KEY for this smoke suite.",
)


def _load_goldens() -> list[dict]:
    with GOLDENS_PATH.open(encoding="utf-8") as file:
        return [json.loads(line) for line in file if line.strip()]


@pytest.mark.parametrize("golden", _load_goldens(), ids=lambda item: item["id"])
def test_rag_grounding_smoke(golden: dict, monkeypatch: pytest.MonkeyPatch):
    deepeval = pytest.importorskip("deepeval")
    metrics_module = pytest.importorskip("deepeval.metrics")
    test_case_module = pytest.importorskip("deepeval.test_case")
    from rag.generation import build_answer
    from rag.retrieval import RetrievedChunk

    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    chunks = [
        RetrievedChunk(
            title=context["title"],
            url=context["url"],
            source=context["source"],
            category=context["category"],
            content=context["content"],
            score=0.95,
        )
        for context in golden["retrieval_context"]
    ]
    actual_output = build_answer(golden["input"], chunks)

    test_case = test_case_module.LLMTestCase(
        input=golden["input"],
        actual_output=actual_output,
        expected_output=golden["expected_output"],
        retrieval_context=[chunk.content for chunk in chunks],
    )
    metrics = [
        metrics_module.AnswerRelevancyMetric(threshold=0.5),
        metrics_module.ContextualRelevancyMetric(threshold=0.5),
        metrics_module.FaithfulnessMetric(threshold=0.7),
    ]
    deepeval.assert_test(test_case, metrics)
