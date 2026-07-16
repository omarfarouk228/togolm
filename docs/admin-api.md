# TogoLM Admin API Reference

Base URL: `https://api.togolm.com/v1` (production) / `http://localhost:8000/v1` (local)

The admin API is intended for platform operators and the admin dashboard. It is not part of the public developer API.

---

## Authentication

All admin endpoints (except `/admin/login`) require a JWT passed as `Authorization: Bearer <token>`.

### POST /v1/admin/login

Exchange the `API_SECRET_KEY` value for a 24-hour JWT token.

**Request**
```json
{ "key": "your_API_SECRET_KEY_value" }
```

**Response**
```json
{
  "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "expires_at": "2026-06-20T10:00:00Z"
}
```

Use the token in subsequent requests:
```bash
curl http://localhost:8000/v1/admin/corpus/stats \
  -H "Authorization: Bearer <token>"
```

> The legacy `X-Admin-Key` header (raw `API_SECRET_KEY` value) is still accepted for backward compatibility.

---

## Endpoints

### Corpus

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/v1/admin/corpus/stats` | Corpus totals by category and language |
| `GET` | `/v1/admin/corpus/sources` | Per-source doc count and last scrape date |
| `GET` | `/v1/admin/corpus/recent` | Recently ingested documents (`?limit=20`) |

**Example — corpus stats**
```bash
curl http://localhost:8000/v1/admin/corpus/stats \
  -H "Authorization: Bearer <token>"
```
```json
{
  "total_documents": 62168,
  "total_chunks": 101240,
  "by_category": { "press": 28400, "legal": 12300, "education": 5200 },
  "by_language": { "fr": 61800, "en": 368 },
  "last_ingested_at": "2026-06-18T22:14:00Z"
}
```

---

### API Keys

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/v1/admin/keys` | List all keys (supports `?plan=free&active_only=true`) |
| `POST` | `/v1/admin/keys` | Create a key |
| `PATCH` | `/v1/admin/keys/{id}` | Update plan or active status |
| `DELETE` | `/v1/admin/keys/{id}` | Hard-delete a key |

**Create a key**
```json
// POST /v1/admin/keys
{ "owner": "Akossiwa Dev", "email": "akossiwa@example.com", "plan": "dev" }
```
```json
// 201 Created
{ "key": "tlm_abc123...", "id": "uuid", "plan": "dev", "created_at": "..." }
```

**Update a key**
```json
// PATCH /v1/admin/keys/{id}
{ "plan": "institution", "is_active": true }
```

---

### Queries

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/v1/admin/queries` | Paginated query history (`?page=1&page_size=20&off_topic_only=false`) |
| `GET` | `/v1/admin/queries/stats` | Analytics: off-topic rate, avg latency, totals (`?days=7`) |

---

### Usage & Health

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/v1/admin/stats` | API request counts from Redis (`?days=7`) |
| `GET` | `/v1/admin/health/detailed` | DB connection, Redis, embedding coverage |

**Health response**
```json
{
  "db": "ok",
  "redis": "ok",
  "documents_total": 62168,
  "chunks_with_embeddings": 101240,
  "embedding_coverage": 0.997
}
```
