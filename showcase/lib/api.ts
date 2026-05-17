const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

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
  const res = await fetch(`${API_BASE}/v1/stats`, { next: { revalidate: 60 } });
  if (!res.ok) throw new Error("Failed to fetch stats");
  return res.json();
}

export async function searchCorpus(q: string, source?: string): Promise<SearchResponse> {
  const params = new URLSearchParams({ q });
  if (source) params.set("source", source);
  const res = await fetch(`${API_BASE}/v1/search?${params}`, { cache: "no-store" });
  if (!res.ok) throw new Error("Search failed");
  return res.json();
}

export async function queryRAG(question: string): Promise<QueryResponse> {
  const res = await fetch(`${API_BASE}/v1/query`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question }),
    cache: "no-store",
  });
  if (!res.ok) throw new Error("Query failed");
  return res.json();
}

export type StreamEvent =
  | { type: "chunk"; text: string }
  | { type: "sources"; sources: QuerySource[]; latency_ms: number }
  | { type: "error"; message: string };

export async function* queryRAGStream(
  question: string,
  signal?: AbortSignal
): AsyncGenerator<StreamEvent> {
  const res = await fetch(`${API_BASE}/v1/query/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question }),
    cache: "no-store",
    signal,
  });
  if (!res.ok) throw new Error("Stream failed");

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
