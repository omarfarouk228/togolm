"use client";

import Link from "next/link";
import { useLanguage } from "@/contexts/language";

export function RateLimitBanner() {
  const { lang } = useLanguage();

  return (
    <div className="rounded-xl border border-amber-200 bg-amber-50 px-5 py-4 flex flex-col sm:flex-row sm:items-center gap-3">
      <div className="flex-1">
        <p className="text-sm font-semibold text-amber-800 mb-0.5">
          {lang === "fr" ? "Limite de 20 requêtes/jour atteinte" : "20 requests/day limit reached"}
        </p>
        <p className="text-xs text-amber-700 leading-relaxed">
          {lang === "fr"
            ? "Les visiteurs sans clé API sont limités à 20 requêtes par jour. Obtenez une clé gratuite pour 200 requêtes/jour."
            : "Anonymous visitors are limited to 20 requests per day. Get a free key for 200 requests/day."}
        </p>
      </div>
      <Link
        href="/developers"
        className="flex-shrink-0 inline-flex items-center px-4 py-2 rounded-lg text-white text-xs font-semibold hover:opacity-90 transition-opacity"
        style={{ background: "var(--togo-green)" }}
      >
        {lang === "fr" ? "Obtenir une clé" : "Get a free key"} →
      </Link>
    </div>
  );
}
