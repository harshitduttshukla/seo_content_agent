"use client";

import { useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import {
  Layers,
  Sparkles,
  GitFork,
  CheckCircle2,
  XCircle,
  Plus,
  ArrowRight,
  RefreshCw,
} from "lucide-react";
import { Card } from "@/components/card";
import type {
  ContentArchitectureGraph,
  ContentOpportunity,
  ContentPillar,
  KeywordPageMapping,
  Topic,
} from "@/lib/api-types";
import { clientApi } from "@/lib/client-api";

export function ArchitectureDashboard({
  projectId,
  websiteId,
  initialPillars,
  initialTopics,
  initialOpportunities,
  initialMappings,
  initialGraph,
}: {
  projectId: string;
  websiteId?: string;
  initialPillars: ContentPillar[];
  initialTopics: Topic[];
  initialOpportunities: ContentOpportunity[];
  initialMappings: KeywordPageMapping[];
  initialGraph: ContentArchitectureGraph;
}) {
  const router = useRouter();
  const [isPending, startTransition] = useTransition();
  const [activeTab, setActiveTab] = useState<"pillars" | "opportunities" | "mappings" | "graph">("pillars");

  // Modals
  const [showPillarModal, setShowPillarModal] = useState(false);
  const [showTopicModal, setShowTopicModal] = useState(false);

  // Forms
  const [pillarName, setPillarName] = useState("");
  const [pillarDesc, setPillarDesc] = useState("");
  const [pillarGoal, setPillarGoal] = useState("");

  const [topicName, setTopicName] = useState("");
  const [topicDesc, setTopicDesc] = useState("");
  const [selectedPillarId, setSelectedPillarId] = useState<string>(initialPillars[0]?.id || "");

  const [notification, setNotification] = useState<string | null>(null);

  const handleCreatePillar = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!pillarName.trim()) return;

    startTransition(async () => {
      try {
        await clientApi(`/projects/${projectId}/content-pillars`, {
          method: "POST",
          body: JSON.stringify({
            name: pillarName.trim(),
            description: pillarDesc.trim(),
            business_goal: pillarGoal.trim(),
          }),
        });
        setShowPillarModal(false);
        setPillarName("");
        setPillarDesc("");
        setPillarGoal("");
        setNotification("Content pillar created!");
        router.refresh();
      } catch (err) {
        alert(err instanceof Error ? err.message : "Failed to create pillar");
      }
    });
  };

  const handleCreateTopic = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!topicName.trim()) return;

    startTransition(async () => {
      try {
        await clientApi(`/projects/${projectId}/topics`, {
          method: "POST",
          body: JSON.stringify({
            name: topicName.trim(),
            description: topicDesc.trim(),
            pillar_id: selectedPillarId || null,
          }),
        });
        setShowTopicModal(false);
        setTopicName("");
        setTopicDesc("");
        setNotification("Topic created!");
        router.refresh();
      } catch (err) {
        alert(err instanceof Error ? err.message : "Failed to create topic");
      }
    });
  };

  const handleAnalyzeMappings = async () => {
    if (!websiteId) {
      alert("Please connect a website first.");
      return;
    }
    startTransition(async () => {
      try {
        await clientApi(`/projects/${projectId}/keyword-mappings/analyze?website_id=${websiteId}`, {
          method: "POST",
        });
        setNotification("Keyword-to-page mapping and content gap analysis complete!");
        setActiveTab("opportunities");
        router.refresh();
      } catch (err) {
        alert(err instanceof Error ? err.message : "Failed to analyze mappings");
      }
    });
  };

  const handleUpdateOpportunityStatus = async (oppId: string, newStatus: string) => {
    startTransition(async () => {
      try {
        await clientApi(`/projects/${projectId}/content-opportunities/${oppId}`, {
          method: "PUT",
          body: JSON.stringify({ status: newStatus }),
        });
        setNotification(`Opportunity marked as ${newStatus}`);
        router.refresh();
      } catch (err) {
        alert(err instanceof Error ? err.message : "Failed to update status");
      }
    });
  };

  return (
    <div className="grid gap-6">
      {notification && (
        <div className="flex items-center gap-2 rounded-lg bg-emerald-50 p-3 text-sm font-medium text-emerald-800 border border-emerald-200">
          <CheckCircle2 size={16} /> {notification}
        </div>
      )}

      {/* Tabs & Action bar */}
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div className="flex flex-wrap rounded-lg bg-slate-100 p-1">
          <button
            type="button"
            onClick={() => setActiveTab("pillars")}
            className={`rounded-md px-3.5 py-1.5 text-xs font-bold transition ${
              activeTab === "pillars" ? "bg-white text-[var(--accent)] shadow-sm" : "text-[var(--muted)] hover:text-[var(--ink)]"
            }`}
          >
            Pillars & Topics ({initialPillars.length})
          </button>
          <button
            type="button"
            onClick={() => setActiveTab("opportunities")}
            className={`rounded-md px-3.5 py-1.5 text-xs font-bold transition ${
              activeTab === "opportunities" ? "bg-white text-[var(--accent)] shadow-sm" : "text-[var(--muted)] hover:text-[var(--ink)]"
            }`}
          >
            Content Gaps & Opportunities ({initialOpportunities.length})
          </button>
          <button
            type="button"
            onClick={() => setActiveTab("mappings")}
            className={`rounded-md px-3.5 py-1.5 text-xs font-bold transition ${
              activeTab === "mappings" ? "bg-white text-[var(--accent)] shadow-sm" : "text-[var(--muted)] hover:text-[var(--ink)]"
            }`}
          >
            Page Mappings ({initialMappings.length})
          </button>
          <button
            type="button"
            onClick={() => setActiveTab("graph")}
            className={`rounded-md px-3.5 py-1.5 text-xs font-bold transition ${
              activeTab === "graph" ? "bg-white text-[var(--accent)] shadow-sm" : "text-[var(--muted)] hover:text-[var(--ink)]"
            }`}
          >
            Architecture Graph ({initialGraph.nodes.length} Nodes)
          </button>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          {activeTab === "pillars" && (
            <>
              <button
                type="button"
                onClick={() => setShowPillarModal(true)}
                className="inline-flex items-center gap-1.5 rounded-lg border border-[var(--border)] bg-white px-3 py-1.5 text-xs font-bold hover:bg-slate-50 transition"
              >
                <Plus size={14} /> Add Pillar
              </button>
              <button
                type="button"
                onClick={() => setShowTopicModal(true)}
                className="inline-flex items-center gap-1.5 rounded-lg border border-[var(--border)] bg-white px-3 py-1.5 text-xs font-bold hover:bg-slate-50 transition"
              >
                <Plus size={14} /> Add Topic
              </button>
            </>
          )}
          {activeTab === "mappings" && (
            <button
              type="button"
              onClick={handleAnalyzeMappings}
              disabled={isPending}
              className="inline-flex items-center gap-1.5 rounded-lg bg-[var(--accent)] px-3.5 py-1.5 text-xs font-bold text-white hover:opacity-90 shadow-sm transition"
            >
              <RefreshCw size={14} className={isPending ? "animate-spin" : ""} /> Analyze Website Mappings
            </button>
          )}
        </div>
      </div>

      {/* Tab 1: Pillars & Topics */}
      {activeTab === "pillars" && (
        <div className="grid gap-6">
          {initialPillars.length === 0 ? (
            <Card className="p-8 text-center text-sm text-[var(--muted)]">
              No content pillars created yet. Click <strong>"Add Pillar"</strong> above to organize your content architecture into core strategic pillars.
            </Card>
          ) : (
            <div className="grid gap-4 md:grid-cols-2">
              {initialPillars.map((pillar) => {
                const childTopics = initialTopics.filter((t) => t.pillar_id === pillar.id);
                return (
                  <Card key={pillar.id} className="p-5">
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <span className="text-[10px] font-bold uppercase tracking-wider text-[var(--accent)]">
                          Strategic Pillar
                        </span>
                        <h3 className="text-lg font-bold text-[var(--ink)] mt-0.5">{pillar.name}</h3>
                      </div>
                      <span className="rounded-full bg-slate-100 px-2.5 py-0.5 text-xs font-bold text-slate-700">
                        Priority {pillar.priority}
                      </span>
                    </div>

                    <p className="mt-2 text-xs text-[var(--muted)]">{pillar.description || "No description"}</p>
                    {pillar.business_goal && (
                      <p className="mt-1 text-xs font-semibold text-indigo-700">Goal: {pillar.business_goal}</p>
                    )}

                    <div className="mt-4 pt-3 border-t border-[var(--border)]">
                      <p className="text-xs font-bold text-[var(--muted)] mb-2">
                        Topics under this pillar ({childTopics.length})
                      </p>
                      <div className="grid gap-1.5">
                        {childTopics.length === 0 ? (
                          <p className="text-xs text-slate-400 italic">No topics assigned yet</p>
                        ) : (
                          childTopics.map((topic) => (
                            <div
                              key={topic.id}
                              className="flex items-center justify-between p-2 rounded-lg bg-slate-50 border border-[var(--border)] text-xs"
                            >
                              <span className="font-semibold text-[var(--ink)]">{topic.name}</span>
                              <span className="text-[var(--muted)]">{topic.cluster_count} clusters</span>
                            </div>
                          ))
                        )}
                      </div>
                    </div>
                  </Card>
                );
              })}
            </div>
          )}
        </div>
      )}

      {/* Tab 2: Content Opportunities & Gaps */}
      {activeTab === "opportunities" && (
        <Card className="p-0 overflow-hidden">
          <div className="p-4 bg-slate-50/50 border-b border-[var(--border)]">
            <h2 className="text-sm font-bold text-[var(--ink)]">Target Page Recommendations & Gaps</h2>
            <p className="text-xs text-[var(--muted)] mt-0.5">
              Governed recommendations for creating new pages or expanding existing content to cover high-value clusters.
            </p>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="border-b border-[var(--border)] bg-slate-100/70 text-xs font-bold uppercase text-[var(--muted)]">
                <tr>
                  <th className="px-4 py-3">Cluster / Keyword</th>
                  <th className="px-4 py-3">Recommended Action</th>
                  <th className="px-4 py-3">Priority</th>
                  <th className="px-4 py-3">Rationale</th>
                  <th className="px-4 py-3">Status</th>
                  <th className="px-4 py-3 text-right">Human Review</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--border)]">
                {initialOpportunities.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="px-4 py-8 text-center text-sm text-[var(--muted)]">
                      No content opportunities generated yet. Run <strong>"Analyze Website Mappings"</strong> under the Page Mappings tab.
                    </td>
                  </tr>
                ) : (
                  initialOpportunities.map((opp) => (
                    <tr key={opp.id} className="hover:bg-slate-50/70 transition">
                      <td className="px-4 py-3">
                        <span className="font-bold text-[var(--ink)] block">{opp.cluster_name || opp.keyword || "Unassigned"}</span>
                        {opp.existing_page_url && (
                          <span className="text-xs text-[var(--muted)] font-mono truncate block max-w-xs">{opp.existing_page_url}</span>
                        )}
                      </td>
                      <td className="px-4 py-3">
                        <span className={`inline-block rounded-full px-2.5 py-0.5 text-xs font-bold ${
                          opp.action === "NEW_PAGE" ? "bg-emerald-100 text-emerald-800" : "bg-indigo-100 text-indigo-800"
                        }`}>
                          {opp.action}
                        </span>
                      </td>
                      <td className="px-4 py-3 font-bold text-xs text-[var(--accent)]">{opp.priority}</td>
                      <td className="px-4 py-3 text-xs text-slate-700 max-w-md">{opp.reason}</td>
                      <td className="px-4 py-3">
                        <span className="text-xs font-semibold capitalize">{opp.status}</span>
                      </td>
                      <td className="px-4 py-3 text-right">
                        <div className="inline-flex items-center gap-1.5">
                          <button
                            type="button"
                            onClick={() => handleUpdateOpportunityStatus(opp.id, "approved")}
                            className="rounded p-1 text-emerald-600 hover:bg-emerald-50"
                            title="Approve opportunity"
                          >
                            <CheckCircle2 size={18} />
                          </button>
                          <button
                            type="button"
                            onClick={() => handleUpdateOpportunityStatus(opp.id, "rejected")}
                            className="rounded p-1 text-rose-600 hover:bg-rose-50"
                            title="Reject opportunity"
                          >
                            <XCircle size={18} />
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
      )}

      {/* Tab 3: Keyword-Page Mappings */}
      {activeTab === "mappings" && (
        <Card className="p-0 overflow-hidden">
          <div className="p-4 bg-slate-50/50 border-b border-[var(--border)] flex justify-between items-center">
            <div>
              <h2 className="text-sm font-bold text-[var(--ink)]">Keyword-to-Page Mappings</h2>
              <p className="text-xs text-[var(--muted)] mt-0.5">
                Deterministic mapping connecting your target keywords to crawled live website URLs.
              </p>
            </div>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="border-b border-[var(--border)] bg-slate-100/70 text-xs font-bold uppercase text-[var(--muted)]">
                <tr>
                  <th className="px-4 py-3">Keyword</th>
                  <th className="px-4 py-3">Search Volume</th>
                  <th className="px-4 py-3">Target Page</th>
                  <th className="px-4 py-3">Mapping Type</th>
                  <th className="px-4 py-3">Confidence</th>
                  <th className="px-4 py-3">Rationale</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--border)]">
                {initialMappings.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="px-4 py-8 text-center text-sm text-[var(--muted)]">
                      No mappings analyzed yet. Click <strong>"Analyze Website Mappings"</strong> above.
                    </td>
                  </tr>
                ) : (
                  initialMappings.map((m) => (
                    <tr key={m.id} className="hover:bg-slate-50/70 transition">
                      <td className="px-4 py-3 font-semibold text-[var(--ink)]">{m.keyword}</td>
                      <td className="px-4 py-3 font-mono text-xs">{m.search_volume.toLocaleString()}</td>
                      <td className="px-4 py-3 max-w-xs">
                        {m.page_url ? (
                          <div className="truncate text-xs">
                            <span className="font-semibold block truncate">{m.page_title || "Untitled Page"}</span>
                            <span className="font-mono text-[var(--muted)] truncate block">{m.page_url}</span>
                          </div>
                        ) : (
                          <span className="text-xs text-rose-600 font-semibold">No Target Page (Gap)</span>
                        )}
                      </td>
                      <td className="px-4 py-3">
                        <span className={`inline-block rounded px-2 py-0.5 text-[11px] font-bold ${
                          m.mapping_type === "PRIMARY_TARGET"
                            ? "bg-emerald-100 text-emerald-800"
                            : m.mapping_type === "SECONDARY_TARGET"
                            ? "bg-indigo-100 text-indigo-800"
                            : "bg-rose-100 text-rose-800"
                        }`}>
                          {m.mapping_type}
                        </span>
                      </td>
                      <td className="px-4 py-3 font-mono text-xs">{Math.round(m.confidence * 100)}%</td>
                      <td className="px-4 py-3 text-xs text-slate-600 max-w-sm">{m.rationale}</td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </Card>
      )}

      {/* Tab 4: Architecture Graph Inspector */}
      {activeTab === "graph" && (
        <Card className="p-6">
          <div className="mb-4">
            <h2 className="text-base font-bold text-[var(--ink)]">Content Architecture Graph Projection</h2>
            <p className="text-xs text-[var(--muted)] mt-0.5">
              Structured representation ready for React Flow interactive canvas: Pillars → Topics → Clusters → Pages.
            </p>
          </div>

          <div className="grid gap-3">
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
              <div className="p-3 rounded-lg bg-indigo-50 border border-indigo-100">
                <span className="text-xs text-indigo-700 font-bold uppercase">Pillars</span>
                <p className="text-2xl font-bold text-indigo-950 mt-1">
                  {initialGraph.nodes.filter((n) => n.type === "pillar").length}
                </p>
              </div>
              <div className="p-3 rounded-lg bg-emerald-50 border border-emerald-100">
                <span className="text-xs text-emerald-700 font-bold uppercase">Topics</span>
                <p className="text-2xl font-bold text-emerald-950 mt-1">
                  {initialGraph.nodes.filter((n) => n.type === "topic").length}
                </p>
              </div>
              <div className="p-3 rounded-lg bg-amber-50 border border-amber-100">
                <span className="text-xs text-amber-700 font-bold uppercase">Clusters</span>
                <p className="text-2xl font-bold text-amber-950 mt-1">
                  {initialGraph.nodes.filter((n) => n.type === "cluster").length}
                </p>
              </div>
              <div className="p-3 rounded-lg bg-slate-100 border border-slate-200">
                <span className="text-xs text-slate-700 font-bold uppercase">Target Pages</span>
                <p className="text-2xl font-bold text-slate-950 mt-1">
                  {initialGraph.nodes.filter((n) => n.type === "page").length}
                </p>
              </div>
            </div>

            <div className="mt-4 p-4 rounded-lg bg-slate-900 text-slate-100 font-mono text-xs overflow-x-auto max-h-72">
              <pre>{JSON.stringify(initialGraph, null, 2)}</pre>
            </div>
          </div>
        </Card>
      )}

      {/* Add Pillar Modal */}
      {showPillarModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
          <Card className="w-full max-w-md p-6 bg-white shadow-2xl">
            <h2 className="text-lg font-bold mb-4">Add Content Pillar</h2>
            <form onSubmit={handleCreatePillar} className="grid gap-4">
              <div>
                <label className="block text-xs font-bold uppercase text-[var(--muted)] mb-1">Pillar Name</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Technical SEO Guide"
                  className="w-full rounded-lg border border-[var(--border)] p-2.5 text-sm"
                  value={pillarName}
                  onChange={(e) => setPillarName(e.target.value)}
                />
              </div>
              <div>
                <label className="block text-xs font-bold uppercase text-[var(--muted)] mb-1">Description</label>
                <textarea
                  rows={2}
                  placeholder="What scope does this pillar cover?"
                  className="w-full rounded-lg border border-[var(--border)] p-2 text-sm"
                  value={pillarDesc}
                  onChange={(e) => setPillarDesc(e.target.value)}
                />
              </div>
              <div>
                <label className="block text-xs font-bold uppercase text-[var(--muted)] mb-1">Business Goal</label>
                <input
                  type="text"
                  placeholder="e.g. Drive organic enterprise demo requests"
                  className="w-full rounded-lg border border-[var(--border)] p-2 text-sm"
                  value={pillarGoal}
                  onChange={(e) => setPillarGoal(e.target.value)}
                />
              </div>
              <div className="flex justify-end gap-2 mt-2">
                <button
                  type="button"
                  onClick={() => setShowPillarModal(false)}
                  className="rounded-lg border px-4 py-2 text-sm font-semibold hover:bg-slate-50"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isPending}
                  className="rounded-lg bg-[var(--accent)] px-4 py-2 text-sm font-bold text-white hover:opacity-90"
                >
                  Create Pillar
                </button>
              </div>
            </form>
          </Card>
        </div>
      )}

      {/* Add Topic Modal */}
      {showTopicModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
          <Card className="w-full max-w-md p-6 bg-white shadow-2xl">
            <h2 className="text-lg font-bold mb-4">Add Topic</h2>
            <form onSubmit={handleCreateTopic} className="grid gap-4">
              <div>
                <label className="block text-xs font-bold uppercase text-[var(--muted)] mb-1">Parent Pillar</label>
                <select
                  className="w-full rounded-lg border border-[var(--border)] p-2.5 text-sm"
                  value={selectedPillarId}
                  onChange={(e) => setSelectedPillarId(e.target.value)}
                >
                  {initialPillars.map((p) => (
                    <option key={p.id} value={p.id}>{p.name}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-xs font-bold uppercase text-[var(--muted)] mb-1">Topic Name</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Core Web Vitals"
                  className="w-full rounded-lg border border-[var(--border)] p-2.5 text-sm"
                  value={topicName}
                  onChange={(e) => setTopicName(e.target.value)}
                />
              </div>
              <div>
                <label className="block text-xs font-bold uppercase text-[var(--muted)] mb-1">Description</label>
                <textarea
                  rows={2}
                  placeholder="Topic details and objectives"
                  className="w-full rounded-lg border border-[var(--border)] p-2 text-sm"
                  value={topicDesc}
                  onChange={(e) => setTopicDesc(e.target.value)}
                />
              </div>
              <div className="flex justify-end gap-2 mt-2">
                <button
                  type="button"
                  onClick={() => setShowTopicModal(false)}
                  className="rounded-lg border px-4 py-2 text-sm font-semibold hover:bg-slate-50"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isPending}
                  className="rounded-lg bg-[var(--accent)] px-4 py-2 text-sm font-bold text-white hover:opacity-90"
                >
                  Create Topic
                </button>
              </div>
            </form>
          </Card>
        </div>
      )}
    </div>
  );
}
