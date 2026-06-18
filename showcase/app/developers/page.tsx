"use client";

import React, { useState, useEffect, useRef, type ReactNode } from "react";
import {
  Copy, Check, Download, LayoutGrid, KeyRound,
  AlertCircle, BarChart2, FileText, Search as SearchIcon,
  MessageSquare, Zap, Shield,
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

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type CodeTab = "curl" | "python" | "js";
type AuthLevel = "none" | "optional" | "required";

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
  examples: { curl: string; python?: string; js?: string };
  responseExample?: string;
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
    responseExample: `{\n  "total_documents": 62168,\n  "total_chunks": 310840,\n  "languages": ["fr"],\n  "sources": [\n    { "source": "jo.gouv.tg", "documents": 34, "chunks": 187 },\n    { "source": "inseed.tg",  "documents": 90, "chunks": 450 }\n  ],\n  "last_updated": "2026-06-12T08:00:00"\n}`,
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
      { name: "page",      type: "integer", in: "query", required: false, description: "Page number", default: "1" },
      { name: "page_size", type: "integer", in: "query", required: false, description: "Results per page (max 100)", default: "20" },
      { name: "source",    type: "string",  in: "query", required: false, description: "Filter by source domain (e.g. jo.gouv.tg)" },
      { name: "category",  type: "string",  in: "query", required: false, description: "legal · education · economy · agriculture · health · politics · press" },
      { name: "language",  type: "string",  in: "query", required: false, description: "Language code", default: "fr" },
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
      en: "Full-text search using French-optimized PostgreSQL FTS (ts_rank) with ILIKE fallback. Returns excerpts with relevance scores.",
    },
    auth: "optional",
    params: [
      { name: "q",        type: "string",  in: "query", required: true,  description: "Search query (min 2, max 500 chars)" },
      { name: "source",   type: "string",  in: "query", required: false, description: "Restrict to a specific source domain" },
      { name: "category", type: "string",  in: "query", required: false, description: "Restrict to a category" },
      { name: "limit",    type: "integer", in: "query", required: false, description: "Max results (max 50)", default: "10" },
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
      { name: "question", type: "string", in: "body", required: true,  description: "The question to answer (min 3, max 1000 chars)" },
      { name: "category", type: "string", in: "body", required: false, description: "Restrict retrieval to a category" },
      { name: "language", type: "string", in: "body", required: false, description: "Response language", default: "fr" },
    ],
    examples: {
      curl: `curl -X POST ${API_BASE}/v1/query \\\n  -H "Content-Type: application/json" \\\n  -H "X-API-Key: YOUR_KEY" \\\n  -d '{"question": "Quel est le budget de l\\'État togolais ?"}'`,
      python: `import requests\n\nres = requests.post(\n    "${API_BASE}/v1/query",\n    json={"question": "Quel est le budget de l'État togolais ?"},\n    headers={"X-API-Key": "YOUR_KEY"}\n)\ndata = res.json()\nprint(data["answer"])`,
      js: `const res = await fetch("${API_BASE}/v1/query", {\n  method: "POST",\n  headers: {\n    "Content-Type": "application/json",\n    "X-API-Key": "YOUR_KEY"\n  },\n  body: JSON.stringify({\n    question: "Quel est le budget de l'État togolais ?"\n  })\n});\nconst { answer, sources } = await res.json();`,
    },
    responseExample: `{\n  "answer": "Le budget de l'État togolais pour 2025 s'élève à 2 400 milliards de FCFA…",\n  "sources": [\n    {\n      "title": "Loi de finances 2025",\n      "url": "https://jo.gouv.tg/loi-finances-2025",\n      "score": 0.91\n    }\n  ],\n  "model": "togolm-rag-v1",\n  "latency_ms": 1842\n}`,
  },
  {
    id: "query-stream",
    method: "POST",
    path: "/v1/query/stream",
    summary: { fr: "Question RAG (streaming SSE)", en: "RAG query (SSE stream)" },
    description: {
      fr: "Identique à /v1/query mais diffuse la réponse token par token via Server-Sent Events. Événements : thinking (réflexion) · chunk (texte) · sources (citations).",
      en: "Same as /v1/query but streams the answer token-by-token via Server-Sent Events. Events: thinking (reasoning) · chunk (text) · sources (citations).",
    },
    auth: "optional",
    params: [
      { name: "question", type: "string", in: "body", required: true,  description: "The question to answer" },
      { name: "category", type: "string", in: "body", required: false, description: "Restrict retrieval to a category" },
      { name: "language", type: "string", in: "body", required: false, description: "Response language", default: "fr" },
    ],
    examples: {
      curl: `curl -X POST ${API_BASE}/v1/query/stream \\\n  -H "Content-Type: application/json" \\\n  -H "X-API-Key: YOUR_KEY" \\\n  --no-buffer \\\n  -d '{"question": "Comment créer une entreprise au Togo ?"}'`,
      python: `import requests, json\n\nwith requests.post(\n    "${API_BASE}/v1/query/stream",\n    json={"question": "Comment créer une entreprise au Togo ?"},\n    headers={"X-API-Key": "YOUR_KEY"},\n    stream=True\n) as res:\n    for line in res.iter_lines():\n        if line.startswith(b"data: "):\n            event = json.loads(line[6:])\n            if event["type"] == "chunk":\n                print(event["text"], end="", flush=True)`,
      js: `const res = await fetch("${API_BASE}/v1/query/stream", {\n  method: "POST",\n  headers: {\n    "Content-Type": "application/json",\n    "X-API-Key": "YOUR_KEY"\n  },\n  body: JSON.stringify({ question: "Comment créer une entreprise ?" })\n});\n\nconst reader = res.body.getReader();\nconst decoder = new TextDecoder();\nlet buf = "";\n\nwhile (true) {\n  const { done, value } = await reader.read();\n  if (done) break;\n  buf += decoder.decode(value, { stream: true });\n  for (const block of buf.split("\\n\\n")) {\n    if (!block.startsWith("data: ")) continue;\n    const e = JSON.parse(block.slice(6));\n    if (e.type === "chunk") process.stdout.write(e.text);\n  }\n}`,
    },
    responseExample: `data: {"type": "thinking", "text": "Je dois analyser…"}\ndata: {"type": "chunk",   "text": "Pour créer"}\ndata: {"type": "chunk",   "text": " une entreprise"}\ndata: {"type": "chunk",   "text": " au Togo…"}\ndata: {\n  "type": "sources",\n  "sources": [\n    { "title": "Création d'entreprise", "url": "…", "score": 0.88 }\n  ],\n  "latency_ms": 2100\n}\ndata: [DONE]`,
  },
];

