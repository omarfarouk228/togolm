import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import { LanguageProvider } from "@/contexts/language";
import { Navbar } from "@/components/navbar";
import { Analytics } from "@/components/analytics";
import "./globals.css";

const geistSans = Geist({ variable: "--font-geist-sans", subsets: ["latin"] });
const geistMono = Geist_Mono({ variable: "--font-geist-mono", subsets: ["latin"] });

const siteUrl = process.env.NEXT_PUBLIC_SITE_URL ?? "https://togolm.ai";

export const metadata: Metadata = {
  metadataBase: new URL(siteUrl),
  title: {
    default: "TogoLM — AI pour le Togo",
    template: "%s | TogoLM",
  },
  description:
    "La première infrastructure IA open-source centrée sur le Togo. Corpus de documents officiels, recherche sémantique et assistant IA pour les connaissances togolaises.",
  keywords: [
    "Togo",
    "intelligence artificielle",
    "IA",
    "corpus",
    "documents officiels",
    "droit togolais",
    "administration",
    "TogoLM",
    "recherche sémantique",
    "RAG",
  ],
  authors: [{ name: "TogoLM" }],
  creator: "TogoLM",
  openGraph: {
    type: "website",
    locale: "fr_TG",
    alternateLocale: "en_US",
    url: siteUrl,
    siteName: "TogoLM",
    title: "TogoLM — AI pour le Togo",
    description:
      "La première infrastructure IA open-source centrée sur le Togo. Corpus de documents officiels et assistant IA.",
  },
  twitter: {
    card: "summary_large_image",
    title: "TogoLM — AI pour le Togo",
    description:
      "La première infrastructure IA open-source centrée sur le Togo.",
  },
  robots: {
    index: true,
    follow: true,
    googleBot: {
      index: true,
      follow: true,
      "max-video-preview": -1,
      "max-image-preview": "large",
      "max-snippet": -1,
    },
  },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="fr" className={`${geistSans.variable} ${geistMono.variable}`}>
      <body className="min-h-screen flex flex-col bg-[#f8fafc] text-slate-900 antialiased">
        <Analytics />
        <LanguageProvider>
          <Navbar />
          <main className="flex-1 pt-14">{children}</main>
          <Footer />
        </LanguageProvider>
      </body>
    </html>
  );
}

function Footer() {
  return (
    <footer className="border-t border-slate-200 bg-white/60 backdrop-blur-sm py-5">
      <div className="max-w-5xl mx-auto px-4 flex items-center justify-between text-xs text-slate-400">
        <span>TogoLM — Open-source AI for Togo</span>
        <span>MIT License</span>
      </div>
    </footer>
  );
}
