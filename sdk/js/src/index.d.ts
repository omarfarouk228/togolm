export interface TogoLMOptions {
  apiKey?: string;
  baseUrl?: string;
}

export interface Source {
  title: string;
  url: string;
  score: number;
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

export declare class TogoLM {
  constructor(options?: TogoLMOptions);
  query(params: { question: string; category?: string; language?: string }): Promise<QueryResponse>;
  queryStream(params: { question: string; category?: string; language?: string }): AsyncGenerator<StreamEvent>;
  embed(text: string): Promise<{ embedding: number[]; model: string; token_count: number }>;
  search(q: string): Promise<unknown>;
  categories(): Promise<{ categories: string[]; total: number }>;
  stats(): Promise<unknown>;
  documents(params?: { page?: number; limit?: number; category?: string }): Promise<unknown>;
  document(id: string): Promise<unknown>;
  registerKey(params?: { email?: string; name?: string }): Promise<unknown>;
  me(): Promise<unknown>;
}

export default TogoLM;
