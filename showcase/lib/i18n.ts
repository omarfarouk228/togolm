export type Lang = "fr" | "en";

export const translations = {
  fr: {
    nav: {
      corpus: "Corpus",
      search: "Recherche",
      askAI: "Poser une question",
      tryFree: "Essayer",
      api: "API",
    },
    home: {
      tagline: "L'IA pour le Togo.",
      description:
        "La première infrastructure IA open-source dédiée au Togo — construite à partir des lois, données gouvernementales, presse et documents éducatifs officiels.",
      askBtn: "Poser une question",
      searchBtn: "Parcourir le corpus",
      stats: {
        documents: "Documents",
        chunks: "Fragments",
        sources: "Sources",
        languages: "Langues",
      },
      features: [
        {
          emoji: "🔍",
          title: "Recherche sémantique",
          desc: "Recherchez parmi des milliers de documents publics togolais par similarité vectorielle — pas seulement par mots-clés.",
        },
        {
          emoji: "🤖",
          title: "Questions & Réponses RAG",
          desc: "Posez des questions complexes en français. Obtenez des réponses précises avec citations de sources officielles.",
        },
        {
          emoji: "🇹🇬",
          title: "Conçu pour le Togo",
          desc: "Lois, budgets, décrets éducatifs, données agricoles — un corpus bâti sur des sources officielles togolaises.",
        },
      ],
      offline: "API hors ligne — démarrer avec",
    },
    corpus: {
      title: "Corpus",
      subtitle: (n: number | string) =>
        `Parcourir les ${typeof n === "number" ? n.toLocaleString() : n} documents indexés dans le corpus TogoLM.`,
      all: "Tous",
      allSources: "Toutes les sources",
      filteringBy: "Filtrer par :",
      clear: "Effacer",
      noDocuments: "Aucun document trouvé pour ce filtre.",
      words: "mots",
      chunks: "fragments",
      previous: "Précédent",
      next: "Suivant",
      page: (current: number, total: number) => `Page ${current} / ${total}`,
      docs: "docs",
      error:
        "Impossible d'atteindre l'API — démarrer avec : uv run uvicorn api.app.main:app --port 8000",
      untitled: "Sans titre",
    },
    search: {
      title: "Recherche",
      subtitle: "Recherche plein texte dans le corpus de documents publics togolais.",
      placeholder: "budget 2024, loi fiscale, recrutement enseignants…",
      searchBtn: "Rechercher",
      results: (n: number, q: string) =>
        `${n} résultat${n !== 1 ? "s" : ""} pour « ${q} »`,
      noResults: "Aucun résultat trouvé",
      noResultsHint: "Essayez un terme différent ou une requête plus large",
      initialHint: "Saisissez une requête pour chercher dans le corpus",
      error: "Recherche échouée — l'API est-elle démarrée ?",
      match: "correspondance",
    },
    chat: {
      title: "Interroger TogoLM",
      subtitle:
        "Posez n'importe quelle question sur le Togo — lois, économie, éducation, gouvernement. Les réponses s'appuient sur des documents officiels togolais.",
      placeholder: "Posez une question sur les lois, l'économie, l'éducation…",
      sources: "Sources",
      error: "Erreur de connexion à l'API. Est-elle démarrée ?",
      suggested: [
        { emoji: "⚖️", text: "Quelles sont les procédures pour créer une entreprise au Togo ?" },
        { emoji: "👷", text: "Quels sont les droits des travailleurs selon le code du travail togolais ?" },
        { emoji: "🎓", text: "Comment fonctionne le système éducatif au Togo ?" },
        { emoji: "💰", text: "Quel est le budget de l'État togolais ?" },
      ],
    },
    categories: {
      administrative: "Administratif",
      legal: "Juridique",
      education: "Éducation",
      economy: "Économie",
      agriculture: "Agriculture",
      health: "Santé",
      politics: "Politique",
      press: "Presse",
    },
  },

  en: {
    nav: {
      corpus: "Corpus",
      search: "Search",
      askAI: "Ask AI",
      tryFree: "Try it free",
      api: "API",
    },
    home: {
      tagline: "AI for Togo.",
      description:
        "The first open-source AI infrastructure focused on Togo — built on public laws, government data, press, and education documents.",
      askBtn: "Ask a question",
      searchBtn: "Search corpus",
      stats: {
        documents: "Documents",
        chunks: "Chunks",
        sources: "Sources",
        languages: "Languages",
      },
      features: [
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
      ],
      offline: "API offline — start with",
    },
    corpus: {
      title: "Corpus",
      subtitle: (n: number | string) =>
        `Browse all ${typeof n === "number" ? n.toLocaleString() : n} documents indexed in the TogoLM corpus.`,
      all: "All",
      allSources: "All sources",
      filteringBy: "Filtering by:",
      clear: "Clear",
      noDocuments: "No documents found for this filter.",
      words: "words",
      chunks: "chunks",
      previous: "Previous",
      next: "Next",
      page: (current: number, total: number) => `Page ${current} / ${total}`,
      docs: "docs",
      error:
        "Cannot reach the API — start with: uv run uvicorn api.app.main:app --port 8000",
      untitled: "Untitled",
    },
    search: {
      title: "Search",
      subtitle: "Full-text search across the Togolese public document corpus.",
      placeholder: "budget 2024, tax law, teacher recruitment…",
      searchBtn: "Search",
      results: (n: number, q: string) =>
        `${n} result${n !== 1 ? "s" : ""} for "${q}"`,
      noResults: "No results found",
      noResultsHint: "Try a different search term or a broader query",
      initialHint: "Type a query above to search the corpus",
      error: "Search failed — is the API running?",
      match: "match",
    },
    chat: {
      title: "Ask TogoLM",
      subtitle:
        "Ask anything about Togo — laws, economy, education, government. Answers are grounded in official Togolese documents.",
      placeholder: "Ask about Togolese laws, economy, education…",
      sources: "Sources",
      error: "Connection error. Is the API running?",
      suggested: [
        { emoji: "⚖️", text: "What are the procedures to register a business in Togo?" },
        { emoji: "👷", text: "What are workers' rights under the Togolese labor code?" },
        { emoji: "🎓", text: "How does the education system work in Togo?" },
        { emoji: "💰", text: "What is the Togolese state budget?" },
      ],
    },
    categories: {
      administrative: "Administrative",
      legal: "Legal",
      education: "Education",
      economy: "Economy",
      agriculture: "Agriculture",
      health: "Health",
      politics: "Politics",
      press: "Press",
    },
  },
} as const;

export type Translations = (typeof translations)[Lang];