// ---------------------------------------------------------------------------
// Export helpers
// ---------------------------------------------------------------------------

function triggerDownload(filename: string, content: string, mime: string) {
  const blob = new Blob([content], { type: mime });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

function buildPostmanCollection(): object {
  const items = ENDPOINTS.map((ep) => {
    const urlPath = ep.path.replace(/^\//, "").split("/");
    const headers: { key: string; value: string; description?: string }[] = [
      { key: "X-API-Key", value: "{{apiKey}}", description: "TogoLM API key" },
    ];
    const isPost = ep.method === "POST";
    if (isPost) headers.push({ key: "Content-Type", value: "application/json" });

    const bodyParams: Record<string, string | number | boolean> = {};
    const queryParams: { key: string; value: string; disabled: boolean }[] = [];
    ep.params?.forEach((p) => {
      if (p.in === "body") bodyParams[p.name] = p.default ?? (p.type === "integer" ? 0 : "");
      else if (p.in === "query") queryParams.push({ key: p.name, value: p.default ?? "", disabled: !p.required });
    });

    const request: Record<string, unknown> = {
      method: ep.method,
      header: headers,
      url: {
        raw: `{{baseUrl}}/${urlPath.join("/")}`,
        host: ["{{baseUrl}}"],
        path: urlPath,
        ...(queryParams.length > 0 ? { query: queryParams } : {}),
      },
      description: ep.description.en,
    };
    if (isPost && Object.keys(bodyParams).length > 0) {
      request.body = { mode: "raw", raw: JSON.stringify(bodyParams, null, 2), options: { raw: { language: "json" } } };
    }
    return { name: `${ep.method} ${ep.path}`, request, response: [] };
  });

  return {
    info: {
      name: "TogoLM API v1",
      description: "The first open-source AI API for Togo — RAG pipeline, semantic search, corpus data.",
      schema: "https://schema.getpostman.com/json/collection/v2.1.0/collection.json",
    },
    variable: [
      { key: "baseUrl", value: API_BASE, type: "string" },
      { key: "apiKey",  value: "",        type: "string", description: "Your TogoLM API key (tgolm_...)" },
    ],
    item: items,
  };
}

// ---------------------------------------------------------------------------
// Dark code panel (code blocks are dark even on white pages — standard)
// ---------------------------------------------------------------------------

function CodePanel({ code, label }: { code: string; label: string }) {
  const { copied, copy } = useCopy(code);
  return (
    <div className="flex-1 min-w-0 flex flex-col min-h-0">
      <div className="flex items-center justify-between px-4 py-2 border-b border-slate-700/60">
        <span className="text-[10px] font-bold tracking-widest uppercase text-slate-500">{label}</span>
        <button
          onClick={copy}
          className="flex items-center gap-1 text-[10px] text-slate-500 hover:text-slate-300 transition-colors"
        >
          {copied ? <Check className="w-3 h-3" /> : <Copy className="w-3 h-3" />}
          {copied ? "Copié" : "Copier"}
        </button>
      </div>
      <pre className="flex-1 px-4 py-3.5 text-xs font-mono text-slate-300 leading-relaxed overflow-x-auto">
        <code>{code}</code>
      </pre>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Method badge
// ---------------------------------------------------------------------------

function MethodBadge({ method }: { method: "GET" | "POST" }) {
  return (
    <span
      className={`text-xs font-bold px-2 py-0.5 rounded font-mono ${
        method === "GET"
          ? "bg-blue-50 text-blue-700 border border-blue-200"
          : "text-white"
      }`}
      style={method === "POST" ? { background: "var(--togo-green)" } : {}}
    >
      {method}
    </span>
  );
}

// ---------------------------------------------------------------------------
// Auth badge
// ---------------------------------------------------------------------------

const AUTH_LABEL = {
  none:     { fr: "Public",          en: "Public" },
  optional: { fr: "Clé optionnelle", en: "Key optional" },
  required: { fr: "Clé requise",     en: "Key required" },
} as const;

// ---------------------------------------------------------------------------
// Endpoint card
// ---------------------------------------------------------------------------

function EndpointCard({ ep }: { ep: Endpoint }) {
  const { lang } = useLanguage();
  const [tab, setTab] = useState<CodeTab>("curl");

  const tabs: { key: CodeTab; label: string }[] = [
    { key: "curl", label: "cURL" },
    ...(ep.examples.python ? [{ key: "python" as CodeTab, label: "Python" }] : []),
    ...(ep.examples.js     ? [{ key: "js"     as CodeTab, label: "JS" }]     : []),
  ];

  const reqCode: Record<string, string> = {
    curl:   ep.examples.curl,
    python: ep.examples.python ?? "",
    js:     ep.examples.js ?? "",
  };

  return (
    <section id={ep.id} className="scroll-mt-8">
      <div className="rounded-xl border border-slate-200 bg-white overflow-hidden shadow-sm">

        {/* Header */}
        <div className="flex items-center justify-between gap-3 px-5 py-3.5 border-b border-slate-100">
          <div className="flex items-center gap-3 min-w-0">
            <MethodBadge method={ep.method} />
            <code className="text-sm font-mono text-slate-800 font-semibold truncate">{ep.path}</code>
          </div>
          <span className="text-[10px] font-mono text-slate-400 bg-slate-50 border border-slate-200 px-2 py-0.5 rounded whitespace-nowrap flex-shrink-0">
            {AUTH_LABEL[ep.auth][lang as "fr" | "en"]}
          </span>
        </div>

        {/* Description */}
        <div className="px-5 py-3 border-b border-slate-100">
          <p className="text-sm text-slate-500 leading-relaxed">{ep.description[lang as "fr" | "en"]}</p>
        </div>

        {/* Params */}
        {ep.params && ep.params.length > 0 && (
          <div className="px-5 py-3 border-b border-slate-100">
            <p className="text-[10px] font-bold tracking-widest uppercase text-slate-400 mb-2">
              {lang === "fr" ? "Paramètres" : "Parameters"}
            </p>
            <div className="divide-y divide-slate-100">
              {ep.params.map((p) => (
                <div key={p.name} className="py-2 flex flex-wrap items-baseline gap-x-2.5 gap-y-0.5">
                  <code className="text-xs font-mono font-semibold" style={{ color: "var(--togo-green)" }}>{p.name}</code>
                  <span className="text-[10px] font-mono text-blue-500">{p.type}</span>
                  <span className={`text-[10px] px-1.5 py-px rounded ${
                    p.in === "body" ? "bg-purple-50 text-purple-600" :
                    p.in === "path" ? "bg-orange-50 text-orange-600" :
                    "bg-slate-100 text-slate-500"
                  }`}>{p.in}</span>
                  {p.required && <span className="text-[10px] text-red-500 font-medium">required</span>}
                  <span className="text-xs text-slate-400 w-full sm:w-auto">{p.description}</span>
                  {p.default && (
                    <span className="text-[10px] text-slate-400">
                      default: <code className="text-slate-500">{p.default}</code>
                    </span>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* REQUÊTE / RÉPONSE */}
        <div className="flex flex-col lg:flex-row divide-y lg:divide-y-0 lg:divide-x divide-slate-200 bg-[#0f172a] rounded-b-xl">
          {/* Left: request */}
          <div className="flex-1 flex flex-col min-h-[180px]">
            <div className="flex items-center gap-2 px-4 pt-3 pb-2">
              <span className="text-[10px] font-bold tracking-widest uppercase text-slate-500 mr-1">
                {lang === "fr" ? "Requête" : "Request"}
              </span>
              {tabs.map(({ key, label }) => (
                <button
                  key={key}
                  onClick={() => setTab(key)}
                  className={`px-2 py-0.5 rounded text-[11px] font-medium transition-colors ${
                    tab === key
                      ? "bg-white/10 text-slate-200"
                      : "text-slate-500 hover:text-slate-400"
                  }`}
                >
                  {label}
                </button>
              ))}
            </div>
            <CodePanel code={reqCode[tab] ?? ""} label="" />
          </div>

          {/* Right: response */}
          {ep.responseExample && (
            <div className="flex-1 flex flex-col min-h-[180px]">
              <div className="px-4 pt-3 pb-2">
                <span className="text-[10px] font-bold tracking-widest uppercase text-slate-500">
                  {lang === "fr" ? "Réponse" : "Response"}
                </span>
              </div>
              <CodePanel code={ep.responseExample} label="" />
            </div>
          )}
        </div>

      </div>
    </section>
  );
}

// ---------------------------------------------------------------------------
// Register form
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
        <div className="flex items-center gap-2 font-medium text-sm" style={{ color: "var(--togo-green)" }}>
          <Check className="w-4 h-4" />
          {lang === "fr" ? "Clé créée avec succès !" : "API key created!"}
        </div>
        <div className="rounded-lg bg-amber-50 border border-amber-200 px-4 py-3 text-xs text-amber-700 leading-relaxed">
          {lang === "fr"
            ? "⚠️ Copiez et sauvegardez cette clé maintenant — elle ne sera plus jamais affichée."
            : "⚠️ Copy and save this key now — it will never be shown again."}
        </div>
        <div className="rounded-lg bg-slate-900 border border-slate-700 overflow-hidden">
          <div className="flex items-center justify-between px-4 py-2 border-b border-slate-700">
            <span className="text-[10px] font-bold tracking-widest uppercase text-slate-400">
              {lang === "fr" ? "Votre clé API" : "Your API key"}
            </span>
            <button
              onClick={copy}
              className={`flex items-center gap-1 text-xs px-2 py-1 rounded transition-all ${
                copied ? "text-emerald-400" : "text-slate-400 hover:text-slate-200"
              }`}
            >
              {copied ? <Check className="w-3 h-3" /> : <Copy className="w-3 h-3" />}
              {copied ? "Copié" : "Copier"}
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
              <div className="font-mono font-semibold text-slate-700">{s.value}</div>
            </div>
          ))}
        </div>
      </div>
    );
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-3">
      {[
        { key: "name",     label: lang === "fr" ? "Nom" : "Name",   type: "text",  required: true,  placeholder: "Kofi Mensah" },
        { key: "email",    label: "Email",                           type: "email", required: true,  placeholder: "kofi@example.com" },
        { key: "use_case", label: lang === "fr" ? "Cas d'usage (optionnel)" : "Use case (optional)", type: "text", required: false, placeholder: lang === "fr" ? "Chatbot éducatif, app mobile…" : "Education chatbot, mobile app…" },
      ].map(({ key, label, type, required, placeholder }) => (
        <div key={key}>
          <label className="block text-xs font-medium text-slate-500 mb-1.5">{label}</label>
          <input
            type={type}
            required={required}
            value={fields[key as keyof typeof fields]}
            onChange={(e) => setFields((f) => ({ ...f, [key]: e.target.value }))}
            placeholder={placeholder}
            className="w-full px-3.5 py-2.5 rounded-lg border border-slate-200 text-sm text-slate-800 placeholder:text-slate-300 focus:outline-none focus:ring-2 focus:border-transparent bg-white transition-all"
            style={{ "--tw-ring-color": "rgba(0,106,78,0.25)" } as React.CSSProperties}
          />
        </div>
      ))}
      {error && (
        <div className="rounded-lg bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-600">
          {error}
        </div>
      )}
      <button
        type="submit"
        disabled={loading}
        className="w-full px-4 py-2.5 rounded-lg text-white text-sm font-semibold disabled:opacity-50 hover:opacity-90 transition-opacity"
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
// Sidebar
// ---------------------------------------------------------------------------

type LucideIcon = React.ComponentType<{ className?: string }>;

interface SidebarItem {
  id: string;
  icon: LucideIcon;
  label: { fr: string; en: string };
  method?: string;
}

const SIDEBAR_SECTIONS: { label: { fr: string; en: string }; items: SidebarItem[] }[] = [
  {
    label: { fr: "Démarrage", en: "Getting started" },
    items: [
      { id: "overview",       icon: LayoutGrid,   label: { fr: "Vue d'ensemble",   en: "Overview" } },
      { id: "get-key",        icon: KeyRound,     label: { fr: "Obtenir une clé",  en: "Get a key" } },
      { id: "authentication", icon: Shield,       label: { fr: "Authentification", en: "Authentication" } },
    ],
  },
  {
    label: { fr: "Endpoints", en: "Endpoints" },
    items: [
      { id: "stats",        icon: BarChart2,     label: { fr: "Statistiques",   en: "Statistics" },   method: "GET"  },
      { id: "documents",    icon: FileText,      label: { fr: "Documents",      en: "Documents" },    method: "GET"  },
      { id: "search",       icon: SearchIcon,    label: { fr: "Recherche",      en: "Search" },       method: "GET"  },
      { id: "query",        icon: MessageSquare, label: { fr: "Query",          en: "Query" },        method: "POST" },
      { id: "query-stream", icon: Zap,           label: { fr: "Query Stream",   en: "Query Stream" }, method: "POST" },
    ],
  },
  {
    label: { fr: "Référence", en: "Reference" },
    items: [
      { id: "errors", icon: AlertCircle, label: { fr: "Codes d'erreur", en: "Error codes" } },
    ],
  },
];

function DocsSidebar({ active }: { active: string }) {
  const { lang } = useLanguage();

  function exportPostman() {
    const collection = buildPostmanCollection();
    triggerDownload("togolm_postman_collection.json", JSON.stringify(collection, null, 2), "application/json");
  }

  return (
    <aside className="fixed top-14 left-0 w-64 h-[calc(100vh-3.5rem)] bg-white border-r border-slate-200 overflow-y-auto flex flex-col z-10">
      <div className="flex-1 py-6 px-3 space-y-5">
        {SIDEBAR_SECTIONS.map((section) => (
          <div key={section.label.fr}>
            <p className="text-[10px] font-bold tracking-widest uppercase text-slate-400 px-2 mb-1.5">
              {section.label[lang as "fr" | "en"]}
            </p>
            <ul className="space-y-0.5">
              {section.items.map(({ id, icon: Icon, label, method }) => {
                const isActive = active === id;
                return (
                  <li key={id}>
                    <a
                      href={`#${id}`}
                      className={`flex items-center gap-2.5 px-2.5 py-1.5 rounded-lg text-sm transition-all ${
                        isActive
                          ? "font-medium border-l-2 -ml-px pl-[9px] rounded-l-none"
                          : "text-slate-500 hover:text-slate-800 hover:bg-slate-50 border-l-2 border-transparent"
                      }`}
                      style={isActive ? {
                        borderColor: "var(--togo-green)",
                        color: "var(--togo-green)",
                        background: "rgba(0,106,78,0.05)",
                      } : {}}
                    >
                      <Icon className="w-3.5 h-3.5 flex-shrink-0" />
                      <span className="flex-1 truncate">{label[lang as "fr" | "en"]}</span>
                      {method && (
                        <span className={`text-[9px] font-bold font-mono ${
                          method === "GET" ? "text-blue-500" : "text-emerald-600"
                        }`}>
                          {method}
                        </span>
                      )}
                    </a>
                  </li>
                );
              })}
            </ul>
          </div>
        ))}
      </div>

      {/* Export button */}
      <div className="px-3 py-4 border-t border-slate-100">
        <button
          onClick={exportPostman}
          className="flex items-center gap-2 text-xs text-slate-400 hover:text-slate-600 transition-colors"
        >
          <Download className="w-3.5 h-3.5" />
          {lang === "fr" ? "Exporter la collection" : "Export collection"}
          <span className="font-mono font-bold text-orange-500 text-[10px]">PM</span>
        </button>
      </div>
    </aside>
  );
}

// ---------------------------------------------------------------------------
// Section wrapper
// ---------------------------------------------------------------------------

function Section({ id, title, subtitle, children }: {
  id: string;
  title: string;
  subtitle?: string;
  children: ReactNode;
}) {
  return (
    <section id={id} className="scroll-mt-8">
      <h2 className="text-xl font-bold text-slate-900 mb-1">{title}</h2>
      {subtitle && <p className="text-sm text-slate-500 mb-5 leading-relaxed">{subtitle}</p>}
      {children}
    </section>
  );
}

// ---------------------------------------------------------------------------
// Inline copy button
// ---------------------------------------------------------------------------

function CopyIconBtn({ text }: { text: string }) {
  const { copied, copy } = useCopy(text);
  return (
    <button
      onClick={copy}
      className="flex items-center gap-1 text-[10px] text-slate-400 hover:text-slate-600 transition-colors"
    >
      {copied ? <Check className="w-3 h-3" /> : <Copy className="w-3 h-3" />}
      {copied ? "Copié" : "Copier"}
    </button>
  );
}

// ---------------------------------------------------------------------------
// All section IDs for intersection observer
// ---------------------------------------------------------------------------

const ALL_SECTION_IDS = [
  "overview", "get-key", "authentication",
  ...ENDPOINTS.map((e) => e.id),
  "errors",
];

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function DevelopersPage() {
  const { lang } = useLanguage();
  const [active, setActive] = useState("overview");
  const { copied: urlCopied, copy: copyUrl } = useCopy(API_BASE);

  useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) { setActive(entry.target.id); break; }
        }
      },
      { rootMargin: "-20% 0px -70% 0px" },
    );
    ALL_SECTION_IDS.forEach((id) => {
      const el = document.getElementById(id);
      if (el) observer.observe(el);
    });
    return () => observer.disconnect();
  }, []);

  return (
    <div className="min-h-screen bg-white">
      <DocsSidebar active={active} />

      <div className="ml-64 min-h-screen">
        <div className="px-10 py-10 space-y-14">

          {/* ── Overview ── */}
          <section id="overview" className="scroll-mt-8">
            <p className="text-xs font-bold tracking-widest uppercase mb-3" style={{ color: "var(--togo-green)" }}>
              Documentation
            </p>
            <h1 className="text-3xl font-extrabold text-slate-900 mb-3 tracking-tight">TogoLM API</h1>
            <p className="text-slate-500 leading-relaxed max-w-2xl mb-6">
              {lang === "fr"
                ? "Une API REST + SSE pour accéder au corpus togolais — recherche sémantique, RAG en streaming avec réflexion visible et navigation des documents publics."
                : "A REST + SSE API to access Togo's knowledge corpus — semantic search, streaming RAG with visible reasoning and public document navigation."}
            </p>

            {/* Postman CTA */}
            <button
              onClick={() => {
                const col = buildPostmanCollection();
                triggerDownload("togolm_postman_collection.json", JSON.stringify(col, null, 2), "application/json");
              }}
              className="inline-flex items-center gap-2 px-4 py-2 rounded-lg border border-slate-200 bg-white text-sm text-slate-600 hover:border-slate-300 hover:bg-slate-50 transition-colors shadow-sm mb-8 font-medium"
            >
              <Download className="w-4 h-4" />
              {lang === "fr" ? "Importer la collection Postman" : "Import Postman collection"}
              <span className="font-mono font-bold text-orange-500 text-xs">PM</span>
            </button>

            {/* Base URL */}
            <div className="rounded-xl border border-slate-200 bg-slate-50 px-5 py-4 mb-8">
              <p className="text-[10px] font-bold tracking-widest uppercase text-slate-400 mb-2">Base URL</p>
              <div className="flex items-center justify-between gap-4">
                <code className="font-mono text-sm text-slate-700">{API_BASE}</code>
                <button
                  onClick={copyUrl}
                  className="flex items-center gap-1.5 text-xs text-slate-400 hover:text-slate-600 transition-colors flex-shrink-0"
                >
                  {urlCopied ? <Check className="w-3.5 h-3.5" /> : <Copy className="w-3.5 h-3.5" />}
                  {urlCopied ? (lang === "fr" ? "Copié" : "Copied") : (lang === "fr" ? "Copier" : "Copy")}
                </button>
              </div>
            </div>

            {/* Headers table */}
            <h3 className="text-base font-semibold text-slate-800 mb-3">
              {lang === "fr" ? "En-têtes HTTP" : "HTTP headers"}
            </h3>
            <div className="rounded-xl border border-slate-200 overflow-hidden mb-10">
              <table className="w-full text-sm">
                <thead className="bg-slate-50">
                  <tr className="border-b border-slate-200">
                    <th className="text-left px-5 py-2.5 text-[10px] font-bold tracking-widest uppercase text-slate-400 w-44">Header</th>
                    <th className="text-left px-5 py-2.5 text-[10px] font-bold tracking-widest uppercase text-slate-400">Description</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 bg-white">
                  {[
                    { key: "X-API-Key",    desc: lang === "fr" ? "Clé API TogoLM — optionnelle sur les endpoints publics, augmente le quota" : "TogoLM API key — optional on public endpoints, increases quota" },
                    { key: "Content-Type", desc: "application/json — " + (lang === "fr" ? "requis pour les requêtes POST" : "required for POST requests") },
                  ].map(({ key, desc }) => (
                    <tr key={key}>
                      <td className="px-5 py-3">
                        <code className="text-xs font-mono font-semibold" style={{ color: "var(--togo-green)" }}>{key}</code>
                      </td>
                      <td className="px-5 py-3 text-slate-500 text-xs">{desc}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* 4 steps */}
            <h3 className="text-base font-semibold text-slate-800 mb-4">
              {lang === "fr" ? "Démarrer en 4 étapes" : "Get started in 4 steps"}
            </h3>
            <div className="rounded-xl border border-slate-200 overflow-hidden divide-y divide-slate-100">
              {[
                {
                  n: "01",
                  title: { fr: "Créez une clé API", en: "Create an API key" },
                  desc:  { fr: "Gratuit, instantané. Utilisez le formulaire ci-dessous — la clé est affichée une seule fois.", en: "Free and instant. Use the form below — the key is shown only once." },
                  href: "#get-key",
                },
                {
                  n: "02",
                  title: { fr: "Ajoutez le header", en: "Add the header" },
                  desc:  { fr: "Passez votre clé via X-API-Key sur chaque requête pour bénéficier de 200 req/jour.", en: "Pass your key via X-API-Key on every request to get 200 req/day." },
                },
                {
                  n: "03",
                  title: { fr: "Interrogez le corpus", en: "Query the corpus" },
                  desc:  { fr: "POST /v1/query/stream — réponse RAG avec réflexion Gemini 2.5 Flash en streaming.", en: "POST /v1/query/stream — RAG answer with Gemini 2.5 Flash thinking, streamed token by token." },
                  href: "#query-stream",
                },
                {
                  n: "04",
                  title: { fr: "Explorez les données", en: "Explore the data" },
                  desc:  { fr: "GET /v1/documents et GET /v1/search pour naviguer les 62 168 documents togolais.", en: "GET /v1/documents and GET /v1/search to browse the 62,168 Togolese documents." },
                  href: "#documents",
                },
              ].map(({ n, title, desc, href }) => (
                <div key={n} className="flex items-start gap-4 px-5 py-4 bg-white hover:bg-slate-50/60 transition-colors">
                  <span className="text-sm font-bold font-mono flex-shrink-0 mt-0.5" style={{ color: "var(--togo-green)" }}>{n}</span>
                  <div>
                    {href ? (
                      <a href={href} className="text-sm font-semibold text-slate-800 hover:underline" style={{ textDecorationColor: "var(--togo-green)" }}>
                        {title[lang as "fr" | "en"]}
                      </a>
                    ) : (
                      <p className="text-sm font-semibold text-slate-800">{title[lang as "fr" | "en"]}</p>
                    )}
                    <p className="text-xs text-slate-400 mt-0.5 leading-relaxed">{desc[lang as "fr" | "en"]}</p>
                  </div>
                </div>
              ))}
            </div>
          </section>

          {/* ── Get a key ── */}
          <Section
            id="get-key"
            title={lang === "fr" ? "Obtenir une clé API" : "Get your API key"}
            subtitle={lang === "fr"
              ? "Gratuit et instantané. La clé n'est affichée qu'une seule fois — sauvegardez-la immédiatement."
              : "Free and instant. The key is shown only once — save it immediately."}
          >
            <div className="grid md:grid-cols-2 gap-5">
              <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
                <RegisterForm />
              </div>
              <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
                <p className="text-[10px] font-bold tracking-widest uppercase text-slate-400 mb-4">
                  {lang === "fr" ? "Plans & quotas" : "Plans & quotas"}
                </p>
                <div className="space-y-2">
                  {[
                    { plan: "Anonymous",   quota: "20 / day",      note: lang === "fr" ? "Par IP" : "Per IP",             active: false },
                    { plan: "Free",        quota: "200 / day",     note: lang === "fr" ? "Avec clé API" : "With API key", active: true  },
                    { plan: "Dev",         quota: "1 000 / day",   note: lang === "fr" ? "Sur demande" : "On request",    active: false },
                    { plan: "Institution", quota: "100 000 / day", note: lang === "fr" ? "Partenaires" : "Partners",      active: false },
                  ].map(({ plan, quota, note, active }) => (
                    <div
                      key={plan}
                      className={`flex items-center justify-between px-3.5 py-2.5 rounded-lg border text-sm ${
                        active ? "border-green-200 bg-green-50" : "border-slate-200 bg-slate-50"
                      }`}
                    >
                      <div className="flex items-center gap-2">
                        <span className={`font-semibold ${active ? "" : "text-slate-600"}`} style={active ? { color: "var(--togo-green)" } : {}}>
                          {plan}
                        </span>
                        {active && (
                          <span className="text-[10px] px-1.5 py-0.5 rounded text-white font-medium" style={{ background: "var(--togo-green)" }}>
                            {lang === "fr" ? "défaut" : "default"}
                          </span>
                        )}
                      </div>
                      <div className="text-right">
                        <div className={`font-mono text-xs font-semibold ${active ? "" : "text-slate-600"}`} style={active ? { color: "var(--togo-green)" } : {}}>
                          {quota}
                        </div>
                        <div className="text-[10px] text-slate-400">{note}</div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </Section>

          {/* ── Authentication ── */}
          <Section
            id="authentication"
            title={lang === "fr" ? "Authentification" : "Authentication"}
            subtitle={lang === "fr"
              ? "Passez votre clé dans le header X-API-Key de chaque requête HTTP."
              : "Pass your key in the X-API-Key header on every request."}
          >
            <div className="rounded-xl border border-slate-200 overflow-hidden shadow-sm">
              <div className="flex items-center justify-between px-4 py-2.5 bg-slate-50 border-b border-slate-200">
                <span className="text-[10px] font-bold tracking-widest uppercase text-slate-400">cURL</span>
                <CopyIconBtn text={`curl ${API_BASE}/v1/search?q=budget \\\n  -H "X-API-Key: tgolm_your_key_here"`} />
              </div>
              <div className="bg-[#0f172a] rounded-b-xl">
                <pre className="px-5 py-4 text-xs font-mono text-slate-300 leading-relaxed overflow-x-auto">
                  <code>{`curl ${API_BASE}/v1/search?q=budget \\\n  -H "X-API-Key: tgolm_your_key_here"`}</code>
                </pre>
              </div>
            </div>
          </Section>

          {/* ── Endpoint cards ── */}
          {ENDPOINTS.map((ep) => (
            <EndpointCard key={ep.id} ep={ep} />
          ))}

          {/* ── Error codes ── */}
          <Section
            id="errors"
            title={lang === "fr" ? "Codes d'erreur" : "Error codes"}
          >
            <div className="rounded-xl border border-slate-200 overflow-hidden shadow-sm">
              <table className="w-full text-sm">
                <thead className="bg-slate-50">
                  <tr className="border-b border-slate-200">
                    <th className="text-left px-5 py-2.5 text-[10px] font-bold tracking-widest uppercase text-slate-400 w-20">Code</th>
                    <th className="text-left px-5 py-2.5 text-[10px] font-bold tracking-widest uppercase text-slate-400">
                      {lang === "fr" ? "Signification" : "Meaning"}
                    </th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-slate-100">
                  {[
                    { code: "200", meaning: { fr: "Succès",                                             en: "Success" } },
                    { code: "400", meaning: { fr: "Requête invalide (paramètre manquant ou malformé)",  en: "Bad request (missing or malformed parameter)" } },
                    { code: "401", meaning: { fr: "Clé API invalide ou absente",                        en: "Invalid or missing API key" } },
                    { code: "409", meaning: { fr: "Email déjà enregistré",                              en: "Email already registered" } },
                    { code: "422", meaning: { fr: "Validation échouée (corps de requête invalide)",     en: "Validation failed (invalid request body)" } },
                    { code: "429", meaning: { fr: "Quota journalier dépassé",                           en: "Daily quota exceeded" } },
                    { code: "500", meaning: { fr: "Erreur serveur interne",                             en: "Internal server error" } },
                  ].map(({ code, meaning }) => (
                    <tr key={code} className="hover:bg-slate-50/60 transition-colors">
                      <td className="px-5 py-3 font-mono text-xs font-bold text-slate-700">{code}</td>
                      <td className="px-5 py-3 text-slate-500 text-sm">{meaning[lang as "fr" | "en"]}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Section>

        </div>
      </div>
    </div>
  );
}
