import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "API",
  description:
    "Documentation de l'API TogoLM — accès programmatique au corpus, à la recherche sémantique et au RAG.",
};

export default function DevelopersLayout({ children }: { children: React.ReactNode }) {
  return children;
}
