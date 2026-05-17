"use client";

import { useState, useRef, useEffect } from "react";
import { queryRAG, type QuerySource } from "@/lib/api";
import { Send, Loader2, ExternalLink, Bot, User } from "lucide-react";

interface Message {
  role: "user" | "assistant";
  content: string;
  sources?: QuerySource[];
  latency_ms?: number;
}

const SUGGESTED = [
  "Quelles sont les procédures pour créer une entreprise au Togo ?",
  "Quels sont les droits des travailleurs selon le code du travail togolais ?",
  "Comment fonctionne le système éducatif au Togo ?",
  "Quel est le budget de l'État togolais ?",
];

export default function ChatPage() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  async function send(question: string) {
    if (!question.trim() || loading) return;
    const q = question.trim();
    setInput("");
    setMessages((prev) => [...prev, { role: "user", content: q }]);
    setLoading(true);
    try {
      const data = await queryRAG(q);
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: data.answer,
          sources: data.sources,
          latency_ms: data.latency_ms,
        },
      ]);
    } catch {
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: "Error reaching the API. Is it running?" },
      ]);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="max-w-3xl mx-auto px-4 py-8 flex flex-col" style={{ minHeight: "calc(100vh - 112px)" }}>
      <h1 className="text-2xl font-bold mb-6">Ask TogoLM</h1>

      {/* Empty state */}
      {messages.length === 0 && (
        <div className="flex-1 flex flex-col items-center justify-center gap-6 text-center">
          <div
            className="w-12 h-12 rounded-full flex items-center justify-center"
            style={{ background: "var(--togo-green)" }}
          >
            <Bot className="w-6 h-6 text-white" />
          </div>
          <div>
            <p className="text-gray-500 text-sm mb-4">Ask anything about Togo — laws, economy, education, news.</p>
            <div className="grid gap-2">
              {SUGGESTED.map((q) => (
                <button
                  key={q}
                  onClick={() => send(q)}
                  className="text-left text-sm px-4 py-2.5 rounded-lg border border-gray-200 bg-white hover:bg-gray-50 transition-colors text-gray-700"
                >
                  {q}
                </button>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Messages */}
      {messages.length > 0 && (
        <div className="flex-1 space-y-6 mb-6">
          {messages.map((m, i) => (
            <div key={i} className={`flex gap-3 ${m.role === "user" ? "justify-end" : ""}`}>
              {m.role === "assistant" && (
                <div
                  className="w-7 h-7 rounded-full flex-shrink-0 flex items-center justify-center mt-0.5"
                  style={{ background: "var(--togo-green)" }}
                >
                  <Bot className="w-4 h-4 text-white" />
                </div>
              )}
              <div className={`max-w-[85%] ${m.role === "user" ? "order-first" : ""}`}>
                <div
                  className={`rounded-xl px-4 py-3 text-sm leading-relaxed ${
                    m.role === "user"
                      ? "text-white"
                      : "bg-white border border-gray-200 text-gray-800"
                  }`}
                  style={m.role === "user" ? { background: "var(--togo-green)" } : {}}
                >
                  {m.content}
                </div>

                {/* Sources */}
                {m.sources && m.sources.length > 0 && (
                  <div className="mt-2 space-y-1">
                    {m.sources.slice(0, 3).map((s, j) => (
                      <div key={j} className="flex items-center gap-1.5 text-xs text-gray-400">
                        <span className="text-gray-300">↳</span>
                        {s.url ? (
                          <a
                            href={s.url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="hover:text-gray-600 transition-colors flex items-center gap-1"
                          >
                            {s.title || s.url}
                            <ExternalLink className="w-3 h-3" />
                          </a>
                        ) : (
                          <span>{s.title}</span>
                        )}
                        <span className="text-gray-300">·</span>
                        <span>{(s.score * 100).toFixed(0)}%</span>
                      </div>
                    ))}
                    {m.latency_ms && (
                      <p className="text-xs text-gray-300 mt-1">{m.latency_ms}ms</p>
                    )}
                  </div>
                )}
              </div>
              {m.role === "user" && (
                <div className="w-7 h-7 rounded-full bg-gray-200 flex-shrink-0 flex items-center justify-center mt-0.5">
                  <User className="w-4 h-4 text-gray-500" />
                </div>
              )}
            </div>
          ))}

          {loading && (
            <div className="flex gap-3">
              <div
                className="w-7 h-7 rounded-full flex-shrink-0 flex items-center justify-center"
                style={{ background: "var(--togo-green)" }}
              >
                <Bot className="w-4 h-4 text-white" />
              </div>
              <div className="bg-white border border-gray-200 rounded-xl px-4 py-3">
                <Loader2 className="w-4 h-4 animate-spin text-gray-400" />
              </div>
            </div>
          )}
          <div ref={bottomRef} />
        </div>
      )}

      {/* Input */}
      <form
        onSubmit={(e) => { e.preventDefault(); send(input); }}
        className="flex gap-2 sticky bottom-4"
      >
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask about Togolese laws, economy, education…"
          className="flex-1 px-4 py-3 border border-gray-200 rounded-xl text-sm bg-white focus:outline-none focus:ring-2 focus:ring-green-600/30 focus:border-green-600 shadow-sm"
        />
        <button
          type="submit"
          disabled={loading || !input.trim()}
          className="px-4 py-3 rounded-xl text-white disabled:opacity-50 transition-opacity hover:opacity-90 shadow-sm"
          style={{ background: "var(--togo-green)" }}
        >
          <Send className="w-4 h-4" />
        </button>
      </form>
    </div>
  );
}
