"use client";

import { useQuery } from "@tanstack/react-query";
import { getCorpusStats, getCorpusSources, getRecentDocuments } from "@/lib/api";
import { useT } from "@/lib/i18n";
import { StatCard } from "@/components/stat-card";
import { FileText, Layers, Globe, Tag } from "lucide-react";
import { ShimmerStatCards, ShimmerTable } from "@/components/shimmer";
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Cell,
} from "recharts";
import { format, parseISO } from "date-fns";

const COLORS = [
  "#22c55e",
  "#3b82f6",
  "#a855f7",
  "#f59e0b",
  "#ef4444",
  "#06b6d4",
  "#ec4899",
  "#14b8a6",
];

function ErrorMsg({ msg }: { msg: string }) {
  return (
    <div className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-lg px-4 py-3">
      {msg}
    </div>
  );
}

export default function CorpusPage() {
  const { t } = useT();

  const { data: stats, isLoading: ls, error: es } = useQuery({
    queryKey: ["corpus-stats"],
    queryFn: getCorpusStats,
  });

  const { data: sources, isLoading: lsrc, error: esrc } = useQuery({
    queryKey: ["corpus-sources"],
    queryFn: getCorpusSources,
  });

  const { data: recent, isLoading: lr, error: er } = useQuery({
    queryKey: ["corpus-recent"],
    queryFn: () => getRecentDocuments(20),
  });

  const categoryData = stats
    ? Object.entries(stats.by_category)
        .sort((a, b) => b[1] - a[1])
        .map(([name, value]) => ({ name, value }))
    : [];

  const languageData = stats
    ? Object.entries(stats.by_language)
        .sort((a, b) => b[1] - a[1])
        .map(([name, value]) => ({ name, value }))
    : [];

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-bold text-slate-800">{t("corpus.title")}</h1>

      {/* Stats cards */}
      {ls ? (
        <ShimmerStatCards count={4} />
      ) : es ? (
        <ErrorMsg msg={t("common.error")} />
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
          <StatCard
            title={t("corpus.totalDocs")}
            value={(stats?.total_documents ?? 0).toLocaleString()}
            icon={FileText}
            color="green"
          />
          <StatCard
            title={t("corpus.totalChunks")}
            value={(stats?.total_chunks ?? 0).toLocaleString()}
            icon={Layers}
            color="blue"
          />
          <StatCard
            title={t("corpus.languages")}
            value={Object.keys(stats?.by_language ?? {}).length}
            icon={Globe}
            color="purple"
          />
          <StatCard
            title={t("corpus.categories")}
            value={Object.keys(stats?.by_category ?? {}).length}
            icon={Tag}
            color="default"
          />
        </div>
      )}

      {/* Charts */}
      {!ls && !es && (
        <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
          {/* By category */}
          <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-5">
            <h2 className="text-sm font-semibold text-slate-700 mb-4">{t("corpus.byCategory")}</h2>
            {categoryData.length === 0 ? (
              <p className="text-sm text-slate-400 text-center py-8">{t("common.noData")}</p>
            ) : (
              <ResponsiveContainer width="100%" height={220}>
                <BarChart data={categoryData} layout="vertical" margin={{ left: 60, right: 16, top: 4, bottom: 4 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" horizontal={false} />
                  <XAxis type="number" tick={{ fontSize: 11, fill: "#94a3b8" }} axisLine={false} tickLine={false} />
                  <YAxis
                    dataKey="name"
                    type="category"
                    tick={{ fontSize: 11, fill: "#64748b" }}
                    axisLine={false}
                    tickLine={false}
                    width={60}
                  />
                  <Tooltip
                    contentStyle={{ fontSize: 12, border: "1px solid #e2e8f0", borderRadius: 8 }}
                    formatter={(v: number) => [v.toLocaleString(), t("corpus.documents")]}
                  />
                  <Bar dataKey="value" radius={[0, 4, 4, 0]}>
                    {categoryData.map((_, i) => (
                      <Cell key={i} fill={COLORS[i % COLORS.length]} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            )}
          </div>

          {/* By language */}
          <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-5">
            <h2 className="text-sm font-semibold text-slate-700 mb-4">{t("corpus.byLanguage")}</h2>
            {languageData.length === 0 ? (
              <p className="text-sm text-slate-400 text-center py-8">{t("common.noData")}</p>
            ) : (
              <ResponsiveContainer width="100%" height={220}>
                <BarChart data={languageData} margin={{ top: 4, right: 8, left: -20, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                  <XAxis dataKey="name" tick={{ fontSize: 11, fill: "#94a3b8" }} axisLine={false} tickLine={false} />
                  <YAxis tick={{ fontSize: 11, fill: "#94a3b8" }} axisLine={false} tickLine={false} />
                  <Tooltip
                    contentStyle={{ fontSize: 12, border: "1px solid #e2e8f0", borderRadius: 8 }}
                    formatter={(v: number) => [v.toLocaleString(), t("corpus.documents")]}
                  />
                  <Bar dataKey="value" radius={[4, 4, 0, 0]}>
                    {languageData.map((_, i) => (
                      <Cell key={i} fill={COLORS[i % COLORS.length]} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            )}
          </div>
        </div>
      )}

      {/* Sources table */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
        <div className="px-5 py-4 border-b border-slate-100">
          <h2 className="text-sm font-semibold text-slate-700">{t("corpus.sources")}</h2>
        </div>
        {lsrc ? (
          <ShimmerTable rows={8} cols={4} />
        ) : esrc ? (
          <div className="p-4"><ErrorMsg msg={t("common.error")} /></div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-100 text-xs text-slate-500 uppercase tracking-wider">
                  <th className="text-left px-5 py-3 font-medium">{t("corpus.source")}</th>
                  <th className="text-left px-5 py-3 font-medium">{t("corpus.category")}</th>
                  <th className="text-right px-5 py-3 font-medium">{t("corpus.docCount")}</th>
                  <th className="text-left px-5 py-3 font-medium">{t("corpus.lastCollected")}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-50">
                {(sources ?? []).map((src) => (
                  <tr key={src.source} className="hover:bg-slate-50 transition-colors">
                    <td className="px-5 py-3 font-medium text-slate-700 max-w-[200px] truncate">
                      {src.source}
                    </td>
                    <td className="px-5 py-3 text-slate-500">{src.category}</td>
                    <td className="px-5 py-3 text-right text-slate-700 font-medium">
                      {src.doc_count.toLocaleString()}
                    </td>
                    <td className="px-5 py-3 text-slate-400 text-xs">
                      {src.last_collected
                        ? format(parseISO(src.last_collected), "MMM d, yyyy HH:mm")
                        : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Recent documents */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
        <div className="px-5 py-4 border-b border-slate-100">
          <h2 className="text-sm font-semibold text-slate-700">{t("corpus.recentDocuments")}</h2>
        </div>
        {lr ? (
          <ShimmerTable rows={8} cols={4} />
        ) : er ? (
          <div className="p-4"><ErrorMsg msg={t("common.error")} /></div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-100 text-xs text-slate-500 uppercase tracking-wider">
                  <th className="text-left px-5 py-3 font-medium">{t("corpus.title2")}</th>
                  <th className="text-left px-5 py-3 font-medium">{t("corpus.source")}</th>
                  <th className="text-left px-5 py-3 font-medium">{t("corpus.language")}</th>
                  <th className="text-left px-5 py-3 font-medium">{t("corpus.date")}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-50">
                {(recent ?? []).map((doc) => (
                  <tr key={doc.id} className="hover:bg-slate-50 transition-colors">
                    <td className="px-5 py-3 text-slate-700 max-w-[260px] truncate font-medium">
                      {doc.title ?? doc.id}
                    </td>
                    <td className="px-5 py-3 text-slate-500 max-w-[160px] truncate">{doc.source}</td>
                    <td className="px-5 py-3 text-slate-500 uppercase text-xs">{doc.language}</td>
                    <td className="px-5 py-3 text-slate-400 text-xs whitespace-nowrap">
                      {doc.created_at ? format(parseISO(doc.created_at), "MMM d, yyyy HH:mm") : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
