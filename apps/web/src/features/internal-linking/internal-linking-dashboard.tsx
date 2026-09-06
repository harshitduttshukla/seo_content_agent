"use client";

import { useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import {
  Link2,
  CheckCircle2,
  XCircle,
  AlertCircle,
  Sparkles,
  ArrowRight,
  GitFork,
  Trash2,
  Plus,
  RefreshCw,
  Search,
  Filter,
  Layers,
  ExternalLink,
  ShieldAlert,
  ArrowUpRight,
  X,
  FileText,
} from "lucide-react";
import { Card } from "@/components/card";
import type {
  LinkOpportunity,
  PageRelationship,
  OrphanPage,
  PlannedContentPage,
} from "@/lib/api-types";
import { clientApi } from "@/lib/client-api";

interface InternalLinkingDashboardProps {
  projectId: string;
  initialOpportunities: LinkOpportunity[];
  initialRelationships: PageRelationship[];
  initialOrphans: OrphanPage[];
  availablePages: PlannedContentPage[];
}

export function InternalLinkingDashboard({
  projectId,
  initialOpportunities,
  initialRelationships,
  initialOrphans,
  availablePages,
}: InternalLinkingDashboardProps) {
  const router = useRouter();
  const [isPending, startTransition] = useTransition();

  // Active tab: opportunities | relationships | orphans
  const [activeTab, setActiveTab] = useState<"opportunities" | "relationships" | "orphans">("opportunities");

  // Filter states
  const [oppStatusFilter, setOppStatusFilter] = useState<string>("all");
  const [oppPriorityFilter, setOppPriorityFilter] = useState<string>("all");
  const [searchQuery, setSearchQuery] = useState("");

  // Modals
  const [showAddRelModal, setShowAddRelModal] = useState(false);
  const [notification, setNotification] = useState<{ type: "success" | "error"; message: string } | null>(null);

  // Form for creating page relationship
  const [relForm, setRelForm] = useState({
    source_page_id: availablePages[0]?.id || "",
    target_page_id: availablePages[1]?.id || "",
    relationship_type: "PILLAR_CLUSTER",
    anchor_text: "",
    reason: "",
    priority: 1,
  });

  // Action: Run Algorithmic Link Analysis
  const handleRunAnalysis = async () => {
    startTransition(async () => {
      try {
        const result = await clientApi<{ items: LinkOpportunity[] }>(
          `/projects/${projectId}/link-opportunities/analyze`,
          { method: "POST" }
        );
        setNotification({
          type: "success",
          message: `Link analysis complete! Found ${result.items.length} proposed link opportunities.`,
        });
        router.refresh();
      } catch (err) {
        setNotification({
          type: "error",
          message: err instanceof Error ? err.message : "Failed to run link analysis",
        });
      }
    });
  };

  // Action: Approve Link Opportunity
  const handleApproveOpportunity = async (opp: LinkOpportunity) => {
    startTransition(async () => {
      try {
        await clientApi(`/projects/${projectId}/link-opportunities/${opp.id}/approve`, {
          method: "POST",
        });
        setNotification({ type: "success", message: "Link opportunity approved!" });
        router.refresh();
      } catch (err) {
        setNotification({
          type: "error",
          message: err instanceof Error ? err.message : "Failed to approve link",
        });
      }
    });
  };

  // Action: Reject Link Opportunity
  const handleRejectOpportunity = async (opp: LinkOpportunity) => {
    startTransition(async () => {
      try {
        await clientApi(`/projects/${projectId}/link-opportunities/${opp.id}/reject`, {
          method: "POST",
        });
        setNotification({ type: "success", message: "Link opportunity rejected." });
        router.refresh();
      } catch (err) {
        setNotification({
          type: "error",
          message: err instanceof Error ? err.message : "Failed to reject link",
        });
      }
    });
  };

  // Action: Create Relationship
  const handleCreateRelationship = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!relForm.source_page_id || !relForm.target_page_id) return;
    if (relForm.source_page_id === relForm.target_page_id) {
      alert("Source page and target page must be distinct.");
      return;
    }

    startTransition(async () => {
      try {
        await clientApi(`/projects/${projectId}/page-relationships`, {
          method: "POST",
          body: JSON.stringify({
            source_page_id: relForm.source_page_id,
            target_page_id: relForm.target_page_id,
            relationship_type: relForm.relationship_type,
            anchor_text: relForm.anchor_text || "Learn more",
            reason: relForm.reason || "Hierarchical context link",
            priority: Number(relForm.priority) || 1,
          }),
        });
        setShowAddRelModal(false);
        setNotification({ type: "success", message: "Page relationship established!" });
        router.refresh();
      } catch (err) {
        setNotification({
          type: "error",
          message: err instanceof Error ? err.message : "Failed to create relationship",
        });
      }
    });
  };

  // Action: Delete Relationship
  const handleDeleteRelationship = async (relId: string) => {
    if (!confirm("Remove this architectural relationship?")) return;

    startTransition(async () => {
      try {
        await clientApi(`/projects/${projectId}/page-relationships/${relId}`, {
          method: "DELETE",
        });
        setNotification({ type: "success", message: "Relationship removed." });
        router.refresh();
      } catch (err) {
        setNotification({
          type: "error",
          message: err instanceof Error ? err.message : "Failed to delete relationship",
        });
      }
    });
  };

  // Filter opportunities
  const filteredOpportunities = initialOpportunities.filter((opp) => {
    if (oppStatusFilter !== "all" && opp.status !== oppStatusFilter) return false;
    if (oppPriorityFilter !== "all" && opp.priority !== Number(oppPriorityFilter)) return false;
    if (searchQuery) {
      const q = searchQuery.toLowerCase();
      const matchAnchor = opp.anchor_suggestion?.toLowerCase().includes(q);
      const matchReason = opp.reason?.toLowerCase().includes(q);
      if (!matchAnchor && !matchReason) return false;
    }
    return true;
  });

  // Calculate metrics
  const proposedOpps = initialOpportunities.filter((o) => o.status === "proposed").length;
  const approvedOpps = initialOpportunities.filter((o) => o.status === "approved").length;
  const totalRels = initialRelationships.length;
  const totalOrphans = initialOrphans.length;

  return (
    <div className="space-y-6">
      {/* Toast Notification */}
      {notification && (
        <div
          className={`flex items-center justify-between rounded-xl p-4 text-sm font-medium shadow-sm transition ${
            notification.type === "success"
              ? "bg-emerald-50 text-emerald-800 border border-emerald-200"
              : "bg-rose-50 text-rose-800 border border-rose-200"
          }`}
        >
          <div className="flex items-center gap-2">
            {notification.type === "success" ? (
              <CheckCircle2 size={18} className="text-emerald-600" />
            ) : (
              <AlertCircle size={18} className="text-rose-600" />
            )}
            <span>{notification.message}</span>
          </div>
          <button onClick={() => setNotification(null)} className="text-gray-400 hover:text-gray-700 ml-4">
            <X size={16} />
          </button>
        </div>
      )}

      {/* Metrics Strip */}
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        <Card className="p-4 border border-[var(--border)] bg-white shadow-xs">
          <p className="text-xs font-semibold uppercase tracking-wider text-[var(--muted)]">Proposed Links</p>
          <p className="mt-1 text-2xl font-bold text-[var(--ink)]">{proposedOpps}</p>
          <p className="text-xs text-[var(--muted)] mt-1">Pending review</p>
        </Card>

        <Card className="p-4 border border-emerald-200 bg-emerald-50/40 shadow-xs">
          <p className="text-xs font-semibold uppercase tracking-wider text-emerald-700">Approved Links</p>
          <p className="mt-1 text-2xl font-bold text-emerald-900">{approvedOpps}</p>
          <p className="text-xs text-emerald-700 mt-1">Governed architecture</p>
        </Card>

        <Card className="p-4 border border-indigo-200 bg-indigo-50/40 shadow-xs">
          <p className="text-xs font-semibold uppercase tracking-wider text-indigo-700">Relationships</p>
          <p className="mt-1 text-2xl font-bold text-indigo-900">{totalRels}</p>
          <p className="text-xs text-indigo-700 mt-1">Pillar & cluster hierarchy</p>
        </Card>

        <Card
          className={`p-4 shadow-xs border ${
            totalOrphans > 0 ? "border-rose-200 bg-rose-50/40" : "border-gray-200 bg-white"
          }`}
        >
          <div className="flex items-center justify-between">
            <p
              className={`text-xs font-semibold uppercase tracking-wider ${
                totalOrphans > 0 ? "text-rose-700" : "text-[var(--muted)]"
              }`}
            >
              Orphan Pages
            </p>
            {totalOrphans > 0 && <ShieldAlert size={15} className="text-rose-600" />}
          </div>
          <p className={`mt-1 text-2xl font-bold ${totalOrphans > 0 ? "text-rose-900" : "text-[var(--ink)]"}`}>
            {totalOrphans}
          </p>
          <p className={`text-xs mt-1 ${totalOrphans > 0 ? "text-rose-700" : "text-[var(--muted)]"}`}>
            0 incoming internal links
          </p>
        </Card>
      </div>

      {/* Main Tabs and Actions */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-[var(--border)] pb-3">
        <div className="flex items-center gap-2">
          <button
            onClick={() => setActiveTab("opportunities")}
            className={`px-4 py-2 rounded-lg text-sm font-semibold transition ${
              activeTab === "opportunities"
                ? "bg-[var(--accent)] text-white shadow-xs"
                : "text-[var(--muted)] hover:text-[var(--ink)] hover:bg-gray-100"
            }`}
          >
            Link Opportunities ({initialOpportunities.length})
          </button>
          <button
            onClick={() => setActiveTab("relationships")}
            className={`px-4 py-2 rounded-lg text-sm font-semibold transition ${
              activeTab === "relationships"
                ? "bg-[var(--accent)] text-white shadow-xs"
                : "text-[var(--muted)] hover:text-[var(--ink)] hover:bg-gray-100"
            }`}
          >
            Page Relationships ({initialRelationships.length})
          </button>
          <button
            onClick={() => setActiveTab("orphans")}
            className={`px-4 py-2 rounded-lg text-sm font-semibold transition ${
              activeTab === "orphans"
                ? "bg-[var(--accent)] text-white shadow-xs"
                : "text-[var(--muted)] hover:text-[var(--ink)] hover:bg-gray-100"
            }`}
          >
            Orphan Pages ({initialOrphans.length})
          </button>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={handleRunAnalysis}
            disabled={isPending}
            className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg border border-[var(--border)] bg-white text-xs font-semibold text-[var(--ink)] hover:bg-gray-50 shadow-2xs disabled:opacity-50"
          >
            <Sparkles size={14} className="text-[var(--accent)]" />
            {isPending ? "Analyzing..." : "Analyze Link Opportunities"}
          </button>

          <button
            onClick={() => setShowAddRelModal(true)}
            className="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg bg-[var(--accent)] text-white text-xs font-semibold hover:bg-opacity-90 shadow-2xs"
          >
            <Plus size={15} />
            Add Relationship
          </button>
        </div>
      </div>

      {/* TAB 1: LINK OPPORTUNITIES */}
      {activeTab === "opportunities" && (
        <div className="space-y-4">
          {/* Filters and search */}
          <div className="flex flex-wrap items-center gap-3 bg-white p-3 rounded-xl border border-[var(--border)]">
            <div className="relative flex-1 min-w-[200px]">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" size={16} />
              <input
                type="text"
                placeholder="Search by anchor text, snippet, or reason..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full pl-9 pr-3 py-1.5 text-xs rounded-md border border-[var(--border)] focus:outline-none focus:ring-1 focus:ring-[var(--accent)]"
              />
            </div>

            <div className="flex items-center gap-1.5 text-xs text-[var(--muted)]">
              <Filter size={14} />
              <select
                value={oppStatusFilter}
                onChange={(e) => setOppStatusFilter(e.target.value)}
                className="rounded-md border border-[var(--border)] px-2.5 py-1.5 text-xs text-[var(--ink)] bg-white"
              >
                <option value="all">All Statuses</option>
                <option value="proposed">Proposed</option>
                <option value="approved">Approved</option>
                <option value="rejected">Rejected</option>
              </select>
            </div>

            <select
              value={oppPriorityFilter}
              onChange={(e) => setOppPriorityFilter(e.target.value)}
              className="rounded-md border border-[var(--border)] px-2.5 py-1.5 text-xs text-[var(--ink)] bg-white"
            >
              <option value="all">All Priorities</option>
              <option value="high">High Priority</option>
              <option value="medium">Medium Priority</option>
              <option value="low">Low Priority</option>
            </select>
          </div>

          {/* Opportunities Cards */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {filteredOpportunities.length === 0 ? (
              <div className="col-span-full py-12 text-center text-[var(--muted)] bg-white rounded-xl border border-[var(--border)]">
                <Link2 size={32} className="mx-auto mb-2 opacity-40 text-gray-400" />
                <p className="font-semibold text-sm">No link opportunities match your filters</p>
                <p className="text-xs mt-1">Click "Analyze Link Opportunities" to run the algorithmic linking engine.</p>
              </div>
            ) : (
              filteredOpportunities.map((opp) => (
                <Card
                  key={opp.id}
                  className={`p-5 border flex flex-col justify-between transition ${
                    opp.status === "approved"
                      ? "border-emerald-200 bg-emerald-50/20"
                      : opp.status === "rejected"
                      ? "border-gray-200 bg-gray-50/40 opacity-70"
                      : "border-[var(--border)] bg-white shadow-xs"
                  }`}
                >
                  <div>
                    {/* Header: Score and status */}
                    <div className="flex items-center justify-between gap-2 mb-3">
                      <div className="flex items-center gap-1.5">
                        <span
                          className={`inline-flex items-center px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider ${
                            opp.priority === 1
                              ? "bg-rose-100 text-rose-800"
                              : opp.priority === 2
                              ? "bg-amber-100 text-amber-800"
                              : "bg-blue-100 text-blue-800"
                          }`}
                        >
                          P{opp.priority} Priority
                        </span>
                        <span className="text-xs font-bold text-[var(--accent)] bg-[var(--accent)]/10 px-2 py-0.5 rounded">
                          Score: {Math.round(opp.confidence * 100)}/100
                        </span>
                      </div>

                      <span
                        className={`inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold ${
                          opp.status === "approved"
                            ? "bg-emerald-100 text-emerald-800"
                            : opp.status === "rejected"
                            ? "bg-rose-100 text-rose-800"
                            : "bg-gray-100 text-gray-700"
                        }`}
                      >
                        {opp.status}
                      </span>
                    </div>

                    {/* Source -> Target Mapping */}
                    <div className="p-3 rounded-lg bg-gray-50/80 border border-gray-200 space-y-1.5 mb-3">
                      <div className="flex items-center gap-2 text-xs">
                        <span className="font-bold text-gray-500 uppercase text-[10px] w-12">From:</span>
                        <span className="font-semibold text-gray-900 truncate">
                          {opp.source_page_title || "Source Page"}
                        </span>
                      </div>
                      <div className="flex items-center gap-2 text-xs">
                        <span className="font-bold text-gray-500 uppercase text-[10px] w-12">To:</span>
                        <span className="font-semibold text-indigo-700 truncate">
                          {opp.target_page_title || "Target Page"}
                        </span>
                      </div>
                    </div>

                    {/* Anchor text badge */}
                    <div className="mb-2">
                      <p className="text-[10px] font-bold uppercase tracking-wider text-gray-500 mb-1">
                        Recommended Anchor Text
                      </p>
                      <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-md text-xs font-mono font-bold bg-indigo-50 text-indigo-800 border border-indigo-200">
                        <Link2 size={12} />
                        {opp.anchor_suggestion}
                      </span>
                    </div>

                    {/* Context / Reason */}
                    {opp.reason && (
                      <p className="text-xs text-gray-600 italic bg-gray-50 p-2.5 rounded-md border border-gray-100 mb-2 leading-relaxed">
                        "{opp.reason}"
                      </p>
                    )}

                    {/* Rationale */}
                    <p className="text-xs text-[var(--muted)]">
                      <strong className="text-gray-700">Rationale: </strong>
                      {opp.reason || "High semantic and topical relevance match."}
                    </p>
                  </div>

                  {/* Actions */}
                  {opp.status === "proposed" && (
                    <div className="mt-4 pt-3 border-t border-[var(--border)] flex items-center justify-end gap-2">
                      <button
                        onClick={() => handleRejectOpportunity(opp)}
                        disabled={isPending}
                        className="inline-flex items-center gap-1 px-3 py-1.5 rounded-lg border border-gray-300 text-xs font-semibold text-gray-700 hover:bg-gray-50 disabled:opacity-50"
                      >
                        <XCircle size={14} className="text-rose-500" />
                        Reject
                      </button>
                      <button
                        onClick={() => handleApproveOpportunity(opp)}
                        disabled={isPending}
                        className="inline-flex items-center gap-1 px-4 py-1.5 rounded-lg bg-emerald-600 text-white text-xs font-semibold hover:bg-emerald-700 disabled:opacity-50 transition"
                      >
                        <CheckCircle2 size={14} />
                        Approve Link
                      </button>
                    </div>
                  )}
                </Card>
              ))
            )}
          </div>
        </div>
      )}

      {/* TAB 2: PAGE RELATIONSHIPS */}
      {activeTab === "relationships" && (
        <div className="space-y-4">
          <div className="rounded-xl border border-[var(--border)] bg-white p-4 shadow-xs">
            <h3 className="font-semibold text-sm text-[var(--ink)]">Architectural Page Relationships</h3>
            <p className="text-xs text-[var(--muted)] mt-0.5">
              Explicit parent-child, pillar-to-cluster, supporting, and related hierarchies that govern how internal links must flow.
            </p>
          </div>

          <div className="rounded-xl border border-[var(--border)] bg-white overflow-hidden shadow-xs">
            <table className="w-full text-left text-xs border-collapse">
              <thead>
                <tr className="border-b border-[var(--border)] bg-gray-50/80 text-[var(--muted)] font-semibold uppercase tracking-wider">
                  <th className="py-3 px-4">Source Page</th>
                  <th className="py-3 px-4">Relationship</th>
                  <th className="py-3 px-4">Target Page</th>
                  <th className="py-3 px-4">Type</th>
                  <th className="py-3 px-4 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--border)]">
                {initialRelationships.length === 0 ? (
                  <tr>
                    <td colSpan={5} className="py-12 text-center text-[var(--muted)]">
                      <GitFork size={32} className="mx-auto mb-2 opacity-40 text-gray-400" />
                      <p className="font-semibold text-sm">No page relationships defined yet</p>
                      <p className="text-xs mt-1">Create relationships to structure your pillar and cluster silos.</p>
                    </td>
                  </tr>
                ) : (
                  initialRelationships.map((rel) => (
                    <tr key={rel.id} className="hover:bg-gray-50/50 transition">
                      <td className="py-3 px-4 font-semibold text-gray-900">
                        {rel.source_page_title || rel.source_page_id}
                      </td>

                      <td className="py-3 px-4">
                        <span
                          className={`inline-flex items-center px-2 py-0.5 rounded text-[11px] font-semibold ${
                            rel.relationship_type === "pillar_cluster"
                              ? "bg-purple-100 text-purple-800"
                              : rel.relationship_type === "parent_child"
                              ? "bg-blue-100 text-blue-800"
                              : "bg-gray-100 text-gray-800"
                          }`}
                        >
                          {rel.relationship_type.replace("_", " ")}
                        </span>
                      </td>

                      <td className="py-3 px-4 font-semibold text-indigo-700">
                        {rel.target_page_title || rel.target_page_id}
                      </td>

                      <td className="py-3 px-4 text-gray-500 font-mono text-[11px]">
                        {rel.anchor_text ? `"${rel.anchor_text}"` : "Contextual link"}
                      </td>

                      <td className="py-3 px-4 text-right">
                        <button
                          onClick={() => handleDeleteRelationship(rel.id)}
                          className="text-gray-400 hover:text-rose-600 p-1"
                          title="Delete relationship"
                        >
                          <Trash2 size={14} />
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

      {/* TAB 3: ORPHAN PAGES */}
      {activeTab === "orphans" && (
        <div className="space-y-4">
          <div className="rounded-xl border border-rose-200 bg-rose-50/40 p-4 shadow-xs">
            <div className="flex items-center gap-2">
              <ShieldAlert size={18} className="text-rose-600" />
              <h3 className="font-bold text-sm text-rose-900">Orphan Pages Audit</h3>
            </div>
            <p className="text-xs text-rose-800 mt-1">
              These pages have zero incoming internal links. Search crawlers and visitors cannot easily discover them, severely hindering indexation and search ranking potential.
            </p>
          </div>

          <div className="rounded-xl border border-[var(--border)] bg-white overflow-hidden shadow-xs">
            <table className="w-full text-left text-xs border-collapse">
              <thead>
                <tr className="border-b border-[var(--border)] bg-gray-50/80 text-[var(--muted)] font-semibold uppercase tracking-wider">
                  <th className="py-3 px-4">Page Title & URL</th>
                  <th className="py-3 px-4">Architecture Type</th>
                  <th className="py-3 px-4">Incoming Links</th>
                  <th className="py-3 px-4">Target Keyword</th>
                  <th className="py-3 px-4 text-right">Remediation</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--border)]">
                {initialOrphans.length === 0 ? (
                  <tr>
                    <td colSpan={5} className="py-12 text-center text-[var(--muted)]">
                      <CheckCircle2 size={32} className="mx-auto mb-2 text-emerald-500" />
                      <p className="font-semibold text-sm text-emerald-900">Zero Orphan Pages!</p>
                      <p className="text-xs mt-1 text-gray-500">
                        Every single page in this project has healthy inbound links from other pages.
                      </p>
                    </td>
                  </tr>
                ) : (
                  initialOrphans.map((orphan) => (
                    <tr key={orphan.page_id} className="hover:bg-gray-50/50 transition">
                      <td className="py-3 px-4">
                        <div className="flex flex-col">
                          <span className="font-semibold text-gray-900">{orphan.title}</span>
                          <span className="font-mono text-gray-500 text-[11px] truncate max-w-xs">{orphan.url}</span>
                        </div>
                      </td>

                      <td className="py-3 px-4">
                        <span className="inline-flex px-2 py-0.5 rounded text-[11px] font-medium bg-gray-100 text-gray-800">
                          {orphan.page_type.replace("_", " ")}
                        </span>
                      </td>

                      <td className="py-3 px-4 font-bold text-rose-600">
                        {orphan.inbound_links} links
                      </td>

                      <td className="py-3 px-4 text-gray-600 font-mono">
                        {orphan.primary_keyword || "—"}
                      </td>

                      <td className="py-3 px-4 text-right">
                        <button
                          onClick={() => {
                            setRelForm((prev) => ({
                              ...prev,
                              target_page_id: orphan.page_id,
                            }));
                            setShowAddRelModal(true);
                          }}
                          className="inline-flex items-center gap-1 px-3 py-1.5 rounded-md bg-[var(--accent)] text-white text-xs font-semibold hover:bg-opacity-90 transition"
                        >
                          <Plus size={13} />
                          Add Inbound Link
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

      {/* MODAL: ADD PAGE RELATIONSHIP */}
      {showAddRelModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-xs p-4">
          <div className="bg-white rounded-2xl shadow-xl border border-[var(--border)] w-full max-w-md overflow-hidden animate-in fade-in zoom-in-95 duration-150">
            <div className="flex items-center justify-between px-6 py-4 border-b border-[var(--border)]">
              <h3 className="font-bold text-base text-[var(--ink)]">Add Page Relationship</h3>
              <button onClick={() => setShowAddRelModal(false)} className="text-gray-400 hover:text-gray-700 p-1">
                <X size={18} />
              </button>
            </div>

            <form onSubmit={handleCreateRelationship} className="p-6 space-y-4">
              <div>
                <label className="block text-xs font-bold text-gray-700 mb-1">Source Page (From)</label>
                <select
                  value={relForm.source_page_id}
                  onChange={(e) => setRelForm((prev) => ({ ...prev, source_page_id: e.target.value }))}
                  required
                  className="w-full text-xs rounded-lg border border-[var(--border)] px-3 py-2 bg-white"
                >
                  <option value="">Select source page...</option>
                  {availablePages.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.title} (/{p.slug})
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-xs font-bold text-gray-700 mb-1">Target Page (To)</label>
                <select
                  value={relForm.target_page_id}
                  onChange={(e) => setRelForm((prev) => ({ ...prev, target_page_id: e.target.value }))}
                  required
                  className="w-full text-xs rounded-lg border border-[var(--border)] px-3 py-2 bg-white"
                >
                  <option value="">Select target page...</option>
                  {availablePages.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.title} (/{p.slug})
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-xs font-bold text-gray-700 mb-1">Relationship Type</label>
                <select
                  value={relForm.relationship_type}
                  onChange={(e) => setRelForm((prev) => ({ ...prev, relationship_type: e.target.value }))}
                  className="w-full text-xs rounded-lg border border-[var(--border)] px-3 py-2 bg-white"
                >
                  <option value="PILLAR_CLUSTER">Pillar to Cluster</option>
                  <option value="PARENT_CHILD">Parent to Child</option>
                  <option value="SUPPORTS">Supporting Article</option>
                  <option value="RELATED">Related Topic</option>
                </select>
              </div>

              <div>
                <label className="block text-xs font-bold text-gray-700 mb-1">Anchor Text (Optional)</label>
                <input
                  type="text"
                  placeholder="e.g. read our in-depth architecture guide"
                  value={relForm.anchor_text}
                  onChange={(e) => setRelForm((prev) => ({ ...prev, anchor_text: e.target.value }))}
                  className="w-full text-xs rounded-lg border border-[var(--border)] px-3 py-2"
                />
              </div>

              <div>
                <label className="block text-xs font-bold text-gray-700 mb-1">Priority (1 = Highest)</label>
                <select
                  value={relForm.priority}
                  onChange={(e) => setRelForm((prev) => ({ ...prev, priority: Number(e.target.value) }))}
                  className="w-full text-xs rounded-lg border border-[var(--border)] px-3 py-2 bg-white"
                >
                  <option value={1}>1 - Highest Priority</option>
                  <option value={2}>2 - Medium Priority</option>
                  <option value={3}>3 - Low Priority</option>
                </select>
              </div>

              <div className="pt-4 border-t border-[var(--border)] flex justify-end gap-2">
                <button
                  type="button"
                  onClick={() => setShowAddRelModal(false)}
                  className="px-4 py-2 rounded-lg border border-[var(--border)] text-xs font-semibold text-gray-700 hover:bg-gray-50"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isPending}
                  className="px-5 py-2 rounded-lg bg-[var(--accent)] text-white text-xs font-semibold hover:bg-opacity-90 disabled:opacity-50"
                >
                  {isPending ? "Establishing..." : "Establish Relationship"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
