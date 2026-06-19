"use client";

import { useQuery } from "@tanstack/react-query";
import { getCorpusStats, getUsageStats } from "@/lib/api";
import { useT } from "@/lib/i18n";
import { StatCard } from "@/components/stat-card";
import { FileText, Layers, Activity, Cpu, Loader2 } from "lucide-react";
import {
  ResponsiveContainer,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
} from "recharts";
import { format, parseISO } from "date-fns";

function Spinner() {
  return (
    <div className="flex items-center justify-center py-20">
      <Loader2 className="animate-spin text-green-500" size={28} />
    </div>
  );
}

function ErrorMessage({ message }: { message: string }) {
  return (
    <div className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-lg px-4 py-3">
      {message}
    </div>
  );
}

export default function DashboardPage() {
  const { t } = useT();

  const {
    data: corpusStats,
    isLoading: loadingCorpus,
    error: corpusError,
  } = useQuery({
    queryKey: ["corpus-stats"],
    queryFn: getCorpusStats,
  });

  const {
    data: usageStats,
    isLoading: loadingUsage,
    error: usageError,
  } = useQuery({
    queryKey: ["usage-stats"],
    queryFn: () => getUsageStats(7),
  });

  const embeddingCoverage =
    corpusStats && corpusStats.total_chunks > 0
      ? Math.round((corpusStats.embedded_chunks / corpusStats.total_chunks) * 100)
      : 0;

  const chartData =
    usageStats?.by_day?.map((d) => ({
      date: format(parseISO(d.date), "MMM d"),
      requests: d.total,
      rateLimitHits: d.rate_limit_hits,
    })) ?? [];

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-bold text-slate-800">{t("dashboard.title")}</h1>

      {/* Stat cards */}
      {loadingCorpus || loadingUsage ? (
        <Spinner />
      ) : corpusError || usageError ? (
        <ErrorMessage message={t("common.error")} />
      ) : (
        <>
          <div className="grid grid-cols-2 gap-4 xl:grid-cols-4">
            <StatCard
              title={t("dashboard.totalDocs")}
              value={(corpusStats?.total_documents ?? 0).toLocaleString()}
              icon={FileText}
              color="green"
            />
            <StatCard
              title={t("dashboard.totalChunks")}
              value={(corpusStats?.total_chunks ?? 0).toLocaleString()}
              icon={Layers}
              color="blue"
            />
            <StatCard
              title={t("dashboard.requestsToday")}
              value={(usageStats?.requests_today ?? 0).toLocaleString()}
              icon={Activity}
              color="purple"
            />
            <StatCard
              title={t("dashboard.embeddingCoverage")}
              value={`${embeddingCoverage}%`}
              icon={Cpu}
              color="green"
              subtitle={`${(corpusStats?.embedded_chunks ?? 0).toLocaleString()} / ${(corpusStats?.total_chunks ?? 0).toLocaleString()}`}
            />
          </div>

          {/* Activity chart */}
          <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-5">
            <h2 className="text-sm font-semibold text-slate-700 mb-4">
              {t("dashboard.activityChart")}
            </h2>
            {chartData.length === 0 ? (
              <p className="text-sm text-slate-400 text-center py-8">{t("common.noData")}</p>
            ) : (
              <ResponsiveContainer width="100%" height={240}>
                <AreaChart data={chartData} margin={{ top: 4, right: 8, left: -20, bottom: 0 }}>
                  <defs>
                    <linearGradient id="reqGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#22c55e" stopOpacity={0.2} />
                      <stop offset="95%" stopColor="#22c55e" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                  <XAxis
                    dataKey="date"
                    tick={{ fontSize: 11, fill: "#94a3b8" }}
                    axisLine={false}
                    tickLine={false}
                  />
                  <YAxis
                    tick={{ fontSize: 11, fill: "#94a3b8" }}
                    axisLine={false}
                    tickLine={false}
                  />
                  <Tooltip
                    contentStyle={{
                      fontSize: 12,
                      border: "1px solid #e2e8f0",
                      borderRadius: 8,
                    }}
                  />
                  <Area
                    type="monotone"
                    dataKey="requests"
                    name={t("dashboard.requests")}
                    stroke="#22c55e"
                    strokeWidth={2}
                    fill="url(#reqGrad)"
                  />
                  <Area
                    type="monotone"
                    dataKey="rateLimitHits"
                    name={t("dashboard.rateLimitHits")}
                    stroke="#ef4444"
                    strokeWidth={1.5}
                    fill="none"
                    strokeDasharray="4 2"
                  />
                </AreaChart>
              </ResponsiveContainer>
            )}
          </div>
        </>
      )}
    </div>
  );
}
