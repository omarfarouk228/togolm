# TogoLM Showcase

Next.js frontend for [TogoLM](https://github.com/togolm/togolm) — browse, search, and query the Togolese AI knowledge layer.

Live: **[togolm.kofcorporation.com](https://togolm.kofcorporation.com)**

---

## Pages

| Route | Description |
|-------|-------------|
| `/` | Homepage — corpus stats, source breakdown |
| `/corpus` | Browse documents by source and category |
| `/search` | Full-text search over 62 000+ documents |
| `/chat` | Streaming RAG chat powered by `togolm-7b-instruct-v1` |
| `/developers` | API reference and code examples |

## Stack

- **Next.js 15** + App Router
- **Tailwind CSS v4**
- **TypeScript**

## Local development

```bash
npm install
cp .env.local.example .env.local
# Set NEXT_PUBLIC_API_URL and NEXT_PUBLIC_API_KEY
npm run dev   # http://localhost:3000
```

## Environment variables

| Variable | Description |
|----------|-------------|
| `NEXT_PUBLIC_API_URL` | TogoLM API base URL (e.g. `https://api.togolm.kofcorporation.com`) |
| `NEXT_PUBLIC_API_KEY` | Public API key for the showcase |

## Deployment

Deployed on VPS via Coolify. Push to `main` triggers automatic redeploy.
