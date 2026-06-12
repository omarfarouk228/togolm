"use client";

import { useState, useEffect, useRef } from "react";
import Link from "next/link";
import {
  Copy, Check, Key, Zap, Shield, Code2,
  ChevronLeft, ExternalLink,
} from "lucide-react";
import { registerAPIKey, type RegisterAPIKeyResponse } from "@/lib/api";
import { useLanguage } from "@/contexts/language";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function useCopy(text: string) {
  const [copied, setCopied] = useState(false);
  function copy() {
    navigator.clipboard.writeText(text).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  }
  return { copied, copy };
}

function CopyBtn({ text, dark = false }: { text: string; dark?: boolean }) {
  const { copied, copy } = useCopy(text);
  return (
    <button
      onClick={copy}
      className={`flex items-center gap-1 text-xs px-2 py-1 rounded-md transition-all ${
        dark
          ? copied
            ? "bg-green-500/20 text-green-400"
            : "bg-white/10 text-slate-400 hover:bg-white/20 hover:text-white"
          : copied
            ? "bg-green-50 text-green-700 border border-green-200"
            : "bg-slate-50 text-slate-500 border border-slate-200 hover:border-slate-300 hover:text-slate-700"
      }`}
    >
      {copied ? <Check className="w-3 h-3" /> : <Copy className="w-3 h-3" />}
      {copied ? "Copied" : "Copy"}
    </button>
  );
}

// ---------------------------------------------------------------------------
// Code block (always dark)
// ---------------------------------------------------------------------------

type Lang = "bash" | "python" | "javascript" | "json";

