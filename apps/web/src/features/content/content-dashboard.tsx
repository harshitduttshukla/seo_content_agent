"use client";

import { useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import {
  FileText,
  Plus,
  Search,
  Filter,
  Sparkles,
  ExternalLink,
  Edit2,
  Trash2,
  KeyRound,
  BookOpen,
  ArrowUpRight,
  Layers,
  CheckCircle2,
  Clock,
  Archive,
  Eye,
  X,
  AlertCircle,
  Tag,
} from "lucide-react";
import { Card } from "@/components/card";
import type {
  PlannedContentPage,
  ContentPillar,
  Topic,
  ContentOpportunity,
  ContentPageSummary,
  Keyword,
  PageKeyword,
} from "@/lib/api-types";
import { clientApi } from "@/lib/client-api";

interface ContentDashboardProps {
  projectId: string;
  websiteId?: string;
  initialPages: PlannedContentPage[];
  initialPillars: ContentPillar[];
  initialTopics: Topic[];
  initialOpportunities: ContentOpportunity[];
  initialCrawledPages?: ContentPageSummary[];
  availableKeywords?: Keyword[];
}

const contentTypeOptions = [
  { value: "PILLAR_PAGE", label: "Pillar Page" },
  { value: "CLUSTER_PAGE", label: "Cluster Page" },
  { value: "SUPPORTING_PAGE", label: "Supporting Page" },
  { value: "LANDING_PAGE", label: "Landing Page" },
  { value: "SERVICE_PAGE", label: "Service Page" },
  { value: "PRODUCT_PAGE", label: "Product Page" },
  { value: "BLOG_POST", label: "Blog Post" },
  { value: "GUIDE", label: "Guide" },
  { value: "COMPARISON", label: "Comparison" },
  { value: "FAQ", label: "FAQ" },
] as const;

const plannedStatusOptions = [
  { value: "PROPOSED", label: "Proposed" },
  { value: "PLANNED", label: "Planned" },
  { value: "APPROVED", label: "Approved / Ready to Write" },
  { value: "IN_PROGRESS", label: "In Progress" },
  { value: "DRAFT", label: "Draft" },
  { value: "PUBLISHED", label: "Published" },
  { value: "ARCHIVED", label: "Archived" },
] as const;

export function ContentDashboard({
  projectId,
  websiteId,
  initialPages,
  initialPillars,
  initialTopics,
  initialOpportunities,
  initialCrawledPages = [],
  availableKeywords = [],
}: ContentDashboardProps) {
  const router = useRouter();
  const [isPending, startTransition] = useTransition();

  // Active Tab: planned | existing | opportunities
  const [activeTab, setActiveTab] = useState<"planned" | "existing" | "opportunities">("planned");

  // Filter & Search states
  const [searchQuery, setSearchQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [typeFilter, setTypeFilter] = useState<string>("all");
  const [pillarFilter, setPillarFilter] = useState<string>("all");

  // Modals & Drawers
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [showEditModal, setShowEditModal] = useState(false);
  const [showKeywordModal, setShowKeywordModal] = useState(false);
  const [showConvertModal, setShowConvertModal] = useState(false);
  const [selectedPage, setSelectedPage] = useState<PlannedContentPage | null>(null);
  const [selectedOpportunity, setSelectedOpportunity] = useState<ContentOpportunity | null>(null);

  // Keyword management state
  const [pageKeywords, setPageKeywords] = useState<PageKeyword[]>([]);
  const [selectedKeywordId, setSelectedKeywordId] = useState<string>("");
  const [keywordRole, setKeywordRole] = useState<"primary" | "secondary" | "lsi" | "question">("primary");
  const [loadingKeywords, setLoadingKeywords] = useState(false);

  // Create/Edit form state
  const [formData, setFormData] = useState({
    title: "",
    slug: "",
    url: "",
    page_type: "PLANNED",
    content_type: "CLUSTER_PAGE",
    target_word_count_min: 1200,
    target_word_count_max: 2000,
    search_intent: "INFORMATIONAL",
    notes: "",
    pillar_id: "",
    topic_id: "",
    status: "PLANNED",
    existing_page_id: "",
  });

  const [notification, setNotification] = useState<{ type: "success" | "error"; message: string } | null>(null);

  const resetForm = () => {
    setFormData({
      title: "",
      slug: "",
      url: "",
      page_type: "PLANNED",
      content_type: "CLUSTER_PAGE",
      target_word_count_min: 1200,
      target_word_count_max: 2000,
      search_intent: "INFORMATIONAL",
      notes: "",
      pillar_id: initialPillars[0]?.id || "",
      topic_id: "",
      status: "PLANNED",
      existing_page_id: "",
    });
  };

  const handleCreatePage = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!formData.title.trim() || !formData.slug.trim()) return;

    startTransition(async () => {
      try {
        await clientApi(`/projects/${projectId}/content-pages`, {
          method: "POST",
          body: JSON.stringify({
            title: formData.title.trim(),
            slug: formData.slug.trim().toLowerCase(),
            url: formData.url,
            page_type: formData.existing_page_id ? "EXISTING" : "PLANNED",
            content_type: formData.content_type,
            status: "PLANNED",
            primary_keyword: formData.title.trim(),
            intent: formData.search_intent,
            pillar_id: formData.pillar_id || null,
            topic_id: formData.topic_id || null,
            existing_page_id: formData.existing_page_id || null,
            website_id: websiteId || null,
          }),
        });
        setShowCreateModal(false);
        resetForm();
        setNotification({ type: "success", message: "Planned content page created successfully!" });
        router.refresh();
      } catch (err) {
        setNotification({ type: "error", message: err instanceof Error ? err.message : "Failed to create page" });
      }
    });
  };

  const handleUpdatePage = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedPage) return;

    startTransition(async () => {
      try {
        await clientApi(`/content-pages/${selectedPage.id}`, {
          method: "PUT",
          body: JSON.stringify({
            title: formData.title.trim(),
            slug: formData.slug.trim().toLowerCase(),
            page_type: formData.page_type,
            content_type: formData.content_type,
            status: formData.status,
            intent: formData.search_intent,
            pillar_id: formData.pillar_id || null,
            topic_id: formData.topic_id || null,
          }),
        });
        setShowEditModal(false);
        setSelectedPage(null);
        setNotification({ type: "success", message: "Page updated successfully!" });
        router.refresh();
      } catch (err) {
        setNotification({ type: "error", message: err instanceof Error ? err.message : "Failed to update page" });
      }
    });
  };

  const handleDeletePage = async (page: PlannedContentPage) => {
    if (!confirm(`Are you sure you want to delete planned page "${page.title}"?`)) return;

    startTransition(async () => {
      try {
        await clientApi(`/content-pages/${page.id}`, {
          method: "DELETE",
        });
        setNotification({ type: "success", message: "Planned page deleted." });
        router.refresh();
      } catch (err) {
        setNotification({ type: "error", message: err instanceof Error ? err.message : "Failed to delete page" });
      }
    });
  };

  const openEditModal = (page: PlannedContentPage) => {
    setSelectedPage(page);
    setFormData({
      title: page.title,
      slug: page.slug,
      url: page.url,
      page_type: page.page_type,
      content_type: page.content_type,
      target_word_count_min: 1200,
      target_word_count_max: 2000,
      search_intent: page.intent || "INFORMATIONAL",
      notes: "",
      pillar_id: page.pillar_id || "",
      topic_id: page.topic_id || "",
      status: page.status,
      existing_page_id: page.existing_page_id || "",
    });
    setShowEditModal(true);
  };

  const openKeywordModal = async (page: PlannedContentPage) => {
    setSelectedPage(page);
    setShowKeywordModal(true);
    setLoadingKeywords(true);
    try {
      const kwList = await clientApi<{ items: PageKeyword[] }>(`/content-pages/${page.id}/keywords`);
      setPageKeywords(kwList?.items || []);
    } catch {
      setPageKeywords([]);
    } finally {
      setLoadingKeywords(false);
    }
  };

  const handleAssignKeyword = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedPage || !selectedKeywordId) return;

    startTransition(async () => {
      try {
        await clientApi(`/content-pages/${selectedPage.id}/keywords`, {
          method: "POST",
          body: JSON.stringify({
            keyword_id: selectedKeywordId,
            keyword_role: keywordRole.toUpperCase(),
          }),
        });
        // Refresh keywords list
        const kwList = await clientApi<{ items: PageKeyword[] }>(`/content-pages/${selectedPage.id}/keywords`);
        setPageKeywords(kwList?.items || []);
        setSelectedKeywordId("");
        setNotification({ type: "success", message: "Keyword assigned to page." });
        router.refresh();
      } catch (err) {
        setNotification({ type: "error", message: err instanceof Error ? err.message : "Failed to assign keyword" });
      }
    });
  };

  const handleRemoveKeyword = async (keywordId: string) => {
    if (!selectedPage) return;

    startTransition(async () => {
      try {
        await clientApi(`/content-pages/${selectedPage.id}/keywords/${keywordId}`, {
          method: "DELETE",
        });
        setPageKeywords((prev) => prev.filter((k) => k.keyword_id !== keywordId));
        setNotification({ type: "success", message: "Keyword removed from page." });
        router.refresh();
      } catch (err) {
        setNotification({ type: "error", message: err instanceof Error ? err.message : "Failed to remove keyword" });
      }
    });
  };

  const handleConvertOpportunity = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedOpportunity) return;

    startTransition(async () => {
      try {
        const oppTitle = selectedOpportunity.cluster_name || selectedOpportunity.keyword || "New Content Page";
        const oppSlug = (selectedOpportunity.keyword || selectedOpportunity.cluster_name || "new-page")
          .toLowerCase()
          .replace(/[^a-z0-9]+/g, "-")
          .replace(/^-+|-+$/g, "");
        await clientApi(`/projects/${projectId}/content-opportunities/${selectedOpportunity.id}/convert-to-page`, {
          method: "POST",
          body: JSON.stringify({
            title: oppTitle,
            slug: oppSlug,
            content_type: formData.content_type,
          }),
        });
        setShowConvertModal(false);
        setSelectedOpportunity(null);
        setNotification({ type: "success", message: "Content opportunity converted to planned page!" });
        router.refresh();
      } catch (err) {
        setNotification({ type: "error", message: err instanceof Error ? err.message : "Failed to convert opportunity" });
      }
    });
  };

  // Filtered pages
  const filteredPages = initialPages.filter((page) => {
    if (searchQuery) {
      const q = searchQuery.toLowerCase();
      const matchTitle = page.title.toLowerCase().includes(q);
      const matchSlug = page.slug.toLowerCase().includes(q);
      const matchKw = page.primary_keyword?.toLowerCase().includes(q);
      if (!matchTitle && !matchSlug && !matchKw) return false;
    }
    if (statusFilter !== "all" && page.status !== statusFilter) return false;
    if (typeFilter !== "all" && page.content_type !== typeFilter) return false;
    if (pillarFilter !== "all" && page.pillar_id !== pillarFilter) return false;
    return true;
  });

  // Calculate stats
  const totalPages = initialPages.length;
  const readyPages = initialPages.filter((p) => p.status === "APPROVED").length;
  const writingPages = initialPages.filter((p) => p.status === "IN_PROGRESS").length;
  const publishedPages = initialPages.filter((p) => p.status === "PUBLISHED").length;
  const draftPages = initialPages.filter((p) =>
    ["PROPOSED", "PLANNED", "DRAFT"].includes(p.status)
  ).length;

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
          <button
            onClick={() => setNotification(null)}
            className="text-gray-400 hover:text-gray-700 ml-4"
          >
            <X size={16} />
          </button>
        </div>
      )}

      {/* Metric Summary Cards */}
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-5">
        <Card className="p-4 border border-[var(--border)] bg-white shadow-xs">
          <p className="text-xs font-semibold uppercase tracking-wider text-[var(--muted)]">Total Planned</p>
          <p className="mt-1 text-2xl font-bold text-[var(--ink)]">{totalPages}</p>
          <p className="text-xs text-[var(--muted)] mt-1">Across all pillars</p>
        </Card>
        <Card className="p-4 border border-amber-200 bg-amber-50/40 shadow-xs">
          <p className="text-xs font-semibold uppercase tracking-wider text-amber-700">Drafts</p>
          <p className="mt-1 text-2xl font-bold text-amber-900">{draftPages}</p>
          <p className="text-xs text-amber-700 mt-1">Under architecture</p>
        </Card>
        <Card className="p-4 border border-blue-200 bg-blue-50/40 shadow-xs">
          <p className="text-xs font-semibold uppercase tracking-wider text-blue-700">Ready to Write</p>
          <p className="mt-1 text-2xl font-bold text-blue-900">{readyPages}</p>
          <p className="text-xs text-blue-700 mt-1">SEO guide ready</p>
        </Card>
        <Card className="p-4 border border-indigo-200 bg-indigo-50/40 shadow-xs">
          <p className="text-xs font-semibold uppercase tracking-wider text-indigo-700">In Production</p>
          <p className="mt-1 text-2xl font-bold text-indigo-900">{writingPages}</p>
          <p className="text-xs text-indigo-700 mt-1">Being drafted</p>
        </Card>
        <Card className="p-4 border border-emerald-200 bg-emerald-50/40 shadow-xs">
          <p className="text-xs font-semibold uppercase tracking-wider text-emerald-700">Published</p>
          <p className="mt-1 text-2xl font-bold text-emerald-900">{publishedPages}</p>
          <p className="text-xs text-emerald-700 mt-1">Live on website</p>
        </Card>
      </div>

      {/* Main Tabs and Actions */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-[var(--border)] pb-3">
        <div className="flex items-center gap-2">
          <button
            onClick={() => setActiveTab("planned")}
            className={`px-4 py-2 rounded-lg text-sm font-semibold transition ${
              activeTab === "planned"
                ? "bg-[var(--accent)] text-white shadow-xs"
                : "text-[var(--muted)] hover:text-[var(--ink)] hover:bg-gray-100"
            }`}
          >
            Planned Pages ({initialPages.length})
          </button>
          <button
            onClick={() => setActiveTab("existing")}
            className={`px-4 py-2 rounded-lg text-sm font-semibold transition ${
              activeTab === "existing"
                ? "bg-[var(--accent)] text-white shadow-xs"
                : "text-[var(--muted)] hover:text-[var(--ink)] hover:bg-gray-100"
            }`}
          >
            Existing Live Pages ({initialCrawledPages.length})
          </button>
          <button
            onClick={() => setActiveTab("opportunities")}
            className={`px-4 py-2 rounded-lg text-sm font-semibold transition ${
              activeTab === "opportunities"
                ? "bg-[var(--accent)] text-white shadow-xs"
                : "text-[var(--muted)] hover:text-[var(--ink)] hover:bg-gray-100"
            }`}
          >
            Opportunities ({initialOpportunities.length})
          </button>
        </div>

        <div className="flex items-center gap-2">
          <Link
            href={`/projects/${projectId}/content-map`}
            className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg border border-[var(--border)] bg-white text-xs font-semibold text-[var(--ink)] hover:bg-gray-50 shadow-2xs"
          >
            <Layers size={14} />
            Visual Content Map
          </Link>
          <button
            onClick={() => {
              resetForm();
              setShowCreateModal(true);
            }}
            className="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg bg-[var(--accent)] text-white text-xs font-semibold hover:bg-opacity-90 shadow-2xs"
          >
            <Plus size={15} />
            Plan New Page
          </button>
        </div>
      </div>

      {/* TAB 1: PLANNED PAGES */}
      {activeTab === "planned" && (
        <div className="space-y-4">
          {/* Filters and search */}
          <div className="flex flex-wrap items-center gap-3 bg-white p-3 rounded-xl border border-[var(--border)]">
            <div className="relative flex-1 min-w-[200px]">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" size={16} />
              <input
                type="text"
                placeholder="Search planned pages by title, slug, or notes..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full pl-9 pr-3 py-1.5 text-xs rounded-md border border-[var(--border)] focus:outline-none focus:ring-1 focus:ring-[var(--accent)]"
              />
            </div>

            {/* Status filter */}
            <div className="flex items-center gap-1.5 text-xs text-[var(--muted)]">
              <Filter size={14} />
              <select
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value)}
                className="rounded-md border border-[var(--border)] px-2.5 py-1.5 text-xs text-[var(--ink)] bg-white"
              >
                <option value="all">All Statuses</option>
                {plannedStatusOptions.map((status) => (
                  <option key={status.value} value={status.value}>
                    {status.label}
                  </option>
                ))}
              </select>
            </div>

            {/* Type filter */}
            <select
              value={typeFilter}
              onChange={(e) => setTypeFilter(e.target.value)}
              className="rounded-md border border-[var(--border)] px-2.5 py-1.5 text-xs text-[var(--ink)] bg-white"
            >
              <option value="all">All Page Types</option>
              {contentTypeOptions.map((type) => (
                <option key={type.value} value={type.value}>
                  {type.label}
                </option>
              ))}
            </select>

            {/* Pillar filter */}
            <select
              value={pillarFilter}
              onChange={(e) => setPillarFilter(e.target.value)}
              className="rounded-md border border-[var(--border)] px-2.5 py-1.5 text-xs text-[var(--ink)] bg-white"
            >
              <option value="all">All Content Pillars</option>
              {initialPillars.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
            </select>
          </div>

          {/* Planned Pages Table */}
          <div className="rounded-xl border border-[var(--border)] bg-white overflow-hidden shadow-xs">
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs border-collapse">
                <thead>
                  <tr className="border-b border-[var(--border)] bg-gray-50/80 text-[var(--muted)] font-semibold uppercase tracking-wider">
                    <th className="py-3 px-4">Page Title & Slug</th>
                    <th className="py-3 px-4">Architecture Type</th>
                    <th className="py-3 px-4">Primary Keyword</th>
                    <th className="py-3 px-4">Search Intent</th>
                    <th className="py-3 px-4">Status</th>
                    <th className="py-3 px-4 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[var(--border)]">
                  {filteredPages.length === 0 ? (
                    <tr>
                      <td colSpan={6} className="py-12 text-center text-[var(--muted)]">
                        <FileText size={32} className="mx-auto mb-2 opacity-40 text-gray-400" />
                        <p className="font-semibold text-sm">No planned pages match your filter</p>
                        <p className="text-xs mt-1">Create your first planned page or convert opportunities.</p>
                      </td>
                    </tr>
                  ) : (
                    filteredPages.map((page) => (
                      <tr key={page.id} className="hover:bg-gray-50/50 transition">
                        <td className="py-3 px-4">
                          <div className="flex flex-col">
                            <span className="font-semibold text-[var(--ink)] text-sm">{page.title}</span>
                            <span className="font-mono text-gray-500 text-[11px] mt-0.5">/{page.slug}</span>
                            {page.existing_page_id && (
                              <span className="inline-flex items-center gap-1 text-[10px] text-indigo-600 font-medium mt-1">
                                <ArrowUpRight size={10} />
                                Existing Page Optimization
                              </span>
                            )}
                          </div>
                        </td>

                        <td className="py-3 px-4">
                          <span
                            className={`inline-flex items-center px-2 py-0.5 rounded text-[11px] font-medium ${
                              page.content_type === "PILLAR_PAGE"
                                ? "bg-purple-100 text-purple-800"
                                : page.content_type === "CLUSTER_PAGE"
                                ? "bg-blue-100 text-blue-800"
                                : page.content_type === "SUPPORTING_PAGE"
                                ? "bg-emerald-100 text-emerald-800"
                                : "bg-gray-100 text-gray-800"
                            }`}
                          >
                            {page.content_type.replaceAll("_", " ").toLowerCase()}
                          </span>
                        </td>

                        <td className="py-3 px-4">
                          <span className="font-mono text-xs font-semibold text-gray-800">
                            {page.primary_keyword || "—"}
                          </span>
                        </td>

                        <td className="py-3 px-4">
                          <span className="capitalize text-gray-600 font-medium">
                            {page.intent || "Informational"}
                          </span>
                        </td>

                        <td className="py-3 px-4">
                          <span
                            className={`inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-semibold ${
                              page.status === "APPROVED"
                                ? "bg-blue-50 text-blue-700 border border-blue-200"
                                : page.status === "IN_PROGRESS"
                                ? "bg-amber-50 text-amber-700 border border-amber-200"
                                : page.status === "PUBLISHED"
                                ? "bg-emerald-50 text-emerald-700 border border-emerald-200"
                                : "bg-gray-100 text-gray-700 border border-gray-200"
                            }`}
                          >
                            {page.status.replaceAll("_", " ").toLowerCase()}
                          </span>
                        </td>

                        <td className="py-3 px-4 text-right">
                          <div className="flex items-center justify-end gap-1.5">
                            <Link
                              href={`/projects/${projectId}/content/seo-guide/${page.id}`}
                              className="inline-flex items-center gap-1 px-2.5 py-1.5 rounded-md bg-indigo-50 text-indigo-700 hover:bg-indigo-100 text-xs font-semibold transition"
                              title="Open SEO Guide & Outline"
                            >
                              <BookOpen size={13} />
                              SEO Guide
                            </Link>

                            <button
                              onClick={() => openKeywordModal(page)}
                              className="inline-flex items-center gap-1 p-1.5 rounded-md text-gray-500 hover:text-gray-900 hover:bg-gray-100 transition"
                              title="Assign Target Keywords"
                            >
                              <KeyRound size={15} />
                            </button>

                            <button
                              onClick={() => openEditModal(page)}
                              className="inline-flex items-center gap-1 p-1.5 rounded-md text-gray-500 hover:text-gray-900 hover:bg-gray-100 transition"
                              title="Edit Page Details"
                            >
                              <Edit2 size={14} />
                            </button>

                            <button
                              onClick={() => handleDeletePage(page)}
                              className="inline-flex items-center gap-1 p-1.5 rounded-md text-rose-500 hover:text-rose-700 hover:bg-rose-50 transition"
                              title="Delete Page"
                            >
                              <Trash2 size={14} />
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* TAB 2: EXISTING CRAWLED PAGES INVENTORY */}
      {activeTab === "existing" && (
        <div className="space-y-4">
          <div className="rounded-xl border border-[var(--border)] bg-white p-4 shadow-xs">
            <h3 className="font-semibold text-sm text-[var(--ink)]">Live Website Inventory</h3>
            <p className="text-xs text-[var(--muted)] mt-0.5">
              Pages discovered during website crawls. Convert any live page into a planned optimization project to build an SEO Guide and update internal links.
            </p>
          </div>

          <div className="rounded-xl border border-[var(--border)] bg-white overflow-hidden shadow-xs">
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs border-collapse">
                <thead>
                  <tr className="border-b border-[var(--border)] bg-gray-50/80 text-[var(--muted)] font-semibold uppercase tracking-wider">
                    <th className="py-3 px-4">Title & URL</th>
                    <th className="py-3 px-4">HTTP Status</th>
                    <th className="py-3 px-4">Word Count</th>
                    <th className="py-3 px-4">Inbound Links</th>
                    <th className="py-3 px-4 text-right">Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[var(--border)]">
                  {initialCrawledPages.length === 0 ? (
                    <tr>
                      <td colSpan={5} className="py-12 text-center text-[var(--muted)]">
                        <ExternalLink size={32} className="mx-auto mb-2 opacity-40 text-gray-400" />
                        <p className="font-semibold text-sm">No live pages crawled yet</p>
                        <p className="text-xs mt-1">Run a website crawl in the Website section to import existing pages.</p>
                      </td>
                    </tr>
                  ) : (
                    initialCrawledPages.map((cpage) => {
                      const alreadyPlanned = initialPages.find((p) => p.existing_page_id === cpage.id);
                      return (
                        <tr key={cpage.id} className="hover:bg-gray-50/50 transition">
                          <td className="py-3 px-4">
                            <div className="flex flex-col">
                              <span className="font-semibold text-[var(--ink)] text-sm">{cpage.title || "Untitled Page"}</span>
                              <span className="font-mono text-gray-500 text-[11px] mt-0.5 truncate max-w-md">{cpage.url}</span>
                            </div>
                          </td>

                          <td className="py-3 px-4">
                            <span className="inline-flex px-2 py-0.5 rounded text-[11px] font-semibold bg-emerald-50 text-emerald-700">
                              {cpage.http_status || 200} OK
                            </span>
                          </td>

                          <td className="py-3 px-4 font-medium text-gray-700">
                            {cpage.word_count ? `${cpage.word_count.toLocaleString()} words` : "—"}
                          </td>

                          <td className="py-3 px-4 font-medium text-gray-700 capitalize">
                            {cpage.content_status || "Crawled"}
                          </td>

                          <td className="py-3 px-4 text-right">
                            {alreadyPlanned ? (
                              <Link
                                href={`/projects/${projectId}/content/seo-guide/${alreadyPlanned.id}`}
                                className="inline-flex items-center gap-1 px-3 py-1.5 rounded-md bg-gray-100 text-gray-700 hover:bg-gray-200 text-xs font-semibold transition"
                              >
                                View Planned Guide
                              </Link>
                            ) : (
                              <button
                                onClick={() => {
                                  resetForm();
                                  const slug = cpage.normalized_url
                                    .replace(/^https?:\/\/[^\/]+/, "")
                                    .replace(/^\/+|\/+$/g, "");
                                  setFormData((prev) => ({
                                    ...prev,
                                    title: cpage.title || "Optimized Page",
                                    slug: slug || "home-optimization",
                                    url: cpage.url,
                                    page_type: "EXISTING",
                                    existing_page_id: cpage.id,
                                    notes: `Targeting existing live URL: ${cpage.url}`,
                                  }));
                                  setShowCreateModal(true);
                                }}
                                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-[var(--accent)] text-white hover:bg-opacity-90 text-xs font-semibold transition"
                              >
                                <Sparkles size={13} />
                                Plan Optimization
                              </button>
                            )}
                          </td>
                        </tr>
                      );
                    })
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* TAB 3: CONTENT OPPORTUNITIES */}
      {activeTab === "opportunities" && (
        <div className="space-y-4">
          <div className="rounded-xl border border-[var(--border)] bg-white p-4 shadow-xs">
            <h3 className="font-semibold text-sm text-[var(--ink)]">Discovered Content Opportunities</h3>
            <p className="text-xs text-[var(--muted)] mt-0.5">
              Algorithmically discovered topic gaps and keyword clusters from Phase 3. One click converts them directly into a planned content page with target specifications.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {initialOpportunities.length === 0 ? (
              <div className="col-span-full py-12 text-center text-[var(--muted)]">
                <Sparkles size={32} className="mx-auto mb-2 opacity-40 text-gray-400" />
                <p className="font-semibold text-sm">No content opportunities available</p>
                <p className="text-xs mt-1">Run keyword clustering and architecture discovery in Strategy & Keywords.</p>
              </div>
            ) : (
              initialOpportunities.map((opp) => (
                <Card key={opp.id} className="p-4 border border-[var(--border)] bg-white flex flex-col justify-between">
                  <div>
                    <div className="flex items-start justify-between gap-2">
                      <span className="inline-flex px-2 py-0.5 rounded text-[10px] font-semibold uppercase tracking-wider bg-amber-50 text-amber-800 border border-amber-200">
                        {opp.action.replace("_", " ")}
                      </span>
                      <span className="text-xs font-bold text-[var(--accent)]">
                        Value: {opp.business_value_score ?? 85}/100
                      </span>
                    </div>

                    <h4 className="font-bold text-sm text-[var(--ink)] mt-2">
                      {opp.cluster_name || opp.keyword || "Content Opportunity"}
                    </h4>
                    <p className="text-xs text-[var(--muted)] mt-1 line-clamp-2">
                      {opp.reason || "Strategic opportunity targeting high intent search queries."}
                    </p>

                    {opp.keyword && (
                      <div className="mt-3 flex flex-wrap gap-1">
                        <span className="text-[10px] bg-gray-100 text-gray-700 px-1.5 py-0.5 rounded font-mono">
                          {opp.keyword}
                        </span>
                      </div>
                    )}
                  </div>

                  <div className="mt-4 pt-3 border-t border-[var(--border)] flex items-center justify-between">
                    <span className="text-xs text-gray-500 capitalize">{opp.status}</span>
                    <button
                      onClick={() => {
                        setSelectedOpportunity(opp);
                        setShowConvertModal(true);
                      }}
                      className="inline-flex items-center gap-1 px-3 py-1.5 rounded-md bg-[var(--accent)] text-white text-xs font-semibold hover:bg-opacity-90 transition"
                    >
                      <Plus size={13} />
                      Convert to Page
                    </button>
                  </div>
                </Card>
              ))
            )}
          </div>
        </div>
      )}

      {/* MODAL: CREATE PLANNED PAGE */}
      {showCreateModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-xs p-4">
          <div className="bg-white rounded-2xl shadow-xl border border-[var(--border)] w-full max-w-lg overflow-hidden animate-in fade-in zoom-in-95 duration-150">
            <div className="flex items-center justify-between px-6 py-4 border-b border-[var(--border)]">
              <h3 className="font-bold text-base text-[var(--ink)]">Plan New Content Page</h3>
              <button
                onClick={() => setShowCreateModal(false)}
                className="text-gray-400 hover:text-gray-700 p-1 rounded-md"
              >
                <X size={18} />
              </button>
            </div>

            <form onSubmit={handleCreatePage} className="p-6 space-y-4 max-h-[80vh] overflow-y-auto">
              <div>
                <label className="block text-xs font-bold text-gray-700 mb-1">Page Title *</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. The Complete Guide to Cloud Security Architecture"
                  value={formData.title}
                  onChange={(e) => {
                    const title = e.target.value;
                    const slug = title
                      .toLowerCase()
                      .replace(/[^a-z0-9]+/g, "-")
                      .replace(/^-+|-+$/g, "");
                    setFormData((prev) => ({ ...prev, title, slug }));
                  }}
                  className="w-full text-xs rounded-lg border border-[var(--border)] px-3 py-2 text-[var(--ink)] focus:ring-1 focus:ring-[var(--accent)]"
                />
              </div>

              <div>
                <label className="block text-xs font-bold text-gray-700 mb-1">URL Slug *</label>
                <div className="flex items-center rounded-lg border border-[var(--border)] px-3 py-2 bg-gray-50 focus-within:bg-white focus-within:ring-1 focus-within:ring-[var(--accent)]">
                  <span className="text-xs text-gray-400 font-mono">/</span>
                  <input
                    type="text"
                    required
                    placeholder="cloud-security-architecture-guide"
                    value={formData.slug}
                    onChange={(e) => setFormData((prev) => ({ ...prev, slug: e.target.value }))}
                    className="w-full text-xs bg-transparent border-0 p-0 focus:outline-none font-mono"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-bold text-gray-700 mb-1">Architecture Page Type</label>
                  <select
                    value={formData.page_type}
                    onChange={(e) => setFormData((prev) => ({ ...prev, page_type: e.target.value }))}
                    className="w-full text-xs rounded-lg border border-[var(--border)] px-3 py-2 bg-white"
                  >
                    <option value="pillar_page">Pillar Page</option>
                    <option value="cluster_page">Cluster Page</option>
                    <option value="supporting_page">Supporting Page</option>
                    <option value="blog_post">Blog Post</option>
                    <option value="landing_page">Landing Page</option>
                    <option value="glossary">Glossary</option>
                  </select>
                </div>

                <div>
                  <label className="block text-xs font-bold text-gray-700 mb-1">Content Format</label>
                  <select
                    value={formData.content_type}
                    onChange={(e) => setFormData((prev) => ({ ...prev, content_type: e.target.value }))}
                    className="w-full text-xs rounded-lg border border-[var(--border)] px-3 py-2 bg-white"
                  >
                    <option value="article">Article</option>
                    <option value="guide">Guide</option>
                    <option value="comparison">Comparison / Review</option>
                    <option value="case_study">Case Study</option>
                    <option value="tool_template">Template / Tool</option>
                  </select>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-bold text-gray-700 mb-1">Content Pillar</label>
                  <select
                    value={formData.pillar_id}
                    onChange={(e) => setFormData((prev) => ({ ...prev, pillar_id: e.target.value }))}
                    className="w-full text-xs rounded-lg border border-[var(--border)] px-3 py-2 bg-white"
                  >
                    <option value="">None / Unassigned</option>
                    {initialPillars.map((p) => (
                      <option key={p.id} value={p.id}>
                        {p.name}
                      </option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="block text-xs font-bold text-gray-700 mb-1">Topic</label>
                  <select
                    value={formData.topic_id}
                    onChange={(e) => setFormData((prev) => ({ ...prev, topic_id: e.target.value }))}
                    className="w-full text-xs rounded-lg border border-[var(--border)] px-3 py-2 bg-white"
                  >
                    <option value="">None / Unassigned</option>
                    {initialTopics.map((t) => (
                      <option key={t.id} value={t.id}>
                        {t.name}
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-bold text-gray-700 mb-1">Min Word Count</label>
                  <input
                    type="number"
                    value={formData.target_word_count_min}
                    onChange={(e) => setFormData((prev) => ({ ...prev, target_word_count_min: Number(e.target.value) }))}
                    className="w-full text-xs rounded-lg border border-[var(--border)] px-3 py-2"
                  />
                </div>
                <div>
                  <label className="block text-xs font-bold text-gray-700 mb-1">Max Word Count</label>
                  <input
                    type="number"
                    value={formData.target_word_count_max}
                    onChange={(e) => setFormData((prev) => ({ ...prev, target_word_count_max: Number(e.target.value) }))}
                    className="w-full text-xs rounded-lg border border-[var(--border)] px-3 py-2"
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-bold text-gray-700 mb-1">Search Intent</label>
                <select
                  value={formData.search_intent}
                  onChange={(e) => setFormData((prev) => ({ ...prev, search_intent: e.target.value }))}
                  className="w-full text-xs rounded-lg border border-[var(--border)] px-3 py-2 bg-white"
                >
                  <option value="informational">Informational</option>
                  <option value="commercial">Commercial</option>
                  <option value="transactional">Transactional</option>
                  <option value="navigational">Navigational</option>
                </select>
              </div>

              <div>
                <label className="block text-xs font-bold text-gray-700 mb-1">Strategic Notes / Scope</label>
                <textarea
                  rows={2}
                  placeholder="Key concepts to cover, target audience personas, internal linking mandates..."
                  value={formData.notes}
                  onChange={(e) => setFormData((prev) => ({ ...prev, notes: e.target.value }))}
                  className="w-full text-xs rounded-lg border border-[var(--border)] px-3 py-2"
                />
              </div>

              <div className="pt-4 border-t border-[var(--border)] flex justify-end gap-2">
                <button
                  type="button"
                  onClick={() => setShowCreateModal(false)}
                  className="px-4 py-2 rounded-lg border border-[var(--border)] text-xs font-semibold text-gray-700 hover:bg-gray-50"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isPending}
                  className="px-5 py-2 rounded-lg bg-[var(--accent)] text-white text-xs font-semibold hover:bg-opacity-90 disabled:opacity-50"
                >
                  {isPending ? "Creating..." : "Create Planned Page"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* MODAL: EDIT PLANNED PAGE */}
      {showEditModal && selectedPage && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-xs p-4">
          <div className="bg-white rounded-2xl shadow-xl border border-[var(--border)] w-full max-w-lg overflow-hidden animate-in fade-in zoom-in-95 duration-150">
            <div className="flex items-center justify-between px-6 py-4 border-b border-[var(--border)]">
              <h3 className="font-bold text-base text-[var(--ink)]">Edit Planned Page</h3>
              <button onClick={() => setShowEditModal(false)} className="text-gray-400 hover:text-gray-700 p-1 rounded-md">
                <X size={18} />
              </button>
            </div>

            <form onSubmit={handleUpdatePage} className="p-6 space-y-4 max-h-[80vh] overflow-y-auto">
              <div>
                <label className="block text-xs font-bold text-gray-700 mb-1">Page Title *</label>
                <input
                  type="text"
                  required
                  value={formData.title}
                  onChange={(e) => setFormData((prev) => ({ ...prev, title: e.target.value }))}
                  className="w-full text-xs rounded-lg border border-[var(--border)] px-3 py-2"
                />
              </div>

              <div>
                <label className="block text-xs font-bold text-gray-700 mb-1">URL Slug *</label>
                <input
                  type="text"
                  required
                  value={formData.slug}
                  onChange={(e) => setFormData((prev) => ({ ...prev, slug: e.target.value }))}
                  className="w-full text-xs rounded-lg border border-[var(--border)] px-3 py-2 font-mono"
                />
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-bold text-gray-700 mb-1">Status</label>
                  <select
                    value={formData.status}
                    onChange={(e) => setFormData((prev) => ({ ...prev, status: e.target.value }))}
                    className="w-full text-xs rounded-lg border border-[var(--border)] px-3 py-2 bg-white"
                  >
                    <option value="draft">Draft</option>
                    <option value="in_review">In Review</option>
                    <option value="ready_to_write">Ready to Write</option>
                    <option value="writing">Writing</option>
                    <option value="published">Published</option>
                    <option value="archived">Archived</option>
                  </select>
                </div>

                <div>
                  <label className="block text-xs font-bold text-gray-700 mb-1">Page Type</label>
                  <select
                    value={formData.page_type}
                    onChange={(e) => setFormData((prev) => ({ ...prev, page_type: e.target.value }))}
                    className="w-full text-xs rounded-lg border border-[var(--border)] px-3 py-2 bg-white"
                  >
                    <option value="pillar_page">Pillar Page</option>
                    <option value="cluster_page">Cluster Page</option>
                    <option value="supporting_page">Supporting Page</option>
                    <option value="blog_post">Blog Post</option>
                    <option value="landing_page">Landing Page</option>
                    <option value="glossary">Glossary</option>
                  </select>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-bold text-gray-700 mb-1">Min Word Count</label>
                  <input
                    type="number"
                    value={formData.target_word_count_min}
                    onChange={(e) => setFormData((prev) => ({ ...prev, target_word_count_min: Number(e.target.value) }))}
                    className="w-full text-xs rounded-lg border border-[var(--border)] px-3 py-2"
                  />
                </div>
                <div>
                  <label className="block text-xs font-bold text-gray-700 mb-1">Max Word Count</label>
                  <input
                    type="number"
                    value={formData.target_word_count_max}
                    onChange={(e) => setFormData((prev) => ({ ...prev, target_word_count_max: Number(e.target.value) }))}
                    className="w-full text-xs rounded-lg border border-[var(--border)] px-3 py-2"
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-bold text-gray-700 mb-1">Notes</label>
                <textarea
                  rows={2}
                  value={formData.notes}
                  onChange={(e) => setFormData((prev) => ({ ...prev, notes: e.target.value }))}
                  className="w-full text-xs rounded-lg border border-[var(--border)] px-3 py-2"
                />
              </div>

              <div className="pt-4 border-t border-[var(--border)] flex justify-end gap-2">
                <button
                  type="button"
                  onClick={() => setShowEditModal(false)}
                  className="px-4 py-2 rounded-lg border border-[var(--border)] text-xs font-semibold text-gray-700 hover:bg-gray-50"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isPending}
                  className="px-5 py-2 rounded-lg bg-[var(--accent)] text-white text-xs font-semibold hover:bg-opacity-90 disabled:opacity-50"
                >
                  {isPending ? "Saving..." : "Save Changes"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* MODAL: ASSIGN KEYWORDS */}
      {showKeywordModal && selectedPage && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-xs p-4">
          <div className="bg-white rounded-2xl shadow-xl border border-[var(--border)] w-full max-w-lg overflow-hidden animate-in fade-in zoom-in-95 duration-150">
            <div className="flex items-center justify-between px-6 py-4 border-b border-[var(--border)]">
              <div>
                <h3 className="font-bold text-base text-[var(--ink)]">Target Keywords</h3>
                <p className="text-xs text-[var(--muted)]">{selectedPage.title}</p>
              </div>
              <button onClick={() => setShowKeywordModal(false)} className="text-gray-400 hover:text-gray-700 p-1 rounded-md">
                <X size={18} />
              </button>
            </div>

            <div className="p-6 space-y-4 max-h-[80vh] overflow-y-auto">
              {/* Form to assign a new keyword */}
              <form onSubmit={handleAssignKeyword} className="bg-gray-50 p-4 rounded-xl border border-[var(--border)] space-y-3">
                <h4 className="text-xs font-bold text-gray-700">Assign Keyword to Page</h4>
                <div>
                  <select
                    value={selectedKeywordId}
                    onChange={(e) => setSelectedKeywordId(e.target.value)}
                    required
                    className="w-full text-xs rounded-lg border border-[var(--border)] px-3 py-2 bg-white"
                  >
                    <option value="">Select a keyword...</option>
                    {availableKeywords
                      .filter((kw) => !pageKeywords.some((pk) => pk.keyword_id === kw.id))
                      .map((kw) => (
                        <option key={kw.id} value={kw.id}>
                          {kw.keyword} ({kw.search_volume ?? 0} vol, KD: {kw.keyword_difficulty ?? 0})
                        </option>
                      ))}
                  </select>
                </div>

                <div>
                  <label className="block text-[11px] font-bold text-gray-600 mb-1">Target Role</label>
                  <select
                    value={keywordRole}
                    onChange={(e) => setKeywordRole(e.target.value as any)}
                    className="w-full text-xs rounded-lg border border-[var(--border)] px-2 py-1.5 bg-white"
                  >
                    <option value="primary">Primary (Main Target)</option>
                    <option value="secondary">Secondary</option>
                    <option value="lsi">LSI / Semantic</option>
                    <option value="question">Question / PAA</option>
                  </select>
                </div>

                <button
                  type="submit"
                  disabled={isPending || !selectedKeywordId}
                  className="w-full py-2 rounded-lg bg-[var(--accent)] text-white text-xs font-semibold hover:bg-opacity-90 disabled:opacity-50 transition"
                >
                  {isPending ? "Assigning..." : "Assign Keyword"}
                </button>
              </form>

              {/* Current assigned keywords list */}
              <div className="space-y-2">
                <h4 className="text-xs font-bold text-gray-700">Assigned Keywords ({pageKeywords.length})</h4>
                {loadingKeywords ? (
                  <p className="text-xs text-gray-400 py-3 text-center">Loading assigned keywords...</p>
                ) : pageKeywords.length === 0 ? (
                  <p className="text-xs text-gray-400 py-3 text-center">No keywords assigned yet.</p>
                ) : (
                  <div className="divide-y divide-[var(--border)] border border-[var(--border)] rounded-xl overflow-hidden bg-white">
                    {pageKeywords.map((pk) => (
                      <div key={pk.id} className="flex items-center justify-between p-3 hover:bg-gray-50/50 text-xs">
                        <div className="flex flex-col">
                          <span className="font-semibold text-gray-900">{pk.keyword}</span>
                          <span className="text-[10px] text-gray-500 capitalize">
                            Role: {pk.keyword_role}
                          </span>
                        </div>
                        <button
                          onClick={() => handleRemoveKeyword(pk.keyword_id)}
                          className="text-rose-500 hover:text-rose-700 p-1 rounded"
                          title="Remove keyword"
                        >
                          <Trash2 size={13} />
                        </button>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* MODAL: CONVERT OPPORTUNITY */}
      {showConvertModal && selectedOpportunity && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-xs p-4">
          <div className="bg-white rounded-2xl shadow-xl border border-[var(--border)] w-full max-w-md overflow-hidden animate-in fade-in zoom-in-95 duration-150">
            <div className="flex items-center justify-between px-6 py-4 border-b border-[var(--border)]">
              <h3 className="font-bold text-base text-[var(--ink)]">Convert to Planned Page</h3>
              <button onClick={() => setShowConvertModal(false)} className="text-gray-400 hover:text-gray-700 p-1 rounded-md">
                <X size={18} />
              </button>
            </div>

            <form onSubmit={handleConvertOpportunity} className="p-6 space-y-4">
              <div>
                <p className="text-xs font-bold text-gray-700">Opportunity</p>
                <p className="text-sm font-semibold text-[var(--accent)] mt-0.5">
                  {selectedOpportunity.cluster_name || selectedOpportunity.keyword || "Content Opportunity"}
                </p>
                <p className="text-xs text-gray-500 mt-1">{selectedOpportunity.reason}</p>
              </div>

              <div>
                <label className="block text-xs font-bold text-gray-700 mb-1">Page Type</label>
                <select
                  value={formData.page_type}
                  onChange={(e) => setFormData((prev) => ({ ...prev, page_type: e.target.value }))}
                  className="w-full text-xs rounded-lg border border-[var(--border)] px-3 py-2 bg-white"
                >
                  <option value="pillar_page">Pillar Page</option>
                  <option value="cluster_page">Cluster Page</option>
                  <option value="supporting_page">Supporting Page</option>
                  <option value="blog_post">Blog Post</option>
                  <option value="landing_page">Landing Page</option>
                  <option value="glossary">Glossary</option>
                </select>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-bold text-gray-700 mb-1">Min Words</label>
                  <input
                    type="number"
                    value={formData.target_word_count_min}
                    onChange={(e) => setFormData((prev) => ({ ...prev, target_word_count_min: Number(e.target.value) }))}
                    className="w-full text-xs rounded-lg border border-[var(--border)] px-3 py-2"
                  />
                </div>
                <div>
                  <label className="block text-xs font-bold text-gray-700 mb-1">Max Words</label>
                  <input
                    type="number"
                    value={formData.target_word_count_max}
                    onChange={(e) => setFormData((prev) => ({ ...prev, target_word_count_max: Number(e.target.value) }))}
                    className="w-full text-xs rounded-lg border border-[var(--border)] px-3 py-2"
                  />
                </div>
              </div>

              <div className="pt-4 border-t border-[var(--border)] flex justify-end gap-2">
                <button
                  type="button"
                  onClick={() => setShowConvertModal(false)}
                  className="px-4 py-2 rounded-lg border border-[var(--border)] text-xs font-semibold text-gray-700 hover:bg-gray-50"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isPending}
                  className="px-5 py-2 rounded-lg bg-[var(--accent)] text-white text-xs font-semibold hover:bg-opacity-90 disabled:opacity-50"
                >
                  {isPending ? "Converting..." : "Convert Now"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
