"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { getQueries, getQueryStats, type QueryRecord, type QueryFilters } from "@/lib/api";
import { useT } from "@/lib/i18n";
import { StatCard } from "@/components/stat-card";
import { StatusBadge } from "@/components/status-badge";
import { ShimmerStatCards, ShimmerTable } from "@/components/shimmer";
import {
  MessageSquare,
  AlertTriangle,
  Clock,
  ChevronLeft,
  ChevronRight,
  Eye,
  X,
  SlidersHorizontal,
} from "lucide-react";
import { format, parseISO } from "date-fns";

function ErrorMsg({ msg }: { msg: string }) {
  return (
    <div className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-lg px-4 py-3">
      {msg}
    </div>
  );
}

function FilterInput({ label, ...props }: { label: string } & React.InputHTMLAttributes<HTMLInputElement>) {
  return (
    <div>
      <label className="block text-xs text-slate-500 mb-1">{label}</label>
      <input
        {...props}
        className="w-full px-3 py-1.5 text-sm border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-green-500 bg-white"
      />
    </div>
  );
}

function FilterSelect({ label, children, ...props }: { label: string } & React.SelectHTMLAttributes<HTMLSelectElement>) {
  return (
    <div>
      <label className="block text-xs text-slate-500 mb-1">{label}</label>
      <select
        {...props}
        className="w-full px-3 py-1.5 text-sm border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-green-500 bg-white"
      >
        {children}
      </select>
    </div>
  );
}

function QuerySheet({ query, onClose, t }: { query: QueryRecord; onClose: () => void; t: (k: string) => string }) {
  return (
    <>
      <div className="fixed inset-0 z-40 bg-black/30 backdrop-blur-sm" onClick={onClose} />
      <div className="fixed inset-y-0 right-0 z-50 w-full max-w-md bg-white shadow-xl flex flex-col">
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-100">
          <h2 className="font-semibold text-slate-800">{t("queries.detail")}</h2>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-600 transition-colors">
            <X size={18} />
          </button>
        </div>
        <div className="flex-1 overflow-y-auto px-6 py-5 space-y-5">
          <div>
            <p className="text-xs font-medium text-slate-400 uppercase tracking-wider mb-2">
              {t("queries.question")}
            </p>
            <p className="text-slate-800 text-sm leading-relaxed">{query.question}</p>
          </div>

          <div className="border-t border-slate-100" />

          <div className="grid grid-cols-2 gap-4">
            <div>
              <p className="text-xs text-slate-400 mb-1">{t("queries.date")}</p>
              <p className="text-sm font-medium text-slate-700">
                {query.created_at ? format(parseISO(query.created_at), "MMM d, yyyy HH:mm") : "—"}
              </p>
            </div>
            <div>
              <p className="text-xs text-slate-400 mb-1">{t("queries.offTopic")}</p>
              <div className="mt-0.5">
                {query.is_off_topic
                  ? <StatusBadge label={t("queries.yes")} variant="red" />
                  : <StatusBadge label={t("queries.no")} variant="green" />}
              </div>
            </div>
            <div>
              <p className="text-xs text-slate-400 mb-1">{t("queries.chunksFound")}</p>
              <p className="text-sm font-medium text-slate-700">{query.chunks_found}</p>
            </div>
            <div>
              <p className="text-xs text-slate-400 mb-1">{t("queries.latency")}</p>
              <p className="text-sm font-medium text-slate-700">
                {query.latency_ms != null ? `${Math.round(query.latency_ms)} ms` : "—"}
              </p>
            </div>
            <div>
              <p className="text-xs text-slate-400 mb-1">{t("queries.language")}</p>
              <p className="text-sm font-medium text-slate-700 uppercase">{query.language ?? "—"}</p>
            </div>
            <div>
              <p className="text-xs text-slate-400 mb-1">{t("queries.category")}</p>
              <p className="text-sm font-medium text-slate-700">{query.category ?? "—"}</p>
            </div>
            <div className="col-span-2">
              <p className="text-xs text-slate-400 mb-1">{t("queries.apiKey")}</p>
              <p className="text-sm font-mono text-slate-600">
                {query.api_key_prefix ? `${query.api_key_prefix}…` : "—"}
              </p>
            </div>
          </div>
        </div>
      </div>
    </>
  );
}

const EMPTY_FILTERS: QueryFilters = {};

