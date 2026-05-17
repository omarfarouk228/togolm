"use client";

import { useState } from "react";
import { searchCorpus, type SearchResult } from "@/lib/api";
import { Search, ExternalLink, Loader2, FileText } from "lucide-react";

function SkeletonCard() {
  return (
    <div className="bg-white rounded-2xl border border-slate-200 p-6">
      <div className="flex gap-3 mb-3">
        <div className="skeleton w-8 h-8 rounded-lg flex-shrink-0" />
        <div className="skeleton h-5 w-3/4 rounded" />
      </div>
      <div className="sm:pl-11 space-y-2">
        <div className="skeleton h-3.5 w-full rounded" />
        <div className="skeleton h-3.5 w-5/6 rounded" />
        <div className="skeleton h-3.5 w-4/6 rounded" />
      </div>
      <div className="flex gap-2 mt-4 sm:pl-11">
        <div className="skeleton h-5 w-24 rounded-md" />
        <div className="skeleton h-5 w-16 rounded-md" />
      </div>
    </div>
  );
}

export default function SearchPage() {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<SearchResult[]>([]);
  const [total, setTotal] = useState<number | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [searched, setSearched] = useState(false);
  const [lastQuery, setLastQuery] = useState("");

  async function handleSearch(e: React.FormEvent) {
    e.preventDefault();
    if (!query.trim()) return;
    const q = query.trim();
    setLoading(true);
    setError(null);
    setSearched(false);
    try {
      const data = await searchCorpus(q);
      setResults(data.results);
      setTotal(data.total);
      setLastQuery(q);
      setSearched(true);
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
      <div className="mb-8">
        <h1 className="text-3xl font-bold tracking-tight mb-2">Search</h1>
        <p className="text-sm text-slate-500">Full-text search across the Togolese public document corpus.</p>
      </div>

      <form onSubmit={handleSearch} className="flex gap-2 mb-8">
        <div className="flex-1 relative">
          <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400 pointer-events-none" />
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="budget 2024, loi fiscale, recrutement enseignants…"
            className="w-full pl-11 pr-4 py-3.5 border border-slate-200 rounded-xl text-sm bg-white focus:outline-none focus:ring-2 focus:ring-green-800/25 focus:border-green-800/50 shadow-sm transition-all"
          />
        </div>
        <button
          type="submit"
          disabled={loading || !query.trim()}
          className="px-5 py-3.5 rounded-xl text-white text-sm font-semibold disabled:opacity-40 transition-opacity hover:opacity-90 shadow-sm"
          style={{ background: "var(--togo-green)" }}
        >
          {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : "Search"}
        </button>
      </form>

      {error && (
        <div className="bg-red-50 border border-red-200 rounded-xl px-4 py-3 text-sm text-red-600 mb-6">
          {error}
        </div>
      )}

      {total !== null && !loading && (
        <p className="text-sm text-slate-400 mb-5">
          <span className="font-semibold text-slate-700">{total}</span> result{total !== 1 ? "s" : ""} for{" "}
          <span className="font-medium text-slate-700">&ldquo;{lastQuery}&rdquo;</span>
        </p>
      )}

      {/* Skeleton loading */}
      {loading && (
        <div className="space-y-4">
          {Array.from({ length: 4 }).map((_, i) => <SkeletonCard key={i} />)}
        </div>
      )}

      {/* Results */}
      {!loading && results.length > 0 && (
        <div className="space-y-4 animate-fade-in-up">
          {results.map((r) => (
            <div key={r.id} className="bg-white rounded-2xl border border-slate-200 p-6 card-hover">
              <div className="flex items-start justify-between gap-3 mb-3">
                <div className="flex items-start gap-3">
                  <div
                    className="w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0 mt-0.5"
                    style={{ background: "rgba(0, 106, 78, 0.08)" }}
                  >
                    <FileText className="w-4 h-4" style={{ color: "var(--togo-green)" }} />
                  </div>
                  <h2 className="font-semibold text-slate-900 leading-snug">{r.title ?? "Untitled"}</h2>
                </div>
                {r.url && (
                  <a
                    href={r.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex-shrink-0 text-slate-300 hover:text-slate-600 transition-colors"
                  >
                    <ExternalLink className="w-4 h-4" />
                  </a>
                )}
              </div>

              <p className="text-sm text-slate-500 leading-relaxed mb-4 sm:pl-11">{r.excerpt}</p>

              <div className="flex items-center gap-3 text-xs text-slate-400 sm:pl-11">
                <span className="font-mono bg-slate-100 px-2 py-1 rounded-md text-slate-600">{r.source}</span>
                <span className="flex items-center gap-1.5">
                  <span
                    className="w-1.5 h-1.5 rounded-full inline-block"
                    style={{ background: `hsl(${Math.round(r.score * 120)}, 60%, 42%)` }}
                  />
                  {(r.score * 100).toFixed(1)}% match
                </span>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Empty state */}
      {searched && results.length === 0 && !loading && (
        <div className="text-center py-16 animate-fade-in-up">
          <div className="w-12 h-12 rounded-xl bg-slate-100 flex items-center justify-center mx-auto mb-4">
            <Search className="w-5 h-5 text-slate-400" />
          </div>
          <p className="text-slate-600 font-medium mb-1">No results found</p>
          <p className="text-slate-400 text-sm">Try a different search term or a broader query</p>
        </div>
      )}

      {/* Initial state */}
      {!searched && !loading && !error && (
        <div className="text-center py-16 text-slate-400 text-sm">
          Type a query above to search the corpus
        </div>
      )}
    </div>
  );
}
