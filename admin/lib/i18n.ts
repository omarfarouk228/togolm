"use client";

import { useState, useEffect, useCallback } from "react";

const LANG_KEY = "togolm_admin_lang";

export type Lang = "en" | "fr";

const translations: Record<string, Record<Lang, string>> = {
  // Nav
  "nav.dashboard": { en: "Dashboard", fr: "Tableau de bord" },
  "nav.corpus": { en: "Corpus", fr: "Corpus" },
  "nav.apiKeys": { en: "API Keys", fr: "Clés API" },
  "nav.queries": { en: "Queries", fr: "Requêtes" },
  "nav.health": { en: "Health", fr: "Santé" },
  "nav.logout": { en: "Logout", fr: "Déconnexion" },

  // Login
  "login.title": { en: "TogoLM Admin", fr: "TogoLM Admin" },
  "login.subtitle": { en: "Sign in to your account", fr: "Connectez-vous à votre compte" },
  "login.password": { en: "Admin Password", fr: "Mot de passe admin" },
  "login.passwordPlaceholder": { en: "Enter your password", fr: "Entrez votre mot de passe" },
  "login.submit": { en: "Sign In", fr: "Se connecter" },
  "login.signing": { en: "Signing in…", fr: "Connexion…" },
  "login.error": { en: "Invalid credentials", fr: "Identifiants invalides" },

  // Dashboard
  "dashboard.title": { en: "Dashboard", fr: "Tableau de bord" },
  "dashboard.totalDocs": { en: "Total Documents", fr: "Documents totaux" },
  "dashboard.totalChunks": { en: "Total Chunks", fr: "Chunks totaux" },
  "dashboard.requestsToday": { en: "Requests Today", fr: "Requêtes aujourd'hui" },
  "dashboard.embeddingCoverage": { en: "Embedding Coverage", fr: "Couverture embeddings" },
  "dashboard.activityChart": { en: "Activity (last 7 days)", fr: "Activité (7 derniers jours)" },
  "dashboard.requests": { en: "Requests", fr: "Requêtes" },
  "dashboard.rateLimitHits": { en: "Rate limit hits", fr: "Limites atteintes" },

  // Corpus
  "corpus.title": { en: "Corpus", fr: "Corpus" },
  "corpus.byCategory": { en: "By Category", fr: "Par catégorie" },
  "corpus.byLanguage": { en: "By Language", fr: "Par langue" },
  "corpus.sources": { en: "Sources", fr: "Sources" },
  "corpus.source": { en: "Source", fr: "Source" },
  "corpus.category": { en: "Category", fr: "Catégorie" },
  "corpus.docCount": { en: "Documents", fr: "Documents" },
  "corpus.lastCollected": { en: "Last Collected", fr: "Dernière collecte" },
  "corpus.recentDocuments": { en: "Recent Documents", fr: "Documents récents" },
  "corpus.documentId": { en: "Document ID", fr: "ID Document" },
  "corpus.title2": { en: "Title", fr: "Titre" },
  "corpus.language": { en: "Language", fr: "Langue" },
  "corpus.date": { en: "Date", fr: "Date" },
  "corpus.totalDocs": { en: "Total Documents", fr: "Documents totaux" },
  "corpus.totalChunks": { en: "Total Chunks", fr: "Chunks totaux" },
  "corpus.languages": { en: "Languages", fr: "Langues" },
  "corpus.categories": { en: "Categories", fr: "Catégories" },
  "corpus.documents": { en: "documents", fr: "documents" },

  // Keys
  "keys.title": { en: "API Keys", fr: "Clés API" },
  "keys.create": { en: "Create Key", fr: "Créer une clé" },
  "keys.name": { en: "Name", fr: "Nom" },
  "keys.email": { en: "Email", fr: "Email" },
  "keys.plan": { en: "Plan", fr: "Plan" },
  "keys.useCase": { en: "Use Case", fr: "Cas d'usage" },
  "keys.active": { en: "Active", fr: "Actif" },
  "keys.created": { en: "Created", fr: "Créé" },
  "keys.actions": { en: "Actions", fr: "Actions" },
  "keys.delete": { en: "Delete", fr: "Supprimer" },
  "keys.cancel": { en: "Cancel", fr: "Annuler" },
  "keys.save": { en: "Save", fr: "Enregistrer" },
  "keys.creating": { en: "Creating…", fr: "Création…" },
  "keys.planFree": { en: "Free", fr: "Gratuit" },
  "keys.planDev": { en: "Developer", fr: "Développeur" },
  "keys.planInstitution": { en: "Institution", fr: "Institution" },
  "keys.confirmDelete": { en: "Delete API Key?", fr: "Supprimer la clé API ?" },
  "keys.confirmDeleteMsg": {
    en: "This action cannot be undone. The key will be permanently removed.",
    fr: "Cette action est irréversible. La clé sera définitivement supprimée.",
  },
  "keys.noKeys": { en: "No API keys yet. Create one above.", fr: "Aucune clé API. Créez-en une ci-dessus." },

  // Queries
  "queries.title": { en: "Query History", fr: "Historique des requêtes" },
  "queries.question": { en: "Question", fr: "Question" },
  "queries.offTopic": { en: "Off Topic", fr: "Hors sujet" },
  "queries.offTopicFilter": { en: "Show off-topic only", fr: "Afficher hors sujet uniquement" },
  "queries.chunksFound": { en: "Chunks", fr: "Chunks" },
  "queries.latency": { en: "Latency (ms)", fr: "Latence (ms)" },
  "queries.date": { en: "Date", fr: "Date" },
  "queries.total": { en: "Total Queries", fr: "Requêtes totales" },
  "queries.offTopicRate": { en: "Off-topic Rate", fr: "Taux hors sujet" },
  "queries.avgLatency": { en: "Avg Latency", fr: "Latence moy." },
  "queries.previous": { en: "Previous", fr: "Précédent" },
  "queries.next": { en: "Next", fr: "Suivant" },
  "queries.page": { en: "Page", fr: "Page" },
  "queries.yes": { en: "Yes", fr: "Oui" },
  "queries.no": { en: "No", fr: "Non" },

  // Health
  "health.title": { en: "System Health", fr: "Santé du système" },
  "health.database": { en: "Database", fr: "Base de données" },
  "health.redis": { en: "Redis", fr: "Redis" },
  "health.status": { en: "Status", fr: "Statut" },
  "health.ok": { en: "OK", fr: "OK" },
  "health.error": { en: "Error", fr: "Erreur" },
  "health.embeddingCoverage": { en: "Embedding Coverage", fr: "Couverture embeddings" },
  "health.chunksWithEmbeddings": { en: "Chunks with embeddings", fr: "Chunks avec embeddings" },
  "health.responseTime": { en: "Response time", fr: "Temps de réponse" },
  "health.details": { en: "Details", fr: "Détails" },

  // Common
  "common.loading": { en: "Loading…", fr: "Chargement…" },
  "nav.logoutConfirm": { en: "Sign out?", fr: "Se déconnecter ?" },
  "nav.logoutConfirmMsg": { en: "You will be redirected to the login page.", fr: "Vous serez redirigé vers la page de connexion." },
  "common.error": { en: "Error loading data", fr: "Erreur de chargement" },
  "common.retry": { en: "Retry", fr: "Réessayer" },
  "common.confirm": { en: "Confirm", fr: "Confirmer" },
  "common.cancel": { en: "Cancel", fr: "Annuler" },
  "common.noData": { en: "No data available", fr: "Aucune donnée disponible" },
  "common.ms": { en: "ms", fr: "ms" },
};

export function getLang(): Lang {
  if (typeof window === "undefined") return "en";
  return (localStorage.getItem(LANG_KEY) as Lang) ?? "en";
}

export function setLang(lang: Lang): void {
  localStorage.setItem(LANG_KEY, lang);
}

export function translate(key: string, lang: Lang): string {
  return translations[key]?.[lang] ?? key;
}

export function useT() {
  const [lang, setLangState] = useState<Lang>("en");

  useEffect(() => {
    setLangState(getLang());
  }, []);

  const toggleLang = useCallback(() => {
    const next: Lang = lang === "en" ? "fr" : "en";
    setLang(next);
    setLangState(next);
  }, [lang]);

  const changeLang = useCallback((next: Lang) => {
    setLang(next);
    setLangState(next);
  }, []);

  const t = useCallback(
    (key: string) => translate(key, lang),
    [lang]
  );

  return { t, lang, toggleLang, setLang: changeLang };
}
