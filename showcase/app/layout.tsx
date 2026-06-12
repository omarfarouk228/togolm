import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import { LanguageProvider } from "@/contexts/language";
import { Navbar } from "@/components/navbar";
import "./globals.css";

const geistSans = Geist({ variable: "--font-geist-sans", subsets: ["latin"] });
const geistMono = Geist_Mono({ variable: "--font-geist-mono", subsets: ["latin"] });

export const metadata: Metadata = {
  title: "TogoLM — AI for Togo",
  description: "The first open-source AI infrastructure focused on Togo",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="fr" className={`${geistSans.variable} ${geistMono.variable}`}>
      <body className="min-h-screen flex flex-col bg-[#f8fafc] text-slate-900 antialiased">
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
