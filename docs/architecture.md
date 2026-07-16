# Architecture Technique — TogoLM

> Première infrastructure IA open source centrée sur le Togo
> Version : 1.0 — Juin 2026

---

## Vue d'ensemble

```
┌─────────────────────────────────────────────────────────────────┐
│                      SOURCES DE DONNÉES                          │
│  Gouvernement · Presse · Journal Officiel · OTR · INSEED        │
└──────────────────────────┬──────────────────────────────────────┘
                           │ Scrapy (35 spiders)
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                    PIPELINE DE COLLECTE                          │
│  corpus/scrapers/   →   corpus/processors/   →  corpus/tasks/  │
│  Scrapy spiders         Cleaner · Chunker        Celery Beat    │
│                         Embedder · Ingestor                     │
└──────────────────────────┬──────────────────────────────────────┘
                           │ psycopg2 + pgvector
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                   POSTGRESQL + PGVECTOR                          │
│  Table: documents    (62 000+ docs, 55+ sources distinctes)       │
│  Table: chunks       (101 000+ chunks, 384-dim embeddings)      │
│  Table: api_keys     (SHA-256, plans: free / dev / institution) │
│  Table: user_queries (query logs, latency, off-topic tracking)  │
│  Migrations: Alembic (alembic upgrade head)                     │
└──────────┬──────────────────────────────┬───────────────────────┘
           │                              │
           ▼                              ▼
┌──────────────────────┐      ┌───────────────────────────────────┐
│     FINE-TUNING      │      │           RAG ENGINE               │
│  finetuning/         │      │  rag/ (LangChain + LangGraph)     │
│  QLoRA · Mistral 7B  │      │  guard → router → enrich          │
│  Hugging Face Hub    │      │  → retrieve → answer              │
└──────────────────────┘      └──────────────────┬────────────────┘
                                                 │
                                                 ▼
┌─────────────────────────────────────────────────────────────────┐
│                      API FASTAPI (v1)                            │
│  POST /v1/query             RAG question-answering              │
│  POST /v1/query/stream      SSE streaming                       │
│  GET  /v1/corpus/stats      Corpus statistics                   │
│  GET  /v1/documents/search  Semantic document search            │
│  Auth: X-API-Key header     Rate limit: Redis INCR/EXPIRE       │
└──────────┬──────────────────────────────┬───────────────────────┘
           │                              │
           ▼                              ▼
┌─────────────────────┐      ┌────────────────────────────────────┐
│ SDK (public)        │      │    CONSOMMATEURS EXTERNES          │
│ sdk/js · sdk/python │      │    Apps · Institutions · Devs      │
└─────────────────────┘      └────────────────────────────────────┘
```

---

## Composants détaillés

### 1. Pipeline de collecte (`corpus/`)

#### 1.1 Scrapers (`corpus/scrapers/`)

35 fichiers spider (hors `base_spider.py`) couvrant 55+ sources distinctes. Certains spiders agrègent plusieurs domaines (`gouv_ministry` → 13 sources, `beta_sources` → 5, `international` → 8).

