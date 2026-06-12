import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Corpus",
  description:
    "Explorez les documents officiels du corpus TogoLM — textes législatifs, administratifs, éducatifs et économiques du Togo.",
};

export default function CorpusLayout({ children }: { children: React.ReactNode }) {
  return children;
}
