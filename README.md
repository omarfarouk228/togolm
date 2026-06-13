# TogoLM

> **The first open-source AI infrastructure focused on Togo**

[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://python.org)
[![Next.js](https://img.shields.io/badge/Next.js-16-black)](https://nextjs.org)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-pgvector-336791)](https://github.com/pgvector/pgvector)
[![HuggingFace](https://img.shields.io/badge/🤗-togolm-yellow)](https://huggingface.co/togolm)

TogoLM is an open-source AI knowledge layer for Togo — a complete pipeline from raw web scraping to a fine-tuned LLM and public REST API that developers, startups, and institutions can build upon.

---

## What it does

| Layer | Description |
|-------|-------------|
| **Corpus** | 62 000+ structured Togolese documents — laws, government data, press, education |
| **RAG Engine** | Retrieval-Augmented Generation over the Togolese corpus |
| **Public API** | REST endpoints consumable by any developer or app |
| **Fine-tuned LLM** | Mistral 7B adapted to the Togolese context (training in progress) |
| **Showcase** | Next.js interface to explore and query the corpus |

## Why

Togolese public data is scattered across dozens of government portals and absent from the training sets of international LLMs. TogoLM provides a reusable, open infrastructure layer for Togo and francophone West Africa.

---

## Repository structure

```
togolm/
├── corpus/
│   ├── scrapers/
│   │   └── spiders/          # Scrapy spiders — one per source
│   ├── processors/
│   │   ├── cleaner.py        # HTML → clean text
│   │   ├── chunker.py        # Split into 400-word chunks
│   │   ├── embedder.py       # Local (MiniLM) or Gemini embeddings
│   │   └── ingestor.py       # JSONL → PostgreSQL + pgvector
│   └── datasets/             # Scraped JSONL files (gitignored)
├── api/
│   ├── app/
│   │   ├── main.py           # FastAPI entry point
│   │   ├── routers/          # corpus.py, documents.py, query.py
│   │   └── services/rag.py   # Vector retrieval + Gemini generation
│   └── tests/                # 11 pytest integration tests
├── finetuning/
│   ├── dataset/
│   │   ├── generator.py      # Q&A pair generation (Gemini)
│   │   └── formatter.py      # Alpaca / ShareGPT format
│   ├── train/
│   │   ├── config.py         # QLoRA hyperparameters
│   │   └── trainer.py        # SFTTrainer fine-tuning script
│   └── notebooks/
│       └── train_colab.ipynb # Google Colab training notebook
├── showcase/                  # Next.js 16 + Tailwind v4 frontend
│   ├── app/
│   │   ├── page.tsx          # Homepage — stats + source table
│   │   ├── corpus/page.tsx   # Browse corpus by source/category
│   │   ├── search/page.tsx   # Full-text search UI
│   │   └── chat/page.tsx     # Streaming RAG chat UI
│   └── lib/api.ts            # Typed API client + SSE stream
├── scripts/
│   └── init.sql              # PostgreSQL schema (documents + chunks)
├── .env.example
└── pyproject.toml
```

---

## Quick start

### Prerequisites

- Python 3.11+, [uv](https://github.com/astral-sh/uv), Node.js 20+
- PostgreSQL with [pgvector](https://github.com/pgvector/pgvector) extension

### 1 — Clone and configure

```bash
git clone https://github.com/togolm/togolm.git
cd togolm
cp .env.example .env
# Edit .env — set POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_DB
```

### 2 — Initialize the database

```bash
psql -U $POSTGRES_USER -d $POSTGRES_DB -f scripts/init.sql
```

### 3 — Install Python dependencies

```bash
uv sync
```

### 4 — Scrape a source

```bash
# Run from the corpus/ directory (where scrapy.cfg lives)
cd corpus
uv run scrapy crawl service_public \
  -o datasets/service_public.jsonl \
  -s JOBDIR=.crawls/service_public \
  --logfile .crawls/service_public.log
```

Available spiders: `journal_officiel`, `presidence`, `assemblee_nationale`,
`inseed`, `gouv_ministry`, `service_public`, `icilome`, `togofirst`,
`togoactualite`, `lomeinfos`, `republicoftogo`, `savoirnews`, `letogolais`,
`otr`, `wikipedia`, `cnss`, `legitogo`, `inam`, `international`

### 5 — Ingest into PostgreSQL

```bash
# Uses the local sentence-transformers model (no API key needed)
uv run python -m corpus.processors.ingestor corpus/datasets/service_public.jsonl

# Multiple files at once
uv run python -m corpus.processors.ingestor corpus/datasets/*.jsonl
```

### 6 — Start the API

```bash
uv run uvicorn api.app.main:app --reload --port 8000
```

```bash
# Query the corpus
curl -X POST http://localhost:8000/v1/query \
  -H "Content-Type: application/json" \
  -d '{"question": "Comment créer une entreprise au Togo ?"}'

# Stream the answer (SSE)
curl -N -X POST http://localhost:8000/v1/query/stream \
  -H "Content-Type: application/json" \
  -d '{"question": "Quel est le budget de l'\''État togolais ?"}'
```

Full API reference → [`docs/api-reference.md`](docs/api-reference.md)

### 7 — Start the showcase

```bash
cd showcase
npm install
npm run dev      # http://localhost:3000
```

---

## API endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/v1/stats` | Corpus statistics (doc/chunk counts per source) |
| `GET` | `/v1/categories` | Available corpus categories |
| `GET` | `/v1/documents` | Paginated document list with source/category filters |
| `GET` | `/v1/documents/{id}` | Document detail + chunks |
| `GET` | `/v1/search?q=` | French full-text search (ts_rank + ILIKE fallback) |
| `POST` | `/v1/query` | RAG query → full JSON response |
| `POST` | `/v1/query/stream` | RAG query → SSE stream (chunk by chunk) |
| `POST` | `/v1/embed` | Generate a 384-dim embedding vector |

---

## Embeddings

| Backend | Model | Requires |
|---------|-------|----------|
| Local (default) | `paraphrase-multilingual-MiniLM-L12-v2` | Nothing (auto-downloaded ~120 MB) |
| Gemini | `gemini-embedding-001` (384-dim) | `GEMINI_API_KEY` in `.env` |

The embedder auto-selects based on the presence of a valid `GEMINI_API_KEY`.

---

## Fine-tuning

The fine-tuning pipeline targets Mistral 7B Instruct v0.3 with QLoRA.

```bash
# 1. Generate Q&A pairs from the corpus (requires GEMINI_API_KEY)
uv run python -m finetuning.dataset.generator \
  --out finetuning/datasets/qa_raw.jsonl \
  --limit 500

# 2. Format to Alpaca / ShareGPT
uv run python -m finetuning.dataset.formatter \
  --input finetuning/datasets/qa_raw.jsonl \
  --output finetuning/datasets/train.jsonl \
  --format alpaca

# 3. Fine-tune (Google Colab recommended)
# Open: finetuning/notebooks/train_colab.ipynb
```

---

## Corpus coverage (62 000+ docs — 30 sources)

| Source | Category | Docs | Status |
|--------|----------|-----:|--------|
| icilome.com | Press | 22 387 | ✅ Ingested |
| togoactualite.com | Press | 13 196 | ✅ Ingested |
| togofirst.com | Press / Economy | 8 863 | ✅ Ingested |
| lomeinfos.com | Press | 4 361 | ✅ Ingested |
| jo.gouv.tg | Legal | 4 066 | ✅ Ingested |
| fr.wikipedia.org | Encyclopedic | 1 839 | ✅ Ingested |
| letogolais.com | Press | 1 377 | ✅ Ingested |
| finances.gouv.tg | Economy | 1 027 | ✅ Ingested |
| savoirnews.net | Press | 1 019 | ✅ Ingested |
| commerce.gouv.tg | Economy | 580 | ✅ Ingested |
| environnement.gouv.tg | Agriculture | 509 | ✅ Ingested |
| agriculture.gouv.tg | Agriculture | 438 | ✅ Ingested |
| tourisme.gouv.tg | Economy | 371 | ✅ Ingested |
| otr.tg | Legal / Fiscal | 323 | ✅ Ingested |
| presidenceduconseil.gouv.tg | Politics | 303 | ✅ Ingested |
| education.gouv.tg | Education | 295 | ✅ Ingested |
| urbanisme.gouv.tg | Economy | 228 | ✅ Ingested |
| justice.gouv.tg | Legal | 214 | ✅ Ingested |
| cnss.tg | Administrative | 192 | ✅ Ingested |
| republicoftogo.com | Press | 152 | ✅ Ingested |
| service-public.gouv.tg | Administrative | 141 | ✅ Ingested |
| securite.gouv.tg | Politics | 98 | ✅ Ingested |
| inseed.tg | Economy / Statistics | 96 | ✅ Ingested |
| energie.gouv.tg | Economy | 54 | ✅ Ingested |
| presidence.gouv.tg | Politics | 17 | ✅ Ingested |
| legitogo.gouv.tg | Legal | 9 | ✅ Ingested |
| assemblee-nationale.tg | Legal | 8 | ✅ Ingested |
| inam.tg | Health | 3 | ✅ Ingested |
| europa.eu | International | 1 | ✅ Ingested |
| unicef.org | International | 1 | ✅ Ingested |
| sante.gouv.tg | Health | — | ⏭ React SPA — no sitemap |
| travail.gouv.tg | Legal | — | ⏭ No site deployed |
| infrastructure.gouv.tg | Economy | — | ⏭ SSL error |
| plan.gouv.tg | Economy | — | ⏭ Unreachable |

---

## Contributing

We welcome contributions — new corpus sources, scrapers, API improvements, translations.

→ [CONTRIBUTING.md](CONTRIBUTING.md)

**Issue labels:** `corpus` · `api` · `finetuning` · `showcase` · `bug` · `enhancement`

---

## Models on Hugging Face

| Model | Type | Link |
|-------|------|------|
| `togolm-7b-instruct-v1` | Fine-tuned LLM (Mistral 7B QLoRA) | [🤗 togolm/togolm-7b-instruct-v1](https://huggingface.co/togolm/togolm-7b-instruct-v1) |
| `togolm-corpus-v1` | Training dataset (Q&A pairs) | [🤗 togolm/togolm-corpus-v1](https://huggingface.co/togolm/togolm-corpus-v1) |

```python
from transformers import pipeline

pipe = pipeline("text-generation", model="togolm/togolm-7b-instruct-v1")
result = pipe(
    "Comment créer une entreprise au Togo ?",
    max_new_tokens=300,
    temperature=0.7,
)
print(result[0]["generated_text"])
```

---

## License

| Component | License |
|-----------|---------|
| Code | [MIT](LICENSE) |
| Corpus | [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) |
| Fine-tuned model | Apache 2.0 |

---

**Project lead:** Omar Farouk KOUGBADA · GDE Flutter · Director, KOF CORPORATION · Lomé, Togo