| Spider | Source | Catégorie | Statut |
|--------|--------|-----------|--------|
| `service_public` | service-public.gouv.tg | administrative | ✅ Actif |
| `presidence` | presidence.gouv.tg | politics | ✅ Actif |
| `primature` | primature.gouv.tg | politics | ✅ Actif |
| `inseed` | inseed.tg | economy | ✅ Actif |
| `gouv_ministry` | *.gouv.tg (ministères) | government | ✅ Actif |
| `journal_officiel` | jo.gouv.tg | legal | ✅ Actif |
| `otr` | otr.tg | legal/tax | ✅ Actif |
| `ohada` | ohada.com | legal | ✅ Actif |
| `droit_afrique` | droit-afrique.com | legal | ✅ Actif |
| `legal_pdf` | PDFs légaux | legal | ✅ Actif |
| `uemoa` | uemoa.int | legal/economy | ✅ Actif |
| `bceao` | bceao.int | economy/finance | ✅ Actif |
| `togofirst` | togofirst.com | press | ✅ Actif |
| `icilome` | icilome.com | press | ✅ Actif |
| `republicoftogo` | republicoftogo.com | press | ✅ Actif |
| `letogolais` | letogolais.com | press | ✅ Actif |
| `savoirnews` | savoirnews.net | press | ✅ Actif |
| `lomeinfos` | lomeinfos.com | press | ✅ Actif |
| `togoactualite` | togoactualite.com | press | ✅ Actif |
| `togo24` | togo24.net | press | ✅ Actif |
| `moov_africa` | moov-africa.tg | economy/telecoms | ✅ Actif |
| `anpe` | anpe.tg | employment | ✅ Actif |
| `univ_lome` | univ-lome.tg | education | ✅ Actif |
| `edusup` | edusup.gouv.tg | education | ✅ Actif |
| `campus_togo` | campus-togo.tg | education | ✅ Actif |
| `yas` | yas.tg | social | ✅ Actif |
| `wikipedia` | fr.wikipedia.org | encyclopedic | ✅ Actif |
| `international` | sources internationales | international | ✅ Actif |
| `beta_sources` | sources diverses | various | ✅ Actif |
| `mef` | mef.gouv.tg | economy | ❌ DNS failure |
| `assemblee_nationale` | assemblee-nationale.tg | politics | ❌ Cloudflare |
| `atp` | agencetogopresse.com | press | ❌ DNS failure |
| `haac` | haac.tg | government | ❌ DNS failure |
| `togoinfos` | togoinfos.com | press | ❌ DNS failure |
| `togopress` | togopress.net | press | ❌ DNS failure |

Configuration Scrapy (`corpus/scrapers/settings.py`) :
- `ROBOTSTXT_OBEY = True`
- `DOWNLOAD_DELAY = 1.5`
- `CONCURRENT_REQUESTS = 4`
- `RETRY_TIMES = 3`

#### 1.2 Indexation (`rag/indexation/`)

**`cleaner.py`** — Nettoyage du texte
- Suppression du HTML/JS/CSS résiduel
- Normalisation des espaces et caractères
- Filtre `is_useful()` : minimum 50 mots

**`chunker.py`** — Découpage en chunks
- `chunk_by_words()` : taille calculée via `max_chunk_words()` pour tenir dans la fenêtre du modèle d'embedding (< 100 mots, ~12% de chevauchement)
- Retourne des objets `Chunk(document_id, chunk_index, text, word_count)`

**`embedder.py`** — Génération d'embeddings
- Priorité 1 : Gemini `gemini-embedding-001` (384 dims, API key requis)
- Fallback : `paraphrase-multilingual-MiniLM-L12-v2` (384 dims, local, ~120 MB)
- Détection automatique via `GEMINI_API_KEY` dans `.env`

**`ingestor.py`** — Ingestion PostgreSQL
- Lit les fichiers JSONL depuis `corpus/datasets/`
- Upsert idempotent sur `url` (`ON CONFLICT (url) DO UPDATE`)
- Supprime et recrée les chunks à chaque upsert
- Traitement par batch de 20 pour les embeddings Gemini

#### 1.3 Automatisation (`corpus/celery_app.py` + `corpus/tasks.py`)

- **Weekly full scrape** : tous les spiders, dimanche 2h (heure de Lomé)
- **Daily news scrape** : spiders presse uniquement, 6h quotidien
- Broker : Redis (`redis://localhost:6379/0`)
- Backend résultats : Redis (`redis://localhost:6379/1`)

```bash
# Lancer le worker + beat (dev)
celery -A corpus.celery_app worker --beat --loglevel=info
```

---

### 2. Base de données

#### Schéma

Le schéma est géré par Alembic (`alembic upgrade head`). Voir `alembic/versions/` pour les migrations.