function CodeBlock({ code, lang }: { code: string; lang: Lang }) {
  return (
    <div className="rounded-xl bg-[#0d1117] border border-slate-200 overflow-hidden text-xs">
      <div className="flex items-center justify-between px-3 py-2 bg-[#161b22] border-b border-[#30363d]">
        <span className="text-[#8b949e] font-mono">{lang}</span>
        <CopyBtn text={code} dark />
      </div>
      <pre className="px-4 py-3.5 text-[#e6edf3] font-mono leading-relaxed overflow-x-auto">
        <code>{code}</code>
      </pre>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Method badge
// ---------------------------------------------------------------------------

const METHOD_STYLE: Record<string, string> = {
  GET:  "bg-blue-50 text-blue-700 border border-blue-200",
  POST: "bg-emerald-50 text-emerald-700 border border-emerald-200",
};

function MethodBadge({ method }: { method: string }) {
  return (
    <span className={`text-xs font-bold px-2.5 py-1 rounded-md font-mono ${METHOD_STYLE[method] ?? ""}`}>
      {method}
    </span>
  );
}

// ---------------------------------------------------------------------------
// Auth badge
// ---------------------------------------------------------------------------

const AUTH_STYLE = {
  none:     "bg-slate-100 text-slate-500",
  optional: "bg-amber-50 text-amber-700",
  required: "bg-red-50 text-red-600",
} as const;

const AUTH_LABEL = {
  none:     { fr: "Public", en: "Public" },
  optional: { fr: "Clé optionnelle", en: "Key optional" },
  required: { fr: "Clé requise", en: "Key required" },
} as const;

type AuthLevel = keyof typeof AUTH_STYLE;

// ---------------------------------------------------------------------------
// Endpoint section
// ---------------------------------------------------------------------------

interface Param {
  name: string;
  type: string;
  in: "query" | "body" | "path";
  required: boolean;
  description: string;
  default?: string;
}

interface Endpoint {
  id: string;
  method: "GET" | "POST";
  path: string;
  summary: { fr: string; en: string };
  description: { fr: string; en: string };
  auth: AuthLevel;
  params?: Param[];
  examples: {
    curl: string;
    python?: string;
    js?: string;
  };
  responseExample?: string;
}

type CodeTab = "curl" | "python" | "js" | "response";

function EndpointSection({ ep }: { ep: Endpoint }) {
  const { lang } = useLanguage();
  const [tab, setTab] = useState<CodeTab>("curl");

  const tabs: { key: CodeTab; label: string }[] = [
    { key: "curl",     label: "cURL" },
    ...(ep.examples.python   ? [{ key: "python" as CodeTab,   label: "Python" }] : []),
    ...(ep.examples.js       ? [{ key: "js" as CodeTab,       label: "JavaScript" }] : []),
    ...(ep.responseExample   ? [{ key: "response" as CodeTab, label: "Response" }] : []),
  ];

  const codeMap: Partial<Record<CodeTab, { code: string; lang: Lang }>> = {
    curl:     { code: ep.examples.curl,           lang: "bash"       },
    python:   { code: ep.examples.python ?? "",   lang: "python"     },
    js:       { code: ep.examples.js ?? "",       lang: "javascript" },
    response: { code: ep.responseExample ?? "",   lang: "json"       },
  };

  return (
    <section id={ep.id} className="scroll-mt-20">
      {/* Header */}
      <div className="flex flex-wrap items-center gap-2.5 mb-4">
        <MethodBadge method={ep.method} />
        <code className="text-sm font-mono text-slate-900 font-semibold">{ep.path}</code>
        <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${AUTH_STYLE[ep.auth]}`}>
          {AUTH_LABEL[ep.auth][lang as "fr" | "en"]}
        </span>
      </div>

      {/* Two-column body */}
      <div className="grid lg:grid-cols-2 gap-5">
        {/* Left: description + params */}
        <div className="space-y-4">
          <p className="text-sm text-slate-600 leading-relaxed">
            {ep.description[lang as "fr" | "en"]}
          </p>

          {ep.params && ep.params.length > 0 && (
            <div>
              <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">
                Parameters
              </p>
              <div className="rounded-xl border border-slate-200 divide-y divide-slate-100 overflow-hidden">
                {ep.params.map((p) => (
                  <div key={p.name} className="px-3.5 py-2.5 bg-white hover:bg-slate-50 transition-colors">
                    <div className="flex items-center gap-2 mb-0.5">
                      <code className="text-xs font-mono font-semibold text-slate-800">{p.name}</code>
                      <span className="text-xs font-mono text-blue-500">{p.type}</span>
                      <span className={`text-xs px-1.5 py-0.5 rounded-full ${
                        p.in === "body" ? "bg-purple-50 text-purple-600" :
                        p.in === "path" ? "bg-orange-50 text-orange-600" :
                        "bg-slate-100 text-slate-500"
                      }`}>{p.in}</span>
                      {p.required && (
                        <span className="text-xs text-red-500 font-medium">required</span>
                      )}
                    </div>
                    <p className="text-xs text-slate-500 leading-relaxed">{p.description}</p>
                    {p.default && (
                      <p className="text-xs text-slate-400 mt-0.5">
                        Default: <code className="bg-slate-100 px-1 rounded">{p.default}</code>
                      </p>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Right: code examples */}
        <div>
          <div className="flex gap-0.5 mb-2.5 bg-slate-100 rounded-lg p-0.5 w-fit">
            {tabs.map(({ key, label }) => (
              <button
                key={key}
                onClick={() => setTab(key)}
                className={`px-3 py-1.5 rounded-md text-xs font-medium transition-colors ${
                  tab === key
                    ? "bg-white text-slate-900 shadow-sm"
                    : "text-slate-500 hover:text-slate-700"
                }`}
              >
                {label}
              </button>
            ))}
          </div>
          {codeMap[tab] && (
            <CodeBlock code={codeMap[tab]!.code} lang={codeMap[tab]!.lang} />
          )}
        </div>
      </div>
    </section>
  );
}

// ---------------------------------------------------------------------------
// Registration form
// ---------------------------------------------------------------------------

function RegisterForm() {
  const { lang } = useLanguage();
  const [fields, setFields] = useState({ name: "", email: "", use_case: "" });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<RegisterAPIKeyResponse | null>(null);
  const { copied, copy } = useCopy(result?.api_key ?? "");

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const res = await registerAPIKey({
        name: fields.name,
        email: fields.email,
        use_case: fields.use_case || undefined,
      });
      setResult(res);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "An error occurred");
    } finally {
      setLoading(false);
    }
  }

  if (result) {
    return (
      <div className="space-y-4">
        <div className="flex items-center gap-2 text-emerald-600 font-medium text-sm">
          <Check className="w-4 h-4" />
          {lang === "fr" ? "Clé créée avec succès !" : "API key created!"}
        </div>

        <div className="rounded-xl bg-amber-50 border border-amber-200 px-4 py-3 text-xs text-amber-700 leading-relaxed">
          {lang === "fr"
            ? "⚠️ Copiez et sauvegardez cette clé maintenant — elle ne sera plus jamais affichée."
            : "⚠️ Copy and save this key now — it will never be shown again."}
        </div>

        {/* Key display */}
        <div className="rounded-xl bg-[#0d1117] border border-slate-200 overflow-hidden">
          <div className="flex items-center justify-between px-3.5 py-2.5 bg-[#161b22] border-b border-[#30363d]">
            <span className="text-xs text-[#8b949e]">
              {lang === "fr" ? "Votre clé API" : "Your API key"}
            </span>
            <button
              onClick={copy}
              className={`flex items-center gap-1 text-xs px-2 py-1 rounded-md transition-all ${
                copied
                  ? "bg-green-500/20 text-green-400"
                  : "bg-white/10 text-slate-400 hover:bg-white/20 hover:text-white"
              }`}
            >
              {copied ? <Check className="w-3 h-3" /> : <Copy className="w-3 h-3" />}
              {copied ? "Copied!" : "Copy"}
            </button>
          </div>
          <div className="px-4 py-3 font-mono text-sm text-emerald-400 break-all select-all">
            {result.api_key}
          </div>
        </div>

        <div className="grid grid-cols-3 gap-2 text-xs">
          {[
            { label: "Plan",                                           value: result.plan },
            { label: lang === "fr" ? "Quota / jour" : "Quota / day", value: `${result.quota_per_day} req` },
            { label: "Prefix",                                         value: result.key_prefix },
          ].map((s) => (
            <div key={s.label} className="bg-slate-50 border border-slate-200 rounded-lg px-3 py-2">
              <div className="text-slate-400 mb-0.5">{s.label}</div>
              <div className="font-mono font-semibold text-slate-800">{s.value}</div>
            </div>
          ))}
        </div>

        <p className="text-xs text-slate-500">
          {lang === "fr" ? "Utilisez le header " : "Use the header "}
          <code className="bg-slate-100 px-1.5 py-0.5 rounded text-slate-700 font-mono">
            X-API-Key: {result.key_prefix}...
          </code>
          {lang === "fr" ? " dans vos requêtes." : " in your requests."}
        </p>
      </div>
    );
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-3.5">
      {[
        { key: "name",     label: lang === "fr" ? "Nom" : "Name",                       type: "text",  required: true,  placeholder: "Kofi Mensah" },
        { key: "email",    label: "Email",                                                type: "email", required: true,  placeholder: "kofi@example.com" },
        { key: "use_case", label: lang === "fr" ? "Cas d'usage (optionnel)" : "Use case (optional)", type: "text", required: false, placeholder: lang === "fr" ? "Chatbot éducatif, app mobile…" : "Education chatbot, mobile app…" },
      ].map(({ key, label, type, required, placeholder }) => (
        <div key={key}>
          <label className="block text-xs font-medium text-slate-600 mb-1.5">{label}</label>
          <input
            type={type}
            required={required}
            value={fields[key as keyof typeof fields]}
            onChange={(e) => setFields((f) => ({ ...f, [key]: e.target.value }))}
            placeholder={placeholder}
            className="w-full px-3.5 py-2.5 rounded-xl border border-slate-200 text-sm text-slate-900 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-green-700/20 focus:border-green-700/40 bg-white transition-all shadow-sm"
          />
        </div>
      ))}

      {error && (
        <div className="rounded-xl bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-600">
          {error}
        </div>
      )}

      <button
        type="submit"
        disabled={loading}
        className="w-full px-4 py-3 rounded-xl text-white text-sm font-semibold disabled:opacity-50 hover:opacity-90 transition-opacity shadow-sm"
        style={{ background: "var(--togo-green)" }}
      >
        {loading
          ? (lang === "fr" ? "Création…" : "Creating…")
          : (lang === "fr" ? "Obtenir ma clé API" : "Get my API key")}
      </button>
    </form>
  );
}

// ---------------------------------------------------------------------------
// Endpoints data
// ---------------------------------------------------------------------------

const ENDPOINTS: Endpoint[] = [
  {
    id: "stats",
    method: "GET",
    path: "/v1/stats",
    summary: { fr: "Statistiques du corpus", en: "Corpus statistics" },
    description: {
      fr: "Retourne les statistiques en direct du corpus : nombre de documents, de fragments, sources actives et langues supportées.",
      en: "Returns live corpus statistics: document count, chunk count, active sources, and supported languages.",
    },
    auth: "none",
    examples: {
      curl: `curl ${API_BASE}/v1/stats`,
      python: `import requests\n\nres = requests.get("${API_BASE}/v1/stats")\nprint(res.json())`,
      js: `const res = await fetch("${API_BASE}/v1/stats");\nconst data = await res.json();\nconsole.log(data);`,
    },
    responseExample: `{\n  "total_documents": 2847,\n  "total_chunks": 14230,\n  "languages": ["fr"],\n  "sources": [\n    { "source": "jo.gouv.tg", "documents": 34, "chunks": 187 },\n    { "source": "inseed.tg",  "documents": 90, "chunks": 450 }\n  ],\n  "last_updated": "2026-06-12T08:00:00"\n}`,
  },
  {
    id: "documents",
    method: "GET",
    path: "/v1/documents",
    summary: { fr: "Liste des documents", en: "List documents" },
    description: {
      fr: "Liste paginée de tous les documents du corpus. Filtrable par domaine source, catégorie ou langue.",
      en: "Paginated list of all documents in the corpus. Filter by source domain, category, or language.",
    },
    auth: "none",
    params: [
      { name: "page",      type: "integer", in: "query", required: false, description: "Page number",                default: "1"  },
      { name: "page_size", type: "integer", in: "query", required: false, description: "Results per page (max 100)", default: "20" },
      { name: "source",    type: "string",  in: "query", required: false, description: "Filter by source domain (e.g. jo.gouv.tg)" },
      { name: "category",  type: "string",  in: "query", required: false, description: "legal · education · economy · agriculture · health · politics · press" },
      { name: "language",  type: "string",  in: "query", required: false, description: "Language code",              default: "fr" },
    ],
    examples: {
      curl: `curl "${API_BASE}/v1/documents?category=legal&page=1&page_size=10"`,
      python: `import requests\n\nres = requests.get(\n    "${API_BASE}/v1/documents",\n    params={"category": "legal", "page": 1, "page_size": 10}\n)\nfor doc in res.json()["documents"]:\n    print(doc["title"])`,
      js: `const res = await fetch(\n  "${API_BASE}/v1/documents?category=legal&page_size=10"\n);\nconst { documents, total } = await res.json();\nconsole.log(\`\${total} documents found\`);`,
    },
    responseExample: `{\n  "documents": [\n    {\n      "id": "3f2a...",\n      "source": "jo.gouv.tg",\n      "title": "Loi de finances 2025",\n      "category": "legal",\n      "language": "fr",\n      "word_count": 4280,\n      "chunk_count": 11\n    }\n  ],\n  "total": 342,\n  "page": 1,\n  "page_size": 10,\n  "pages": 35\n}`,
  },
  {
    id: "search",
    method: "GET",
    path: "/v1/search",
    summary: { fr: "Recherche plein texte", en: "Full-text search" },
    description: {
      fr: "Recherche plein texte sur le corpus via PostgreSQL FTS optimisé pour le français (ts_rank) avec fallback ILIKE. Retourne des extraits avec score de pertinence.",
      en: "Full-text search over the corpus using French-optimized PostgreSQL FTS (ts_rank) with ILIKE fallback. Returns excerpts with relevance scores.",
    },
    auth: "optional",
    params: [
      { name: "q",        type: "string",  in: "query", required: true,  description: "Search query (min 2, max 500 chars)"    },
      { name: "source",   type: "string",  in: "query", required: false, description: "Restrict to a specific source domain"    },
      { name: "category", type: "string",  in: "query", required: false, description: "Restrict to a category"                  },
      { name: "limit",    type: "integer", in: "query", required: false, description: "Max results (max 50)", default: "10"     },
    ],
    examples: {
      curl: `curl "${API_BASE}/v1/search?q=budget+2024&limit=5" \\\n  -H "X-API-Key: YOUR_KEY"`,
      python: `import requests\n\nres = requests.get(\n    "${API_BASE}/v1/search",\n    params={"q": "budget 2024", "limit": 5},\n    headers={"X-API-Key": "YOUR_KEY"}\n)\nfor r in res.json()["results"]:\n    print(f"{r['score']:.2f} — {r['title']}")`,
      js: `const res = await fetch(\n  \`${API_BASE}/v1/search?q=budget+2024&limit=5\`,\n  { headers: { "X-API-Key": "YOUR_KEY" } }\n);\nconst { results } = await res.json();\nresults.forEach(r => console.log(r.score, r.title));`,
    },
    responseExample: `{\n  "results": [\n    {\n      "id": "9c1b...",\n      "source": "jo.gouv.tg",\n      "title": "Loi de finances 2025",\n      "excerpt": "…le budget de l'État togolais pour 2025…",\n      "score": 0.8412,\n      "url": "https://jo.gouv.tg/loi-finances-2025"\n    }\n  ],\n  "total": 12,\n  "query": "budget 2024"\n}`,
  },
  {
    id: "query",
    method: "POST",
    path: "/v1/query",
    summary: { fr: "Question RAG (réponse complète)", en: "RAG query (full response)" },
    description: {
      fr: "Recherche les fragments les plus pertinents par similarité vectorielle, puis génère une réponse ancrée avec Gemini 2.5 Flash. Retourne la réponse complète + sources.",
      en: "Retrieves the most relevant corpus chunks via vector similarity, then generates a grounded answer with Gemini 2.5 Flash. Returns full answer + source citations.",
    },
    auth: "optional",
    params: [
      { name: "question", type: "string", in: "body", required: true,  description: "The question to answer (min 3, max 1000 chars)"         },
      { name: "category", type: "string", in: "body", required: false, description: "Restrict retrieval to a category"                        },
      { name: "language", type: "string", in: "body", required: false, description: "Response language",       default: "fr"                  },
    ],
    examples: {
      curl: `curl -X POST ${API_BASE}/v1/query \\\n  -H "Content-Type: application/json" \\\n  -H "X-API-Key: YOUR_KEY" \\\n  -d '{"question": "Quel est le budget de l\\'État togolais ?"}'`,
      python: `import requests\n\nres = requests.post(\n    "${API_BASE}/v1/query",\n    json={"question": "Quel est le budget de l'État togolais ?"},\n    headers={"X-API-Key": "YOUR_KEY"}\n)\ndata = res.json()\nprint(data["answer"])\nfor s in data["sources"]:\n    print("↳", s["title"])`,
      js: `const res = await fetch("${API_BASE}/v1/query", {\n  method: "POST",\n  headers: {\n    "Content-Type": "application/json",\n    "X-API-Key": "YOUR_KEY"\n  },\n  body: JSON.stringify({\n    question: "Quel est le budget de l'État togolais ?"\n  })\n});\nconst { answer, sources, latency_ms } = await res.json();`,
    },
    responseExample: `{\n  "answer": "Le budget de l'État togolais pour 2025 s'élève à 2 400 milliards de FCFA…",\n  "sources": [\n    {\n      "title": "Loi de finances 2025",\n      "url": "https://jo.gouv.tg/loi-finances-2025",\n      "score": 0.91\n    }\n  ],\n  "model": "gemini-2.5-flash",\n  "latency_ms": 1842\n}`,
  },
  {
    id: "query-stream",
    method: "POST",
    path: "/v1/query/stream",
    summary: { fr: "Question RAG (streaming SSE)", en: "RAG query (SSE stream)" },
    description: {
      fr: "Identique à /v1/query mais diffuse la réponse token par token via Server-Sent Events. Trois types d'événements : chunk (texte) · sources (citations) · error.",
      en: "Same as /v1/query but streams the answer token-by-token via Server-Sent Events. Three event types: chunk (text) · sources (citations) · error.",
    },
    auth: "optional",
    params: [
      { name: "question", type: "string", in: "body", required: true,  description: "The question to answer" },
      { name: "category", type: "string", in: "body", required: false, description: "Restrict retrieval to a category" },
      { name: "language", type: "string", in: "body", required: false, description: "Response language", default: "fr" },
    ],
    examples: {
      curl: `curl -X POST ${API_BASE}/v1/query/stream \\\n  -H "Content-Type: application/json" \\\n  -H "X-API-Key: YOUR_KEY" \\\n  --no-buffer \\\n  -d '{"question": "Comment créer une entreprise au Togo ?"}'`,
      python: `import requests, json\n\nwith requests.post(\n    "${API_BASE}/v1/query/stream",\n    json={"question": "Comment créer une entreprise au Togo ?"},\n    headers={"X-API-Key": "YOUR_KEY"},\n    stream=True\n) as res:\n    for line in res.iter_lines():\n        if line.startswith(b"data: "):\n            event = json.loads(line[6:])\n            if event["type"] == "chunk":\n                print(event["text"], end="", flush=True)\n            elif event["type"] == "sources":\n                print("\\nSources:", event["sources"])`,
      js: `const res = await fetch("${API_BASE}/v1/query/stream", {\n  method: "POST",\n  headers: {\n    "Content-Type": "application/json",\n    "X-API-Key": "YOUR_KEY"\n  },\n  body: JSON.stringify({ question: "Comment créer une entreprise ?" })\n});\n\nconst reader = res.body.getReader();\nconst decoder = new TextDecoder();\nlet buffer = "";\n\nwhile (true) {\n  const { done, value } = await reader.read();\n  if (done) break;\n  buffer += decoder.decode(value, { stream: true });\n  for (const block of buffer.split("\\n\\n")) {\n    if (!block.startsWith("data: ")) continue;\n    const e = JSON.parse(block.slice(6));\n    if (e.type === "chunk") process.stdout.write(e.text);\n    if (e.type === "sources") console.log("\\nSources:", e.sources);\n  }\n}`,
    },
    responseExample: `// Stream of SSE events:\ndata: {"type": "chunk", "text": "Pour créer"}\ndata: {"type": "chunk", "text": " une entreprise"}\ndata: {"type": "chunk", "text": " au Togo…"}\n\ndata: {\n  "type": "sources",\n  "sources": [\n    { "title": "Création d'entreprise", "url": "…", "score": 0.88 }\n  ],\n  "latency_ms": 2100\n}\n\ndata: [DONE]`,
  },
];

// ---------------------------------------------------------------------------
// Sidebar
// ---------------------------------------------------------------------------

const NAV_SECTIONS = [
  { id: "get-key",        label: { fr: "Obtenir une clé",   en: "Get a key"       } },
  { id: "authentication", label: { fr: "Authentification",  en: "Authentication"  } },
  { id: "endpoints",      label: { fr: "Endpoints",         en: "Endpoints"       }, children: ENDPOINTS.map(e => ({ id: e.id, method: e.method, path: e.path })) },
  { id: "errors",         label: { fr: "Codes d'erreur",    en: "Error codes"     } },
];

function Sidebar({ active }: { active: string }) {
  const { lang } = useLanguage();

  return (
    <nav className="sticky top-20 self-start w-56 flex-shrink-0 hidden lg:block">
      <Link
        href="/"
        className="flex items-center gap-1.5 text-xs text-slate-400 hover:text-slate-700 mb-6 transition-colors"
      >
        <ChevronLeft className="w-3.5 h-3.5" />
        {lang === "fr" ? "Accueil" : "Home"}
      </Link>

      <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-3">
        TogoLM API v1
      </p>

      <ul className="space-y-0.5">
        {NAV_SECTIONS.map(({ id, label, children }) => (
          <li key={id}>
            <a
              href={`#${id}`}
              className={`block px-2.5 py-1.5 rounded-lg text-xs transition-colors ${
                active === id
                  ? "font-semibold text-slate-900 bg-slate-100"
                  : "text-slate-500 hover:text-slate-800 hover:bg-slate-50"
              }`}
            >
              {label[lang as "fr" | "en"]}
            </a>
            {children && (
              <ul className="mt-0.5 ml-3 space-y-0.5">
                {children.map(({ id: cid, method, path }) => (
                  <li key={cid}>
                    <a
                      href={`#${cid}`}
                      className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs transition-colors ${
                        active === cid
                          ? "font-medium text-slate-900 bg-slate-100"
                          : "text-slate-400 hover:text-slate-700 hover:bg-slate-50"
                      }`}
                    >
                      <span className={`text-[10px] font-bold font-mono ${
                        method === "GET" ? "text-blue-500" : "text-emerald-600"
                      }`}>{method}</span>
                      <span className="font-mono truncate">{path}</span>
                    </a>
                  </li>
                ))}
              </ul>
            )}
          </li>
        ))}
      </ul>

      <div className="mt-8 pt-6 border-t border-slate-100">
        <a
          href={`${API_BASE}/docs`}
          target="_blank"
          rel="noopener noreferrer"
          className="flex items-center gap-1.5 text-xs text-slate-400 hover:text-slate-700 transition-colors"
        >
          <ExternalLink className="w-3 h-3" />
          OpenAPI / Swagger
        </a>
      </div>
    </nav>
  );
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function DevelopersPage() {
  const { lang } = useLanguage();
  const [activeSection, setActiveSection] = useState("get-key");
  const observerRef = useRef<IntersectionObserver | null>(null);

  useEffect(() => {
    const allIds = [
      "get-key", "authentication", "endpoints", "errors",
      ...ENDPOINTS.map((e) => e.id),
    ];

    observerRef.current = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) {
            setActiveSection(entry.target.id);
            break;
          }
        }
      },
      { rootMargin: "-20% 0px -70% 0px" }
    );

    allIds.forEach((id) => {
      const el = document.getElementById(id);
      if (el) observerRef.current?.observe(el);
    });

    return () => observerRef.current?.disconnect();
  }, []);

  return (
    <>
      {/* Hero banner */}
      <section className="border-b border-slate-200 bg-white">
        <div className="max-w-6xl mx-auto px-4 py-10 sm:py-14">
          <div className="flex items-center gap-2 mb-4">
            <span
              className="text-xs font-semibold px-2.5 py-1 rounded-full text-white"
              style={{ background: "var(--togo-green)" }}
            >
              API v1
            </span>
            <span className="text-xs text-slate-400">REST · JSON · SSE</span>
          </div>
          <h1 className="text-3xl sm:text-4xl font-extrabold tracking-tight text-slate-900 mb-3">
            {lang === "fr" ? "Référence API TogoLM" : "TogoLM API Reference"}
          </h1>
          <p className="text-slate-500 max-w-2xl leading-relaxed">
            {lang === "fr"
              ? "Accès programmatique au corpus togolais — recherche sémantique, RAG en streaming, données publiques structurées."
              : "Programmatic access to Togo's knowledge corpus — semantic search, streaming RAG, structured public data."}
          </p>
          <div className="flex flex-wrap gap-5 mt-5 text-sm text-slate-500">
            {[
              { icon: <Key className="w-3.5 h-3.5" />,    text: lang === "fr" ? "Clé gratuite" : "Free API key" },
              { icon: <Zap className="w-3.5 h-3.5" />,    text: "200 req / day" },
              { icon: <Shield className="w-3.5 h-3.5" />, text: "Open-source" },
              { icon: <Code2 className="w-3.5 h-3.5" />,  text: "REST + SSE" },
            ].map(({ icon, text }) => (
              <div key={text} className="flex items-center gap-1.5">
                <span style={{ color: "var(--togo-green)" }}>{icon}</span>
                {text}
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Main layout: sidebar + content */}
      <div className="max-w-6xl mx-auto px-4 py-10 flex gap-12">
        <Sidebar active={activeSection} />

        {/* Content */}
        <div className="flex-1 min-w-0 space-y-16">

          {/* Get a key */}
          <section id="get-key" className="scroll-mt-20">
            <h2 className="text-xl font-bold text-slate-900 mb-1">
              {lang === "fr" ? "Obtenir une clé API" : "Get your API key"}
            </h2>
            <p className="text-sm text-slate-500 mb-6">
              {lang === "fr"
                ? "Gratuit et instantané. La clé n'est affichée qu'une seule fois."
                : "Free and instant. The key is shown only once — save it immediately."}
            </p>

            <div className="grid md:grid-cols-2 gap-5">
              <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-sm">
                <RegisterForm />
              </div>

              <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-sm">
                <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-4">
                  {lang === "fr" ? "Plans & quotas" : "Plans & quotas"}
                </p>
                <div className="space-y-2">
                  {[
                    { plan: "Anonymous", quota: "20 / day",       note: lang === "fr" ? "Par IP" : "Per IP",             active: false },
                    { plan: "Free",      quota: "200 / day",      note: lang === "fr" ? "Avec clé API" : "With API key", active: true  },
                    { plan: "Dev",       quota: "1 000 / day",    note: lang === "fr" ? "Sur demande" : "On request",    active: false },
                    { plan: "Institution", quota: "100 000 / day", note: lang === "fr" ? "Partenaires" : "Partners",     active: false },
                  ].map(({ plan, quota, note, active }) => (
                    <div
                      key={plan}
                      className={`flex items-center justify-between px-3.5 py-2.5 rounded-xl border text-sm ${
                        active ? "border-green-200 bg-green-50" : "border-slate-100 bg-slate-50"
                      }`}
                    >
                      <div className="flex items-center gap-2">
                        <span className={`font-semibold ${active ? "text-green-800" : "text-slate-700"}`}>{plan}</span>
                        {active && (
                          <span className="text-xs px-1.5 py-0.5 rounded-full text-white font-medium" style={{ background: "var(--togo-green)" }}>
                            {lang === "fr" ? "défaut" : "default"}
                          </span>
                        )}
                      </div>
                      <div className="text-right">
                        <div className={`font-mono text-xs font-semibold ${active ? "text-green-700" : "text-slate-600"}`}>{quota}</div>
                        <div className="text-xs text-slate-400">{note}</div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </section>

          {/* Authentication */}
          <section id="authentication" className="scroll-mt-20">
            <h2 className="text-xl font-bold text-slate-900 mb-1">
              {lang === "fr" ? "Authentification" : "Authentication"}
            </h2>
            <p className="text-sm text-slate-500 mb-6">
              {lang === "fr"
                ? "Passez votre clé dans le header "
                : "Pass your key in the "}
              <code className="bg-slate-100 px-1.5 py-0.5 rounded font-mono text-slate-700 text-xs">X-API-Key</code>
              {lang === "fr" ? " de chaque requête HTTP." : " header on every request."}
            </p>
            <CodeBlock
              code={`curl ${API_BASE}/v1/search?q=budget \\\n  -H "X-API-Key: tgolm_your_key_here"`}
              lang="bash"
            />
          </section>

          {/* Endpoints */}
          <section id="endpoints" className="scroll-mt-20">
            <h2 className="text-xl font-bold text-slate-900 mb-1">Endpoints</h2>
            <p className="text-sm text-slate-500 mb-8">
              Base URL:{" "}
              <code className="bg-slate-100 px-1.5 py-0.5 rounded font-mono text-slate-700 text-xs">
                {API_BASE}
              </code>
            </p>
            <div className="space-y-12 divide-y divide-slate-100">
              {ENDPOINTS.map((ep) => (
                <div key={ep.id} className="pt-10 first:pt-0">
                  <EndpointSection ep={ep} />
                </div>
              ))}
            </div>
          </section>

          {/* Error codes */}
          <section id="errors" className="scroll-mt-20">
            <h2 className="text-xl font-bold text-slate-900 mb-6">
              {lang === "fr" ? "Codes d'erreur" : "Error codes"}
            </h2>
            <div className="bg-white rounded-2xl border border-slate-200 overflow-hidden shadow-sm">
              <table className="w-full text-sm">
                <thead className="bg-slate-50 text-xs text-slate-400 uppercase tracking-wider">
                  <tr>
                    <th className="text-left px-5 py-3 w-20">Code</th>
                    <th className="text-left px-5 py-3">{lang === "fr" ? "Signification" : "Meaning"}</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {[
                    { code: "200", meaning: { fr: "Succès",                                               en: "Success" } },
                    { code: "400", meaning: { fr: "Requête invalide (paramètre manquant ou malformé)",    en: "Bad request (missing or malformed parameter)" } },
                    { code: "401", meaning: { fr: "Clé API invalide ou absente",                          en: "Invalid or missing API key" } },
                    { code: "409", meaning: { fr: "Email déjà enregistré",                                en: "Email already registered" } },
                    { code: "422", meaning: { fr: "Validation échouée (corps de requête invalide)",       en: "Validation failed (invalid request body)" } },
                    { code: "429", meaning: { fr: "Quota journalier dépassé",                             en: "Daily quota exceeded" } },
                    { code: "500", meaning: { fr: "Erreur serveur interne",                               en: "Internal server error" } },
                  ].map(({ code, meaning }) => (
                    <tr key={code} className="hover:bg-slate-50 transition-colors">
                      <td className="px-5 py-3 font-mono text-xs font-bold text-slate-700">{code}</td>
                      <td className="px-5 py-3 text-slate-500">{meaning[lang as "fr" | "en"]}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>

        </div>
      </div>
    </>
  );
}
