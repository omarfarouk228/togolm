const DEFAULT_BASE_URL = "https://api.togolm.com/v1";

export class TogoLMError extends Error {
  constructor(message, status, body) {
    super(message);
    this.name = "TogoLMError";
    this.status = status;
    this.body = body;
  }
}

export class TogoLM {
  /**
   * @param {{ apiKey?: string, baseUrl?: string }} [options]
   */
  constructor({ apiKey, baseUrl = DEFAULT_BASE_URL } = {}) {
    this.apiKey = apiKey;
    this.baseUrl = baseUrl.replace(/\/$/, "");
  }

  _headers(extra = {}) {
    const headers = { "Content-Type": "application/json", ...extra };
    if (this.apiKey) headers["X-API-Key"] = this.apiKey;
    return headers;
  }

  async _request(method, path, { params, body } = {}) {
    const url = new URL(this.baseUrl + path);
    if (params) {
      for (const [key, value] of Object.entries(params)) {
        if (value !== undefined) url.searchParams.set(key, value);
      }
    }
    const res = await fetch(url, {
      method,
      headers: this._headers(),
      body: body ? JSON.stringify(body) : undefined,
    });
    if (!res.ok) {
      const text = await res.text().catch(() => "");
      throw new TogoLMError(`TogoLM API error: ${res.status}`, res.status, text);
    }
    return res.json();
  }

  /**
   * RAG query, full (non-streamed) response.
   * `history` is a list of {role: "user"|"assistant", content: string}, oldest
   * first, for multi-turn conversations (max 20 messages).
   */
  query({ question, category, language, maxTokens, history }) {
    return this._request("POST", "/query", {
      body: { question, category, language, max_tokens: maxTokens, history },
    });
  }

  /**
   * RAG query streamed via SSE. Yields `{type, ...}` events:
   * "thinking" | "chunk" | "sources" | "error".
   * `history` is a list of {role: "user"|"assistant", content: string}, oldest
   * first, for multi-turn conversations (max 20 messages).
   * @returns {AsyncGenerator<object>}
   */
  async *queryStream({ question, category, language, maxTokens, history }) {
    const res = await fetch(`${this.baseUrl}/query/stream`, {
      method: "POST",
      headers: this._headers(),
      body: JSON.stringify({ question, category, language, max_tokens: maxTokens, history }),
    });
    if (!res.ok || !res.body) {
      const text = await res.text().catch(() => "");
      throw new TogoLMError(`TogoLM API error: ${res.status}`, res.status, text);
    }

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });

      const lines = buffer.split("\n");
      buffer = lines.pop() ?? "";

      for (const line of lines) {
        if (!line.startsWith("data: ")) continue;
        const payload = line.slice(6);
        if (payload === "[DONE]") return;
        yield JSON.parse(payload);
      }
    }
  }

  /** Generate an embedding vector for a text. */
  embed(text) {
    return this._request("POST", "/embed", { body: { text } });
  }

  /** Full-text search over the corpus. */
  search(q) {
    return this._request("GET", "/search", { params: { q } });
  }

  /** List available corpus categories. */
  categories() {
    return this._request("GET", "/categories");
  }

  /** Public corpus statistics. */
  stats() {
    return this._request("GET", "/stats");
  }

  /** Paginated document list. */
  documents({ page, pageSize, category, source, language } = {}) {
    return this._request("GET", "/documents", {
      params: { page, page_size: pageSize, category, source, language },
    });
  }

  /** Document detail, including chunks. */
  document(id) {
    return this._request("GET", `/documents/${id}`);
  }

  /** Request a free API key. The plain-text key is returned once — save it immediately. */
  registerKey({ email, name, useCase }) {
    return this._request("POST", "/auth/register", {
      body: { email, name, use_case: useCase },
    });
  }

  /** Current API key info and usage. */
  me() {
    return this._request("GET", "/auth/me");
  }
}

export default TogoLM;
