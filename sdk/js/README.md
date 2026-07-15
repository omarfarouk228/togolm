# @togolm/sdk

Minimal JavaScript/TypeScript client for the [TogoLM API](../../docs/api-reference.md).

## Install

```bash
npm install @togolm/sdk
```

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

Omit `apiKey` for public, rate-limited access. See the [API reference](../../docs/api-reference.md) for rate limits and full endpoint documentation.
