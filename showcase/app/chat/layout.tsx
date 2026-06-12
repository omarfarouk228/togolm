import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Assistant IA",
  description:
    "Posez vos questions sur le Togo à TogoLM — législation, démarches administratives, économie et plus.",
};

export default function ChatLayout({ children }: { children: React.ReactNode }) {
  return children;
}
