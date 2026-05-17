# TogoLM

> **The first open-source AI infrastructure focused on Togo**

[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://python.org)
[![HuggingFace](https://img.shields.io/badge/🤗-togolm-yellow)](https://huggingface.co/togolm)

TogoLM is an open-source AI knowledge layer for Togo — a reusable infrastructure that developers, startups, and institutions can build upon.

---

## What it is

- **Corpus** — 50 000+ structured Togolese documents (laws, government data, press, education)
- **RAG Engine** — Retrieval-Augmented Generation over the Togolese corpus
- **Fine-tuned LLM** — Mistral 7B / LLaMA 3 8B adapted to the Togolese context
- **Public API** — REST endpoints consumable by any developer or institution
- **Showcase** — Next.js interface to explore and query the corpus

## Repository structure

```
togolm/
├── corpus/
│   ├── scrapers/         # Scrapy spiders (data collection)
│   ├── processors/       # Cleaning, chunking, embedding
│   └── datasets/         # Raw & processed data (gitignored)
├── api/
│   ├── app/              # FastAPI application
│   └── tests/
├── finetuning/
│   ├── scripts/          # Training scripts
│   ├── configs/          # QLoRA configs
│   └── datasets/         # Instruction pairs
├── vitrine/              # Next.js showcase
├── docs/                 # Architecture & API reference
└── scripts/              # DB init, utilities
```

## Quick start (local dev)

**Prerequisites:** Docker, Python 3.11+, [uv](https://github.com/astral-sh/uv)

```bash
# 1. Clone
git clone https://github.com/togolm/togolm.git
cd togolm

# 2. Start PostgreSQL + pgvector
cp .env.example .env
docker compose up -d

# 3. Install dependencies
uv sync

# 4. Run first scraper
cd corpus
scrapy crawl service_public -o ../corpus/datasets/service_public.jsonl
```

## API

```bash
# Start the API
uvicorn api.app.main:app --reload

# Query the corpus
curl -X POST http://localhost:8000/v1/query \
  -H "Content-Type: application/json" \
  -d '{"question": "How to register a company in Togo?", "category": "legal"}'
```

Full API reference → [docs/api-reference.md](docs/api-reference.md)

## Contributing

We welcome contributions — corpus sources, scrapers, corrections, translations.

→ [CONTRIBUTING.md](CONTRIBUTING.md) | Labels: `corpus`, `api`, `finetuning`, `vitrine`, `bug`, `enhancement`

## Model on Hugging Face

```python
# Coming soon
from transformers import pipeline
pipe = pipeline("text-generation", model="togolm/togolm-7b-instruct-v1")
```

## License

| Component | License |
|-----------|---------|
| Code | [MIT](LICENSE) |
| Corpus | [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) |
| Fine-tuned model | Apache 2.0 |

---

**Project lead:** Omar Farouk KOUGBADA · [KOF CORPORATION](https://kofcorporation.com) · Lomé, Togo
