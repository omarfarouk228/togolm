"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  getApiKeys,
  createApiKey,
  updateApiKey,
  deleteApiKey,
  type ApiKey,
  type CreateKeyBody,
} from "@/lib/api";
import { useT } from "@/lib/i18n";
import { StatusBadge } from "@/components/status-badge";
import { ConfirmDialog } from "@/components/confirm-dialog";
import { Plus, Trash2, X } from "lucide-react";
import { ShimmerTable } from "@/components/shimmer";
import { format, parseISO } from "date-fns";

type Plan = "free" | "dev" | "institution";

function planBadge(plan: Plan) {
  const variants: Record<Plan, { label: string; variant: "gray" | "blue" | "purple" }> = {
    free: { label: "Free", variant: "gray" },
    dev: { label: "Developer", variant: "blue" },
    institution: { label: "Institution", variant: "purple" },
  };
  const { label, variant } = variants[plan] ?? { label: plan, variant: "gray" };
  return <StatusBadge label={label} variant={variant} />;
}

function ErrorMsg({ msg }: { msg: string }) {
  return (
    <div className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-lg px-4 py-3">
      {msg}
    </div>
  );
}

interface CreateModalProps {
  open: boolean;
  onClose: () => void;
  onCreated: () => void;
  t: (k: string) => string;
}

