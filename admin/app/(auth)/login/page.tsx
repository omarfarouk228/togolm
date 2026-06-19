"use client";

import { useState, FormEvent } from "react";
import { useRouter } from "next/navigation";
import { adminLogin } from "@/lib/api";
import { setToken } from "@/lib/auth";
import { useT } from "@/lib/i18n";
import { Lock } from "lucide-react";

export default function LoginPage() {
  const router = useRouter();
  const { t } = useT();
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const data = await adminLogin(password);
      setToken(data.token);
      router.push("/");
    } catch {
      setError(t("login.error"));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-50">
      <div className="w-full max-w-sm">
        {/* Header */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-12 h-12 bg-green-500 rounded-xl mb-4">
            <Lock size={22} className="text-white" />
          </div>
          <h1 className="text-2xl font-bold text-slate-800">{t("login.title")}</h1>
          <p className="text-slate-500 mt-1 text-sm">{t("login.subtitle")}</p>
        </div>

        {/* Card */}
        <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6">
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label
                htmlFor="password"
                className="block text-sm font-medium text-slate-700 mb-1.5"
              >
                {t("login.password")}
              </label>
              <input
                id="password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder={t("login.passwordPlaceholder")}
                required
                autoFocus
                className="w-full px-3 py-2.5 border border-slate-200 rounded-lg text-sm text-slate-800 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-green-500 focus:border-transparent transition-shadow"
              />
            </div>

            {error && (
              <div className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-lg px-3 py-2">
                {error}
              </div>
            )}

            <button
              type="submit"
              disabled={loading}
              className="w-full py-2.5 px-4 bg-green-500 hover:bg-green-600 text-white text-sm font-medium rounded-lg transition-colors disabled:opacity-60 disabled:cursor-not-allowed"
            >
              {loading ? t("login.signing") : t("login.submit")}
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}
