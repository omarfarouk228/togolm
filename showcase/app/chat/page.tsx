"use client";

import { useState, useRef, useEffect } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { queryRAGStream, type QuerySource, type HistoryMessage } from "@/lib/api";
import { Send, ExternalLink, Bot, User } from "lucide-react";
import { useLanguage } from "@/contexts/language";
import { RateLimitBanner } from "@/components/rate-limit-banner";

const API_KEY_STORAGE = "togolm-api-key";

interface Message {
  role: "user" | "assistant";
  content: string;
  sources?: QuerySource[];
  latency_ms?: number;
  streaming?: boolean;
}

function StreamingCursor() {
  return (
    <span
      className="inline-block w-0.5 h-3.5 ml-0.5 align-middle rounded-full animate-pulse"
      style={{ background: "var(--togo-green)" }}
    />
  );
}

export default function ChatPage() {
  const { t, lang } = useLanguage();
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [rateLimited, setRateLimited] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  async function send(question: string) {
    if (!question.trim() || loading) return;
    const q = question.trim();
    setInput("");
    setRateLimited(false);

    // Capture completed history before adding the new exchange to state
    const history: HistoryMessage[] = messages
      .filter((m) => m.content && !m.streaming)
      .slice(-6)
      .map((m) => ({ role: m.role, content: m.content }));

    setMessages((prev) => [
      ...prev,
      { role: "user", content: q },
      { role: "assistant", content: "", streaming: true },
    ]);
    setLoading(true);

    const ctrl = new AbortController();
    abortRef.current = ctrl;

    const apiKey = localStorage.getItem(API_KEY_STORAGE) || undefined;

    try {
      for await (const event of queryRAGStream(q, ctrl.signal, apiKey, history)) {
        if (event.type === "chunk") {
          setMessages((prev) => {
            const last = prev[prev.length - 1];
            if (last?.role === "assistant") {
              return [
                ...prev.slice(0, -1),
                { ...last, content: last.content + event.text },
              ];
            }
            return prev;
          });
        } else if (event.type === "sources") {
          setMessages((prev) => {
            const last = prev[prev.length - 1];
            if (last?.role === "assistant") {
              return [
                ...prev.slice(0, -1),
                {
                  ...last,
                  sources: event.sources,
                  latency_ms: event.latency_ms,
                  streaming: false,
                },
              ];
            }
            return prev;
          });
        } else if (event.type === "error") {
          throw new Error(event.message);
        }
      }
    } catch (err: unknown) {
      if (err instanceof Error && err.name === "AbortError") return;
      const msg = err instanceof Error ? err.message : "";
      if (msg === "rate_limited") {
        setRateLimited(true);
        setMessages((prev) => {
          const last = prev[prev.length - 1];
          if (last?.role === "assistant" && last.streaming) {
            return [
              ...prev.slice(0, -1),
              {
                role: "assistant",
                content: lang === "fr"
                  ? "Limite de requêtes atteinte. Obtenez une clé API pour continuer."
                  : "Rate limit reached. Get an API key to continue.",
              },
            ];
          }
          return prev;
        });
      } else {
        setMessages((prev) => {
          const last = prev[prev.length - 1];
          if (last?.role === "assistant" && last.streaming) {
            return [
              ...prev.slice(0, -1),
              { role: "assistant", content: t.chat.error },
            ];
          }
          return prev;
        });
      }
    } finally {
      setLoading(false);
      setMessages((prev) => {
        const last = prev[prev.length - 1];
        if (last?.role === "assistant" && last.streaming) {
          return [...prev.slice(0, -1), { ...last, streaming: false }];
        }
        return prev;
      });
      setTimeout(() => inputRef.current?.focus(), 50);
    }
  }

  return (
    <div className="max-w-3xl mx-auto px-4 py-8 flex flex-col" style={{ minHeight: "calc(100vh - 112px)" }}>

      {/* Empty state */}
      {messages.length === 0 && (
        <div className="flex-1 flex flex-col items-center justify-center gap-8 animate-fade-in-up">
          <div className="text-center">
            <div
              className="w-14 h-14 rounded-2xl flex items-center justify-center mx-auto mb-5 glow-green"
              style={{ background: "var(--togo-green)" }}
            >
              <Bot className="w-7 h-7 text-white" />
            </div>
            <h1 className="text-2xl font-bold text-slate-900 mb-2">{t.chat.title}</h1>
            <p className="text-slate-500 text-sm max-w-sm mx-auto leading-relaxed">
              {t.chat.subtitle}
            </p>
          </div>

          <div className="grid sm:grid-cols-2 gap-3 w-full max-w-xl stagger">
            {t.chat.suggested.map(({ emoji, text }) => (
              <button
                key={text}
                onClick={() => send(text)}
                className="text-left p-4 rounded-2xl border border-slate-200 bg-white hover:border-slate-300 hover:bg-slate-50 transition-all card-hover group animate-fade-in-up"
              >
                <span className="text-xl mb-2 block">{emoji}</span>
                <span className="text-sm text-slate-600 group-hover:text-slate-900 transition-colors leading-snug">
                  {text}
                </span>
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Messages */}
      {messages.length > 0 && (
        <div className="flex-1 space-y-6 mb-6">
          {messages.map((m, i) => (
            <div
              key={i}
              className={`flex gap-3 animate-fade-in-up ${m.role === "user" ? "justify-end" : ""}`}
            >
              {m.role === "assistant" && (
                <div
                  className="w-7 h-7 rounded-full flex-shrink-0 flex items-center justify-center mt-1"
                  style={{ background: "var(--togo-green)" }}
                >
                  <Bot className="w-4 h-4 text-white" />
                </div>
              )}

              <div className={`max-w-[82%] ${m.role === "user" ? "order-first" : ""}`}>
                {m.role === "assistant" && m.streaming && m.content === "" ? (
                  <div className="bg-white border border-slate-200 rounded-2xl rounded-bl-md px-4 py-3.5 flex items-center gap-1.5 shadow-sm">
                    <span className="typing-dot w-1.5 h-1.5 rounded-full bg-slate-400" />
                    <span className="typing-dot w-1.5 h-1.5 rounded-full bg-slate-400" />
                    <span className="typing-dot w-1.5 h-1.5 rounded-full bg-slate-400" />
                  </div>
                ) : (
                  <div
                    className={`rounded-2xl px-4 py-3 text-sm leading-relaxed ${
                      m.role === "user"
                        ? "text-white rounded-br-md"
                        : "bg-white border border-slate-200 text-slate-800 rounded-bl-md shadow-sm"
                    }`}
                    style={m.role === "user" ? { background: "var(--togo-green)" } : {}}
                  >
                    {m.role === "user" ? (
                      m.content
                    ) : (
                      <div className="prose prose-sm prose-slate max-w-none
                        prose-p:my-1 prose-p:leading-relaxed
                        prose-ul:my-1 prose-ul:pl-4
                        prose-ol:my-1 prose-ol:pl-4
                        prose-li:my-0.5
                        prose-strong:font-semibold prose-strong:text-slate-900
                        prose-a:text-green-700 prose-a:no-underline hover:prose-a:underline
                        prose-headings:font-semibold prose-headings:text-slate-900 prose-headings:mt-3 prose-headings:mb-1
                        prose-code:text-xs prose-code:bg-slate-100 prose-code:px-1 prose-code:rounded">
                        <ReactMarkdown remarkPlugins={[remarkGfm]}>
                          {m.content}
                        </ReactMarkdown>
                        {m.streaming && <StreamingCursor />}
                      </div>
                    )}
                  </div>
                )}

                {m.sources && m.sources.length > 0 && (
                  <div className="mt-2 space-y-1 pl-1">
                    <p className="text-xs text-slate-400 font-medium mb-1.5">{t.chat.sources}</p>
                    {m.sources.slice(0, 3).map((s, j) => (
                      <div key={j} className="flex items-center gap-1.5 text-xs text-slate-400">
                        <span className="text-slate-300">↳</span>
                        {s.url ? (
                          <a
                            href={s.url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="hover:text-slate-700 transition-colors flex items-center gap-1 truncate max-w-[160px] sm:max-w-[220px]"
                          >
                            {s.title || s.url}
                            <ExternalLink className="w-3 h-3 flex-shrink-0" />
                          </a>
                        ) : (
                          <span className="truncate max-w-[160px] sm:max-w-[220px]">{s.title}</span>
                        )}
                      </div>
                    ))}
                    {m.latency_ms !== undefined && (
                      <p className="text-xs text-slate-300 mt-1.5 tabular-nums">{m.latency_ms}ms</p>
                    )}
                  </div>
                )}
              </div>

              {m.role === "user" && (
                <div className="w-7 h-7 rounded-full bg-slate-200 flex-shrink-0 flex items-center justify-center mt-1">
                  <User className="w-4 h-4 text-slate-500" />
                </div>
              )}
            </div>
          ))}

          <div ref={bottomRef} />
        </div>
      )}

      {/* Sticky input area */}
      <div className="sticky bottom-4 space-y-2">
        {rateLimited && <RateLimitBanner />}
        <form
          onSubmit={(e) => { e.preventDefault(); send(input); }}
          className="flex gap-2 items-end"
        >
          <div className="flex-1 relative">
            <textarea
              ref={inputRef}
              value={input}
              onChange={(e) => setInput(e.target.value.slice(0, 4000))}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(input); }
              }}
              placeholder={t.chat.placeholder}
              rows={1}
              className="w-full px-4 py-3.5 border border-slate-200 rounded-2xl text-sm bg-white focus:outline-none focus:ring-2 focus:ring-green-800/25 focus:border-green-800/50 shadow-sm transition-all resize-none overflow-hidden"
              style={{ minHeight: "52px", maxHeight: "200px", overflowY: input.length > 200 ? "auto" : "hidden" }}
            />
            {input.length > 3600 && (
              <span className="absolute bottom-1.5 right-3 text-xs text-slate-400 pointer-events-none">
                {input.length}/4000
              </span>
            )}
          </div>
          <button
            type="submit"
            disabled={loading || !input.trim()}
            className="px-4 py-3.5 rounded-2xl text-white disabled:opacity-40 transition-opacity hover:opacity-90 shadow-sm shrink-0"
            style={{ background: "var(--togo-green)" }}
          >
            <Send className="w-4 h-4" />
          </button>
        </form>
      </div>
    </div>
  );
}
