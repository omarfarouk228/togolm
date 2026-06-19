"use client";

import { useState } from "react";
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
  const { t, lang, setLang } = useT();
  const [showLogoutModal, setShowLogoutModal] = useState(false);

  function confirmLogout() {
    removeToken();
    router.push("/login");
  }

  return (
    <>
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
          {/* Language select */}
          <div className="flex items-center gap-3 px-3 py-2">
            <Globe size={17} className="text-slate-400 shrink-0" />
            <select
              value={lang}
              onChange={(e) => setLang(e.target.value as "en" | "fr")}
              className="flex-1 bg-transparent text-sm text-slate-300 border border-white/10 rounded-md px-2 py-1 focus:outline-none focus:border-white/30 cursor-pointer"
            >
              <option value="en" className="bg-slate-800">English</option>
              <option value="fr" className="bg-slate-800">Français</option>
            </select>
          </div>

          {/* Logout */}
          <button
            onClick={() => setShowLogoutModal(true)}
            className="flex items-center gap-3 w-full px-3 py-2.5 rounded-lg text-sm text-slate-300 hover:bg-red-500/10 hover:text-red-400 transition-colors"
          >
            <LogOut size={17} className="text-slate-400" />
            {t("nav.logout")}
          </button>
        </div>
      </aside>

      {/* Logout confirmation modal */}
      {showLogoutModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm">
          <div className="bg-white rounded-xl shadow-xl p-6 w-80 space-y-4">
            <h2 className="text-base font-semibold text-slate-800">{t("nav.logoutConfirm")}</h2>
            <p className="text-sm text-slate-500">{t("nav.logoutConfirmMsg")}</p>
            <div className="flex gap-3 justify-end">
              <button
                onClick={() => setShowLogoutModal(false)}
                className="px-4 py-2 rounded-lg text-sm font-medium text-slate-600 border border-slate-200 hover:bg-slate-50 transition-colors"
              >
                {t("common.cancel")}
              </button>
              <button
                onClick={confirmLogout}
                className="px-4 py-2 rounded-lg text-sm font-medium bg-red-500 text-white hover:bg-red-600 transition-colors"
              >
                {t("nav.logout")}
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
