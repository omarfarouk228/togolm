"use client";

import { useState } from "react";
import { searchCorpus, type SearchResult } from "@/lib/api";
import { Search, ExternalLink, Loader2 } from "lucide-react";

export default function SearchPage() {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<SearchResult[]>([]);
  const [total, setTotal] = useState<number | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSearch(e: React.FormEvent) {
    e.preventDefault();
    if (!query.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const data = await searchCorpus(query.trim());
      setResults(data.results);
      setTotal(data.total);
    } catch {
      setError("Search failed — is the API running?");
      setResults([]);
      setTotal(null);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="max-w-3xl mx-auto px-4 py-12">
      <h1 className="text-2xl font-bold mb-6">Search the corpus</h1>

      <form onSubmit={handleSearch} className="flex gap-2 mb-8">
        <div className="flex-1 relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="budget 2024, loi fiscale, recrutement enseignants…"
            className="w-full pl-9 pr-4 py-2.5 border border-gray-200 rounded-lg text-sm bg-white focus:outline-none focus:ring-2 focus:ring-green-600/30 focus:border-green-600"
          />
        </div>
        <button
          type="submit"
          disabled={loading || !query.trim()}
          className="px-4 py-2.5 rounded-lg text-white text-sm font-medium disabled:opacity-50 transition-opacity hover:opacity-90"
          style={{ background: "var(--togo-green)" }}
        >
          {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : "Search"}
        </button>
      </form>

      {error && (
        <p className="text-sm text-red-500 mb-6">{error}</p>
      )}

      {total !== null && (
        <p className="text-sm text-gray-400 mb-4">
          {total} result{total !== 1 ? "s" : ""} for <span className="font-medium text-gray-700">&ldquo;{query}&rdquo;</span>
        </p>
      )}

      <div className="space-y-4">
        {results.map((r) => (
          <div key={r.id} className="bg-white rounded-xl border border-gray-200 p-5">
            <div className="flex items-start justify-between gap-3 mb-2">
              <h2 className="font-medium text-gray-900 leading-snug">
                {r.title ?? "Untitled"}
              </h2>
              {r.url && (
                <a
                  href={r.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex-shrink-0 text-gray-400 hover:text-gray-600 transition-colors"
                >
                  <ExternalLink className="w-4 h-4" />
                </a>
              )}
            </div>
            <p className="text-sm text-gray-500 leading-relaxed mb-3">{r.excerpt}</p>
            <div className="flex items-center gap-3 text-xs text-gray-400">
              <span className="font-mono bg-gray-100 px-1.5 py-0.5 rounded">{r.source}</span>
              <span>score {r.score.toFixed(3)}</span>
            </div>
          </div>
        ))}
      </div>

      {results.length === 0 && total === 0 && (
        <p className="text-center text-gray-400 text-sm py-12">
          No results found for &ldquo;{query}&rdquo;
        </p>
      )}
    </div>
  );
}
