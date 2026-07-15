# togolm

Minimal Python client for the [TogoLM API](../../docs/api-reference.md).

## Install

```bash
pip install togolm
```

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

Omit `api_key` for public, rate-limited access. See the [API reference](../../docs/api-reference.md) for rate limits and full endpoint documentation.
