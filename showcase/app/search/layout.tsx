import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Recherche",
  description:
    "Recherche sémantique dans le corpus TogoLM — trouvez des documents officiels togolais par pertinence.",
};

export default function SearchLayout({ children }: { children: React.ReactNode }) {
  return children;
}