function CreateModal({ open, onClose, onCreated, t }: CreateModalProps) {
  const [form, setForm] = useState<CreateKeyBody>({
    name: "",
    email: "",
    use_case: "",
    plan: "free",
  });
  const [error, setError] = useState<string | null>(null);

  const mutation = useMutation({
    mutationFn: createApiKey,
    onSuccess: () => {
      onCreated();
      onClose();
      setForm({ name: "", email: "", use_case: "", plan: "free" });
      setError(null);
    },
    onError: () => setError(t("common.error")),
  });

  if (!open) return null;

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    mutation.mutate(form);
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/40 backdrop-blur-sm" onClick={onClose} />
      <div className="relative bg-white rounded-xl shadow-xl p-6 w-full max-w-md mx-4">
        <div className="flex items-center justify-between mb-4">
          <h3 className="font-semibold text-slate-800">{t("keys.create")}</h3>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-600">
            <X size={18} />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="space-y-3">
          <div>
            <label className="block text-xs font-medium text-slate-600 mb-1">{t("keys.name")}</label>
            <input
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              required
              className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-green-500"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-slate-600 mb-1">{t("keys.email")}</label>
            <input
              type="email"
              value={form.email}
              onChange={(e) => setForm({ ...form, email: e.target.value })}
              required
              className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-green-500"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-slate-600 mb-1">{t("keys.plan")}</label>
            <select
              value={form.plan}
              onChange={(e) => setForm({ ...form, plan: e.target.value as Plan })}
              className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-green-500 bg-white"
            >
              <option value="free">{t("keys.planFree")}</option>
              <option value="dev">{t("keys.planDev")}</option>
              <option value="institution">{t("keys.planInstitution")}</option>
            </select>
          </div>
          <div>
            <label className="block text-xs font-medium text-slate-600 mb-1">{t("keys.useCase")}</label>
            <textarea
              value={form.use_case}
              onChange={(e) => setForm({ ...form, use_case: e.target.value })}
              rows={2}
              className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-green-500 resize-none"
            />
          </div>

          {error && <ErrorMsg msg={error} />}

          <div className="flex gap-2 justify-end pt-1">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 text-sm text-slate-600 border border-slate-200 rounded-lg hover:bg-slate-50 transition-colors"
            >
              {t("keys.cancel")}
            </button>
            <button
              type="submit"
              disabled={mutation.isPending}
              className="px-4 py-2 text-sm text-white bg-green-500 hover:bg-green-600 rounded-lg transition-colors disabled:opacity-60"
            >
              {mutation.isPending ? t("keys.creating") : t("keys.save")}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

export default function KeysPage() {
  const { t } = useT();
  const qc = useQueryClient();
  const [createOpen, setCreateOpen] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<ApiKey | null>(null);

  const { data: keys, isLoading, error } = useQuery({
    queryKey: ["api-keys"],
    queryFn: getApiKeys,
  });

  const toggleMutation = useMutation({
    mutationFn: ({ id, is_active }: { id: string; is_active: boolean }) =>
      updateApiKey(id, { is_active }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["api-keys"] }),
  });

  const deleteMutation = useMutation({
    mutationFn: deleteApiKey,
    onSuccess: () => {
      setDeleteTarget(null);
      qc.invalidateQueries({ queryKey: ["api-keys"] });
    },
  });

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-bold text-slate-800">{t("keys.title")}</h1>
        <button
          onClick={() => setCreateOpen(true)}
          className="inline-flex items-center gap-1.5 px-4 py-2 bg-green-500 hover:bg-green-600 text-white text-sm font-medium rounded-lg transition-colors"
        >
          <Plus size={15} />
          {t("keys.create")}
        </button>
      </div>

      {isLoading ? (
        <ShimmerTable rows={6} cols={7} />
      ) : error ? (
        <ErrorMsg msg={t("common.error")} />
      ) : (
        <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-100 text-xs text-slate-500 uppercase tracking-wider">
                  <th className="text-left px-4 py-3 font-medium">{t("keys.name")}</th>
                  <th className="text-left px-4 py-3 font-medium hidden sm:table-cell">{t("keys.email")}</th>
                  <th className="text-left px-4 py-3 font-medium">{t("keys.plan")}</th>
                  <th className="text-left px-4 py-3 font-medium hidden lg:table-cell">{t("keys.useCase")}</th>
                  <th className="text-center px-4 py-3 font-medium">{t("keys.active")}</th>
                  <th className="text-left px-4 py-3 font-medium hidden md:table-cell">{t("keys.created")}</th>
                  <th className="text-right px-4 py-3 font-medium">{t("keys.actions")}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-50">
                {(keys ?? []).length === 0 ? (
                  <tr>
                    <td colSpan={7} className="px-5 py-10 text-center text-sm text-slate-400">
                      {t("keys.noKeys")}
                    </td>
                  </tr>
                ) : (
                  (keys ?? []).map((key) => (
                    <tr key={key.id} className="hover:bg-slate-50 transition-colors">
                      <td className="px-4 py-3 font-medium text-slate-700">
                        <div>{key.name}</div>
                        <div className="text-xs text-slate-400 font-mono">{key.key_prefix}…</div>
                        <div className="text-xs text-slate-400 sm:hidden mt-0.5">{key.email}</div>
                      </td>
                      <td className="px-4 py-3 text-slate-500 hidden sm:table-cell">{key.email}</td>
                      <td className="px-4 py-3">{planBadge(key.plan)}</td>
                      <td className="px-4 py-3 text-slate-500 max-w-[180px] truncate hidden lg:table-cell">
                        {key.use_case || "—"}
                      </td>
                      <td className="px-4 py-3 text-center">
                        <button
                          onClick={() =>
                            toggleMutation.mutate({ id: key.id, is_active: !key.is_active })
                          }
                          className={`relative inline-flex h-5 w-9 items-center rounded-full transition-colors cursor-pointer ${
                            key.is_active ? "bg-green-500" : "bg-slate-200"
                          }`}
                        >
                          <span
                            className={`inline-block h-3.5 w-3.5 transform rounded-full bg-white shadow transition-transform ${
                              key.is_active ? "translate-x-4" : "translate-x-1"
                            }`}
                          />
                        </button>
                      </td>
                      <td className="px-4 py-3 text-slate-400 text-xs whitespace-nowrap hidden md:table-cell">
                        {format(parseISO(key.created_at), "MMM d, yyyy")}
                      </td>
                      <td className="px-4 py-3 text-right">
                        <button
                          onClick={() => setDeleteTarget(key)}
                          className="text-slate-400 hover:text-red-500 transition-colors cursor-pointer"
                          title={t("keys.delete")}
                        >
                          <Trash2 size={15} />
                        </button>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      <CreateModal
        open={createOpen}
        onClose={() => setCreateOpen(false)}
        onCreated={() => qc.invalidateQueries({ queryKey: ["api-keys"] })}
        t={t}
      />

      <ConfirmDialog
        open={deleteTarget !== null}
        title={t("keys.confirmDelete")}
        message={t("keys.confirmDeleteMsg")}
        confirmLabel={t("keys.delete")}
        cancelLabel={t("keys.cancel")}
        loading={deleteMutation.isPending}
        onConfirm={() => deleteTarget && deleteMutation.mutate(deleteTarget.id)}
        onCancel={() => setDeleteTarget(null)}
      />
    </div>
  );
}
