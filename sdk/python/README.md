# togolm

Minimal Python client for the [TogoLM API](https://github.com/omarfarouk228/togolm/blob/main/docs/api-reference.md).

Requires Python 3.9+. Built on [httpx](https://www.python-httpx.org/).

## Install

```bash
pip install togolm
```

## Get an API key

```python
from togolm import TogoLM

client = TogoLM()  # no key needed for this call
result = client.register_key(email="you@example.com", name="Your Name")
api_key = result["api_key"]  # shown once — save it
```

You can also call `client.query(...)` without a key — public access is rate-limited (see [rate limits](https://github.com/omarfarouk228/togolm/blob/main/docs/api-reference.md#rate-limits)).

## Usage

```python
from togolm import TogoLM

client = TogoLM(api_key="your_api_key")

result = client.query("Comment créer une entreprise au Togo ?")
print(result["answer"], result["sources"])
```

### Streaming

```python
for event in client.query_stream("Comment créer une entreprise au Togo ?"):
    if event["type"] == "chunk":
        print(event["text"], end="")
    if event["type"] == "sources":
        print("Sources:", event["sources"])
```

### Multi-turn conversations

```python
history = []
for question in ["Comment créer une entreprise au Togo ?", "Et pour les impôts ?"]:
    result = client.query(question, history=history)
    history.append({"role": "user", "content": question})
    history.append({"role": "assistant", "content": result["answer"]})
```

`history` is capped at 20 messages server-side; oldest first. `max_tokens` (default 3000, 50–4096) caps the generated answer length.

### Local development

Point at a local API instead of production:

```python
client = TogoLM(base_url="http://localhost:8000/v1")
```

### Error handling

Non-2xx responses raise `TogoLMError` (`status` and `body` attributes):

```python
from togolm import TogoLM, TogoLMError

try:
    client.query("...")
except TogoLMError as err:
    print(err.status, err.body)
```

### Context manager

`TogoLM` holds an `httpx.Client`; use it as a context manager to close it automatically:

```python
with TogoLM(api_key="your_api_key") as client:
    result = client.query("...")
```

## All methods

| Method | Description |
|--------|-------------|
| `query(question, category=None, language=None, max_tokens=None, history=None)` | RAG query, full response |
| `query_stream(question, category=None, language=None, max_tokens=None, history=None)` | RAG query, SSE stream (generator) |
| `embed(text)` | Generate an embedding vector |
| `search(q)` | Full-text search over the corpus |
| `categories()` | List available corpus categories |
| `stats()` | Public corpus statistics |
| `documents(page=None, page_size=None, category=None, source=None, language=None)` | Paginated document list |
| `document(doc_id)` | Document detail, including chunks |
| `register_key(email, name, use_case=None)` | Request a free API key |
| `me()` | Current API key info and usage |
| `close()` | Close the underlying HTTP client |

Full request/response shapes: [API reference](https://github.com/omarfarouk228/togolm/blob/main/docs/api-reference.md).
