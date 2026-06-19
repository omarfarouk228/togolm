"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { getQueries, getQueryStats } from "@/lib/api";
import { useT } from "@/lib/i18n";
import { StatCard } from "@/components/stat-card";
import { StatusBadge } from "@/components/status-badge";
import { MessageSquare, AlertTriangle, Clock, ChevronLeft, ChevronRight } from "lucide-react";
import { ShimmerStatCards, ShimmerTable } from "@/components/shimmer";
import { format, parseISO } from "date-fns";

function ErrorMsg({ msg }: { msg: string }) {
  return (
    <div className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-lg px-4 py-3">
      {msg}
    </div>
  );
}

export default function QueriesPage() {
  const { t } = useT();
  const [page, setPage] = useState(1);
  const [offTopicOnly, setOffTopicOnly] = useState(false);
  const PAGE_SIZE = 20;

  const { data: queryList, isLoading: lq, error: eq } = useQuery({
    queryKey: ["queries", page, offTopicOnly],
    queryFn: () => getQueries(page, PAGE_SIZE, offTopicOnly),
  });

  const { data: stats, isLoading: ls, error: es } = useQuery({
    queryKey: ["query-stats"],
    queryFn: () => getQueryStats(7),
  });

  const totalPages = queryList ? Math.ceil(queryList.total / PAGE_SIZE) : 1;

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
          />
          <StatCard
            title={t("queries.offTopicRate")}
            value={`${((stats?.off_topic_rate ?? 0) * 100).toFixed(1)}%`}
            icon={AlertTriangle}
            color="red"
            subtitle={`${stats?.off_topic_count ?? 0} queries`}
          />
          <StatCard
            title={t("queries.avgLatency")}
            value={`${Math.round(stats?.avg_latency_ms ?? 0)} ${t("common.ms")}`}
            icon={Clock}
            color="purple"
          />
        </div>
      )}

      {/* Filter toggle */}
      <div className="flex items-center gap-3">
        <button
          onClick={() => {
            setOffTopicOnly(!offTopicOnly);
            setPage(1);
          }}
          className={`inline-flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium border transition-colors ${
            offTopicOnly
              ? "bg-red-50 text-red-600 border-red-200"
              : "bg-white text-slate-600 border-slate-200 hover:bg-slate-50"
          }`}
        >
          <AlertTriangle size={14} />
          {t("queries.offTopicFilter")}
        </button>
      </div>

      {/* Table */}
      {lq ? (
        <ShimmerTable rows={8} cols={5} />
      ) : eq ? (
        <ErrorMsg msg={t("common.error")} />
      ) : (
        <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-100 text-xs text-slate-500 uppercase tracking-wider">
                  <th className="text-left px-5 py-3 font-medium">{t("queries.question")}</th>
                  <th className="text-center px-5 py-3 font-medium">{t("queries.offTopic")}</th>
                  <th className="text-right px-5 py-3 font-medium">{t("queries.chunksFound")}</th>
                  <th className="text-right px-5 py-3 font-medium">{t("queries.latency")}</th>
                  <th className="text-left px-5 py-3 font-medium">{t("queries.date")}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-50">
                {(queryList?.items ?? []).length === 0 ? (
                  <tr>
                    <td colSpan={5} className="px-5 py-10 text-center text-sm text-slate-400">
                      {t("common.noData")}
                    </td>
                  </tr>
                ) : (
                  (queryList?.items ?? []).map((q) => (
                    <tr key={q.id} className="hover:bg-slate-50 transition-colors">
                      <td className="px-5 py-3 text-slate-700 max-w-[360px]">
                        <p className="truncate">{q.question}</p>
                      </td>
                      <td className="px-5 py-3 text-center">
                        {q.is_off_topic ? (
                          <StatusBadge label={t("queries.yes")} variant="red" />
                        ) : (
                          <StatusBadge label={t("queries.no")} variant="green" />
                        )}
                      </td>
                      <td className="px-5 py-3 text-right text-slate-500">{q.chunks_found}</td>
                      <td className="px-5 py-3 text-right text-slate-500">{Math.round(q.latency_ms)}</td>
                      <td className="px-5 py-3 text-slate-400 text-xs whitespace-nowrap">
                        {format(parseISO(q.created_at), "MMM d, HH:mm")}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>

          {/* Pagination */}
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
    </div>
  );
}
