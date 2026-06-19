"use client";

import { useQuery } from "@tanstack/react-query";
import { getDetailedHealth } from "@/lib/api";
import { useT } from "@/lib/i18n";
import { StatusBadge } from "@/components/status-badge";
import { Database, Cpu, Server, RefreshCw, Loader2 } from "lucide-react";

function Spinner() {
  return (
    <div className="flex items-center justify-center py-16">
      <Loader2 className="animate-spin text-green-500" size={28} />
    </div>
  );
}

function ErrorMsg({ msg }: { msg: string }) {
  return (
    <div className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-lg px-4 py-3">
      {msg}
    </div>
  );
}

function ServiceCard({
  title,
  icon: Icon,
  status,
  responseTime,
  error,
  details,
  okLabel,
  errorLabel,
  responseTimeLabel,
  detailsLabel,
}: {
  title: string;
  icon: React.ElementType;
  status: "ok" | "error";
  responseTime?: number;
  error?: string;
  details?: Record<string, unknown>;
  okLabel: string;
  errorLabel: string;
  responseTimeLabel: string;
  detailsLabel: string;
}) {
  const isOk = status === "ok";
  return (
    <div
      className={`bg-white rounded-xl border shadow-sm p-5 ${
        isOk ? "border-slate-200" : "border-red-200"
      }`}
    >
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-3">
          <div
            className={`p-2 rounded-lg ${
              isOk ? "bg-green-50 text-green-600" : "bg-red-50 text-red-600"
            }`}
          >
            <Icon size={18} />
          </div>
          <h2 className="font-semibold text-slate-800">{title}</h2>
        </div>
        <StatusBadge
          label={isOk ? okLabel : errorLabel}
          variant={isOk ? "green" : "red"}
        />
      </div>

      <div className="space-y-2 text-sm">
        {responseTime !== undefined && (
          <div className="flex justify-between text-slate-600">
            <span className="text-slate-400">{responseTimeLabel}</span>
            <span className="font-medium">{Math.round(responseTime)} ms</span>
          </div>
        )}

        {error && (
          <div className="mt-2 text-red-600 bg-red-50 rounded-lg px-3 py-2 text-xs">
            {error}
          </div>
        )}

        {details && Object.keys(details).length > 0 && (
          <details className="mt-2">
            <summary className="cursor-pointer text-xs text-slate-400 hover:text-slate-600">
              {detailsLabel}
            </summary>
            <pre className="mt-2 text-xs bg-slate-50 rounded-lg p-3 overflow-x-auto text-slate-600">
              {JSON.stringify(details, null, 2)}
            </pre>
          </details>
        )}
      </div>
    </div>
  );
}

export default function HealthPage() {
  const { t } = useT();

  const { data: health, isLoading, error, refetch, isFetching } = useQuery({
    queryKey: ["health-detailed"],
    queryFn: getDetailedHealth,
    refetchInterval: 30_000,
  });

  const coverage = health
    ? health.total_chunks > 0
      ? Math.round((health.chunks_with_embeddings / health.total_chunks) * 100)
      : 0
    : 0;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-bold text-slate-800">{t("health.title")}</h1>
        <button
          onClick={() => refetch()}
          disabled={isFetching}
          className="inline-flex items-center gap-1.5 px-3 py-2 text-sm text-slate-600 border border-slate-200 rounded-lg hover:bg-slate-50 transition-colors disabled:opacity-50"
        >
          <RefreshCw size={14} className={isFetching ? "animate-spin" : ""} />
          {t("common.retry")}
        </button>
      </div>

      {isLoading ? (
        <Spinner />
      ) : error ? (
        <ErrorMsg msg={t("common.error")} />
      ) : (
        <>
          {/* Service cards */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <ServiceCard
              title={t("health.database")}
              icon={Database}
              status={health?.database.status ?? "error"}
              responseTime={health?.database.response_time_ms}
              error={health?.database.error}
              details={health?.database.details}
              okLabel={t("health.ok")}
              errorLabel={t("health.error")}
              responseTimeLabel={t("health.responseTime")}
              detailsLabel={t("health.details")}
            />
            <ServiceCard
              title={t("health.redis")}
              icon={Server}
              status={health?.redis.status ?? "error"}
              responseTime={health?.redis.response_time_ms}
              error={health?.redis.error}
              details={health?.redis.details}
              okLabel={t("health.ok")}
              errorLabel={t("health.error")}
              responseTimeLabel={t("health.responseTime")}
              detailsLabel={t("health.details")}
            />
          </div>

          {/* Embedding coverage */}
          <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-5">
            <div className="flex items-center gap-3 mb-4">
              <div className="p-2 rounded-lg bg-green-50 text-green-600">
                <Cpu size={18} />
              </div>
              <h2 className="font-semibold text-slate-800">{t("health.embeddingCoverage")}</h2>
            </div>

            <div className="space-y-3">
              <div className="flex justify-between text-sm text-slate-600">
                <span>{t("health.chunksWithEmbeddings")}</span>
                <span className="font-medium">
                  {(health?.chunks_with_embeddings ?? 0).toLocaleString()} /{" "}
                  {(health?.total_chunks ?? 0).toLocaleString()}
                </span>
              </div>

              {/* Progress bar */}
              <div className="relative h-3 bg-slate-100 rounded-full overflow-hidden">
                <div
                  className="h-full bg-green-500 rounded-full transition-all duration-500"
                  style={{ width: `${coverage}%` }}
                />
              </div>

              <div className="flex justify-between text-xs text-slate-400">
                <span>0%</span>
                <span className="font-semibold text-slate-700">{coverage}%</span>
                <span>100%</span>
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
