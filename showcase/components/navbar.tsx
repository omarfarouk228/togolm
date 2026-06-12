"use client";

import Link from "next/link";
import { useLanguage } from "@/contexts/language";

export function Navbar() {
  const { lang, t, toggle } = useLanguage();

  return (
    <header className="fixed top-0 inset-x-0 z-50 h-14">
      <div className="absolute inset-0 bg-white/80 backdrop-blur-md border-b border-slate-200/60" />
      <div className="relative max-w-5xl mx-auto px-4 h-full flex items-center gap-4">
        {/* Logo */}
        <Link href="/" className="flex items-center gap-2 flex-shrink-0">
          <div className="flex gap-0.5">
            <span className="w-1.5 h-5 rounded-full" style={{ background: "var(--togo-green)" }} />
            <span className="w-1.5 h-5 rounded-full" style={{ background: "var(--togo-yellow)" }} />
            <span className="w-1.5 h-5 rounded-full" style={{ background: "var(--togo-red)" }} />
          </div>
          <span className="font-bold text-base tracking-tight" style={{ color: "var(--togo-green)" }}>
            TogoLM
          </span>
        </Link>

        {/* Nav links */}
        <nav className="hidden sm:flex gap-1 text-sm">
          {[
            { href: "/corpus",     label: t.nav.corpus },
            { href: "/search",     label: t.nav.search },
            { href: "/chat",       label: t.nav.askAI },
            { href: "/developers", label: t.nav.api },
          ].map(({ href, label }) => (
            <Link
              key={href}
              href={href}
              className="px-3 py-1.5 rounded-lg text-slate-600 hover:text-slate-900 hover:bg-slate-100 transition-all duration-150"
            >
              {label}
            </Link>
          ))}
        </nav>

        {/* Right */}
        <div className="ml-auto flex items-center gap-2 sm:gap-3">
          {/* Language toggle */}
          <button
            onClick={toggle}
            aria-label="Switch language"
            className="flex items-center gap-0.5 text-xs font-semibold rounded-lg border border-slate-200 overflow-hidden"
          >
            <span
              className={`px-2.5 py-1.5 transition-colors ${
                lang === "fr"
                  ? "text-white"
                  : "text-slate-400 hover:text-slate-700"
              }`}
              style={lang === "fr" ? { background: "var(--togo-green)" } : {}}
            >
              FR
            </span>
            <span
              className={`px-2.5 py-1.5 transition-colors ${
                lang === "en"
                  ? "text-white"
                  : "text-slate-400 hover:text-slate-700"
              }`}
              style={lang === "en" ? { background: "var(--togo-green)" } : {}}
            >
              EN
            </span>
          </button>

          <a
            href="https://github.com/omarfarouk228/togolm"
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-1.5 text-xs text-slate-500 hover:text-slate-900 transition-colors"
            aria-label="GitHub"
          >
            <svg className="w-4 h-4 flex-shrink-0" fill="currentColor" viewBox="0 0 24 24">
              <path d="M12 2C6.477 2 2 6.484 2 12.017c0 4.425 2.865 8.18 6.839 9.504.5.092.682-.217.682-.483 0-.237-.008-.868-.013-1.703-2.782.605-3.369-1.343-3.369-1.343-.454-1.158-1.11-1.466-1.11-1.466-.908-.62.069-.608.069-.608 1.003.07 1.531 1.032 1.531 1.032.892 1.53 2.341 1.088 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.113-4.555-4.951 0-1.093.39-1.988 1.029-2.688-.103-.253-.446-1.272.098-2.65 0 0 .84-.27 2.75 1.026A9.564 9.564 0 0112 6.844c.85.004 1.705.115 2.504.337 1.909-1.296 2.747-1.027 2.747-1.027.546 1.379.202 2.398.1 2.651.64.7 1.028 1.595 1.028 2.688 0 3.848-2.339 4.695-4.566 4.943.359.309.678.92.678 1.855 0 1.338-.012 2.419-.012 2.747 0 .268.18.58.688.482A10.019 10.019 0 0022 12.017C22 6.484 17.522 2 12 2z" />
            </svg>
            <span className="hidden sm:inline">GitHub</span>
          </a>

          <Link
            href="/chat"
            className="px-3 py-1.5 rounded-lg text-white text-xs font-medium transition-opacity hover:opacity-90 flex-shrink-0"
            style={{ background: "var(--togo-green)" }}
          >
            {t.nav.tryFree}
          </Link>
        </div>
      </div>
    </header>
  );
}
