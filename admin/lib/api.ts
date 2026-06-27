import { getToken, removeToken } from "./auth";

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

// ---- Types ----------------------------------------------------------------

export interface LoginResponse {
  token: string;
  expires_at: string;
}

export interface CorpusStats {
  total_documents: number;
  total_chunks: number;
  embedded_chunks: number;
  by_category: Record<string, number>;
  by_language: Record<string, number>;
}

export interface CorpusSource {
  source: string;
  category: string;
  doc_count: number;
  last_collected: string | null;
}

export interface RecentDocument {
  id: string;
  title: string | null;
  source: string;
  language: string;
  category: string;
  created_at: string;
}

export interface ApiKey {
  id: string;
  name: string;
  email: string;
  plan: "free" | "dev" | "institution";
  use_case: string;
  is_active: boolean;
  created_at: string;
  key_prefix: string;
}

export interface CreateKeyBody {
  name: string;
  email: string;
  use_case: string;
  plan: "free" | "dev" | "institution";
}

export interface UpdateKeyBody {
  plan?: "free" | "dev" | "institution";
  is_active?: boolean;
}

export interface QueryRecord {
  id: string;
  question: string;
  language: string | null;
  category: string | null;
  is_off_topic: boolean;
  chunks_found: number;
  latency_ms: number | null;
  api_key_prefix: string | null;
  created_at: string | null;
}

export interface QueryListResponse {
  items: QueryRecord[];
  total: number;
  page: number;
  page_size: number;
}

export interface QueryStats {
  total_queries: number;
  period_queries: number;
  off_topic_count: number;
  off_topic_rate_pct: number;
  avg_latency_ms: number;
  days: number;
}

export interface DayStats {
  date: string;
  total: number;
  rate_limit_hits: number;
  by_plan: Record<string, number>;
}

export interface UsageStats {
  by_day: DayStats[];
  requests_today: number;
  total_requests: number;
}

export interface ServiceHealth {
  status: "ok" | "error";
  response_time_ms?: number;
  error?: string;
  details?: Record<string, unknown>;
}

export interface DetailedHealth {
  database: ServiceHealth;
  redis: ServiceHealth;
  embedding_coverage: number;
  chunks_with_embeddings: number;
  total_chunks: number;
}

// ---- Fetch helper ----------------------------------------------------------

async function apiFetch<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const token = getToken();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string>),
  };
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const res = await fetch(`${BASE}${path}`, { ...options, headers });

  if (!res.ok) {
    if (res.status === 401) {
      removeToken();
      window.location.replace("/login");
      return undefined as T;
    }
    const text = await res.text().catch(() => res.statusText);
    throw new Error(`HTTP ${res.status}: ${text}`);
  }

  // 204 No Content
  if (res.status === 204) return undefined as T;

  return res.json() as Promise<T>;
}

// ---- Auth ------------------------------------------------------------------

export async function adminLogin(key: string): Promise<LoginResponse> {
  return apiFetch<LoginResponse>("/v1/admin/login", {
    method: "POST",
    body: JSON.stringify({ key }),
  });
}

// ---- Corpus ----------------------------------------------------------------

export async function getCorpusStats(): Promise<CorpusStats> {
  return apiFetch<CorpusStats>("/v1/admin/corpus/stats");
}

export async function getCorpusSources(): Promise<CorpusSource[]> {
  return apiFetch<CorpusSource[]>("/v1/admin/corpus/sources");
}

export async function getRecentDocuments(limit = 20): Promise<RecentDocument[]> {
  return apiFetch<RecentDocument[]>(`/v1/admin/corpus/recent?limit=${limit}`);
}

// ---- API Keys --------------------------------------------------------------

export async function getApiKeys(): Promise<ApiKey[]> {
  return apiFetch<ApiKey[]>("/v1/admin/keys");
}

export async function createApiKey(body: CreateKeyBody): Promise<ApiKey> {
  return apiFetch<ApiKey>("/v1/admin/keys", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function updateApiKey(id: string, body: UpdateKeyBody): Promise<ApiKey> {
  return apiFetch<ApiKey>(`/v1/admin/keys/${id}`, {
    method: "PATCH",
    body: JSON.stringify(body),
  });
}

export async function deleteApiKey(id: string): Promise<void> {
  return apiFetch<void>(`/v1/admin/keys/${id}`, { method: "DELETE" });
}

// ---- Queries ---------------------------------------------------------------

export interface QueryFilters {
  offTopicOnly?: boolean;
  category?: string;
  language?: string;
  latencyMin?: number;
  latencyMax?: number;
  chunksMin?: number;
  chunksMax?: number;
  dateFrom?: string;
  dateTo?: string;
}

export async function getQueries(
  page = 1,
  pageSize = 20,
  filters: QueryFilters = {}
): Promise<QueryListResponse> {
  const p = new URLSearchParams({
    page: String(page),
    page_size: String(pageSize),
    off_topic_only: String(filters.offTopicOnly ?? false),
  });
  if (filters.category) p.set("category", filters.category);
  if (filters.language) p.set("language", filters.language);
  if (filters.latencyMin != null) p.set("latency_min", String(filters.latencyMin));
  if (filters.latencyMax != null) p.set("latency_max", String(filters.latencyMax));
  if (filters.chunksMin != null) p.set("chunks_min", String(filters.chunksMin));
  if (filters.chunksMax != null) p.set("chunks_max", String(filters.chunksMax));
  if (filters.dateFrom) p.set("date_from", filters.dateFrom);
  if (filters.dateTo) p.set("date_to", filters.dateTo);
  return apiFetch<QueryListResponse>(`/v1/admin/queries?${p.toString()}`);
}

export async function getQueryStats(days = 7): Promise<QueryStats> {
  return apiFetch<QueryStats>(`/v1/admin/queries/stats?days=${days}`);
}

// ---- Usage Stats -----------------------------------------------------------

export async function getUsageStats(days = 7): Promise<UsageStats> {
  return apiFetch<UsageStats>(`/v1/admin/stats?days=${days}`);
}

// ---- Health ----------------------------------------------------------------

export async function getDetailedHealth(): Promise<DetailedHealth> {
  return apiFetch<DetailedHealth>("/v1/admin/health/detailed");
}
