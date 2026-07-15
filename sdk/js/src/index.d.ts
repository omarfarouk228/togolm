export interface TogoLMOptions {
  apiKey?: string;
  baseUrl?: string;
}

export interface Source {
  title: string;
  url: string;
  score: number;
}

export interface HistoryMessage {
  role: "user" | "assistant";
  content: string;
}

export interface QueryResponse {
  answer: string;
  sources: Source[];
  model: string;
  latency_ms: number;
}

export type StreamEvent =
  | { type: "thinking"; text: string }
  | { type: "chunk"; text: string }
  | { type: "sources"; sources: Source[]; latency_ms: number }
  | { type: "error"; message: string };

export declare class TogoLMError extends Error {
  status: number;
  body: string;
}

export interface QueryParams {
  question: string;
  category?: string;
  language?: string;
  maxTokens?: number;
  history?: HistoryMessage[];
}

export declare class TogoLM {
  constructor(options?: TogoLMOptions);
  query(params: QueryParams): Promise<QueryResponse>;
  queryStream(params: QueryParams): AsyncGenerator<StreamEvent>;
  embed(text: string): Promise<{ embedding: number[]; model: string; token_count: number }>;
  search(q: string): Promise<unknown>;
  categories(): Promise<{ categories: string[]; total: number }>;
  stats(): Promise<unknown>;
  documents(params?: {
    page?: number;
    pageSize?: number;
    category?: string;
    source?: string;
    language?: string;
  }): Promise<unknown>;
  document(id: string): Promise<unknown>;
  registerKey(params: { email: string; name: string; useCase?: string }): Promise<{
    api_key: string;
    key_prefix: string;
    plan: string;
    quota_per_day: number;
    message: string;
  }>;
  me(): Promise<unknown>;
}

export default TogoLM;
