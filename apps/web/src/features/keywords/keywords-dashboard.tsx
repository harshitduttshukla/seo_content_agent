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
  Pencil,
  Trash2,
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
  const [keywordToEdit, setKeywordToEdit] = useState<Keyword | null>(null);
  const [keywordToDelete, setKeywordToDelete] = useState<Keyword | null>(null);
  const [keywordMutationError, setKeywordMutationError] = useState<string | null>(null);
  const [clusterToDelete, setClusterToDelete] = useState<KeywordCluster | null>(null);
  const [deleteClusterError, setDeleteClusterError] = useState<string | null>(null);

  // Form states
  const [newKeyword, setNewKeyword] = useState("");
  const [newVolume, setNewVolume] = useState<number>(1000);
  const [newDifficulty, setNewDifficulty] = useState<number>(30);
  const [newCpc, setNewCpc] = useState<number>(2.5);

  const [editKeyword, setEditKeyword] = useState("");
  const [editVolume, setEditVolume] = useState(0);
  const [editDifficulty, setEditDifficulty] = useState(0);
  const [editCpc, setEditCpc] = useState(0);
  const [editIntent, setEditIntent] = useState("UNKNOWN");
  const [editFunnelStage, setEditFunnelStage] = useState("TOFU");
  const [editStatus, setEditStatus] = useState("active");

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
            intent: "UNKNOWN",
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

        const res = await fetch(`/api/backend/projects/${projectId}/keywords/import`, {
          method: "POST",
          body: formData,
        });
        if (!res.ok) {
          let errorMessage = "Failed to import CSV file";
          try {
            const payload = await res.json();
            if (payload?.errors && Array.isArray(payload.errors) && payload.errors.length > 0) {
              errorMessage = payload.errors[0].message || errorMessage;
            } else if (payload?.detail) {
              errorMessage = typeof payload.detail === "string" ? payload.detail : JSON.stringify(payload.detail);
            }
          } catch {
            // fallback if response is not JSON
          }
          throw new Error(errorMessage);
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

  const openKeywordEditor = (keyword: Keyword) => {
    setKeywordMutationError(null);
    setKeywordToEdit(keyword);
    setEditKeyword(keyword.keyword);
    setEditVolume(keyword.search_volume);
    setEditDifficulty(keyword.keyword_difficulty);
    setEditCpc(keyword.cpc);
    setEditIntent(keyword.intent);
    setEditFunnelStage(keyword.funnel_stage);
    setEditStatus(keyword.status);
  };

  const handleUpdateKeyword = (e: React.FormEvent) => {
    e.preventDefault();
    if (!keywordToEdit || !editKeyword.trim()) return;

    const keywordId = keywordToEdit.id;
    setKeywordMutationError(null);
    startTransition(async () => {
      try {
        await clientApi(`/projects/${projectId}/keywords/${keywordId}`, {
          method: "PUT",
          body: JSON.stringify({
            keyword: editKeyword.trim(),
            search_volume: Number(editVolume) || 0,
            keyword_difficulty: Number(editDifficulty) || 0,
            cpc: Number(editCpc) || 0,
            intent: editIntent,
            funnel_stage: editFunnelStage,
            status: editStatus,
          }),
        });
        setKeywordToEdit(null);
        setNotification(`Keyword "${editKeyword.trim()}" updated successfully.`);
        router.refresh();
      } catch (err) {
        setKeywordMutationError(
          err instanceof Error ? err.message : "Failed to update the keyword",
        );
      }
    });
  };

  const handleDeleteKeyword = () => {
    if (!keywordToDelete) return;

    const keyword = keywordToDelete;
    setKeywordMutationError(null);
    startTransition(async () => {
      try {
        await clientApi(`/projects/${projectId}/keywords/${keyword.id}`, {
          method: "DELETE",
        });
        setKeywordToDelete(null);
        setNotification(`Keyword "${keyword.keyword}" deleted successfully.`);
        router.refresh();
      } catch (err) {
        setKeywordMutationError(
          err instanceof Error ? err.message : "Failed to delete the keyword",
        );
      }
    });
  };

  const handleDeleteCluster = () => {
    if (!clusterToDelete) return;

    const cluster = clusterToDelete;
    setDeleteClusterError(null);
    startTransition(async () => {
      try {
        await clientApi(`/projects/${projectId}/clusters/${cluster.id}`, {
          method: "DELETE",
        });
        setClusterToDelete(null);
        setNotification(`Cluster "${cluster.cluster_name}" deleted. Its keywords were kept.`);
        router.refresh();
      } catch (err) {
        setDeleteClusterError(
          err instanceof Error ? err.message : "Failed to delete the cluster",
        );
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
                    <span className="font-bold text-amber-950">&ldquo;{w.keyword}&rdquo;</span>: {w.reason}
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
                  <th className="px-4 py-3 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--border)]">
                {filteredKeywords.length === 0 ? (
                  <tr>
                    <td colSpan={8} className="px-4 py-8 text-center text-sm text-[var(--muted)]">
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
                      <td className="px-4 py-3">
                        <div className="flex items-center justify-end gap-1.5">
                          <button
                            type="button"
                            onClick={() => openKeywordEditor(kw)}
                            className="inline-flex items-center gap-1 rounded-lg border border-slate-200 px-2.5 py-1.5 text-xs font-bold text-slate-700 transition hover:bg-slate-100"
                            aria-label={`Edit keyword ${kw.keyword}`}
                          >
                            <Pencil size={13} /> Edit
                          </button>
                          <button
                            type="button"
                            onClick={() => {
                              setKeywordMutationError(null);
                              setKeywordToDelete(kw);
                            }}
                            className="inline-flex items-center gap-1 rounded-lg border border-red-200 px-2.5 py-1.5 text-xs font-bold text-red-700 transition hover:bg-red-50"
                            aria-label={`Delete keyword ${kw.keyword}`}
                          >
                            <Trash2 size={13} /> Delete
                          </button>
                        </div>
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
              No keyword clusters generated yet. Click <strong>&ldquo;Run Clustering&rdquo;</strong> above to group your keywords into topic clusters deterministically.
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
                  <button
                    type="button"
                    onClick={() => {
                      setDeleteClusterError(null);
                      setClusterToDelete(cluster);
                    }}
                    className="inline-flex items-center gap-1.5 rounded-lg border border-red-200 px-2.5 py-1.5 text-xs font-bold text-red-700 transition hover:bg-red-50"
                    aria-label={`Delete cluster ${cluster.cluster_name}`}
                  >
                    <Trash2 size={14} /> Delete
                  </button>
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

      {/* Keyword editor */}
      {keywordToEdit && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
          <Card
            className="w-full max-w-2xl p-6 bg-white shadow-2xl"
            role="dialog"
            aria-modal="true"
            aria-labelledby="edit-keyword-title"
          >
            <h2 id="edit-keyword-title" className="text-lg font-bold">
              Edit keyword
            </h2>
            <p className="mt-1 text-xs text-[var(--muted)]">
              Changing the keyword, CPC, or intent recalculates its business value and priority.
            </p>

            <form onSubmit={handleUpdateKeyword} className="mt-5 grid gap-4">
              <div>
                <label
                  htmlFor="edit-keyword-value"
                  className="mb-1 block text-xs font-bold uppercase text-[var(--muted)]"
                >
                  Keyword
                </label>
                <input
                  id="edit-keyword-value"
                  type="text"
                  required
                  maxLength={500}
                  value={editKeyword}
                  onChange={(e) => setEditKeyword(e.target.value)}
                  className="w-full rounded-lg border border-[var(--border)] p-2.5 text-sm"
                />
              </div>

              <div className="grid gap-4 sm:grid-cols-3">
                <div>
                  <label
                    htmlFor="edit-keyword-volume"
                    className="mb-1 block text-xs font-bold uppercase text-[var(--muted)]"
                  >
                    Search Volume
                  </label>
                  <input
                    id="edit-keyword-volume"
                    type="number"
                    min="0"
                    value={editVolume}
                    onChange={(e) => setEditVolume(Number(e.target.value))}
                    className="w-full rounded-lg border border-[var(--border)] p-2.5 text-sm"
                  />
                </div>
                <div>
                  <label
                    htmlFor="edit-keyword-difficulty"
                    className="mb-1 block text-xs font-bold uppercase text-[var(--muted)]"
                  >
                    Difficulty
                  </label>
                  <input
                    id="edit-keyword-difficulty"
                    type="number"
                    min="0"
                    max="100"
                    step="0.1"
                    value={editDifficulty}
                    onChange={(e) => setEditDifficulty(Number(e.target.value))}
                    className="w-full rounded-lg border border-[var(--border)] p-2.5 text-sm"
                  />
                </div>
                <div>
                  <label
                    htmlFor="edit-keyword-cpc"
                    className="mb-1 block text-xs font-bold uppercase text-[var(--muted)]"
                  >
                    CPC ($)
                  </label>
                  <input
                    id="edit-keyword-cpc"
                    type="number"
                    min="0"
                    step="0.01"
                    value={editCpc}
                    onChange={(e) => setEditCpc(Number(e.target.value))}
                    className="w-full rounded-lg border border-[var(--border)] p-2.5 text-sm"
                  />
                </div>
              </div>

              <div className="grid gap-4 sm:grid-cols-3">
                <div>
                  <label
                    htmlFor="edit-keyword-intent"
                    className="mb-1 block text-xs font-bold uppercase text-[var(--muted)]"
                  >
                    Intent
                  </label>
                  <select
                    id="edit-keyword-intent"
                    value={editIntent}
                    onChange={(e) => setEditIntent(e.target.value)}
                    className="w-full rounded-lg border border-[var(--border)] bg-white p-2.5 text-sm"
                  >
                    <option value="INFORMATIONAL">Informational</option>
                    <option value="COMMERCIAL">Commercial</option>
                    <option value="TRANSACTIONAL">Transactional</option>
                    <option value="NAVIGATIONAL">Navigational</option>
                    <option value="LOCAL">Local</option>
                    <option value="UNKNOWN">Unknown</option>
                  </select>
                </div>
                <div>
                  <label
                    htmlFor="edit-keyword-funnel"
                    className="mb-1 block text-xs font-bold uppercase text-[var(--muted)]"
                  >
                    Funnel Stage
                  </label>
                  <select
                    id="edit-keyword-funnel"
                    value={editFunnelStage}
                    onChange={(e) => setEditFunnelStage(e.target.value)}
                    className="w-full rounded-lg border border-[var(--border)] bg-white p-2.5 text-sm"
                  >
                    <option value="TOFU">TOFU</option>
                    <option value="MOFU">MOFU</option>
                    <option value="BOFU">BOFU</option>
                  </select>
                </div>
                <div>
                  <label
                    htmlFor="edit-keyword-status"
                    className="mb-1 block text-xs font-bold uppercase text-[var(--muted)]"
                  >
                    Status
                  </label>
                  <select
                    id="edit-keyword-status"
                    value={editStatus}
                    onChange={(e) => setEditStatus(e.target.value)}
                    className="w-full rounded-lg border border-[var(--border)] bg-white p-2.5 text-sm"
                  >
                    <option value="active">Active</option>
                    <option value="archived">Archived</option>
                    <option value="ignored">Ignored</option>
                  </select>
                </div>
              </div>

              {keywordMutationError && (
                <p
                  role="alert"
                  className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm font-medium text-red-800"
                >
                  {keywordMutationError}
                </p>
              )}

              <div className="mt-2 flex justify-end gap-2">
                <button
                  type="button"
                  onClick={() => {
                    setKeywordMutationError(null);
                    setKeywordToEdit(null);
                  }}
                  disabled={isPending}
                  className="rounded-lg border px-4 py-2 text-sm font-semibold hover:bg-slate-50 disabled:opacity-60"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isPending || !editKeyword.trim()}
                  className="rounded-lg bg-[var(--accent)] px-4 py-2 text-sm font-bold text-white transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {isPending ? "Saving..." : "Save changes"}
                </button>
              </div>
            </form>
          </Card>
        </div>
      )}

      {/* Keyword deletion confirmation */}
      {keywordToDelete && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
          <Card
            className="w-full max-w-lg p-6 bg-white shadow-2xl"
            role="dialog"
            aria-modal="true"
            aria-labelledby="delete-keyword-title"
          >
            <div className="flex items-start gap-3">
              <div className="rounded-full bg-red-50 p-2 text-red-700">
                <Trash2 size={20} />
              </div>
              <div>
                <h2 id="delete-keyword-title" className="text-lg font-bold">
                  Delete keyword?
                </h2>
                <p className="mt-1 text-sm text-[var(--muted)]">
                  You are deleting <strong>{keywordToDelete.keyword}</strong>.
                </p>
              </div>
            </div>

            <p className="mt-4 text-sm leading-relaxed text-slate-700">
              This removes the keyword from cluster memberships, page mappings, page keyword
              assignments, and keyword-specific opportunities. Pages and clusters are kept, but
              any primary-keyword reference to this keyword is cleared.
            </p>

            {keywordMutationError && (
              <p
                role="alert"
                className="mt-4 rounded-lg border border-red-200 bg-red-50 p-3 text-sm font-medium text-red-800"
              >
                {keywordMutationError}
              </p>
            )}

            <div className="mt-6 flex justify-end gap-2">
              <button
                type="button"
                onClick={() => {
                  setKeywordMutationError(null);
                  setKeywordToDelete(null);
                }}
                disabled={isPending}
                className="rounded-lg border px-4 py-2 text-sm font-semibold hover:bg-slate-50 disabled:opacity-60"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleDeleteKeyword}
                disabled={isPending}
                className="rounded-lg bg-red-600 px-4 py-2 text-sm font-bold text-white transition hover:bg-red-700 disabled:cursor-not-allowed disabled:opacity-60"
              >
                {isPending ? "Deleting..." : "Delete keyword"}
              </button>
            </div>
          </Card>
        </div>
      )}

      {/* Cluster deletion confirmation */}
      {clusterToDelete && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
          <Card
            className="w-full max-w-lg p-6 bg-white shadow-2xl"
            role="dialog"
            aria-modal="true"
            aria-labelledby="delete-cluster-title"
          >
            <div className="flex items-start gap-3">
              <div className="rounded-full bg-red-50 p-2 text-red-700">
                <Trash2 size={20} />
              </div>
              <div>
                <h2 id="delete-cluster-title" className="text-lg font-bold">
                  Delete cluster?
                </h2>
                <p className="mt-1 text-sm text-[var(--muted)]">
                  You are deleting <strong>{clusterToDelete.cluster_name}</strong>.
                </p>
              </div>
            </div>

            <div className="mt-4 rounded-lg border border-slate-200 bg-slate-50 p-3">
              <p className="text-[11px] font-bold uppercase text-[var(--muted)]">Cluster ID</p>
              <p className="mt-1 break-all font-mono text-xs text-slate-700">
                {clusterToDelete.id}
              </p>
            </div>

            <p className="mt-4 text-sm leading-relaxed text-slate-700">
              This removes the cluster grouping and its derived content opportunities. The
              underlying keywords are kept. Planned pages are also kept, but their cluster
              assignment is cleared.
            </p>

            {deleteClusterError && (
              <p
                role="alert"
                className="mt-4 rounded-lg border border-red-200 bg-red-50 p-3 text-sm font-medium text-red-800"
              >
                {deleteClusterError}
              </p>
            )}

            <div className="mt-6 flex justify-end gap-2">
              <button
                type="button"
                onClick={() => {
                  setDeleteClusterError(null);
                  setClusterToDelete(null);
                }}
                disabled={isPending}
                className="rounded-lg border px-4 py-2 text-sm font-semibold hover:bg-slate-50 disabled:opacity-60"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleDeleteCluster}
                disabled={isPending}
                className="rounded-lg bg-red-600 px-4 py-2 text-sm font-bold text-white transition hover:bg-red-700 disabled:cursor-not-allowed disabled:opacity-60"
              >
                {isPending ? "Deleting..." : "Delete cluster"}
              </button>
            </div>
          </Card>
        </div>
      )}
    </div>
  );
}
