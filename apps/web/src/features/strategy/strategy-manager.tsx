"use client";

import { useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import { History, Save, Plus, Trash2, CheckCircle2, AlertCircle } from "lucide-react";
import { Card } from "@/components/card";
import type { SEOStrategy, SEOStrategyVersion, StrategyData } from "@/lib/api-types";
import { clientApi } from "@/lib/client-api";

type ProductServiceItem = {
  name: string;
  description: string;
  category: string;
  url?: string | null;
  priority: number;
};

export function StrategyManager({
  projectId,
  initialStrategy,
  versions,
}: {
  projectId: string;
  initialStrategy: SEOStrategy;
  versions: SEOStrategyVersion[];
}) {
  const router = useRouter();
  const [isPending, startTransition] = useTransition();
  const [strategyData, setStrategyData] = useState<StrategyData>(initialStrategy.strategy_data);
  const [changeSummary, setChangeSummary] = useState("");
  const [showHistory, setShowHistory] = useState(false);
  const [selectedVersion, setSelectedVersion] = useState<SEOStrategyVersion | null>(null);
  const [saveStatus, setSaveStatus] = useState<"idle" | "success" | "error">("idle");
  const [errorMessage, setErrorMessage] = useState("");

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaveStatus("idle");
    setErrorMessage("");

    startTransition(async () => {
      try {
        await clientApi(`/projects/${projectId}/strategy`, {
          method: "PUT",
          body: JSON.stringify({
            change_summary: changeSummary || `Saved strategy updates`,
            strategy_data: strategyData,
          }),
        });
        setSaveStatus("success");
        setChangeSummary("");
        router.refresh();
      } catch (err: unknown) {
        setSaveStatus("error");
        setErrorMessage(err instanceof Error ? err.message : "Failed to save strategy");
      }
    });
  };

  const addProduct = () => {
    const currentProds = (strategyData.products || []) as ProductServiceItem[];
    setStrategyData({
      ...strategyData,
      products: [
        ...currentProds,
        { name: "", description: "", category: "Core Product", priority: 1, url: null },
      ],
    });
  };

  const removeProduct = (index: number) => {
    const next = [...((strategyData.products || []) as ProductServiceItem[])];
    next.splice(index, 1);
    setStrategyData({ ...strategyData, products: next });
  };

  return (
    <div className="grid gap-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <span className="rounded-full bg-[var(--surface-soft)] px-2.5 py-0.5 text-xs font-semibold text-[var(--accent)]">
              Version {initialStrategy.current_version}
            </span>
            <span className="rounded-full bg-emerald-50 px-2.5 py-0.5 text-xs font-semibold text-emerald-700 capitalize">
              {initialStrategy.status}
            </span>
          </div>
          <p className="mt-1 text-sm text-[var(--muted)]">
            Last updated: {new Date(initialStrategy.updated_at).toLocaleString()}
          </p>
        </div>

        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={() => setShowHistory(!showHistory)}
            className="inline-flex items-center gap-2 rounded-lg border border-[var(--border)] bg-white px-3.5 py-2 text-sm font-semibold hover:bg-slate-50 transition"
          >
            <History size={16} /> Version History ({versions.length})
          </button>
        </div>
      </div>

      {saveStatus === "success" && (
        <div className="flex items-center gap-2 rounded-lg bg-emerald-50 p-4 text-sm font-medium text-emerald-800 border border-emerald-200">
          <CheckCircle2 size={18} /> Strategy successfully updated and new immutable version recorded.
        </div>
      )}

      {saveStatus === "error" && (
        <div className="flex items-center gap-2 rounded-lg bg-rose-50 p-4 text-sm font-medium text-rose-800 border border-rose-200">
          <AlertCircle size={18} /> {errorMessage || "An error occurred while saving."}
        </div>
      )}

      {showHistory && (
        <Card className="p-5 border-indigo-100 bg-slate-50/70">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-base font-bold">Immutable Version History</h3>
            <button
              type="button"
              onClick={() => setShowHistory(false)}
              className="text-xs text-[var(--muted)] hover:text-[var(--ink)]"
            >
              Close
            </button>
          </div>
          <div className="grid gap-2 max-h-60 overflow-y-auto">
            {versions.map((v) => (
              <div
                key={v.id}
                onClick={() => setSelectedVersion(v)}
                className={`p-3 rounded-lg border text-sm cursor-pointer transition flex items-center justify-between ${
                  selectedVersion?.id === v.id ? "border-[var(--accent)] bg-white shadow-sm" : "bg-white border-[var(--border)] hover:bg-slate-50"
                }`}
              >
                <div>
                  <span className="font-bold text-[var(--accent)]">Version {v.version}</span>
                  <span className="ml-3 text-slate-700">{v.change_summary || "No summary provided"}</span>
                </div>
                <span className="text-xs text-[var(--muted)]">{new Date(v.created_at).toLocaleString()}</span>
              </div>
            ))}
          </div>
        </Card>
      )}

      <form onSubmit={handleSave} className="grid gap-6">
        {/* Business Overview & Goals */}
        <Card className="p-6">
          <h2 className="text-lg font-bold text-[var(--ink)] mb-4">1. Business Context & Positioning</h2>
          <div className="grid gap-4 md:grid-cols-2">
            <div>
              <label className="block text-xs font-bold uppercase tracking-wider text-[var(--muted)] mb-1">
                Business Description
              </label>
              <textarea
                rows={3}
                className="w-full rounded-lg border border-[var(--border)] p-3 text-sm focus:outline-[var(--accent)]"
                placeholder="What does your company do and what unique value do you provide?"
                value={strategyData.business_context?.description || ""}
                onChange={(e) =>
                  setStrategyData({
                    ...strategyData,
                    business_context: {
                      business_name: strategyData.business_context?.business_name || "",
                      industry: strategyData.business_context?.industry || "",
                      description: e.target.value,
                    },
                  })
                }
              />
            </div>
            <div>
              <label className="block text-xs font-bold uppercase tracking-wider text-[var(--muted)] mb-1">
                Industry & Market
              </label>
              <input
                type="text"
                className="w-full rounded-lg border border-[var(--border)] p-2.5 text-sm bg-white"
                placeholder="e.g. B2B SaaS / SEO Content Intelligence"
                value={strategyData.business_context?.industry || ""}
                onChange={(e) =>
                  setStrategyData({
                    ...strategyData,
                    business_context: {
                      business_name: strategyData.business_context?.business_name || "",
                      description: strategyData.business_context?.description || "",
                      industry: e.target.value,
                    },
                  })
                }
              />
            </div>
          </div>
        </Card>

        {/* Products & Offerings */}
        <Card className="p-6">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h2 className="text-lg font-bold text-[var(--ink)]">2. Products & Services</h2>
              <p className="text-xs text-[var(--muted)] mt-0.5">Used for deterministic business value keyword scoring</p>
            </div>
            <button
              type="button"
              onClick={addProduct}
              className="inline-flex items-center gap-1.5 rounded-md border border-[var(--border)] px-2.5 py-1 text-xs font-bold hover:bg-slate-50 transition"
            >
              <Plus size={14} /> Add Product
            </button>
          </div>

          <div className="grid gap-3">
            {((strategyData.products || []) as ProductServiceItem[]).map((prod: ProductServiceItem, idx: number) => (
              <div key={idx} className="flex gap-3 items-start p-3 bg-slate-50 rounded-lg border border-[var(--border)]">
                <input
                  type="text"
                  placeholder="Product name"
                  className="flex-1 rounded-md border border-[var(--border)] p-2 text-sm bg-white"
                  value={prod.name || ""}
                  onChange={(e) => {
                    const next = [...((strategyData.products || []) as ProductServiceItem[])];
                    next[idx] = { ...next[idx], name: e.target.value };
                    setStrategyData({ ...strategyData, products: next });
                  }}
                />
                <input
                  type="text"
                  placeholder="Key features / value"
                  className="flex-[2] rounded-md border border-[var(--border)] p-2 text-sm bg-white"
                  value={prod.description || ""}
                  onChange={(e) => {
                    const next = [...((strategyData.products || []) as ProductServiceItem[])];
                    next[idx] = { ...next[idx], description: e.target.value };
                    setStrategyData({ ...strategyData, products: next });
                  }}
                />
                <button
                  type="button"
                  onClick={() => removeProduct(idx)}
                  className="text-slate-400 hover:text-rose-600 p-2"
                >
                  <Trash2 size={16} />
                </button>
              </div>
            ))}
          </div>
        </Card>

        {/* Change summary & Submit */}
        <Card className="p-6 bg-slate-50 border-slate-200">
          <div className="flex flex-col sm:flex-row gap-4 items-end">
            <div className="flex-1 w-full">
              <label className="block text-xs font-bold uppercase tracking-wider text-[var(--muted)] mb-1">
                Version Change Summary
              </label>
              <input
                type="text"
                className="w-full rounded-lg border border-[var(--border)] p-2.5 text-sm bg-white"
                placeholder="Explain what was changed in this version (e.g. Added enterprise product line)"
                value={changeSummary}
                onChange={(e) => setChangeSummary(e.target.value)}
              />
            </div>
            <button
              type="submit"
              disabled={isPending}
              className="inline-flex items-center justify-center gap-2 rounded-lg bg-[var(--accent)] px-5 py-2.5 text-sm font-bold text-white shadow-sm hover:opacity-90 disabled:opacity-50 transition"
            >
              <Save size={16} /> {isPending ? "Saving Version..." : "Save New Version"}
            </button>
          </div>
        </Card>
      </form>
    </div>
  );
}
