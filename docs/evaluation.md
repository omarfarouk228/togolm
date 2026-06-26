# Evaluation

TogoLM uses two complementary test layers:

- `pytest` for deterministic API, retrieval, enrichment, and graph orchestration tests.
- DeepEval for LLM-as-a-judge checks on RAG answer quality and grounding.

## Fast Tests

Run the regular test suite before each pull request:

```bash
uv run pytest api/tests/ -v
```

These tests should not require Gemini, OpenAI, or a production corpus. Mock external
services and database calls when adding unit coverage.

## RAG Evaluations

Install the evaluation extra:

```bash
uv sync --extra eval
```

Set an LLM judge key for DeepEval:

```bash
export OPENAI_API_KEY=...
```

Then run:

```bash
uv run deepeval test run evals/test_rag_deepeval.py
```

The smoke dataset lives in `evals/goldens/rag_smoke.jsonl`. Each record includes:

- `input`: user question
- `expected_output`: compact reference answer
- `retrieval_context`: retrieved snippets used to ground the answer

Use this suite for quality regressions such as answer irrelevance, weak retrieval
context, or hallucinated content. Keep the default CI fast; wire DeepEval into a
separate scheduled or protected workflow once the golden dataset is stable.
