# TogoLM Admin

Private dashboard for monitoring and managing the TogoLM API. Built with Next.js 15, Tailwind CSS, and TanStack Query.

## Pages

| Route | Description |
|---|---|
| `/` | Dashboard — corpus stats, API activity chart (7 days) |
| `/corpus` | Corpus breakdown — by category, by language, sources table, recent documents |
| `/keys` | API key management — create, toggle active, delete |
| `/queries` | Query history — paginated, filterable by off-topic |
| `/health` | System health — PostgreSQL, Redis, embedding coverage |

## Stack

- **Next.js 15** — App Router, client components
- **TanStack Query v5** — data fetching and caching
- **Tailwind CSS v3** — styling
- **Recharts** — area and bar charts
- **lucide-react** — icons
- **date-fns** — date formatting
- **pnpm** — package manager

## Getting started

```bash
cd admin
cp .env.local.example .env.local
# Edit .env.local and set NEXT_PUBLIC_API_URL
pnpm install
pnpm dev
```

Open [http://localhost:3001](http://localhost:3001).

## Environment variables

| Variable | Description |
|---|---|
| `NEXT_PUBLIC_API_URL` | Base URL of the TogoLM API — no trailing slash |

## Authentication

Login at `/login` with the admin key (set via `ADMIN_KEY` env var on the API). The key is exchanged for a 24-hour JWT stored in `localStorage`. All dashboard requests send it as `Authorization: Bearer <token>`. The token is cleared on logout.

## Project structure

```
admin/
├── app/
│   ├── (auth)/login/        # Login page
│   └── (dashboard)/         # Protected dashboard layout
│       ├── page.tsx          # /
│       ├── corpus/           # /corpus
│       ├── keys/             # /keys
│       ├── queries/          # /queries
│       └── health/           # /health
├── components/
│   ├── sidebar.tsx           # Nav + language select + logout modal
│   ├── shimmer.tsx           # Skeleton loading components
│   ├── stat-card.tsx         # Metric card
│   ├── status-badge.tsx      # Colored pill badge
│   └── confirm-dialog.tsx    # Reusable confirmation modal
└── lib/
    ├── api.ts                # Typed fetch wrappers for all admin endpoints
    ├── auth.ts               # JWT helpers (get/set/remove from localStorage)
    └── i18n.ts               # FR/EN translations + useT hook
```

## Internationalisation

The UI supports French and English. Toggle via the language select in the sidebar. The active locale is persisted in `localStorage`.

To add a translation key:

```ts
// lib/i18n.ts
"my.key": { en: "My label", fr: "Mon libellé" },
```

Then use it anywhere with `const { t } = useT(); t("my.key")`.
