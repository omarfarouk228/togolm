# @togolm/sdk

Minimal JavaScript/TypeScript client for the [TogoLM API](https://github.com/omarfarouk228/togolm/blob/main/docs/api-reference.md).

Requires Node.js 18+ (native `fetch`) or any environment with a global `fetch`. Ships its own TypeScript types — no `@types` package needed.

## Install

```bash
npm install @togolm/sdk
```

## Get an API key

```js
import { TogoLM } from "@togolm/sdk";

const client = new TogoLM(); // no key needed for this call
const { api_key } = await client.registerKey({ email: "you@example.com", name: "Your Name" });
// shown once — save it
```

You can also call `client.query(...)` without a key — public access is rate-limited (see [rate limits](https://github.com/omarfarouk228/togolm/blob/main/docs/api-reference.md#rate-limits)).

## Usage

```js
import { TogoLM } from "@togolm/sdk";

const client = new TogoLM({ apiKey: process.env.TOGOLM_API_KEY });

const { answer, sources } = await client.query({
  question: "Comment créer une entreprise au Togo ?",
});
console.log(answer, sources);
```

### Streaming

```js
for await (const event of client.queryStream({ question: "..." })) {
  if (event.type === "chunk") process.stdout.write(event.text);
  if (event.type === "sources") console.log("Sources:", event.sources);
}
```

### Multi-turn conversations

```js
let history = [];
for (const question of ["Comment créer une entreprise au Togo ?", "Et pour les impôts ?"]) {
  const { answer } = await client.query({ question, history });
  history.push({ role: "user", content: question });
  history.push({ role: "assistant", content: answer });
}
```

`history` is capped at 20 messages server-side; oldest first. `maxTokens` (default 3000, 50–4096) caps the generated answer length.

### Local development

Point at a local API instead of production:

```js
const client = new TogoLM({ baseUrl: "http://localhost:8000/v1" });
```

### Error handling

Non-2xx responses throw `TogoLMError` (`status` and `body` fields):

```js
import { TogoLM, TogoLMError } from "@togolm/sdk";

try {
  await client.query({ question: "..." });
} catch (err) {
  if (err instanceof TogoLMError) {
    console.error(err.status, err.body);
  }
}
```

## All methods

| Method | Description |
|--------|-------------|
| `query({ question, category?, language?, maxTokens?, history? })` | RAG query, full response |
| `queryStream({ question, category?, language?, maxTokens?, history? })` | RAG query, SSE stream (async generator) |
| `embed(text)` | Generate an embedding vector |
| `search(q)` | Full-text search over the corpus |
| `categories()` | List available corpus categories |
| `stats()` | Public corpus statistics |
| `documents({ page?, pageSize?, category?, source?, language? })` | Paginated document list |
| `document(id)` | Document detail, including chunks |
| `registerKey({ email, name, useCase? })` | Request a free API key |
| `me()` | Current API key info and usage |

Full request/response shapes: [API reference](https://github.com/omarfarouk228/togolm/blob/main/docs/api-reference.md).