Tables principales :

| Table | Description |
|-------|-------------|
| `documents` | Textes bruts + nettoyés, embedding 384-dim, FTS tsvector généré |
| `chunks` | Chunks 400 mots, embedding 384-dim, lié à `documents` |
| `api_keys` | SHA-256 hash, prefix d'affichage, plan (free/dev/institution) |
| `user_queries` | Logs des requêtes : question, latence, off-topic, chunks trouvés |

#### Index vectoriel

```sql
-- IVFFLAT pour cosine similarity (100 listes, optimal pour ~55k chunks)
CREATE INDEX chunks_embedding_idx ON chunks
    USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
```

#### Configuration Docker

```yaml
# docker-compose.yml (port 5433 pour éviter conflit avec PG local)
services:
  db:
    image: pgvector/pgvector:pg16
    ports: ["5433:5432"]
  redis:
    image: redis:7-alpine
    ports: ["6379:6379"]
```

---

### 3. API FastAPI (`api/`)

#### Structure

```
api/
├── app/
│   ├── main.py               # App entry point, middlewares, routers
│   ├── core/
│   │   ├── auth.py           # X-API-Key → APIKeyRecord (DB lookup + SHA-256)
│   │   ├── rate_limit.py     # Redis INCR/EXPIRE, fail-open
│   │   └── models.py         # SQLAlchemy models (Alembic target_metadata)
│   └── features/
│       ├── admin/
│       │   ├── router.py     # 12 endpoints admin (corpus, keys, queries, health, login)
│       │   ├── service.py    # logique métier admin (JWT, stats, CRUD clés)
│       │   └── schemas.py    # Pydantic models admin
│       ├── auth/router.py    # POST /v1/auth/register, GET /v1/auth/me
│       ├── corpus/router.py  # GET /v1/categories, GET /v1/stats
│       ├── documents/router.py # GET /v1/documents, GET /v1/search
│       └── query/
│           ├── router.py     # POST /v1/query, POST /v1/query/stream, POST /v1/embed
│           └── querylog.py   # log_query() → table user_queries
└── tests/
    ├── conftest.py
    ├── test_rag.py
    ├── test_query.py
    ├── test_query_enrichment.py
    ├── test_query_graph.py
    ├── test_auth.py
    ├── test_rate_limit.py
    ├── test_corpus.py
    └── test_indexation.py

rag/
├── generation/
│   ├── chains.py             # build_answer(), stream_answer(), route_query()
│   ├── prompts.py            # Versioned system prompts (RAG, off-topic, router)
│   └── llm.py                # ChatGoogleGenerativeAI factory, gemini_available()
├── retrieval/
│   ├── search.py             # retrieve() — vector + fulltext search
│   └── enrichment.py         # enrich_query() — category detection
└── orchestration/
    ├── graph.py              # LangGraph query graph (run_query_graph)
    └── classification.py     # is_trivially_off_topic() micro-guard

db/
└── __init__.py               # get_conn() — connexion PostgreSQL partagée
```

#### Authentification

1. Header `X-API-Key` → SHA-256 hash → lookup dans `api_keys`
2. Fallback : env var `API_KEYS` (pour dev sans DB)
3. Anonyme (pas de clé) : autorisé, plan `anon` (100 req/jour)
4. Clé invalide : `401 Unauthorized`

#### Rate limiting

| Plan | Limite | Fenêtre |
|------|--------|---------|
| anon | 100 req | 24h (par IP) |
| free | 100 req | 24h (par clé) |
| dev | 1 000 req | 24h (par clé) |
| institution | 100 000 req | 24h (par clé) |

Implémentation Redis (atomic, fail-open si Redis indisponible) :
```python
pipe.incr(key)
pipe.expire(key, window_seconds)
```

#### RAG Pipeline

