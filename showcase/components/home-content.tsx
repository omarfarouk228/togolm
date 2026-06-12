"use client";

import Link from "next/link";
import { useLanguage } from "@/contexts/language";
import type { CorpusStats } from "@/lib/api";

export function HomeContent({ stats }: { stats: CorpusStats | null }) {
  const { t } = useLanguage();
  const h = t.home;

  return (
    <>
      {/* Hero */}
      <section className="relative overflow-hidden">
        <div className="absolute inset-0 bg-grid" />
        <div className="absolute inset-0 bg-gradient-to-b from-transparent via-transparent to-[#f8fafc]" />
        <div className="relative max-w-5xl mx-auto px-4 py-16 sm:py-24 text-center">
          <div className="flex justify-center gap-1.5 mb-8">
            <span className="w-1.5 h-14 rounded-full" style={{ background: "var(--togo-green)" }} />
            <span className="w-1.5 h-14 rounded-full" style={{ background: "var(--togo-yellow)" }} />
            <span className="w-1.5 h-14 rounded-full" style={{ background: "var(--togo-red)" }} />
          </div>

          <h1 className="text-5xl md:text-7xl font-extrabold tracking-tight mb-6 animate-fade-in-up">
            <span className="text-gradient">{h.tagline}</span>
          </h1>

          <p
            className="text-xl text-slate-500 max-w-2xl mx-auto mb-10 leading-relaxed animate-fade-in-up"
            style={{ animationDelay: "80ms" }}
          >
            {h.description}
          </p>

          <div
            className="flex flex-col sm:flex-row gap-3 justify-center animate-fade-in-up"
            style={{ animationDelay: "160ms" }}
          >
            <Link
              href="/chat"
              className="inline-flex items-center justify-center gap-2 px-7 py-3.5 rounded-xl text-white text-sm font-semibold hover:opacity-90 transition-opacity glow-green shadow-lg"
              style={{ background: "var(--togo-green)" }}
            >
              {h.askBtn}
            </Link>
            <Link
              href="/search"
              className="inline-flex items-center justify-center gap-2 px-7 py-3.5 rounded-xl text-sm font-semibold border border-slate-200 bg-white hover:bg-slate-50 transition-colors shadow-sm"
            >
              {h.searchBtn}
            </Link>
          </div>
        </div>
      </section>

      <div className="max-w-5xl mx-auto px-4 pb-24">
        {stats ? (
          <>
            {/* Stats grid */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-12 stagger">
              {[
                { label: h.stats.documents, value: stats.total_documents.toLocaleString(), accent: "var(--togo-green)" },
                { label: h.stats.chunks, value: stats.total_chunks.toLocaleString(), accent: "var(--togo-yellow)" },
                { label: h.stats.sources, value: String(stats.sources.length), accent: "var(--togo-red)" },
                { label: h.stats.languages, value: stats.languages.join(" · ").toUpperCase(), accent: "var(--togo-green)" },
              ].map((s) => (
                <div
                  key={s.label}
                  className="bg-white rounded-2xl border border-slate-200 p-6 text-center card-hover animate-fade-in-up"
                >
                  <div className="w-2 h-2 rounded-full mx-auto mb-3" style={{ background: s.accent }} />
                  <div className="text-2xl font-bold tabular-nums text-slate-900">{s.value}</div>
                  <div className="text-xs text-slate-400 mt-1 font-medium uppercase tracking-wider">{s.label}</div>
                </div>
              ))}
            </div>

            {/* Feature highlights */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              {h.features.map((f) => (
                <div
                  key={f.title}
                  className="bg-white rounded-2xl border border-slate-200 p-6 card-hover animate-fade-in-up"
                >
                  <div className="text-3xl mb-4">{f.emoji}</div>
                  <h3 className="font-semibold text-slate-900 mb-2">{f.title}</h3>
                  <p className="text-sm text-slate-500 leading-relaxed">{f.desc}</p>
                </div>
              ))}
            </div>
          </>
        ) : (
          <div>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-12">
              {Array.from({ length: 4 }).map((_, i) => (
                <div key={i} className="bg-white rounded-2xl border border-slate-200 p-6 text-center">
                  <div className="skeleton h-8 w-16 mx-auto mb-2 rounded-lg" />
                  <div className="skeleton h-3 w-20 mx-auto rounded" />
                </div>
              ))}
            </div>
            <p className="text-center text-slate-400 text-sm py-8">
              {h.offline}{" "}
              <code className="bg-slate-100 px-1.5 py-0.5 rounded text-xs font-mono">
                uv run uvicorn api.app.main:app --port 8000
              </code>
            </p>
          </div>
        )}
      </div>
    </>
  );
}
