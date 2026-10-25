# TogoLM

> **The first open-source AI infrastructure focused on Togo**

[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://python.org)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-pgvector-336791)](https://github.com/pgvector/pgvector)
[![HuggingFace](https://img.shields.io/badge/🤗-togolm-yellow)](https://huggingface.co/togolm)

TogoLM is an open-source AI knowledge layer for Togo — a complete pipeline from raw web scraping to a fine-tuned LLM and public REST API that developers, startups, and institutions can build upon.

---

## What it does

| Layer | Description |
|-------|-------------|
| **Corpus** | 99 000+ structured Togolese documents (laws, official journal, government data, press, education, health) from 59 sources, in French, Éwé and Kabiyè |
| **RAG Engine** | Retrieval-Augmented Generation over the Togolese corpus |
| **Public API** | REST endpoints consumable by any developer or app: JSON or streamed (SSE) answers, voice transcription, image questions |
| **Procedure cards** | Exact cost, delay and documents to bring for administrative procedures (service-public.gouv.tg, investirautogo.tg), attached to answers |
| **Bots** | Telegram and WhatsApp bots answering from the same RAG engine |
| **Alerts** | Daily e-mail of new public documents on a topic (double opt-in) |
| **Billing** | Paid plans through PayGate Global (Flooz, T-Money) |
| **Admin API** | Protected endpoints for corpus management, API key CRUD, query analytics |
| **Fine-tuned LLM** | Mistral 7B adapted to the Togolese context (training in progress) |
| **SDKs** | Official JS/TS and Python clients (`sdk/`) for the public API |

## Why

Togolese public data is scattered across dozens of government portals and absent from the training sets of international LLMs. TogoLM provides a reusable, open infrastructure layer for Togo and francophone West Africa.

---

## Repository structure

```
togolm/
├── corpus/
│   ├── scrapers/
│   │   └── spiders/          # 44 Scrapy spiders, one per source or family of sources
│   └── datasets/             # Scraped JSONL files (gitignored)
├── rag/
│   ├── generation/           # LangChain LCEL chains, prompts, LLM config
│   ├── retrieval/            # Vector + fulltext search, query enrichment
│   ├── indexation/           # Chunker, cleaner, embedder, ingestor
│   └── orchestration/        # LangGraph query graph, intent classification
├── db/                       # Shared PostgreSQL connection (get_conn)
├── api/
│   ├── app/
│   │   ├── main.py           # FastAPI entry point
│   │   ├── core/             # auth.py, rate_limit.py, models.py
│   │   └── features/
│   │       ├── admin/        # router.py, service.py, schemas.py
│   │       ├── alerts/       # topic alerts by e-mail (double opt-in)
│   │       ├── auth/         # register, me, key rotation, usage
│   │       ├── billing/      # plans, PayGate checkout and callback
│   │       ├── bots/         # Telegram and WhatsApp webhooks
│   │       ├── contribute/   # Éwé / Kabiyè answer reviews
│   │       ├── corpus/       # public stats
│   │       ├── documents/    # list, detail, search, link preview
│   │       ├── feedback/     # answer feedback
│   │       ├── procedures/   # procedure cards
│   │       └── query/        # HTTP layer, delegates to rag/
│   └── tests/                # pytest integration tests
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
├── sdk/
│   ├── js/                    # @togolm/sdk — npm package
│   └── python/                # togolm — PyPI package
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

- Python 3.11+, [uv](https://github.com/astral-sh/uv)
- PostgreSQL with [pgvector](https://github.com/pgvector/pgvector) extension
- Node.js 18+ (optional — only needed to use `sdk/js`)

### 1 — Clone and configure

```bash
git clone https://github.com/omarfarouk228/togolm.git
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
# Query the corpus (in development, with API_KEYS empty, any X-API-Key is accepted)
curl -X POST http://localhost:8000/v1/query \
  -H "X-API-Key: dev" \
  -H "Content-Type: application/json" \
  -d '{"question": "Comment créer une entreprise au Togo ?"}'
```

### 6 — Use a client SDK

```bash
npm install @togolm/sdk       # JS/TS
pip install togolm            # Python
```

```ts
import { TogoLM } from "@togolm/sdk";

const client = new TogoLM({ baseUrl: "http://localhost:8000/v1" });
const { answer } = await client.query({ question: "Comment créer une entreprise au Togo ?" });
```

See [`sdk/js`](sdk/js) and [`sdk/python`](sdk/python) for full usage, including SSE streaming.

---

## API endpoints

Interactive docs: `GET /docs` (OpenAPI at `/openapi.json`). Endpoints marked 🔑 are rate limited: 20 requests per day without a key, 200 per day with a free key (`X-API-Key` header), more on paid plans.

### Public

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/v1/stats` | Corpus statistics |
| `GET` | `/v1/categories` | Categories that currently hold documents |
| `GET` | `/v1/documents/recent` | Recent documents feed |
| `GET` | `/v1/documents` 🔑 | Paginated document list |
| `GET` | `/v1/documents/{id}` 🔑 | Document detail + chunks |
| `GET` | `/v1/documents/preview?url=` 🔑 | Title, description and favicon of a cited URL |
| `GET` | `/v1/search?q=` 🔑 | French full-text search |
| `POST` | `/v1/query` 🔑 | RAG answer as JSON, with sources and the procedure card when relevant |
| `POST` | `/v1/query/stream` 🔑 | Same answer streamed as Server-Sent Events |
| `POST` | `/v1/embed` 🔑 | 384-dim embedding vector |
| `POST` | `/v1/transcribe` 🔑 | Transcribe a spoken question (Éwé and Kabiyè included) |
| `GET` | `/v1/procedures?q=` | Search procedure cards |
| `GET` | `/v1/procedures/{id}` | One procedure card: cost, delay, documents, steps |
| `POST` | `/v1/feedback` | Rate an answer |
| `GET` | `/v1/contribute/items` | Éwé / Kabiyè answers waiting for review |
| `POST` | `/v1/contribute/reviews` | Submit a review (daily cap per IP) |
| `POST` | `/v1/alerts` | Subscribe to a topic alert (confirmation e-mail) |
| `GET` | `/v1/alerts/confirm` | Confirm an alert |
| `GET` | `/v1/alerts/unsubscribe` | Stop an alert |

### Account and billing

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/v1/auth/register` | Request a free API key (5 per IP per day) |
| `GET` | `/v1/auth/me` 🔑 | Current key info and usage |
| `GET` | `/v1/auth/usage` 🔑 | Daily usage history |
| `POST` | `/v1/auth/keys/rotate` 🔑 | Revoke this key and issue its replacement |
| `POST` | `/v1/auth/keys/claim` | Website only (`X-Internal-Token`): new key for a verified e-mail |
| `GET` | `/v1/billing/plans` | Plans and prices |
| `POST` | `/v1/billing/checkout` 🔑 | Start a PayGate payment (one pending at a time) |
| `GET` | `/v1/billing/payments` 🔑 | This key's payments |
| `GET` | `/v1/billing/payments/{identifier}` 🔑 | One payment's status |
| `POST` | `/v1/billing/paygate/callback` | PayGate notification (status re-checked with PayGate) |

### Bots

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/v1/bots/telegram/webhook` | Telegram updates (secret token header) |
| `GET` | `/v1/bots/whatsapp/webhook` | WhatsApp webhook verification |
| `POST` | `/v1/bots/whatsapp/webhook` | WhatsApp messages (signed by Meta) |

### Admin (JWT from `POST /v1/admin/login`)

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/v1/admin/login` | Exchange the admin key for an 8-hour JWT (10 failures per IP per 15 min) |
| `GET` | `/v1/admin/overview` | Dashboard summary |
| `GET` | `/v1/admin/corpus/stats` | Corpus totals by category/language |
| `GET` | `/v1/admin/corpus/sources` | Per-source doc count and last scrape |
| `GET` | `/v1/admin/corpus/recent` | Recently ingested documents |
| `GET` | `/v1/admin/keys` | List API keys |
| `POST` | `/v1/admin/keys` | Create an API key |
| `PATCH` | `/v1/admin/keys/{id}` | Update plan or active status |
| `POST` | `/v1/admin/keys/{id}/reset` | Reset an API key (new secret) |
| `DELETE` | `/v1/admin/keys/{id}` | Delete an API key |
| `GET` | `/v1/admin/queries` | Paginated query history |
| `GET` | `/v1/admin/queries/stats` | Query analytics (off-topic rate, latency) |
| `GET` | `/v1/admin/feedback` | Answer feedback |
| `PATCH` | `/v1/admin/feedback/{id}` | Set feedback status (approved, rejected, pending) |
| `GET` | `/v1/admin/language-reviews` | Éwé / Kabiyè reviews |
| `PATCH` | `/v1/admin/language-reviews/{id}` | Set review status (approved, rejected, pending) |
| `GET` | `/v1/admin/billing/plans` | Plans (editable) |
| `PUT` | `/v1/admin/billing/plans/{plan}` | Update a plan's price or quota |
| `GET` | `/v1/admin/billing/payments` | All payments |
| `GET` | `/v1/admin/eval/retrieval` | Last retrieval evaluation |
| `POST` | `/v1/admin/eval/retrieval/run` | Run the retrieval evaluation |
| `GET` | `/v1/admin/stats` | API request counts from Redis |
| `GET` | `/v1/admin/health/detailed` | DB, Redis, embedding coverage |

---

## Configuration

All settings come from environment variables (see [`.env.example`](.env.example)).

| Variable | Purpose |
|----------|---------|
| `POSTGRES_*` | Database connection |
| `GEMINI_API_KEY`, `GEMINI_MODEL`, `GEMINI_FALLBACK_MODEL` | Generation, routing, image understanding, embeddings |
| `ANTHROPIC_API_KEY`, `CLAUDE_MODEL` | Optional Claude fallback when Gemini is unavailable |
| `API_ENV` | `production` disables the development key fallback |
| `API_KEYS` | Static keys; empty in development means any key is accepted (never in production) |
| `API_SECRET_KEY` | Admin key for `POST /v1/admin/login`: long and random |
| `ADMIN_JWT_SECRET` | Signs admin JWTs; must differ from `API_SECRET_KEY` (`openssl rand -hex 32`) |
| `INTERNAL_API_TOKEN` | Shared with the website for `/v1/auth/keys/claim` and the register cap exemption |
| `REGISTER_PER_IP_PER_DAY` | Free keys per IP per day (default 5) |
| `CORS_ORIGINS` | Allowed browser origins |
| `CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND`, `REDIS_URL` | Celery and rate limits |
| `EMAIL_SERVER_HOST`, `EMAIL_SERVER_PORT`, `EMAIL_SERVER_USER`, `EMAIL_SERVER_PASSWORD`, `EMAIL_FROM` | Alert e-mails |
| `PUBLIC_API_URL` | Base URL used in alert confirmation links |
| `PAYGATE_API_KEY` | PayGate Global payments |
| `TELEGRAM_BOT_TOKEN`, `TELEGRAM_WEBHOOK_SECRET` | Telegram bot |
| `WHATSAPP_TOKEN`, `WHATSAPP_PHONE_NUMBER_ID`, `WHATSAPP_APP_SECRET`, `WHATSAPP_VERIFY_TOKEN` | WhatsApp bot |
| `BOT_DAILY_LIMIT` | Questions per bot user per day (default 30) |
| `RAG_HNSW_EF_SEARCH`, `RAG_CONTEXT_NEIGHBORS` | Retrieval tuning |

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

## Corpus coverage (99 926 documents, 59 sources)

Snapshot of 2026-10-25; live numbers: `GET /v1/stats`. Categories: administrative, legal, education, economy, health, agriculture, politics, press.

| Source | Documents |
|--------|-----------|
| icilome.com | 23 143 |
| atop.tg | 14 699 |
| togoactualite.com | 13 678 |
| togofirst.com | 9 541 |
| lomeinfos.com | 4 363 |
| jo.gouv.tg | 4 066 |
| letogolais.com | 2 297 |
| fr.wikipedia.org | 2 167 |
| anpetogo.org | 2 041 |
| savoirnews.net | 2 015 |
| kbp.wikipedia.org | 1 962 |
| edusup.net | 1 801 |
| republicoftogo.com | 1 424 |
| campus-togo.com | 1 256 |
| ee.wikipedia.org | 1 167 |
| togo24.tg | 1 150 |
| finances.gouv.tg | 1 109 |
| environnement.gouv.tg | 1 102 |
| republiquetogolaise.tg | 971 |
| sante-assurances.gouv.tg | 707 |
| arcep.tg | 687 |
| univ-lome.tg | 658 |
| commerce.gouv.tg | 605 |
| cnss.tg | 538 |
| yas.tg | 502 |
| diplomatie.gouv.tg | 482 |
| agriculture.gouv.tg | 464 |
| presidenceduconseil.gouv.tg | 422 |
| tourisme.gouv.tg | 402 |
| planification.gouv.tg | 394 |
| defense.gouv.tg | 366 |
| numerique.gouv.tg | 356 |
| otr.tg | 336 |
| education.gouv.tg | 334 |
| togo-port.net | 316 |
| urbanisme.gouv.tg | 253 |
| sports.gouv.tg | 239 |
| justice.gouv.tg | 228 |
| communication.gouv.tg | 213 |
| ohada.org | 205 |
| service-public.gouv.tg | 145 |
| tde.tg | 143 |
| edusup.gouv.tg | 138 |
| eau.gouv.tg | 133 |
| securite.gouv.tg | 106 |
| inseed.tg | 103 |
| legitogo.gouv.tg | 87 |
| fonctionpublique.gouv.tg | 86 |
| moov-africa.tg | 84 |
| energie.gouv.tg | 69 |
| investirautogo.tg | 54 |
| economie.gouv.tg | 49 |
| transports.gouv.tg | 31 |
| presidence.gouv.tg | 22 |
| assemblee-nationale.tg | 8 |
| ftf.tg | 4 |
| inam.tg | 3 |
| unicef.org | 1 |
| europa.eu | 1 |

---

## Contributing

We welcome contributions — new corpus sources, scrapers, API improvements, translations.

→ [CONTRIBUTING.md](CONTRIBUTING.md)

**Issue labels:** `corpus` · `api` · `finetuning` · `sdk` · `bug` · `enhancement`

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