```
Question → Micro-guard (trivially off-topic ?)
         → LLM router (on_topic / off_topic)
         → Query enrichment (category detection, rewrite with history)
         → Embedding (384 dims) → pgvector cosine search (top-5 chunks)
         → Gemini 2.5 Flash (LangChain) ou fallback extractif local
         → Réponse streamée (SSE) + sources
```

---

### 4. Fine-tuning (`finetuning/`)

**Modèle base** : Mistral 7B Instruct v0.3
**Méthode** : QLoRA (4-bit quantization, LoRA rank=16, alpha=32)
**Dataset** : 5 000-10 000 paires (instruction, réponse) format Alpaca
**Infrastructure** : RunPod / Modal (GPU A100 ou H100)

```bash
# Génération du dataset
python finetuning/dataset/generator.py --source corpus/datasets/ --output finetuning/datasets/

# Fine-tuning
python finetuning/scripts/train.py --config finetuning/configs/qlora_mistral7b.yaml

# Publication HuggingFace
python finetuning/scripts/publish.py --model outputs/togolm-7b-v1 --repo togolm/togolm-7b-v1
```

---

### 5. SDK (`sdk/`)

Clients officiels minimalistes pour l'API publique — aucune dépendance aux apps privées.

```
sdk/
├── js/          # @togolm/sdk (npm) — fetch-based, streaming SSE via ReadableStream
└── python/      # togolm (PyPI) — httpx-based, streaming SSE via iter_lines
```

```ts
import { TogoLM } from "@togolm/sdk";

const client = new TogoLM({ apiKey });
const { answer } = await client.query({ question: "Comment créer une entreprise au Togo ?" });
```

Voir [`sdk/js/README.md`](../sdk/js/README.md) et [`sdk/python/README.md`](../sdk/python/README.md) pour l'usage complet (streaming inclus).

---

### 6. Gestion des clés API

```bash
# Créer une nouvelle clé
python scripts/admin/create_api_key.py create --owner "Nom" --email "email@example.com" --plan dev

# Lister les clés actives
python scripts/admin/create_api_key.py list

# Révoquer une clé
python scripts/admin/create_api_key.py revoke <key_id>
```

Format des clés : `tlm_` + 64 caractères hexadécimaux
Stockage : SHA-256 hash dans la table `api_keys` (clé en clair jamais stockée)

---

### 7. Variables d'environnement

| Variable | Description | Exemple |
|----------|-------------|---------|
| `POSTGRES_HOST` | Hôte PostgreSQL | `localhost` |
| `POSTGRES_PORT` | Port PostgreSQL | `5433` |
| `POSTGRES_DB` | Nom de la base | `togolm` |
| `POSTGRES_USER` | Utilisateur | `postgres` |
| `POSTGRES_PASSWORD` | Mot de passe | — |
| `GEMINI_API_KEY` | Clé API Gemini | `AQ...` |
| `GEMINI_MODEL` | Modèle de chat Gemini (optionnel) | `gemini-2.5-flash` (défaut) |
| `GEMINI_FALLBACK_MODEL` | Modèle de secours si `GEMINI_MODEL` échoue (quota, indisponibilité...) (optionnel) | `gemini-3-flash-preview` (défaut) |
| `API_SECRET_KEY` | Secret interne | SHA-256 hex |
| `API_KEYS` | Clés dev (virgule-séparées) | vide = dev mode |
| `CELERY_BROKER_URL` | Redis broker | `redis://localhost:6379/0` |
| `CELERY_RESULT_BACKEND` | Redis backend | `redis://localhost:6379/1` |

---

### 8. Déploiement VPS

```bash
# API
uvicorn api.app.main:app --host 0.0.0.0 --port 8000 --workers 4

# Celery worker + beat
celery -A corpus.celery_app worker --beat --concurrency=2 --loglevel=info

# Nginx reverse proxy
server {
    server_name api.togolm.ai;
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

---

*Document maintenu par KOF CORPORATION — Lomé, Togo*
*Dernière mise à jour : Juin 2026*
