import Link from "next/link";
import { fetchStats } from "@/lib/api";

export const revalidate = 60;

export default async function Home() {
  let stats = null;
  try {
    stats = await fetchStats();
  } catch {
    // API not running — show placeholder
  }

  return (
    <>
      {/* Hero */}
      <section className="relative overflow-hidden">
        <div className="absolute inset-0 bg-grid" />
        <div className="absolute inset-0 bg-gradient-to-b from-transparent via-transparent to-[#f8fafc]" />
        <div className="relative max-w-5xl mx-auto px-4 py-24 text-center">
          <div className="flex justify-center gap-1.5 mb-8">
            <span className="w-1.5 h-14 rounded-full" style={{ background: "var(--togo-green)" }} />
            <span className="w-1.5 h-14 rounded-full" style={{ background: "var(--togo-yellow)" }} />
            <span className="w-1.5 h-14 rounded-full" style={{ background: "var(--togo-red)" }} />
          </div>

          <h1 className="text-5xl md:text-7xl font-extrabold tracking-tight mb-6 animate-fade-in-up">
            <span className="text-gradient">AI for Togo.</span>
          </h1>

          <p
            className="text-xl text-slate-500 max-w-2xl mx-auto mb-10 leading-relaxed animate-fade-in-up"
            style={{ animationDelay: "80ms" }}
          >
            The first open-source AI infrastructure focused on Togo — built on public laws,
            government data, press, and education documents.
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
              Ask a question
            </Link>
            <Link
              href="/search"
              className="inline-flex items-center justify-center gap-2 px-7 py-3.5 rounded-xl text-sm font-semibold border border-slate-200 bg-white hover:bg-slate-50 transition-colors shadow-sm"
            >
              Search corpus
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
                { label: "Documents", value: stats.total_documents.toLocaleString(), accent: "var(--togo-green)" },
                { label: "Chunks", value: stats.total_chunks.toLocaleString(), accent: "var(--togo-yellow)" },
                { label: "Sources", value: String(stats.sources.length), accent: "var(--togo-red)" },
                { label: "Languages", value: stats.languages.join(" · ").toUpperCase(), accent: "var(--togo-green)" },
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
            <div className="grid md:grid-cols-3 gap-4 mb-12">
              {[
                {
                  emoji: "🔍",
                  title: "Semantic Search",
                  desc: "Search thousands of Togolese public documents using vector similarity — not just keywords.",
                },
                {
                  emoji: "🤖",
                  title: "RAG-Powered Q&A",
                  desc: "Ask complex questions in French. Get grounded answers with source citations from the corpus.",
                },
                {
                  emoji: "🇹🇬",
                  title: "Built for Togo",
                  desc: "Laws, budgets, education decrees, agriculture data — a corpus built from official Togolese sources.",
                },
              ].map((f) => (
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

            {/* Sources table */}
            <div className="bg-white rounded-2xl border border-slate-200 overflow-hidden animate-fade-in-up">
              <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between">
                <span className="text-sm font-semibold text-slate-700">Corpus Sources</span>
                <span className="text-xs text-slate-400">{stats.sources.length} active sources</span>
              </div>
              <table className="w-full text-sm">
                <thead className="bg-slate-50 text-xs text-slate-400 uppercase tracking-wider">
                  <tr>
                    <th className="text-left px-6 py-3">Source</th>
                    <th className="text-right px-6 py-3">Docs</th>
                    <th className="text-right px-6 py-3">Chunks</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {stats.sources.map((s) => (
                    <tr key={s.source} className="hover:bg-slate-50 transition-colors">
                      <td className="px-6 py-3 font-mono text-xs text-slate-600">{s.source}</td>
                      <td className="px-6 py-3 text-right tabular-nums text-slate-700 font-medium">
                        {s.documents.toLocaleString()}
                      </td>
                      <td className="px-6 py-3 text-right tabular-nums text-slate-400">
                        {s.chunks.toLocaleString()}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {stats.last_updated && (
                <div className="px-6 py-3 border-t border-slate-100 text-xs text-slate-400">
                  Last updated: {new Date(stats.last_updated).toLocaleDateString("en-TG")}
                </div>
              )}
            </div>
          </>
        ) : (
          /* Skeleton / offline state */
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
              API offline — start with{" "}
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