export default function QueriesPage() {
  const { t } = useT();
  const [page, setPage] = useState(1);
  const [filters, setFilters] = useState<QueryFilters>(EMPTY_FILTERS);
  const [draft, setDraft] = useState<QueryFilters>(EMPTY_FILTERS);
  const [showFilters, setShowFilters] = useState(false);
  const [selected, setSelected] = useState<QueryRecord | null>(null);
  const PAGE_SIZE = 20;

  const { data: queryList, isLoading: lq, error: eq } = useQuery({
    queryKey: ["queries", page, filters],
    queryFn: () => getQueries(page, PAGE_SIZE, filters),
  });

  const { data: stats, isLoading: ls, error: es } = useQuery({
    queryKey: ["query-stats"],
    queryFn: () => getQueryStats(7),
  });

  const totalPages = queryList ? Math.ceil(queryList.total / PAGE_SIZE) : 1;

  const activeFilterCount = Object.values(filters).filter((v) => v !== undefined && v !== false && v !== "").length;

  function applyFilters() {
    setFilters(draft);
    setPage(1);
  }

  function resetFilters() {
    setDraft(EMPTY_FILTERS);
    setFilters(EMPTY_FILTERS);
    setPage(1);
  }

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-bold text-slate-800">{t("queries.title")}</h1>

      {/* Stats */}
      {ls ? (
        <ShimmerStatCards count={3} />
      ) : es ? (
        <ErrorMsg msg={t("common.error")} />
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <StatCard
            title={t("queries.total")}
            value={(stats?.total_queries ?? 0).toLocaleString()}
            icon={MessageSquare}
            color="blue"
            subtitle={`${(stats?.period_queries ?? 0).toLocaleString()} ces 7 derniers jours`}
          />
          <StatCard
            title={t("queries.offTopicRate")}
            value={`${(stats?.off_topic_rate_pct ?? 0).toFixed(1)}%`}
            icon={AlertTriangle}
            color="red"
            subtitle={`${stats?.off_topic_count ?? 0} hors-sujet (7j)`}
          />
          <StatCard
            title={t("queries.avgLatency")}
            value={`${Math.round(stats?.avg_latency_ms ?? 0)} ${t("common.ms")}`}
            icon={Clock}
            color="purple"
          />
        </div>
      )}

      {/* Toolbar */}
      <div className="flex items-center gap-3">
        <button
          onClick={() => {
            setDraft((d) => ({ ...d, offTopicOnly: !d.offTopicOnly }));
            setFilters((f) => { const next = { ...f, offTopicOnly: !f.offTopicOnly }; return next; });
            setPage(1);
          }}
          className={`inline-flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium border transition-colors ${
            filters.offTopicOnly
              ? "bg-red-50 text-red-600 border-red-200"
              : "bg-white text-slate-600 border-slate-200 hover:bg-slate-50"
          }`}
        >
          <AlertTriangle size={14} />
          {t("queries.offTopicFilter")}
        </button>

        <button
          onClick={() => setShowFilters(!showFilters)}
          className={`inline-flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium border transition-colors ${
            showFilters || activeFilterCount > 0
              ? "bg-green-50 text-green-600 border-green-200"
              : "bg-white text-slate-600 border-slate-200 hover:bg-slate-50"
          }`}
        >
          <SlidersHorizontal size={14} />
          {t("queries.filters")}
          {activeFilterCount > 0 && (
            <span className="ml-1 bg-green-500 text-white text-xs rounded-full w-4 h-4 flex items-center justify-center">
              {activeFilterCount}
            </span>
          )}
        </button>
      </div>

      {/* Advanced filters panel */}
      {showFilters && (
        <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-5 space-y-4">
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-4">
            <FilterSelect
              label={t("queries.language")}
              value={draft.language ?? ""}
              onChange={(e) => setDraft((d) => ({ ...d, language: e.target.value || undefined }))}
            >
              <option value="">{t("queries.all")}</option>
              <option value="fr">Français</option>
              <option value="en">English</option>
            </FilterSelect>

            <FilterInput
              label={t("queries.category")}
              type="text"
              placeholder="e.g. legal"
              value={draft.category ?? ""}
              onChange={(e) => setDraft((d) => ({ ...d, category: e.target.value || undefined }))}
            />

            <FilterInput
              label={t("queries.latencyMin")}
              type="number"
              min={0}
              placeholder="ms"
              value={draft.latencyMin ?? ""}
              onChange={(e) => setDraft((d) => ({ ...d, latencyMin: e.target.value ? Number(e.target.value) : undefined }))}
            />

            <FilterInput
              label={t("queries.latencyMax")}
              type="number"
              min={0}
              placeholder="ms"
              value={draft.latencyMax ?? ""}
              onChange={(e) => setDraft((d) => ({ ...d, latencyMax: e.target.value ? Number(e.target.value) : undefined }))}
            />

            <FilterInput
              label={t("queries.chunksMin")}
              type="number"
              min={0}
              placeholder="0"
              value={draft.chunksMin ?? ""}
              onChange={(e) => setDraft((d) => ({ ...d, chunksMin: e.target.value ? Number(e.target.value) : undefined }))}
            />

            <FilterInput
              label={t("queries.chunksMax")}
              type="number"
              min={0}
              placeholder="10"
              value={draft.chunksMax ?? ""}
              onChange={(e) => setDraft((d) => ({ ...d, chunksMax: e.target.value ? Number(e.target.value) : undefined }))}
            />

            <FilterInput
              label={t("queries.dateFrom")}
              type="date"
              value={draft.dateFrom ?? ""}
              onChange={(e) => setDraft((d) => ({ ...d, dateFrom: e.target.value || undefined }))}
            />

            <FilterInput
              label={t("queries.dateTo")}
              type="date"
              value={draft.dateTo ?? ""}
              onChange={(e) => setDraft((d) => ({ ...d, dateTo: e.target.value || undefined }))}
            />
          </div>

          <div className="flex gap-2 justify-end pt-1">
            <button
              onClick={resetFilters}
              className="px-4 py-2 text-sm text-slate-600 border border-slate-200 rounded-lg hover:bg-slate-50 transition-colors"
            >
              {t("common.cancel")}
            </button>
            <button
              onClick={applyFilters}
              className="px-4 py-2 text-sm text-white bg-green-500 hover:bg-green-600 rounded-lg transition-colors"
            >
              {t("queries.applyFilters")}
            </button>
          </div>
        </div>
      )}

      {/* Table */}
      {lq ? (
        <ShimmerTable rows={8} cols={6} />
      ) : eq ? (
        <ErrorMsg msg={t("common.error")} />
      ) : (
        <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-100 text-xs text-slate-500 uppercase tracking-wider">
                  <th className="text-left px-4 py-3 font-medium">{t("queries.question")}</th>
                  <th className="text-center px-4 py-3 font-medium">{t("queries.offTopic")}</th>
                  <th className="text-right px-4 py-3 font-medium hidden sm:table-cell">{t("queries.chunksFound")}</th>
                  <th className="text-right px-4 py-3 font-medium hidden sm:table-cell">{t("queries.latency")}</th>
                  <th className="text-left px-4 py-3 font-medium hidden md:table-cell">{t("queries.date")}</th>
                  <th className="px-4 py-3" />
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-50">
                {(queryList?.items ?? []).length === 0 ? (
                  <tr>
                    <td colSpan={6} className="px-4 py-10 text-center text-sm text-slate-400">
                      {t("common.noData")}
                    </td>
                  </tr>
                ) : (
                  (queryList?.items ?? []).map((q) => (
                    <tr key={q.id} className="hover:bg-slate-50 transition-colors">
                      <td className="px-4 py-3 text-slate-700 max-w-[200px] sm:max-w-[320px]">
                        <p className="truncate">{q.question}</p>
                        <p className="text-xs text-slate-400 mt-0.5 md:hidden">
                          {q.created_at ? format(parseISO(q.created_at), "MMM d, HH:mm") : "—"}
                        </p>
                      </td>
                      <td className="px-4 py-3 text-center">
                        {q.is_off_topic
                          ? <StatusBadge label={t("queries.yes")} variant="red" />
                          : <StatusBadge label={t("queries.no")} variant="green" />}
                      </td>
                      <td className="px-4 py-3 text-right text-slate-500 hidden sm:table-cell">{q.chunks_found}</td>
                      <td className="px-4 py-3 text-right text-slate-500 hidden sm:table-cell">
                        {q.latency_ms != null ? Math.round(q.latency_ms) : "—"}
                      </td>
                      <td className="px-4 py-3 text-slate-400 text-xs whitespace-nowrap hidden md:table-cell">
                        {q.created_at ? format(parseISO(q.created_at), "MMM d, HH:mm") : "—"}
                      </td>
                      <td className="px-3 py-3">
                        <button
                          onClick={() => setSelected(q)}
                          className="text-slate-400 hover:text-green-500 transition-colors cursor-pointer"
                        >
                          <Eye size={15} />
                        </button>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>

          {totalPages > 1 && (
            <div className="flex items-center justify-between px-5 py-3 border-t border-slate-100">
              <span className="text-xs text-slate-400">
                {t("queries.page")} {page} / {totalPages}
              </span>
              <div className="flex items-center gap-1">
                <button
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                  disabled={page === 1}
                  className="p-1.5 rounded text-slate-400 hover:text-slate-700 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
                >
                  <ChevronLeft size={16} />
                </button>
                <button
                  onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                  disabled={page === totalPages}
                  className="p-1.5 rounded text-slate-400 hover:text-slate-700 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
                >
                  <ChevronRight size={16} />
                </button>
              </div>
            </div>
          )}
        </div>
      )}

      {selected && (
        <QuerySheet query={selected} onClose={() => setSelected(null)} t={t} />
      )}
    </div>
  );
}
