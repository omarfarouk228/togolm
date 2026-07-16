import json
from collections.abc import Iterator
from typing import Any

import httpx

DEFAULT_BASE_URL = "https://api.togolm.com/v1"


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

    @staticmethod
    def _query_body(
        question: str,
        category: str | None,
        language: str | None,
        max_tokens: int | None,
        history: list[dict] | None,
    ) -> dict:
        body: dict = {"question": question}
        if category is not None:
            body["category"] = category
        if language is not None:
            body["language"] = language
        if max_tokens is not None:
            body["max_tokens"] = max_tokens
        if history is not None:
            body["history"] = history
        return body

    def query(
        self,
        question: str,
        category: str | None = None,
        language: str | None = None,
        max_tokens: int | None = None,
        history: list[dict] | None = None,
    ) -> dict:
        """RAG query, full (non-streamed) response.

        `history` is a list of {"role": "user" | "assistant", "content": str},
        oldest first, for multi-turn conversations (max 20 messages).
        """
        body = self._query_body(question, category, language, max_tokens, history)
        return self._request("POST", "/query", json=body)

    def query_stream(
        self,
        question: str,
        category: str | None = None,
        language: str | None = None,
        max_tokens: int | None = None,
        history: list[dict] | None = None,
    ) -> Iterator[dict]:
        """RAG query streamed via SSE. Yields {"type": ...} events:
        "thinking" | "chunk" | "sources" | "error".

        `history` is a list of {"role": "user" | "assistant", "content": str},
        oldest first, for multi-turn conversations (max 20 messages).
        """
        body = self._query_body(question, category, language, max_tokens, history)
        with self._client.stream("POST", "/query/stream", json=body) as res:
            if res.is_error:
                raise TogoLMError(
                    f"TogoLM API error: {res.status_code}", res.status_code, res.read().decode()
                )
            for line in res.iter_lines():
                if not line.startswith("data: "):
                    continue
                payload = line[len("data: ") :]
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
        self,
        page: int | None = None,
        page_size: int | None = None,
        category: str | None = None,
        source: str | None = None,
        language: str | None = None,
    ) -> dict:
        """Paginated document list."""
        params = {
            "page": page,
            "page_size": page_size,
            "category": category,
            "source": source,
            "language": language,
        }
        return self._request(
            "GET", "/documents", params={k: v for k, v in params.items() if v is not None}
        )

    def document(self, doc_id: str) -> dict:
        """Document detail, including chunks."""
        return self._request("GET", f"/documents/{doc_id}")

    def register_key(self, email: str, name: str, use_case: str | None = None) -> dict:
        """Request a free API key. The plain-text key is returned once — save it immediately."""
        body = {"email": email, "name": name}
        if use_case is not None:
            body["use_case"] = use_case
        return self._request("POST", "/auth/register", json=body)

    def me(self) -> dict:
        """Current API key info and usage."""
        return self._request("GET", "/auth/me")

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "TogoLM":
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()
