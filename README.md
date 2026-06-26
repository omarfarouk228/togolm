# TogoLM

> **The first open-source AI infrastructure focused on Togo**

[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://python.org)
[![Next.js](https://img.shields.io/badge/Next.js-15-black)](https://nextjs.org)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-pgvector-336791)](https://github.com/pgvector/pgvector)
[![HuggingFace](https://img.shields.io/badge/🤗-togolm-yellow)](https://huggingface.co/togolm)

TogoLM is an open-source AI knowledge layer for Togo — a complete pipeline from raw web scraping to a fine-tuned LLM and public REST API that developers, startups, and institutions can build upon.

---

## What it does

| Layer | Description |
|-------|-------------|
| **Corpus** | 62 000+ structured Togolese documents — laws, government data, press, education — from 55+ sources |
| **RAG Engine** | Retrieval-Augmented Generation over the Togolese corpus |
| **Public API** | REST endpoints consumable by any developer or app |
| **Admin API** | Protected endpoints for corpus management, API key CRUD, query analytics |
| **Fine-tuned LLM** | Mistral 7B adapted to the Togolese context (training in progress) |
| **Showcase** | Next.js public interface to explore and query the corpus |
| **Admin Dashboard** | Next.js 15 private dashboard to monitor and manage the platform |

## Why

Togolese public data is scattered across dozens of government portals and absent from the training sets of international LLMs. TogoLM provides a reusable, open infrastructure layer for Togo and francophone West Africa.

---

## Repository structure

```
togolm/
├── corpus/
│   ├── scrapers/
│   │   └── spiders/          # 29 Scrapy spiders — one per source
│   ├── processors/
│   │   ├── cleaner.py        # HTML → clean text
│   │   ├── chunker.py        # Split into 400-word chunks
│   │   ├── embedder.py       # Local (MiniLM) or Gemini embeddings
│   │   └── ingestor.py       # JSONL → PostgreSQL + pgvector
│   └── datasets/             # Scraped JSONL files (gitignored)
├── api/
│   ├── app/
│   │   ├── main.py           # FastAPI entry point
│   │   ├── core/             # db.py, auth.py, rate_limit.py, models.py
│   │   └── features/
│   │       ├── admin/        # router.py, service.py, schemas.py
│   │       ├── auth/         # register, me
│   │       ├── corpus/       # public stats
│   │       ├── documents/    # list, detail, search
│   │       └── query/        # RAG service + router
│   └── tests/                # pytest integration tests (80 tests)
├── alembic/                  # Database migrations (Alembic)
│   └── versions/
├── finetuning/
│   ├── dataset/
│   │   ├── generator.py      # Q&A pair generation (Gemini)
│   │   └── formatter.py      # Alpaca / ShareGPT format
│   ├── train/
│   │   ├── config.py         # QLoRA hyperparameters
│   │   └── trainer.py        # SFTTrainer fine-tuning script
│   ├── scripts/
│   │   ├── publish.py        # Push LoRA adapter to HuggingFace
│   │   └── push_model_card.py
│   └── notebooks/
│       └── train_colab.ipynb # Google Colab training notebook
├── showcase/                 # Next.js public frontend
│   ├── app/
│   │   ├── page.tsx          # Homepage — stats + source table
│   │   ├── corpus/page.tsx   # Browse corpus by source/category
│   │   ├── search/page.tsx   # Full-text search UI
│   │   └── chat/page.tsx     # Streaming RAG chat UI
│   └── lib/api.ts
├── admin/                    # Next.js 15 admin dashboard (EN/FR)
│   ├── app/
│   │   ├── (auth)/login/     # Admin login (JWT)
│   │   └── (dashboard)/      # Dashboard, corpus, keys, queries, health
│   └── lib/
│       ├── api.ts            # Typed admin API client
│       ├── auth.ts           # JWT helpers
│       └── i18n.ts           # EN/FR translations
├── scripts/
│   ├── corpus/
│   │   ├── run_scrapers.py   # Master scraping + ingest + embed pipeline
│   │   ├── ingest_docs.sh    # Convert local PDF/TXT/MD to corpus JSONL
│   │   ├── embed_missing.py  # Backfill embeddings for existing docs
│   │   └── push_dataset.py   # Export corpus to HuggingFace dataset
│   ├── vps/
│   │   ├── setup.sh          # One-time VPS provisioning
│   │   ├── update.sh         # Run corpus pipeline on VPS via SSH
│   │   ├── ingest_docs.sh    # Upload JSONL + ingest + embed on VPS
│   │   ├── push_dataset.sh   # Push corpus to HuggingFace from VPS
│   │   └── db_export.sh      # Export local DB and import on VPS
│   └── admin/
│       └── create_api_key.py # CLI to create/list/revoke API keys
├── .env.example
└── pyproject.toml
```

---

## Quick start

### Prerequisites

- Python 3.11+, [uv](https://github.com/astral-sh/uv), Node.js 20+, pnpm
- PostgreSQL with [pgvector](https://github.com/pgvector/pgvector) extension

### 1 — Clone and configure

```bash
git clone https://github.com/togolm/togolm.git
cd togolm
cp .env.example .env
# Edit .env — set POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_DB, GEMINI_API_KEY
```

### 2 — Install Python dependencies

```bash
uv sync
```

### 3 — Initialize the database

```bash
uv run --env-file .env alembic upgrade head
```

### 4 — Run the full corpus pipeline

```bash
# Scrape all sources, ingest into PostgreSQL, embed
uv run python scripts/corpus/run_scrapers.py

# Or a single spider
uv run python scripts/corpus/run_scrapers.py --spiders inseed
```

### 5 — Start the API

```bash
uv run uvicorn api.app.main:app --reload --port 8000
```

```bash
# Query the corpus
curl -X POST http://localhost:8000/v1/query \
  -H "Content-Type: application/json" \
  -d '{"question": "Comment créer une entreprise au Togo ?"}'
```

### 6 — Start the showcase

```bash
cd showcase && pnpm install && pnpm dev   # http://localhost:3000
```

### 7 — Start the admin dashboard

```bash
cd admin
cp .env.local.example .env.local
# Edit .env.local: NEXT_PUBLIC_API_URL=http://localhost:8000
pnpm install && pnpm dev   # http://localhost:3001
```

Login with your `API_SECRET_KEY` from `.env`.

---

## API endpoints

### Public

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/v1/stats` | Corpus statistics |
| `GET` | `/v1/categories` | Available corpus categories |
| `GET` | `/v1/documents` | Paginated document list |
| `GET` | `/v1/documents/{id}` | Document detail + chunks |
| `GET` | `/v1/search?q=` | French full-text search |
| `POST` | `/v1/query` | RAG query → JSON response |
| `POST` | `/v1/embed` | Generate a 384-dim embedding vector |
| `POST` | `/v1/auth/register` | Request a free API key |
| `GET` | `/v1/auth/me` | Current key info and usage |

### Admin (JWT — `POST /v1/admin/login`)

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/v1/admin/login` | Exchange admin key for JWT token |
| `GET` | `/v1/admin/corpus/stats` | Corpus totals by category/language |
| `GET` | `/v1/admin/corpus/sources` | Per-source doc count and last scrape |
| `GET` | `/v1/admin/corpus/recent` | Recently ingested documents |
| `GET` | `/v1/admin/keys` | List all API keys |
| `POST` | `/v1/admin/keys` | Create an API key |
| `PATCH` | `/v1/admin/keys/{id}` | Update plan or active status |
| `DELETE` | `/v1/admin/keys/{id}` | Delete an API key |
| `GET` | `/v1/admin/queries` | Paginated query history |
| `GET` | `/v1/admin/queries/stats` | Query analytics (off-topic rate, latency) |
| `GET` | `/v1/admin/stats` | API request counts from Redis |
| `GET` | `/v1/admin/health/detailed` | DB, Redis, embedding coverage |

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

# 4. Publish to HuggingFace
uv run python -m finetuning.scripts.publish \
  --model finetuning/checkpoints/togolm-7b/final \
  --repo togolm/togolm-7b-instruct-v1
```

---

## Corpus coverage (62 000+ docs — 35 spiders, 55+ sources)

| Source | Category | Status |
|--------|----------|--------|
| icilome.com | Press | ✅ |
| **gouv_ministry** *(13 sources)* | Government | ✅ |
| — finances.gouv.tg | Economy / Finance | ✅ |
| — commerce.gouv.tg | Economy | ✅ |
| — education.gouv.tg | Education | ✅ |
| — agriculture.gouv.tg | Agriculture | ✅ |
| — environnement.gouv.tg | Agriculture / Environment | ✅ |
| — sante.gouv.tg | Health | ✅ |
| — justice.gouv.tg | Legal | ✅ |
| — securite.gouv.tg | Politics | ✅ |
| — energie.gouv.tg | Economy | ✅ |
| — tourisme.gouv.tg | Economy | ✅ |
| — presidenceduconseil.gouv.tg | Politics | ✅ |
| — urbanisme.gouv.tg | Economy | ✅ |
| — cnss.tg | Legal / Social | ✅ |
| **beta_sources** *(5 sources)* | Various | ✅ |
| — ul.tg | Education | ✅ |
| — api.tg | Economy / Investment | ✅ |
| — ceet.tg | Economy / Utilities | ✅ |
| — cour-constitutionnelle.tg | Legal | ✅ |
| — inam.tg | Health | ✅ |
| **international** *(8 sources)* | International | ✅ |
| — banquemondiale.org | Economy | ✅ |
| — imf.org | Economy | ✅ |
| — afdb.org | Economy | ✅ |
| — undp.org | Economy / Development | ✅ |
| — who.int | Health | ✅ |
| — unicef.org | Health | ✅ |
| — oecd.org | Economy | ✅ |
| — europa.eu | Economy / Cooperation | ✅ |
| togoactualite.com | Press | ✅ |
| togofirst.com | Press / Economy | ✅ |
| lomeinfos.com | Press | ✅ |
| letogolais.com | Press | ✅ |
| savoirnews.net | Press | ✅ |
| republicoftogo.com | Press | ✅ |
| republiquetogolaise.com | Press | ✅ |
| togo24.net | Press | ✅ |
| togoinfos.com | Press | ⚠️ DNS failure |
| togopress.info | Press | ⚠️ DNS failure |
| atp.tg | Press (Agence Togolaise de Presse) | ⚠️ DNS failure |
| jo.gouv.tg | Legal | ✅ |
| ohada.com | Legal | ✅ |
| droit-afrique.com | Legal | ✅ |
| legal-pdf | Legal (PDF) | ✅ |
| otr.tg | Legal / Fiscal | ✅ |
| uemoa.int | Legal / Economy | ✅ |
| presidence.gouv.tg | Politics | ✅ |
| primature.gouv.tg | Politics | ✅ |
| assemblee-nationale.tg | Politics | ⚠️ Cloudflare block |
| haac.tg | Politics / Media Regulation | ⚠️ DNS failure |
| service-public.gouv.tg | Administrative | ✅ |
| mef.gouv.tg | Economy / Finance | ⚠️ DNS failure |
| inseed.tg | Economy / Statistics | ✅ |
| bceao.int | Economy / Finance | ✅ |
| moov-africa.tg | Economy / Telecoms | ✅ |
| anpe.tg | Employment | ✅ |
| univ-lome.tg | Education | ✅ |
| edusup.gouv.tg | Education | ✅ |
| campus-togo.tg | Education | ✅ |
| yas.tg | Social | ✅ |
| fr.wikipedia.org | Encyclopedic | ✅ |
| international | International | ✅ |
| gouv_ministry | Government (misc. ministries) | ✅ |
| beta_sources | Various (beta) | ✅ |

---

## Contributing

We welcome contributions — new corpus sources, scrapers, API improvements, translations.

→ [CONTRIBUTING.md](CONTRIBUTING.md)

**Issue labels:** `corpus` · `api` · `admin` · `finetuning` · `showcase` · `bug` · `enhancement`

---

## HuggingFace

| Artifact | Type | Link |
|----------|------|------|
| `togolm-7b-instruct-v1` | Fine-tuned LLM (Mistral 7B QLoRA) | [🤗 togolm/togolm-7b-instruct-v1](https://huggingface.co/togolm/togolm-7b-instruct-v1) |
| `togolm-corpus-v1` | Corpus dataset | [🤗 togolm/togolm-corpus-v1](https://huggingface.co/datasets/togolm/togolm-corpus-v1) |

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
