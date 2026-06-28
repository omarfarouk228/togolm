const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

const BASE_HEADERS: HeadersInit = {
  "ngrok-skip-browser-warning": "true",
};

async function checkResponse(res: Response): Promise<Response> {
  if (res.ok) return res;
  if (res.status === 429) throw new Error("rate_limited");
  throw new Error(`http_${res.status}`);
}

export interface CorpusStats {
  total_documents: number;
  total_chunks: number;
  languages: string[];
  sources: { source: string; documents: number; chunks: number }[];
  last_updated: string | null;
  model_version: string;
}

export interface SearchResult {
  id: string;
  source: string;
  url: string | null;
  title: string | null;
  excerpt: string;
  score: number;
}

export interface SearchResponse {
  results: SearchResult[];
  total: number;
  query: string;
}

export interface QuerySource {
  title: string;
  url: string | null;
  score: number;
}

export interface QueryResponse {
  answer: string;
  sources: QuerySource[];
  model: string;
  latency_ms: number;
}

export async function fetchStats(): Promise<CorpusStats> {
  const res = await fetch(`${API_BASE}/v1/stats`, {
    headers: BASE_HEADERS,
    next: { revalidate: 60 },
  });
  if (!res.ok) throw new Error("Failed to fetch stats");
  return res.json();
}

export async function searchCorpus(q: string, source?: string, apiKey?: string): Promise<SearchResponse> {
  const params = new URLSearchParams({ q });
  if (source) params.set("source", source);
  const res = await fetch(`${API_BASE}/v1/search?${params}`, {
    headers: { ...BASE_HEADERS, ...(apiKey ? { "X-API-Key": apiKey } : {}) },
    cache: "no-store",
  });
  await checkResponse(res);
  return res.json();
}

export interface RegisterAPIKeyRequest {
  name: string;
  email: string;
  use_case?: string;
}

export interface RegisterAPIKeyResponse {
  api_key: string;
  key_prefix: string;
  plan: string;
  quota_per_day: number;
  message: string;
}

export interface APIKeyUsage {
  name: string | null;
  email: string | null;
  plan: string;
  key_prefix: string;
  requests_today: number;
  quota_per_day: number;
  remaining_today: number;
}

export async function registerAPIKey(data: RegisterAPIKeyRequest): Promise<RegisterAPIKeyResponse> {
  const res = await fetch(`${API_BASE}/v1/auth/register`, {
    method: "POST",
    headers: { ...BASE_HEADERS, "Content-Type": "application/json" },
    body: JSON.stringify(data),
    cache: "no-store",
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error((err as { detail?: string }).detail ?? "Registration failed");
  }
  return res.json();
}

export async function getAPIKeyUsage(apiKey: string): Promise<APIKeyUsage> {
  const res = await fetch(`${API_BASE}/v1/auth/me`, {
    headers: { ...BASE_HEADERS, "X-API-Key": apiKey },
    cache: "no-store",
  });
  if (!res.ok) throw new Error("Invalid API key");
  return res.json();
}

export async function queryRAG(question: string): Promise<QueryResponse> {
  const res = await fetch(`${API_BASE}/v1/query`, {
    method: "POST",
    headers: { ...BASE_HEADERS, "Content-Type": "application/json" },
    body: JSON.stringify({ question }),
    cache: "no-store",
  });
  await checkResponse(res);
  return res.json();
}

export interface HistoryMessage {
  role: "user" | "assistant";
  content: string;
}

export type StreamEvent =
  | { type: "chunk"; text: string }
  | { type: "thinking"; text: string }
  | { type: "sources"; sources: QuerySource[]; latency_ms: number }
  | { type: "error"; message: string };

export async function* queryRAGStream(
  question: string,
  signal?: AbortSignal,
  apiKey?: string,
  history?: HistoryMessage[],
): AsyncGenerator<StreamEvent> {
  const body: Record<string, unknown> = { question, max_tokens: 1500 };
  if (history && history.length > 0) {
    body.history = history.map((m) => ({
      role: m.role,
      content: m.content.slice(0, 500),
    }));
  }
  const res = await fetch(`${API_BASE}/v1/query/stream`, {
    method: "POST",
    headers: {
      ...BASE_HEADERS,
      "Content-Type": "application/json",
      ...(apiKey ? { "X-API-Key": apiKey } : {}),
    },
    body: JSON.stringify(body),
    cache: "no-store",
    signal,
  });
  await checkResponse(res);

  const reader = res.body!.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });

      const blocks = buffer.split("\n\n");
      buffer = blocks.pop() ?? "";

      for (const block of blocks) {
        const line = block.trim();
        if (!line.startsWith("data: ")) continue;
        const payload = line.slice(6).trim();
        if (payload === "[DONE]") return;
        try {
          yield JSON.parse(payload) as StreamEvent;
        } catch {
          // malformed SSE line — skip
        }
      }
    }
  } finally {
    reader.releaseLock();
  }
}
