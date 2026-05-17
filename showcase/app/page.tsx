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
    <div className="max-w-5xl mx-auto px-4 py-16">
      {/* Hero */}
      <div className="text-center mb-16">
        <div className="flex justify-center gap-1 mb-6">
          <span className="w-3 h-10 rounded-sm" style={{ background: "var(--togo-green)" }} />
          <span className="w-3 h-10 rounded-sm" style={{ background: "var(--togo-yellow)" }} />
          <span className="w-3 h-10 rounded-sm" style={{ background: "var(--togo-red)" }} />
          <span className="w-3 h-10 rounded-sm" style={{ background: "var(--togo-yellow)" }} />
          <span className="w-3 h-10 rounded-sm" style={{ background: "var(--togo-green)" }} />
        </div>
        <h1 className="text-4xl font-bold mb-3 tracking-tight">TogoLM</h1>
        <p className="text-lg text-gray-500 max-w-xl mx-auto">
          The first open-source AI infrastructure focused on Togo — built on public laws,
          government data, press, and education documents.
        </p>
        <div className="flex gap-3 justify-center mt-8">
          <Link
            href="/chat"
            className="px-5 py-2.5 rounded-lg text-white text-sm font-medium transition-opacity hover:opacity-90"
            style={{ background: "var(--togo-green)" }}
          >
            Ask a question
          </Link>
          <Link
            href="/search"
            className="px-5 py-2.5 rounded-lg text-sm font-medium border border-gray-200 bg-white hover:bg-gray-50 transition-colors"
          >
            Search corpus
          </Link>
        </div>
      </div>

      {/* Stats */}
      {stats ? (
        <>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-12">
            {[
              { label: "Documents", value: stats.total_documents.toLocaleString() },
              { label: "Chunks", value: stats.total_chunks.toLocaleString() },
              { label: "Sources", value: stats.sources.length },
              { label: "Languages", value: stats.languages.join(", ").toUpperCase() },
            ].map((s) => (
              <div key={s.label} className="bg-white rounded-xl border border-gray-200 p-5 text-center">
                <div className="text-2xl font-bold tabular-nums">{s.value}</div>
                <div className="text-sm text-gray-500 mt-1">{s.label}</div>
              </div>
            ))}
          </div>

          <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
            <div className="px-5 py-3 border-b border-gray-100 text-sm font-medium text-gray-700">
              Corpus sources
            </div>
            <table className="w-full text-sm">
              <thead className="bg-gray-50 text-xs text-gray-500 uppercase tracking-wide">
                <tr>
                  <th className="text-left px-5 py-2">Source</th>
                  <th className="text-right px-5 py-2">Documents</th>
                  <th className="text-right px-5 py-2">Chunks</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {stats.sources.map((s) => (
                  <tr key={s.source} className="hover:bg-gray-50 transition-colors">
                    <td className="px-5 py-2.5 font-mono text-xs text-gray-700">{s.source}</td>
                    <td className="px-5 py-2.5 text-right tabular-nums">{s.documents}</td>
                    <td className="px-5 py-2.5 text-right tabular-nums text-gray-400">{s.chunks}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            {stats.last_updated && (
              <div className="px-5 py-2 border-t border-gray-100 text-xs text-gray-400">
                Last updated: {new Date(stats.last_updated).toLocaleDateString("fr-TG")}
              </div>
            )}
          </div>
        </>
      ) : (
        <div className="text-center text-gray-400 text-sm py-12">
          API not reachable — start with{" "}
          <code className="bg-gray-100 px-1.5 py-0.5 rounded text-xs">
            uv run uvicorn api.app.main:app --port 8000
          </code>
        </div>
      )}
    </div>
  );
}
