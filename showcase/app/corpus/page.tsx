"use client";

import { useState, useEffect, useCallback } from "react";
import { ExternalLink, FileText, Layers, ChevronLeft, ChevronRight, Filter } from "lucide-react";
import { useLanguage } from "@/contexts/language";
import { RateLimitBanner } from "@/components/rate-limit-banner";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const BASE_HEADERS: HeadersInit = { "ngrok-skip-browser-warning": "true" };

interface DocumentSummary {
  id: string;
  source: string;
  url: string | null;
  category: string | null;
  subcategory: string | null;
  title: string | null;
  language: string | null;
  published_at: string | null;
  word_count: number | null;
  chunk_count: number;
}

interface DocumentListResponse {
  documents: DocumentSummary[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

const CATEGORIES = [
  "administrative",
  "legal",
  "education",
  "economy",
  "agriculture",
  "health",
  "politics",
  "press",
] as const;

type Category = (typeof CATEGORIES)[number];

const CATEGORY_COLORS: Record<string, string> = {
  administrative: "#006a4e",
  legal: "#d21034",
  education: "#ffce00",
  economy: "#1d4ed8",
  agriculture: "#16a34a",
  health: "#0891b2",
  politics: "#7c3aed",
  press: "#ea580c",
};

function DocCard({ doc }: { doc: DocumentSummary }) {
  const { t } = useLanguage();
  const color = CATEGORY_COLORS[doc.category ?? ""] ?? "#64748b";

  return (
    <div className="bg-white rounded-2xl border border-slate-200 p-5 card-hover flex flex-col gap-3">
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-start gap-3 min-w-0">
          <div
            className="w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0 mt-0.5"
            style={{ background: `${color}14` }}
          >
            <FileText className="w-4 h-4" style={{ color }} />
          </div>
          <h2 className="text-sm font-semibold text-slate-900 leading-snug line-clamp-2">
            {doc.title ?? t.corpus.untitled}
          </h2>
        </div>
        {doc.url && (
          <a
            href={doc.url}
            target="_blank"
            rel="noopener noreferrer"
            className="flex-shrink-0 text-slate-300 hover:text-slate-600 transition-colors mt-0.5"
          >
            <ExternalLink className="w-3.5 h-3.5" />
          </a>
        )}
      </div>

      <div className="flex flex-wrap items-center gap-1.5 text-xs">
        <span className="font-mono bg-slate-100 px-2 py-0.5 rounded-md text-slate-600 truncate max-w-[140px]">
          {doc.source}
        </span>
        {doc.category && (
          <span
            className="px-2 py-0.5 rounded-md text-white font-medium"
            style={{ background: color }}
          >
            {t.categories[doc.category as Category] ?? doc.category}
          </span>
        )}
        {doc.subcategory && (
          <span className="bg-slate-100 px-2 py-0.5 rounded-md text-slate-500">
            {doc.subcategory}
          </span>
        )}
      </div>

      <div className="flex items-center gap-3 text-xs text-slate-400">
        {doc.word_count != null && (
          <span>{doc.word_count.toLocaleString()} {t.corpus.words}</span>
        )}
        {doc.chunk_count > 0 && (
          <span className="flex items-center gap-1">
            <Layers className="w-3 h-3" />
            {doc.chunk_count} {t.corpus.chunks}
          </span>
        )}
        {doc.published_at && (
          <span>{new Date(doc.published_at).toLocaleDateString("fr-TG")}</span>
        )}
      </div>
    </div>
  );
}

function SkeletonCard() {
  return (
    <div className="bg-white rounded-2xl border border-slate-200 p-5 flex flex-col gap-3">
      <div className="flex gap-3">
        <div className="skeleton w-8 h-8 rounded-lg flex-shrink-0" />
        <div className="flex-1 space-y-2">
          <div className="skeleton h-4 w-5/6 rounded" />
          <div className="skeleton h-4 w-3/6 rounded" />
        </div>
      </div>
      <div className="flex gap-2">
        <div className="skeleton h-5 w-24 rounded-md" />
        <div className="skeleton h-5 w-16 rounded-md" />
      </div>
      <div className="flex gap-3">
        <div className="skeleton h-3 w-20 rounded" />
        <div className="skeleton h-3 w-16 rounded" />
      </div>
    </div>
  );
}

export default function CorpusPage() {
  const { t } = useLanguage();
  const [docs, setDocs] = useState<DocumentSummary[]>([]);
  const [total, setTotal] = useState(0);
  const [pages, setPages] = useState(1);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [rateLimited, setRateLimited] = useState(false);
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null);
  const [selectedSource, setSelectedSource] = useState<string | null>(null);
  const [sources, setSources] = useState<string[]>([]);

  const PAGE_SIZE = 24;

  const fetchDocs = useCallback(async () => {
    setLoading(true);
    setError(null);
    setRateLimited(false);
    try {
      const params = new URLSearchParams({ page: String(page), page_size: String(PAGE_SIZE) });
      if (selectedCategory) params.set("category", selectedCategory);
      if (selectedSource) params.set("source", selectedSource);

      const key = localStorage.getItem("togolm-api-key") ?? "";
      const res = await fetch(`${API_BASE}/v1/documents?${params}`, {
        headers: { ...BASE_HEADERS, ...(key ? { "X-API-Key": key } : {}) },
        cache: "no-store",
      });
      if (!res.ok) {
        if (res.status === 429) throw new Error("rate_limited");
        throw new Error(`HTTP ${res.status}`);
      }
      const data: DocumentListResponse = await res.json();
      setDocs(data.documents);
      setTotal(data.total);
      setPages(data.pages);
    } catch (err) {
      const msg = err instanceof Error ? err.message : "";
      if (msg === "rate_limited") {
        setRateLimited(true);
      } else {
        console.error("[Corpus] fetch failed:", msg, "API_BASE:", API_BASE);
        setError(`${t.corpus.error}${msg ? ` (${msg})` : ""}`);
      }
    } finally {
      setLoading(false);
    }
  }, [page, selectedCategory, selectedSource, t.corpus.error]);

  useEffect(() => {
    fetchDocs();
  }, [fetchDocs]);

  useEffect(() => {
    fetch(`${API_BASE}/v1/stats`, { headers: BASE_HEADERS, cache: "no-store" })
      .then((r) => r.json())
      .then((d) => setSources((d.sources ?? []).map((s: { source: string }) => s.source)))
      .catch(() => {});
  }, []);

  function setCategory(cat: string | null) {
    setSelectedCategory(cat);
    setPage(1);
  }

  function setSource(src: string | null) {
    setSelectedSource(src);
    setPage(1);
  }

  return (
    <div className="max-w-6xl mx-auto px-4 py-10">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-3xl font-bold tracking-tight mb-2">{t.corpus.title}</h1>
        <p className="text-sm text-slate-500">
          {t.corpus.subtitle(total > 0 ? total : "…")}
        </p>
      </div>

      {/* Filters */}
      <div className="flex flex-col sm:flex-row gap-4 mb-6">
        {/* Category tabs */}
        <div className="flex flex-wrap gap-2">
          <button
            onClick={() => setCategory(null)}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
              selectedCategory === null
                ? "bg-slate-900 text-white"
                : "bg-white border border-slate-200 text-slate-600 hover:bg-slate-50"
            }`}
          >
            {t.corpus.all}
          </button>
          {CATEGORIES.map((cat) => (
            <button
              key={cat}
              onClick={() => setCategory(cat === selectedCategory ? null : cat)}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
                selectedCategory === cat
                  ? "text-white"
                  : "bg-white border border-slate-200 text-slate-600 hover:bg-slate-50"
              }`}
              style={selectedCategory === cat ? { background: CATEGORY_COLORS[cat] } : {}}
            >
              {t.categories[cat]}
            </button>
          ))}
        </div>

        {/* Source select */}
        {sources.length > 0 && (
          <div className="flex items-center gap-2 sm:ml-auto">
            <Filter className="w-3.5 h-3.5 text-slate-400 flex-shrink-0" />
            <select
              value={selectedSource ?? ""}
              onChange={(e) => setSource(e.target.value || null)}
              className="text-xs border border-slate-200 rounded-lg px-2.5 py-1.5 bg-white text-slate-700 focus:outline-none focus:ring-2 focus:ring-green-800/20"
            >
              <option value="">{t.corpus.allSources}</option>
              {sources.map((s) => (
                <option key={s} value={s}>{s}</option>
              ))}
            </select>
          </div>
        )}
      </div>

      {/* Active filters summary */}
      {(selectedCategory || selectedSource) && (
        <div className="flex items-center gap-2 mb-5 text-xs text-slate-500">
          <span>{t.corpus.filteringBy}</span>
          {selectedCategory && (
            <span
              className="px-2 py-0.5 rounded-md text-white"
              style={{ background: CATEGORY_COLORS[selectedCategory] }}
            >
              {t.categories[selectedCategory as Category] ?? selectedCategory}
            </span>
          )}
          {selectedSource && (
            <span className="font-mono bg-slate-100 px-2 py-0.5 rounded-md text-slate-600">
              {selectedSource}
            </span>
          )}
          <button
            onClick={() => { setCategory(null); setSource(null); }}
            className="text-slate-400 hover:text-slate-700 underline transition-colors"
          >
            {t.corpus.clear}
          </button>
        </div>
      )}

      {/* Rate limit banner */}
      {rateLimited && (
        <div className="mb-6">
          <RateLimitBanner />
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="bg-red-50 border border-red-200 rounded-xl px-4 py-3 text-sm text-red-600 mb-6 flex items-center justify-between gap-4">
          <span>
            {error}
            <span className="ml-1 font-mono text-xs text-red-400">{API_BASE}</span>
          </span>
          <button
            onClick={fetchDocs}
            className="flex-shrink-0 text-xs underline hover:no-underline"
          >
            Réessayer
          </button>
        </div>
      )}

      {/* Grid */}
      {loading ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {Array.from({ length: 12 }).map((_, i) => <SkeletonCard key={i} />)}
        </div>
      ) : docs.length === 0 ? (
        <div className="text-center py-20 text-slate-400 text-sm">
          {t.corpus.noDocuments}
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 animate-fade-in-up">
          {docs.map((doc) => <DocCard key={doc.id} doc={doc} />)}
        </div>
      )}

      {/* Pagination */}
      {pages > 1 && !loading && (
        <div className="flex items-center justify-between mt-8">
          <button
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={page === 1}
            className="flex items-center gap-1.5 px-4 py-2 text-sm border border-slate-200 rounded-xl bg-white hover:bg-slate-50 disabled:opacity-40 transition-all"
          >
            <ChevronLeft className="w-4 h-4" /> {t.corpus.previous}
          </button>

          <span className="text-sm text-slate-500 tabular-nums">
            {t.corpus.page(page, pages)} &nbsp;·&nbsp; {total.toLocaleString()} {t.corpus.docs}
          </span>

          <button
            onClick={() => setPage((p) => Math.min(pages, p + 1))}
            disabled={page === pages}
            className="flex items-center gap-1.5 px-4 py-2 text-sm border border-slate-200 rounded-xl bg-white hover:bg-slate-50 disabled:opacity-40 transition-all"
          >
            {t.corpus.next} <ChevronRight className="w-4 h-4" />
          </button>
        </div>
      )}
    </div>
  );
}
