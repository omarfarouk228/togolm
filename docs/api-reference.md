# TogoLM API Reference

Base URL: `https://api.togolm.ai/v1` (production) / `http://localhost:8000/v1` (local)

## Authentication

```
X-API-Key: your_api_key
```

V1 uses simple API key authentication. Omit the header for public (rate-limited) access.

---

## POST /v1/query

Query the Togolese corpus via RAG.

**Request**
```json
{
  "question": "How to register a company in Togo?",
  "category": "legal",
  "language": "fr",
  "max_tokens": 500
}
```

**Response**
```json
{
  "answer": "To register a company in Togo...",
  "sources": [
    {
      "title": "Service Public Togo — Business Registration",
      "url": "https://service-public.gouv.tg/...",
      "score": 0.92
    }
  ],
  "model": "togolm-7b-v1",
  "latency_ms": 340
}
```

---

## POST /v1/embed

Generate an embedding vector for a text.

**Request**
```json
{
  "text": "Agricultural policy in Togo 2025",
  "model": "togolm-embed-v1"
}
```

**Response**
```json
{
  "embedding": [0.023, -0.411, ...],
  "model": "togolm-embed-v1",
  "token_count": 8
}
```

---

## GET /v1/categories

Returns all corpus categories.

**Response**
```json
{
  "categories": ["administrative", "legal", "education", "economy", "health", "agriculture", "politics", "press"],
  "total": 8
}
```

---

## GET /v1/stats

Public corpus statistics.

**Response**
```json
{
  "total_documents": 12450,
  "total_chunks": 89320,
  "languages": ["fr"],
  "categories": ["administrative", "legal", ...],
  "last_updated": "2026-05-17T08:00:00Z",
  "model_version": "togolm-7b-v1"
}
```

---

## Rate limits

| Plan | Requests/day | Tokens/month |
|------|-------------|--------------|
| Free | 100 | 500 000 |
| Dev | 1 000 | 5 000 000 |
| Institution | Unlimited | Unlimited |
