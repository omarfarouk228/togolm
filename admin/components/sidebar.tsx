"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import {
  LayoutDashboard,
  Database,
  Key,
  MessageSquare,
  HeartPulse,
  LogOut,
  Globe,
} from "lucide-react";
import { removeToken } from "@/lib/auth";
import { useT } from "@/lib/i18n";

const navItems = [
  { href: "/", labelKey: "nav.dashboard", icon: LayoutDashboard },
  { href: "/corpus", labelKey: "nav.corpus", icon: Database },
  { href: "/keys", labelKey: "nav.apiKeys", icon: Key },
  { href: "/queries", labelKey: "nav.queries", icon: MessageSquare },
  { href: "/health", labelKey: "nav.health", icon: HeartPulse },
];

export function Sidebar() {
  const pathname = usePathname();
  const router = useRouter();
  const { t, lang, toggleLang } = useT();

  function handleLogout() {
    removeToken();
    router.push("/login");
  }

  return (
    <aside className="flex flex-col h-screen w-56 bg-sidebar text-white shrink-0">
      {/* Logo */}
      <div className="px-5 py-6 border-b border-white/10">
        <span className="text-lg font-bold tracking-tight text-white">
          TogoLM{" "}
          <span className="text-green-400 font-normal">Admin</span>
        </span>
      </div>

      {/* Nav */}
      <nav className="flex-1 py-4 overflow-y-auto">
        <ul className="space-y-0.5 px-3">
          {navItems.map(({ href, labelKey, icon: Icon }) => {
            const isActive =
              href === "/" ? pathname === "/" : pathname.startsWith(href);
            return (
              <li key={href}>
                <Link
                  href={href}
                  className={`flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors ${
                    isActive
                      ? "bg-green-500/20 text-green-400"
                      : "text-slate-300 hover:bg-white/5 hover:text-white"
                  }`}
                >
                  <Icon
                    size={17}
                    className={isActive ? "text-green-400" : "text-slate-400"}
                  />
                  {t(labelKey)}
                </Link>
              </li>
            );
          })}
        </ul>
      </nav>

      {/* Bottom actions */}
      <div className="border-t border-white/10 px-3 py-4 space-y-1">
        {/* Language toggle */}
        <button
          onClick={toggleLang}
          className="flex items-center gap-3 w-full px-3 py-2.5 rounded-lg text-sm text-slate-300 hover:bg-white/5 hover:text-white transition-colors"
        >
          <Globe size={17} className="text-slate-400" />
          {lang === "en" ? "Français" : "English"}
        </button>

        {/* Logout */}
        <button
          onClick={handleLogout}
          className="flex items-center gap-3 w-full px-3 py-2.5 rounded-lg text-sm text-slate-300 hover:bg-red-500/10 hover:text-red-400 transition-colors"
        >
          <LogOut size={17} className="text-slate-400" />
          {t("nav.logout")}
        </button>
      </div>
    </aside>
  );
}
