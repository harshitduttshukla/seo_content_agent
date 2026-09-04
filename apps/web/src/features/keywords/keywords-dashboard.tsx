"use client";

import { useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import {
  Search,
  Upload,
  Layers,
  Plus,
  AlertTriangle,
  Flame,
  CheckCircle2,
  FolderPlus,
  ExternalLink,
} from "lucide-react";
import { Card } from "@/components/card";
import type {
  Keyword,
  KeywordCluster,
  CannibalizationWarning,
  ClusteringRun,
} from "@/lib/api-types";
import { clientApi } from "@/lib/client-api";

export function KeywordsDashboard({
  projectId,
  initialKeywords,
  initialClusters,
  initialWarnings,
}: {
  projectId: string;
  initialKeywords: Keyword[];
  initialClusters: KeywordCluster[];
  initialWarnings: CannibalizationWarning[];
}) {
  const router = useRouter();
  const [isPending, startTransition] = useTransition();
  const [activeTab, setActiveTab] = useState<"keywords" | "clusters">("keywords");
  const [search, setSearch] = useState("");
  const [intentFilter, setIntentFilter] = useState<string>("ALL");

  // Modals state
  const [showAddModal, setShowAddModal] = useState(false);
  const [showImportModal, setShowImportModal] = useState(false);
  const [showClusterModal, setShowClusterModal] = useState(false);

  // Form states
  const [newKeyword, setNewKeyword] = useState("");
  const [newVolume, setNewVolume] = useState<number>(1000);
  const [newDifficulty, setNewDifficulty] = useState<number>(30);
  const [newCpc, setNewCpc] = useState<number>(2.5);
  const [newIntent, setNewIntent] = useState("UNKNOWN");

  const [importFile, setImportFile] = useState<File | null>(null);
  const [clusterThreshold, setClusterThreshold] = useState(0.45);
  const [notification, setNotification] = useState<string | null>(null);

  const handleCreateKeyword = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newKeyword.trim()) return;

    startTransition(async () => {
      try {
        await clientApi(`/projects/${projectId}/keywords`, {
          method: "POST",
          body: JSON.stringify({
            keyword: newKeyword.trim(),
            search_volume: Number(newVolume) || 0,
            keyword_difficulty: Number(newDifficulty) || 0,
            cpc: Number(newCpc) || 0,
            intent: newIntent,
          }),
        });
        setShowAddModal(false);
        setNewKeyword("");
        setNotification("Keyword created successfully!");
        router.refresh();
      } catch (err) {
        alert(err instanceof Error ? err.message : "Failed to create keyword");
      }
    });
  };

  const handleImportCsv = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!importFile) return;

    startTransition(async () => {
      try {
        const formData = new FormData();
        formData.append("file", importFile);

        const res = await fetch(`/api/v1/projects/${projectId}/keywords/import`, {
          method: "POST",
          body: formData,
        });
        if (!res.ok) {
          throw new Error("Failed to import CSV file");
        }
        setShowImportModal(false);
        setImportFile(null);
        setNotification("CSV imported successfully!");
        router.refresh();
      } catch (err) {
        alert(err instanceof Error ? err.message : "Failed to import CSV");
      }
    });
  };

  const handleRunClustering = async (e: React.FormEvent) => {
    e.preventDefault();
    startTransition(async () => {
      try {
        await clientApi<ClusteringRun>(`/projects/${projectId}/clustering-runs`, {
          method: "POST",
          body: JSON.stringify({
            similarity_threshold: Number(clusterThreshold),
          }),
        });
        setShowClusterModal(false);
        setNotification("Clustering complete! Keyword clusters updated.");
        setActiveTab("clusters");
        router.refresh();
      } catch (err) {
        alert(err instanceof Error ? err.message : "Failed to run clustering");
      }
    });
  };

  const filteredKeywords = initialKeywords.filter((k) => {
    const matchSearch =
      !search ||
      k.keyword.toLowerCase().includes(search.toLowerCase()) ||
      k.normalized_keyword.includes(search.toLowerCase());
    const matchIntent = intentFilter === "ALL" || k.intent.toUpperCase() === intentFilter;
    return matchSearch && matchIntent;
  });

  return (
    <div className="grid gap-6">
      {/* Cannibalization Warning Banner */}
      {initialWarnings.length > 0 && (
        <div className="rounded-xl border border-amber-300 bg-amber-50 p-4 text-amber-900 shadow-sm">
          <div className="flex items-start gap-3">
            <AlertTriangle className="mt-0.5 text-amber-600 flex-shrink-0" size={20} />
            <div className="flex-1">
              <h3 className="font-bold text-sm">
                Keyword Cannibalization Detected ({initialWarnings.length} queries)
              </h3>
              <p className="text-xs text-amber-800 mt-1">
                Multiple live pages on your website have competing Title tags or H1 headings targeting the exact same search term.
              </p>
              <div className="mt-3 grid gap-2">
                {initialWarnings.slice(0, 3).map((w, idx) => (
                  <div key={idx} className="rounded-lg bg-white/80 p-2.5 text-xs border border-amber-200">
                    <span className="font-bold text-amber-950">"{w.keyword}"</span>: {w.reason}
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}

      {notification && (
        <div className="flex items-center gap-2 rounded-lg bg-emerald-50 p-3 text-sm font-medium text-emerald-800 border border-emerald-200">
          <CheckCircle2 size={16} /> {notification}
        </div>
      )}

      {/* Top action bar */}
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div className="flex rounded-lg bg-slate-100 p-1">
          <button
            type="button"
            onClick={() => setActiveTab("keywords")}
            className={`rounded-md px-4 py-2 text-sm font-bold transition ${
              activeTab === "keywords" ? "bg-white text-[var(--accent)] shadow-sm" : "text-[var(--muted)] hover:text-[var(--ink)]"
            }`}
          >
            Keywords ({initialKeywords.length})
          </button>
          <button
            type="button"
            onClick={() => setActiveTab("clusters")}
            className={`rounded-md px-4 py-2 text-sm font-bold transition ${
              activeTab === "clusters" ? "bg-white text-[var(--accent)] shadow-sm" : "text-[var(--muted)] hover:text-[var(--ink)]"
            }`}
          >
            Clusters ({initialClusters.length})
          </button>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <button
            type="button"
            onClick={() => setShowAddModal(true)}
            className="inline-flex items-center gap-1.5 rounded-lg border border-[var(--border)] bg-white px-3.5 py-2 text-sm font-semibold hover:bg-slate-50 transition"
          >
            <Plus size={16} /> Add Keyword
          </button>
          <button
            type="button"
            onClick={() => setShowImportModal(true)}
            className="inline-flex items-center gap-1.5 rounded-lg border border-[var(--border)] bg-white px-3.5 py-2 text-sm font-semibold hover:bg-slate-50 transition"
          >
            <Upload size={16} /> Import CSV
          </button>
          <button
            type="button"
            onClick={() => setShowClusterModal(true)}
            className="inline-flex items-center gap-1.5 rounded-lg bg-[var(--accent)] px-4 py-2 text-sm font-bold text-white hover:opacity-90 shadow-sm transition"
          >
            <Layers size={16} /> Run Clustering
          </button>
        </div>
      </div>

      {activeTab === "keywords" ? (
        <Card className="p-0 overflow-hidden">
          {/* Filters header */}
          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-[var(--border)] p-4 bg-slate-50/50">
            <div className="relative flex-1 min-w-[200px] max-w-sm">
              <Search className="absolute left-3 top-2.5 text-slate-400" size={16} />
              <input
                type="text"
                placeholder="Search keywords..."
                className="w-full rounded-lg border border-[var(--border)] bg-white pl-9 pr-3 py-1.5 text-sm"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
              />
            </div>
            <div className="flex items-center gap-2">
              <span className="text-xs text-[var(--muted)] font-medium">Intent:</span>
              <select
                className="rounded-lg border border-[var(--border)] bg-white px-3 py-1.5 text-xs font-semibold"
                value={intentFilter}
                onChange={(e) => setIntentFilter(e.target.value)}
              >
                <option value="ALL">All Intents</option>
                <option value="INFORMATIONAL">Informational (TOFU)</option>
                <option value="COMMERCIAL">Commercial (MOFU)</option>
                <option value="TRANSACTIONAL">Transactional (BOFU)</option>
                <option value="NAVIGATIONAL">Navigational</option>
                <option value="LOCAL">Local</option>
              </select>
            </div>
          </div>

          {/* Keywords Table */}
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="border-b border-[var(--border)] bg-slate-100/70 text-xs font-bold uppercase text-[var(--muted)]">
                <tr>
                  <th className="px-4 py-3">Keyword</th>
                  <th className="px-4 py-3">Intent</th>
                  <th className="px-4 py-3">Volume</th>
                  <th className="px-4 py-3">Difficulty</th>
                  <th className="px-4 py-3">CPC</th>
                  <th className="px-4 py-3">Business Value</th>
                  <th className="px-4 py-3">Priority</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--border)]">
                {filteredKeywords.length === 0 ? (
                  <tr>
                    <td colSpan={7} className="px-4 py-8 text-center text-sm text-[var(--muted)]">
                      No keywords found. Add keywords or import a CSV file to build your keyword universe.
                    </td>
                  </tr>
                ) : (
                  filteredKeywords.map((kw) => (
                    <tr key={kw.id} className="hover:bg-slate-50/70 transition">
                      <td className="px-4 py-3 font-semibold text-[var(--ink)]">
                        {kw.keyword}
                      </td>
                      <td className="px-4 py-3">
                        <span className={`inline-block rounded-full px-2 py-0.5 text-[11px] font-bold ${
                          kw.intent === "TRANSACTIONAL"
                            ? "bg-emerald-100 text-emerald-800"
                            : kw.intent === "COMMERCIAL"
                            ? "bg-indigo-100 text-indigo-800"
                            : "bg-slate-100 text-slate-700"
                        }`}>
                          {kw.intent}
                        </span>
                      </td>
                      <td className="px-4 py-3 font-mono text-xs">{kw.search_volume.toLocaleString()}</td>
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-2">
                          <span className="font-mono text-xs">{kw.keyword_difficulty}</span>
                          <div className="h-1.5 w-12 rounded-full bg-slate-200 overflow-hidden">
                            <div
                              className={`h-full ${
                                kw.keyword_difficulty > 60
                                  ? "bg-rose-500"
                                  : kw.keyword_difficulty > 30
                                  ? "bg-amber-500"
                                  : "bg-emerald-500"
                              }`}
                              style={{ width: `${Math.min(100, kw.keyword_difficulty)}%` }}
                            />
                          </div>
                        </div>
                      </td>
                      <td className="px-4 py-3 font-mono text-xs">${kw.cpc.toFixed(2)}</td>
                      <td className="px-4 py-3">
                        <span className="font-bold text-xs text-indigo-700">{kw.business_value_score}</span>
                      </td>
                      <td className="px-4 py-3">
                        <span className="inline-flex items-center gap-1 font-bold text-xs text-[var(--accent)]">
                          <Flame size={13} className="text-amber-500" /> {kw.priority_score}
                        </span>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </Card>
      ) : (
        /* Clusters View */
        <div className="grid gap-4 md:grid-cols-2">
          {initialClusters.length === 0 ? (
            <Card className="p-8 text-center text-sm text-[var(--muted)] col-span-2">
              No keyword clusters generated yet. Click <strong>"Run Clustering"</strong> above to group your keywords into topic clusters deterministically.
            </Card>
          ) : (
            initialClusters.map((cluster) => (
              <Card key={cluster.id} className="p-5 flex flex-col justify-between">
                <div>
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <span className="text-[11px] font-bold uppercase tracking-wider text-[var(--accent)]">
                        Cluster
                      </span>
                      <h3 className="text-lg font-bold text-[var(--ink)] mt-0.5">{cluster.cluster_name}</h3>
                    </div>
                    <span className="rounded-full bg-slate-100 px-2.5 py-0.5 text-xs font-bold text-slate-700">
                      Score {cluster.cluster_score}
                    </span>
                  </div>

                  <p className="mt-2 text-xs text-[var(--muted)] leading-relaxed">{cluster.rationale}</p>

                  <div className="mt-4 rounded-lg bg-slate-50 p-3 border border-[var(--border)]">
                    <p className="text-[11px] font-bold text-[var(--muted)] uppercase">Primary Target Keyword</p>
                    <p className="text-sm font-bold text-[var(--ink)] mt-0.5">
                      {cluster.primary_keyword || "Not designated"}
                    </p>
                  </div>

                  <div className="mt-4">
                    <p className="text-xs font-bold text-[var(--muted)] mb-2">
                      Keywords in Cluster ({cluster.member_count})
                    </p>
                    <div className="grid gap-1.5 max-h-36 overflow-y-auto">
                      {(cluster.members || []).map((m) => (
                        <div key={m.id} className="flex items-center justify-between text-xs p-1.5 rounded bg-white border border-[var(--border)]">
                          <span className={m.is_primary ? "font-bold text-[var(--accent)]" : "text-slate-700"}>
                            {m.keyword} {m.is_primary && "★"}
                          </span>
                          <span className="text-[var(--muted)] font-mono">{m.search_volume} vol</span>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>

                <div className="mt-5 pt-3 border-t border-[var(--border)] flex items-center justify-between">
                  <span className="text-xs font-semibold capitalize text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded">
                    Status: {cluster.status}
                  </span>
                </div>
              </Card>
            ))
          )}
        </div>
      )}

      {/* Add Keyword Modal */}
      {showAddModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
          <Card className="w-full max-w-md p-6 bg-white shadow-2xl">
            <h2 className="text-lg font-bold mb-4">Add Keyword</h2>
            <form onSubmit={handleCreateKeyword} className="grid gap-4">
              <div>
                <label className="block text-xs font-bold uppercase text-[var(--muted)] mb-1">Keyword</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. b2b seo tools"
                  className="w-full rounded-lg border border-[var(--border)] p-2.5 text-sm"
                  value={newKeyword}
                  onChange={(e) => setNewKeyword(e.target.value)}
                />
              </div>
              <div className="grid grid-cols-3 gap-2">
                <div>
                  <label className="block text-xs font-bold uppercase text-[var(--muted)] mb-1">Volume</label>
                  <input
                    type="number"
                    className="w-full rounded-lg border border-[var(--border)] p-2 text-sm"
                    value={newVolume}
                    onChange={(e) => setNewVolume(Number(e.target.value))}
                  />
                </div>
                <div>
                  <label className="block text-xs font-bold uppercase text-[var(--muted)] mb-1">KD (0-100)</label>
                  <input
                    type="number"
                    className="w-full rounded-lg border border-[var(--border)] p-2 text-sm"
                    value={newDifficulty}
                    onChange={(e) => setNewDifficulty(Number(e.target.value))}
                  />
                </div>
                <div>
                  <label className="block text-xs font-bold uppercase text-[var(--muted)] mb-1">CPC ($)</label>
                  <input
                    type="number"
                    step="0.1"
                    className="w-full rounded-lg border border-[var(--border)] p-2 text-sm"
                    value={newCpc}
                    onChange={(e) => setNewCpc(Number(e.target.value))}
                  />
                </div>
              </div>
              <div className="flex justify-end gap-2 mt-2">
                <button
                  type="button"
                  onClick={() => setShowAddModal(false)}
                  className="rounded-lg border px-4 py-2 text-sm font-semibold hover:bg-slate-50"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isPending}
                  className="rounded-lg bg-[var(--accent)] px-4 py-2 text-sm font-bold text-white hover:opacity-90"
                >
                  Save Keyword
                </button>
              </div>
            </form>
          </Card>
        </div>
      )}

      {/* CSV Import Modal */}
      {showImportModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
          <Card className="w-full max-w-md p-6 bg-white shadow-2xl">
            <h2 className="text-lg font-bold mb-2">Import Keywords CSV</h2>
            <p className="text-xs text-[var(--muted)] mb-4">
              Upload a CSV file containing columns for <code>Keyword</code>, <code>Search Volume</code>, <code>Difficulty</code>, <code>CPC</code>, and optional <code>Intent</code>.
            </p>
            <form onSubmit={handleImportCsv} className="grid gap-4">
              <input
                type="file"
                accept=".csv"
                required
                onChange={(e) => setImportFile(e.target.files?.[0] || null)}
                className="w-full text-sm file:mr-4 file:rounded-lg file:border-0 file:bg-[var(--accent)] file:px-4 file:py-2 file:text-xs file:font-bold file:text-white hover:file:opacity-90"
              />
              <div className="flex justify-end gap-2 mt-2">
                <button
                  type="button"
                  onClick={() => setShowImportModal(false)}
                  className="rounded-lg border px-4 py-2 text-sm font-semibold hover:bg-slate-50"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={!importFile || isPending}
                  className="rounded-lg bg-[var(--accent)] px-4 py-2 text-sm font-bold text-white hover:opacity-90"
                >
                  {isPending ? "Importing..." : "Upload & Ingest"}
                </button>
              </div>
            </form>
          </Card>
        </div>
      )}

      {/* Clustering Config Modal */}
      {showClusterModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
          <Card className="w-full max-w-md p-6 bg-white shadow-2xl">
            <h2 className="text-lg font-bold mb-2">Run Keyword Clustering</h2>
            <p className="text-xs text-[var(--muted)] mb-4">
              Deterministically groups keywords into semantic clusters using token Jaccard similarity and search intent grouping.
            </p>
            <form onSubmit={handleRunClustering} className="grid gap-4">
              <div>
                <label className="block text-xs font-bold uppercase text-[var(--muted)] mb-1">
                  Similarity Threshold ({clusterThreshold})
                </label>
                <input
                  type="range"
                  min="0.30"
                  max="0.80"
                  step="0.05"
                  className="w-full"
                  value={clusterThreshold}
                  onChange={(e) => setClusterThreshold(Number(e.target.value))}
                />
                <div className="flex justify-between text-[11px] text-[var(--muted)] mt-1">
                  <span>Broader Clusters (0.30)</span>
                  <span>Tighter Clusters (0.80)</span>
                </div>
              </div>
              <div className="flex justify-end gap-2 mt-2">
                <button
                  type="button"
                  onClick={() => setShowClusterModal(false)}
                  className="rounded-lg border px-4 py-2 text-sm font-semibold hover:bg-slate-50"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isPending}
                  className="rounded-lg bg-[var(--accent)] px-4 py-2 text-sm font-bold text-white hover:opacity-90"
                >
                  {isPending ? "Clustering..." : "Run Clustering"}
                </button>
              </div>
            </form>
          </Card>
        </div>
      )}
    </div>
  );
}
