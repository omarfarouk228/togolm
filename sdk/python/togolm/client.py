import json
from collections.abc import Iterator
from typing import Any

import httpx

DEFAULT_BASE_URL = "https://api.togolm.kofcorporation.com/v1"


class TogoLMError(Exception):
    def __init__(self, message: str, status: int, body: str):
        super().__init__(message)
        self.status = status
        self.body = body


class TogoLM:
    def __init__(self, api_key: str | None = None, base_url: str = DEFAULT_BASE_URL):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self._client = httpx.Client(base_url=self.base_url, headers=self._headers())

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["X-API-Key"] = self.api_key
        return headers

    def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        res = self._client.request(method, path, **kwargs)
        if res.is_error:
            raise TogoLMError(f"TogoLM API error: {res.status_code}", res.status_code, res.text)
        return res.json()

    def query(
        self, question: str, category: str | None = None, language: str | None = None
    ) -> dict:
        """RAG query, full (non-streamed) response."""
        body = {"question": question, "category": category, "language": language}
        return self._request("POST", "/query", json=body)

    def query_stream(
        self, question: str, category: str | None = None, language: str | None = None
    ) -> Iterator[dict]:
        """RAG query streamed via SSE. Yields {"type": ...} events:
        "thinking" | "chunk" | "sources" | "error"."""
        body = {"question": question, "category": category, "language": language}
        with self._client.stream("POST", "/query/stream", json=body) as res:
            if res.is_error:
                raise TogoLMError(f"TogoLM API error: {res.status_code}", res.status_code, res.read().decode())
            for line in res.iter_lines():
                if not line.startswith("data: "):
                    continue
                payload = line[len("data: "):]
                if payload == "[DONE]":
                    return
                yield json.loads(payload)

    def embed(self, text: str) -> dict:
        """Generate an embedding vector for a text."""
        return self._request("POST", "/embed", json={"text": text})

    def search(self, q: str) -> dict:
        """Full-text search over the corpus."""
        return self._request("GET", "/search", params={"q": q})

    def categories(self) -> dict:
        """List available corpus categories."""
        return self._request("GET", "/categories")

    def stats(self) -> dict:
        """Public corpus statistics."""
        return self._request("GET", "/stats")

    def documents(
        self, page: int | None = None, limit: int | None = None, category: str | None = None
    ) -> dict:
        """Paginated document list."""
        params = {"page": page, "limit": limit, "category": category}
        return self._request("GET", "/documents", params={k: v for k, v in params.items() if v is not None})

    def document(self, doc_id: str) -> dict:
        """Document detail, including chunks."""
        return self._request("GET", f"/documents/{doc_id}")

    def register_key(self, email: str | None = None, name: str | None = None) -> dict:
        """Request a free API key."""
        return self._request("POST", "/auth/register", json={"email": email, "name": name})

    def me(self) -> dict:
        """Current API key info and usage."""
        return self._request("GET", "/auth/me")

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "TogoLM":
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()
