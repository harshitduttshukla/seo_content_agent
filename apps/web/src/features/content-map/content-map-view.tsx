"use client";

import { useState, useMemo, useTransition } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  GitBranch,
  Search,
  ZoomIn,
  ZoomOut,
  Maximize2,
  RefreshCw,
  Plus,
  AlertTriangle,
  CheckCircle2,
  BookOpen,
  Link2,
  X,
  FileText,
  History,
  LayoutGrid,
  ListTree,
} from "lucide-react";
import { Card } from "@/components/card";
import type {
  ContentMapGraph,
  ContentMapNode,
  ContentMapValidation,
  ContentArchitectureVersion,
} from "@/lib/api-types";
import { clientApi } from "@/lib/client-api";

export function ContentMapView({
  projectId,
  initialGraph,
  initialValidation,
  initialVersions,
}: {
  projectId: string;
  initialGraph: ContentMapGraph;
  initialValidation: ContentMapValidation;
  initialVersions: ContentArchitectureVersion[];
}) {
  const router = useRouter();
  const [isPending, startTransition] = useTransition();

  const [graph, setGraph] = useState<ContentMapGraph>(initialGraph);
  const [validation, setValidation] = useState<ContentMapValidation>(initialValidation);
  const [versions, setVersions] = useState<ContentArchitectureVersion[]>(initialVersions);

  // View state
  const [viewMode, setViewMode] = useState<"graph" | "tree">("graph");
  const [search, setSearch] = useState("");
  const [selectedNodeType, setSelectedNodeType] = useState<string>("ALL");
  const [selectedStatus, setSelectedStatus] = useState<string>("ALL");
  const [filterOrphanOnly, setFilterOrphanOnly] = useState(false);
  const [filterCannibalizationOnly, setFilterCannibalizationOnly] = useState(false);

  // Inspector & Modals
  const [selectedNode, setSelectedNode] = useState<ContentMapNode | null>(null);
  const [showValidationDrawer, setShowValidationDrawer] = useState(false);
  const [showVersionsDrawer, setShowVersionsDrawer] = useState(false);
  const [showCreatePageModal, setShowCreatePageModal] = useState(false);

  // Zoom & Pan state for visual canvas
  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState({ x: 0, y: 0 });

  // Create Page Form (prepopulated from cluster if selected)
  const [pageTitle, setPageTitle] = useState("");
  const [pageSlug, setPageSlug] = useState("");
  const [pageContentType, setPageContentType] = useState("GUIDE");
  const [pageClusterId, setPageClusterId] = useState<string>("");
  const [pagePrimaryKw, setPagePrimaryKw] = useState("");
  const [pagePriority, setPagePriority] = useState<number>(3);
  const [pageFormError, setPageFormError] = useState<string | null>(null);

  const [notification, setNotification] = useState<string | null>(null);

  const stats = useMemo(() => {
    return (
      graph.stats ?? {
        cannibalization_warnings: 0,
        existing_pages: 0,
        orphan_pages: 0,
        planned_pages: 0,
        total_clusters: 0,
        total_pages: 0,
        total_pillars: 0,
        total_topics: 0,
      }
    );
  }, [graph.stats]);

  // Filtered nodes
  const filteredNodes = useMemo(() => {
    return graph.nodes.filter((node) => {
      // Type filter
      if (selectedNodeType !== "ALL" && node.type.toUpperCase() !== selectedNodeType) {
        return false;
      }
      // Status filter
      if (selectedStatus !== "ALL" && node.data.status.toUpperCase() !== selectedStatus) {
        return false;
      }
      // Special filters
      if (filterOrphanOnly && !node.data.flags?.includes("is_orphan") && !node.data.flags?.includes("orphan")) {
        return false;
      }
      if (filterCannibalizationOnly && !node.data.flags?.includes("cannibalization_risk") && !node.data.flags?.includes("cannibalization")) {
        return false;
      }
      // Search
      if (search.trim()) {
        const q = search.toLowerCase();
        const matchesLabel = node.data.label.toLowerCase().includes(q);
        const matchesKw = node.data.primary_keyword.toLowerCase().includes(q);
        const matchesSubtitle = node.data.subtitle.toLowerCase().includes(q);
        if (!matchesLabel && !matchesKw && !matchesSubtitle) {
          return false;
        }
      }
      return true;
    });
  }, [graph.nodes, selectedNodeType, selectedStatus, filterOrphanOnly, filterCannibalizationOnly, search]);

  // Group nodes by hierarchical layer for clean visual canvas
  const layeredNodes = useMemo(() => {
    const pillars = filteredNodes.filter((n) => n.type === "pillar");
    const topics = filteredNodes.filter((n) => n.type === "topic");
    const clusters = filteredNodes.filter((n) => n.type === "cluster");
    const pages = filteredNodes.filter((n) => n.type === "page");
    return { pillars, topics, clusters, pages };
  }, [filteredNodes]);

  const handleZoomIn = () => setZoom((z) => Math.min(1.6, z + 0.15));
  const handleZoomOut = () => setZoom((z) => Math.max(0.6, z - 0.15));
  const handleResetZoom = () => {
    setZoom(1);
    setPan({ x: 0, y: 0 });
  };

  const handleGenerateInitialMap = async () => {
    setNotification("Generating Content Map from strategy intelligence...");
    startTransition(async () => {
      try {
        const res = await clientApi<ContentMapGraph>(`/projects/${projectId}/content-map/generate`, {
          method: "POST",
        });
        if (res) {
          setGraph(res);
          setNotification("Initial Content Map successfully generated.");
          const valRes = await clientApi<ContentMapValidation>(`/projects/${projectId}/content-map/validation`);
          if (valRes) setValidation(valRes);
          router.refresh();
        }
      } catch (err: unknown) {
        setNotification(err instanceof Error ? err.message : "Failed to generate map.");
      }
    });
  };

  const handleCreateVersion = async () => {
    startTransition(async () => {
      try {
        const res = await clientApi<ContentArchitectureVersion>(`/projects/${projectId}/content-map/versions`, {
          method: "POST",
          body: JSON.stringify({ change_summary: `Snapshot at ${new Date().toLocaleTimeString()}` }),
        });
        if (res) {
          setVersions((prev) => [res, ...prev]);
          setNotification(`Created Architecture Snapshot v${res.version}`);
        }
      } catch (err: unknown) {
        setNotification(err instanceof Error ? err.message : "Failed to create version.");
      }
    });
  };

  const handleCreatePageSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!pageTitle.trim() || !pageSlug.trim()) return;

    setPageFormError(null);
    startTransition(async () => {
      try {
        await clientApi(`/projects/${projectId}/content-pages`, {
          method: "POST",
          body: JSON.stringify({
            title: pageTitle.trim(),
            slug: pageSlug.trim().toLowerCase().replace(/\s+/g, "-"),
            content_type: pageContentType,
            cluster_id: pageClusterId || undefined,
            primary_keyword: pagePrimaryKw.trim(),
            priority: pagePriority,
            status: "PLANNED",
          }),
        });

        // Refresh graph and validation
        const graphRes = await clientApi<ContentMapGraph>(`/projects/${projectId}/content-map`);
        if (graphRes) setGraph(graphRes);
        const valRes = await clientApi<ContentMapValidation>(`/projects/${projectId}/content-map/validation`);
        if (valRes) setValidation(valRes);

        setShowCreatePageModal(false);
        setPageTitle("");
        setPageSlug("");
        setPagePrimaryKw("");
        setPageFormError(null);
        setNotification("Planned page successfully created.");
        router.refresh();
      } catch (err: unknown) {
        const message = err instanceof Error ? err.message : "Failed to create page.";
        setPageFormError(message);
        setNotification(message);
      }
    });
  };

  const openCreatePageForCluster = (clusterNode: ContentMapNode) => {
    setPageTitle(clusterNode.data.label);
    setPageSlug(clusterNode.data.label.toLowerCase().replace(/[^a-z0-9]+/g, "-"));
    setPageClusterId(String(clusterNode.data.entity_id));
    setPagePrimaryKw(clusterNode.data.label);
    setPageFormError(null);
    setShowCreatePageModal(true);
  };

  return (
    <div className="flex flex-col gap-6">
      {/* Header & Metrics */}
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <span className="eyebrow">Content Architecture</span>
            <span className="rounded-full bg-indigo-100 text-indigo-800 text-[11px] font-bold px-2 py-0.5">
              Source of Truth
            </span>
          </div>
          <h1 className="page-title mt-1">Visual Content Map</h1>
          <p className="mt-1 text-sm text-[var(--muted)]">
            Explore hierarchy (Pillars ➔ Topics ➔ Clusters ➔ Pages), SEO targeting, and internal connectivity.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2.5">
          <button
            onClick={handleGenerateInitialMap}
            disabled={isPending}
            className="btn btn-secondary text-xs flex items-center gap-1.5"
            title="Generate planned pages from approved Phase 3 keyword clusters"
          >
            <RefreshCw size={14} className={isPending ? "animate-spin" : ""} />
            Generate from Strategy
          </button>
          <button
            onClick={() => setShowValidationDrawer(true)}
            className="btn btn-secondary text-xs flex items-center gap-1.5"
          >
            <AlertTriangle
              size={14}
              className={validation.issues.length > 0 ? "text-amber-600" : "text-emerald-600"}
            />
            Validation ({validation.total_issues})
          </button>
          <button
            onClick={() => setShowVersionsDrawer(true)}
            className="btn btn-secondary text-xs flex items-center gap-1.5"
          >
            <History size={14} />
            History ({versions.length})
          </button>
          <button
            onClick={() => {
              setPageTitle("");
              setPageSlug("");
              setPageClusterId("");
              setPagePrimaryKw("");
              setPageFormError(null);
              setShowCreatePageModal(true);
            }}
            className="btn btn-primary text-xs flex items-center gap-1.5"
          >
            <Plus size={14} />
            Create Planned Page
          </button>
        </div>
      </div>

      {notification && (
        <div className="flex items-center justify-between rounded-lg bg-indigo-50 px-4 py-2.5 text-xs text-indigo-900 border border-indigo-200">
          <span>{notification}</span>
          <button onClick={() => setNotification(null)} className="text-indigo-700 hover:text-indigo-900 font-bold">
            ×
          </button>
        </div>
      )}

      {/* Stats Cards */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 lg:grid-cols-8">
        <Card className="p-3 text-center">
          <p className="text-[11px] font-bold text-[var(--muted)] uppercase">Pillars</p>
          <p className="mt-1 text-xl font-extrabold text-indigo-700">{stats.total_pillars}</p>
        </Card>
        <Card className="p-3 text-center">
          <p className="text-[11px] font-bold text-[var(--muted)] uppercase">Topics</p>
          <p className="mt-1 text-xl font-extrabold text-blue-700">{stats.total_topics}</p>
        </Card>
        <Card className="p-3 text-center">
          <p className="text-[11px] font-bold text-[var(--muted)] uppercase">Clusters</p>
          <p className="mt-1 text-xl font-extrabold text-purple-700">{stats.total_clusters}</p>
        </Card>
        <Card className="p-3 text-center">
          <p className="text-[11px] font-bold text-[var(--muted)] uppercase">Planned Pages</p>
          <p className="mt-1 text-xl font-extrabold text-emerald-700">{stats.planned_pages}</p>
        </Card>
        <Card className="p-3 text-center">
          <p className="text-[11px] font-bold text-[var(--muted)] uppercase">Existing Pages</p>
          <p className="mt-1 text-xl font-extrabold text-slate-700">{stats.existing_pages}</p>
        </Card>
        <Card className="p-3 text-center">
          <p className="text-[11px] font-bold text-[var(--muted)] uppercase">Orphan Pages</p>
          <p className={`mt-1 text-xl font-extrabold ${stats.orphan_pages > 0 ? "text-amber-600" : "text-slate-400"}`}>
            {stats.orphan_pages}
          </p>
        </Card>
        <Card className="p-3 text-center">
          <p className="text-[11px] font-bold text-[var(--muted)] uppercase">Cannibalization</p>
          <p className={`mt-1 text-xl font-extrabold ${stats.cannibalization_warnings > 0 ? "text-rose-600" : "text-slate-400"}`}>
            {stats.cannibalization_warnings}
          </p>
        </Card>
        <Card className="p-3 text-center">
          <p className="text-[11px] font-bold text-[var(--muted)] uppercase">Health Status</p>
          <span
            className={`mt-1 inline-block rounded-full px-2 py-0.5 text-[10px] font-bold uppercase ${
              validation.is_valid ? "bg-emerald-100 text-emerald-800" : "bg-amber-100 text-amber-800"
            }`}
          >
            {validation.is_valid ? "Valid" : "Issues Found"}
          </span>
        </Card>
      </div>

      {/* Control Bar: Search, Filters, View Modes */}
      <Card className="p-3">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex flex-wrap items-center gap-2 flex-1 min-w-[280px]">
            <div className="relative flex-1 max-w-sm">
              <Search className="absolute left-3 top-2.5 text-slate-400" size={15} />
              <input
                type="text"
                placeholder="Search page, keyword, cluster, topic..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="input pl-9 text-xs py-1.5 w-full"
              />
              {search && (
                <button
                  onClick={() => setSearch("")}
                  className="absolute right-2.5 top-2.5 text-xs text-slate-400 hover:text-slate-600"
                >
                  <X size={13} />
                </button>
              )}
            </div>

            {/* Type Selector */}
            <select
              value={selectedNodeType}
              onChange={(e) => setSelectedNodeType(e.target.value)}
              className="input text-xs py-1.5 w-auto"
            >
              <option value="ALL">All Node Types</option>
              <option value="PILLAR">Pillars</option>
              <option value="TOPIC">Topics</option>
              <option value="CLUSTER">Clusters</option>
              <option value="PAGE">Pages</option>
            </select>

            {/* Status Selector */}
            <select
              value={selectedStatus}
              onChange={(e) => setSelectedStatus(e.target.value)}
              className="input text-xs py-1.5 w-auto"
            >
              <option value="ALL">All Statuses</option>
              <option value="PLANNED">Planned</option>
              <option value="APPROVED">Approved</option>
              <option value="PROPOSED">Proposed</option>
              <option value="PUBLISHED">Published</option>
            </select>

            {/* Quick Filter Badges */}
            <button
              onClick={() => setFilterOrphanOnly((prev) => !prev)}
              className={`rounded-full px-2.5 py-1 text-xs font-semibold transition ${
                filterOrphanOnly ? "bg-amber-600 text-white" : "bg-slate-100 text-slate-700 hover:bg-slate-200"
              }`}
            >
              Orphans {stats.orphan_pages > 0 && `(${stats.orphan_pages})`}
            </button>
            <button
              onClick={() => setFilterCannibalizationOnly((prev) => !prev)}
              className={`rounded-full px-2.5 py-1 text-xs font-semibold transition ${
                filterCannibalizationOnly ? "bg-rose-600 text-white" : "bg-slate-100 text-slate-700 hover:bg-slate-200"
              }`}
            >
              Cannibalization {stats.cannibalization_warnings > 0 && `(${stats.cannibalization_warnings})`}
            </button>
          </div>

          <div className="flex items-center gap-1.5">
            <div className="flex items-center bg-slate-100 rounded-lg p-0.5">
              <button
                onClick={() => setViewMode("graph")}
                className={`p-1.5 rounded-md text-xs font-bold flex items-center gap-1 transition ${
                  viewMode === "graph" ? "bg-white text-[var(--accent)] shadow-sm" : "text-slate-600"
                }`}
              >
                <LayoutGrid size={14} /> Map
              </button>
              <button
                onClick={() => setViewMode("tree")}
                className={`p-1.5 rounded-md text-xs font-bold flex items-center gap-1 transition ${
                  viewMode === "tree" ? "bg-white text-[var(--accent)] shadow-sm" : "text-slate-600"
                }`}
              >
                <ListTree size={14} /> Table
              </button>
            </div>

            {viewMode === "graph" && (
              <div className="flex items-center gap-1 border-l pl-2 border-slate-200">
                <button
                  onClick={handleZoomOut}
                  className="p-1.5 rounded text-slate-600 hover:bg-slate-100"
                  title="Zoom Out"
                >
                  <ZoomOut size={15} />
                </button>
                <span className="text-[11px] font-mono text-slate-500 w-10 text-center">
                  {Math.round(zoom * 100)}%
                </span>
                <button
                  onClick={handleZoomIn}
                  className="p-1.5 rounded text-slate-600 hover:bg-slate-100"
                  title="Zoom In"
                >
                  <ZoomIn size={15} />
                </button>
                <button
                  onClick={handleResetZoom}
                  className="p-1.5 rounded text-slate-600 hover:bg-slate-100"
                  title="Fit to Screen"
                >
                  <Maximize2 size={15} />
                </button>
              </div>
            )}
          </div>
        </div>
      </Card>

      {/* Main Visual Canvas or Tabular Tree */}
      {viewMode === "graph" ? (
        <div className="relative border border-[var(--border)] rounded-2xl bg-gradient-to-br from-slate-50 via-white to-indigo-50/20 overflow-hidden min-h-[640px] shadow-inner flex flex-col">
          {/* Canvas Viewport */}
          <div
            className="flex-1 p-8 overflow-auto transition-transform duration-100"
            style={{
              transform: `scale(${zoom}) translate(${pan.x}px, ${pan.y}px)`,
              transformOrigin: "top left",
            }}
          >
            {filteredNodes.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-20 text-center">
                <GitBranch size={40} className="text-slate-300 mb-3" />
                <p className="text-sm font-bold text-slate-700">No content architecture nodes found</p>
                <p className="text-xs text-slate-500 mt-1 max-w-sm">
                  Click &ldquo;Generate from Strategy&rdquo; to turn your keyword clusters and strategy into planned pages,
                  or adjust active search and filters.
                </p>
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-4 gap-8">
                {/* Column 1: Pillars */}
                <div className="flex flex-col gap-4">
                  <div className="flex items-center gap-2 border-b border-indigo-200 pb-2">
                    <span className="w-2.5 h-2.5 rounded-full bg-indigo-600"></span>
                    <h2 className="text-xs font-bold text-indigo-900 uppercase tracking-wider">
                      Content Pillars ({layeredNodes.pillars.length})
                    </h2>
                  </div>
                  <div className="flex flex-col gap-3">
                    {layeredNodes.pillars.map((node) => (
                      <div
                        key={node.id}
                        onClick={() => setSelectedNode(node)}
                        className={`cursor-pointer rounded-xl border p-4 bg-white/90 shadow-sm transition hover:shadow-md hover:border-indigo-500 ${
                          selectedNode?.id === node.id ? "ring-2 ring-indigo-600 border-indigo-600" : "border-slate-200"
                        }`}
                      >
                        <div className="flex items-center justify-between">
                          <span className="text-[10px] font-extrabold uppercase px-2 py-0.5 rounded bg-indigo-100 text-indigo-800">
                            Pillar
                          </span>
                          <span className="text-xs text-slate-500">P{node.data.priority}</span>
                        </div>
                        <h3 className="mt-2 font-bold text-sm text-slate-900">{node.data.title}</h3>
                        <p className="mt-1 text-xs text-slate-500 line-clamp-2">{node.data.subtitle}</p>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Column 2: Topics */}
                <div className="flex flex-col gap-4">
                  <div className="flex items-center gap-2 border-b border-blue-200 pb-2">
                    <span className="w-2.5 h-2.5 rounded-full bg-blue-600"></span>
                    <h2 className="text-xs font-bold text-blue-900 uppercase tracking-wider">
                      Topics ({layeredNodes.topics.length})
                    </h2>
                  </div>
                  <div className="flex flex-col gap-3">
                    {layeredNodes.topics.map((node) => (
                      <div
                        key={node.id}
                        onClick={() => setSelectedNode(node)}
                        className={`cursor-pointer rounded-xl border p-4 bg-white/90 shadow-sm transition hover:shadow-md hover:border-blue-500 ${
                          selectedNode?.id === node.id ? "ring-2 ring-blue-600 border-blue-600" : "border-slate-200"
                        }`}
                      >
                        <div className="flex items-center justify-between">
                          <span className="text-[10px] font-extrabold uppercase px-2 py-0.5 rounded bg-blue-100 text-blue-800">
                            Topic
                          </span>
                          <span className="text-xs text-slate-500">{node.data.status}</span>
                        </div>
                        <h3 className="mt-2 font-bold text-sm text-slate-900">{node.data.title}</h3>
                        <p className="mt-1 font-mono text-[11px] text-slate-500 truncate">/{node.data.subtitle}</p>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Column 3: Keyword Clusters */}
                <div className="flex flex-col gap-4">
                  <div className="flex items-center gap-2 border-b border-purple-200 pb-2">
                    <span className="w-2.5 h-2.5 rounded-full bg-purple-600"></span>
                    <h2 className="text-xs font-bold text-purple-900 uppercase tracking-wider">
                      Clusters ({layeredNodes.clusters.length})
                    </h2>
                  </div>
                  <div className="flex flex-col gap-3">
                    {layeredNodes.clusters.map((node) => (
                      <div
                        key={node.id}
                        onClick={() => setSelectedNode(node)}
                        className={`cursor-pointer rounded-xl border p-4 bg-white/90 shadow-sm transition hover:shadow-md hover:border-purple-500 ${
                          selectedNode?.id === node.id ? "ring-2 ring-purple-600 border-purple-600" : "border-slate-200"
                        }`}
                      >
                        <div className="flex items-center justify-between">
                          <span className="text-[10px] font-extrabold uppercase px-2 py-0.5 rounded bg-purple-100 text-purple-800">
                            {node.data.intent}
                          </span>
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              openCreatePageForCluster(node);
                            }}
                            className="text-[10px] font-bold text-purple-700 hover:underline flex items-center gap-0.5"
                          >
                            + Page
                          </button>
                        </div>
                        <h3 className="mt-2 font-bold text-sm text-slate-900">{node.data.title}</h3>
                        <div className="mt-2 flex items-center justify-between text-xs text-slate-500">
                          <span>Cluster Score</span>
                          <span className="font-mono font-bold text-purple-700">
                            {Number(node.data.business_value || 0).toFixed(0)}
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Column 4: Planned Content Pages */}
                <div className="flex flex-col gap-4">
                  <div className="flex items-center gap-2 border-b border-emerald-200 pb-2">
                    <span className="w-2.5 h-2.5 rounded-full bg-emerald-600"></span>
                    <h2 className="text-xs font-bold text-emerald-900 uppercase tracking-wider">
                      Planned & Existing Pages ({layeredNodes.pages.length})
                    </h2>
                  </div>
                  <div className="flex flex-col gap-3">
                    {layeredNodes.pages.map((node) => {
                      const isOrphan = Boolean(node.data.flags?.includes("is_orphan") || node.data.flags?.includes("orphan"));
                      const isCannibal = Boolean(node.data.flags?.includes("cannibalization_risk") || node.data.flags?.includes("cannibalization"));
                      return (
                        <div
                          key={node.id}
                          onClick={() => setSelectedNode(node)}
                          className={`cursor-pointer rounded-xl border p-4 bg-white shadow-sm transition hover:shadow-md hover:border-emerald-500 ${
                            selectedNode?.id === node.id
                              ? "ring-2 ring-emerald-600 border-emerald-600"
                              : isCannibal
                              ? "border-rose-400 bg-rose-50/40"
                              : isOrphan
                              ? "border-amber-300 bg-amber-50/30"
                              : "border-slate-200"
                          }`}
                        >
                          <div className="flex items-center justify-between gap-2">
                            <span
                              className={`text-[10px] font-extrabold uppercase px-2 py-0.5 rounded ${
                                node.data.page_type === "EXISTING"
                                  ? "bg-slate-100 text-slate-800"
                                  : "bg-emerald-100 text-emerald-800"
                              }`}
                            >
                              {node.data.page_type}
                            </span>
                            <div className="flex items-center gap-1">
                              {isOrphan && (
                                <span className="bg-amber-100 text-amber-800 text-[10px] font-bold px-1.5 py-0.5 rounded">
                                  Orphan
                                </span>
                              )}
                              {isCannibal && (
                                <span className="bg-rose-100 text-rose-800 text-[10px] font-bold px-1.5 py-0.5 rounded">
                                  Collision
                                </span>
                              )}
                            </div>
                          </div>

                          <h3 className="mt-2 font-bold text-sm text-slate-900 line-clamp-1">{node.data.title}</h3>
                          <p className="text-xs text-slate-500 font-mono mt-0.5 truncate">{node.data.url}</p>

                          <div className="mt-3 flex items-center justify-between text-xs pt-2 border-t border-slate-100">
                            <span className="text-slate-500 truncate max-w-[120px]">
                              {node.data.primary_keyword || "No primary kw"}
                            </span>
                            <span className="font-bold text-emerald-700">P{node.data.priority}</span>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      ) : (
        /* Accessible Tabular / Tree View */
        <Card className="overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-50 border-b border-slate-200 text-slate-700 font-bold uppercase tracking-wider">
                <tr>
                  <th className="p-3">Type</th>
                  <th className="p-3">Title / Entity</th>
                  <th className="p-3">Primary Keyword / Slug</th>
                  <th className="p-3">Status</th>
                  <th className="p-3">Inbound / Outbound</th>
                  <th className="p-3">Flags</th>
                  <th className="p-3 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {filteredNodes.map((node) => (
                  <tr key={node.id} className="hover:bg-slate-50/80 transition">
                    <td className="p-3">
                      <span
                        className={`text-[10px] font-extrabold uppercase px-2 py-0.5 rounded ${
                          node.type === "pillar"
                            ? "bg-indigo-100 text-indigo-800"
                            : node.type === "topic"
                            ? "bg-blue-100 text-blue-800"
                            : node.type === "cluster"
                            ? "bg-purple-100 text-purple-800"
                            : "bg-emerald-100 text-emerald-800"
                        }`}
                      >
                        {node.type}
                      </span>
                    </td>
                    <td className="p-3 font-semibold text-slate-900">{node.data.title}</td>
                    <td className="p-3 font-mono text-slate-600">
                      {node.data.primary_keyword || node.data.subtitle || "—"}
                    </td>
                    <td className="p-3 text-slate-600">{node.data.status}</td>
                    <td className="p-3 text-slate-600">
                      {node.type === "page" ? `${node.data.inbound_links_count} in / ${node.data.outbound_links_count} out` : "—"}
                    </td>
                    <td className="p-3">
                      {(node.data.flags?.length ?? 0) > 0 ? (
                        <div className="flex items-center gap-1">
                          {node.data.flags?.map((f) => (
                            <span key={f} className="rounded bg-amber-100 text-amber-800 text-[10px] font-bold px-1.5 py-0.5">
                              {f}
                            </span>
                          ))}
                        </div>
                      ) : (
                        <span className="text-slate-400">—</span>
                      )}
                    </td>
                    <td className="p-3 text-right">
                      <button
                        onClick={() => setSelectedNode(node)}
                        className="text-xs font-bold text-[var(--accent)] hover:underline"
                      >
                        Inspect
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}

      {/* Node Inspector Side Panel / Drawer */}
      {selectedNode && (
        <div className="fixed inset-y-0 right-0 z-50 w-full sm:w-[450px] bg-white border-l border-slate-200 shadow-2xl p-6 flex flex-col justify-between overflow-y-auto">
          <div>
            <div className="flex items-center justify-between border-b pb-4">
              <div>
                <span className="text-[10px] font-extrabold uppercase px-2 py-0.5 rounded bg-indigo-100 text-indigo-800">
                  {selectedNode.type} Node
                </span>
                <h2 className="text-lg font-bold text-slate-900 mt-1">{selectedNode.data.title}</h2>
              </div>
              <button
                onClick={() => setSelectedNode(null)}
                className="p-1.5 rounded-full hover:bg-slate-100 text-slate-500"
              >
                <X size={18} />
              </button>
            </div>

            <div className="mt-6 flex flex-col gap-4 text-xs">
              <div>
                <p className="font-bold text-slate-500 uppercase tracking-wider text-[10px]">URL / Slug</p>
                <p className="mt-1 font-mono text-slate-800 bg-slate-50 p-2 rounded border break-all">
                  {selectedNode.data.url || selectedNode.data.subtitle || "—"}
                </p>
              </div>

              {selectedNode.type === "page" && (
                <>
                  <div className="grid grid-cols-2 gap-3">
                    <div className="bg-slate-50 p-2.5 rounded border">
                      <p className="text-[10px] font-bold text-slate-500 uppercase">Primary Keyword</p>
                      <p className="mt-1 font-semibold text-slate-900">
                        {selectedNode.data.primary_keyword || "Not assigned"}
                      </p>
                    </div>
                    <div className="bg-slate-50 p-2.5 rounded border">
                      <p className="text-[10px] font-bold text-slate-500 uppercase">Search Intent</p>
                      <p className="mt-1 font-semibold text-slate-900">{selectedNode.data.intent}</p>
                    </div>
                  </div>

                  <div className="grid grid-cols-2 gap-3">
                    <div className="bg-slate-50 p-2.5 rounded border">
                      <p className="text-[10px] font-bold text-slate-500 uppercase">Priority</p>
                      <p className="mt-1 font-bold text-indigo-700">P{selectedNode.data.priority}</p>
                    </div>
                    <div className="bg-slate-50 p-2.5 rounded border">
                      <p className="text-[10px] font-bold text-slate-500 uppercase">Business Value</p>
                      <p className="mt-1 font-bold text-emerald-700">
                        {Number(selectedNode.data.business_value).toFixed(0)} / 100
                      </p>
                    </div>
                  </div>

                  <div className="grid grid-cols-2 gap-3">
                    <div className="bg-slate-50 p-2.5 rounded border">
                      <p className="text-[10px] font-bold text-slate-500 uppercase">Inbound Links</p>
                      <p className="mt-1 font-bold text-slate-800">{selectedNode.data.inbound_links_count}</p>
                    </div>
                    <div className="bg-slate-50 p-2.5 rounded border">
                      <p className="text-[10px] font-bold text-slate-500 uppercase">Outbound Links</p>
                      <p className="mt-1 font-bold text-slate-800">{selectedNode.data.outbound_links_count}</p>
                    </div>
                  </div>

                  {(selectedNode.data.flags?.length ?? 0) > 0 && (
                    <div>
                      <p className="font-bold text-slate-500 uppercase tracking-wider text-[10px]">Architecture Flags</p>
                      <div className="mt-1 flex flex-wrap gap-1.5">
                        {selectedNode.data.flags?.map((flag) => (
                          <span key={flag} className="bg-amber-100 text-amber-800 font-bold px-2 py-0.5 rounded text-[11px]">
                            {flag}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}
                </>
              )}
            </div>
          </div>

          <div className="mt-8 border-t pt-4 flex flex-col gap-2">
            {selectedNode.type === "page" && (
              <>
                <Link
                  href={`/projects/${projectId}/content/${selectedNode.data.entity_id}`}
                  className="btn btn-primary text-xs flex items-center justify-center gap-1.5 w-full py-2"
                >
                  <FileText size={14} /> Open Brief & Editor
                </Link>
                <Link
                  href={`/projects/${projectId}/content/seo-guide/${selectedNode.data.entity_id}`}
                  className="btn btn-secondary text-xs flex items-center justify-center gap-1.5 w-full py-2"
                >
                  <BookOpen size={14} /> Open SEO Guide
                </Link>
                <Link
                  href={`/projects/${projectId}/internal-linking`}
                  className="btn btn-secondary text-xs flex items-center justify-center gap-1.5 w-full py-2"
                >
                  <Link2 size={14} /> Manage Internal Links
                </Link>
              </>
            )}
            {selectedNode.type === "cluster" && (
              <button
                onClick={() => openCreatePageForCluster(selectedNode)}
                className="btn btn-primary text-xs flex items-center justify-center gap-1.5 w-full py-2"
              >
                <Plus size={14} /> Create Page for Cluster
              </button>
            )}
          </div>
        </div>
      )}

      {/* Validation Drawer */}
      {showValidationDrawer && (
        <div className="fixed inset-y-0 right-0 z-50 w-full sm:w-[500px] bg-white border-l border-slate-200 shadow-2xl p-6 flex flex-col justify-between overflow-y-auto">
          <div>
            <div className="flex items-center justify-between border-b pb-4">
              <div className="flex items-center gap-2">
                <AlertTriangle size={18} className="text-amber-600" />
                <h2 className="text-lg font-bold text-slate-900">Architecture Validation</h2>
              </div>
              <button onClick={() => setShowValidationDrawer(false)} className="p-1 rounded hover:bg-slate-100">
                <X size={18} />
              </button>
            </div>

            <p className="mt-3 text-xs text-slate-600">
              8 automated validation checks inspecting unmapped clusters, cannibalization duplicate targets, orphan pages,
              and broken relationships.
            </p>

            <div className="mt-5 flex flex-col gap-3">
              {validation.issues.length === 0 ? (
                <div className="p-6 text-center bg-emerald-50 rounded-xl border border-emerald-200">
                  <CheckCircle2 size={32} className="text-emerald-600 mx-auto mb-2" />
                  <p className="text-xs font-bold text-emerald-900">All Architecture Checks Passed</p>
                  <p className="text-[11px] text-emerald-700 mt-1">Zero orphan pages or cannibalization conflicts found.</p>
                </div>
              ) : (
                validation.issues.map((issue) => (
                  <div
                    key={issue.id}
                    className={`p-3.5 rounded-xl border text-xs ${
                      issue.severity === "error"
                        ? "bg-rose-50/50 border-rose-200 text-rose-900"
                        : issue.severity === "warning"
                        ? "bg-amber-50/50 border-amber-200 text-amber-900"
                        : "bg-blue-50/50 border-blue-200 text-blue-900"
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <span className="font-extrabold uppercase text-[10px] tracking-wider px-1.5 py-0.5 rounded bg-white/80">
                        {issue.issue_type}
                      </span>
                      <span className="font-bold text-[10px] uppercase">{issue.severity}</span>
                    </div>
                    <p className="mt-2 font-bold text-slate-900">{issue.entity_label}</p>
                    <p className="mt-1 text-slate-700 text-xs">{issue.reason}</p>
                    <div className="mt-2 pt-2 border-t border-black/5 text-[11px] text-slate-600">
                      <strong>Recommended Action:</strong> {issue.recommended_action}
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      )}

      {/* History / Versions Drawer */}
      {showVersionsDrawer && (
        <div className="fixed inset-y-0 right-0 z-50 w-full sm:w-[440px] bg-white border-l border-slate-200 shadow-2xl p-6 flex flex-col justify-between overflow-y-auto">
          <div>
            <div className="flex items-center justify-between border-b pb-4">
              <div className="flex items-center gap-2">
                <History size={18} className="text-indigo-600" />
                <h2 className="text-lg font-bold text-slate-900">Architecture Versions</h2>
              </div>
              <button onClick={() => setShowVersionsDrawer(false)} className="p-1 rounded hover:bg-slate-100">
                <X size={18} />
              </button>
            </div>

            <div className="mt-4 flex items-center justify-between">
              <p className="text-xs text-slate-500">Immutable historical snapshots</p>
              <button
                onClick={handleCreateVersion}
                disabled={isPending}
                className="btn btn-primary text-xs py-1 px-2.5"
              >
                + Snapshot
              </button>
            </div>

            <div className="mt-4 flex flex-col gap-3">
              {versions.length === 0 ? (
                <p className="text-xs text-slate-400 py-6 text-center">No snapshots recorded yet.</p>
              ) : (
                versions.map((v) => (
                  <div key={v.id} className="p-3.5 rounded-xl border border-slate-200 bg-slate-50/60 text-xs">
                    <div className="flex items-center justify-between">
                      <span className="font-bold text-indigo-700">Version {v.version}</span>
                      <span className="text-[10px] text-slate-400">
                        {new Date(v.created_at).toLocaleString()}
                      </span>
                    </div>
                    <p className="mt-1.5 text-slate-700 font-medium">{v.change_summary || "Snapshot"}</p>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      )}

      {/* Create Planned Page Modal */}
      {showCreatePageModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4 backdrop-blur-xs">
          <div className="w-full max-w-lg rounded-2xl bg-white p-6 shadow-2xl border border-slate-200">
            <div className="flex items-center justify-between border-b pb-3">
              <h2 className="text-base font-bold text-slate-900">Create Planned Content Page</h2>
              <button onClick={() => setShowCreatePageModal(false)} className="p-1 rounded hover:bg-slate-100">
                <X size={18} />
              </button>
            </div>

            <form onSubmit={handleCreatePageSubmit} className="mt-4 flex flex-col gap-3.5 text-xs">
              {pageFormError && (
                <div
                  role="alert"
                  aria-live="assertive"
                  className="flex items-start gap-2 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2.5 text-rose-800"
                >
                  <AlertTriangle size={15} className="mt-0.5 shrink-0" />
                  <span>{pageFormError}</span>
                </div>
              )}

              <div>
                <label className="font-bold text-slate-700">Page Title *</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Technical SEO Audit Guide"
                  value={pageTitle}
                  onChange={(e) => {
                    setPageTitle(e.target.value);
                    if (!pageSlug) {
                      setPageSlug(e.target.value.toLowerCase().replace(/[^a-z0-9]+/g, "-"));
                    }
                  }}
                  className="input mt-1 w-full text-xs"
                />
              </div>

              <div>
                <label className="font-bold text-slate-700">URL Slug *</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. technical-seo-audit"
                  value={pageSlug}
                  onChange={(e) => setPageSlug(e.target.value)}
                  className="input mt-1 w-full text-xs font-mono"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="font-bold text-slate-700">Content Type</label>
                  <select
                    value={pageContentType}
                    onChange={(e) => setPageContentType(e.target.value)}
                    className="input mt-1 w-full text-xs"
                  >
                    <option value="GUIDE">Guide</option>
                    <option value="PILLAR_PAGE">Pillar Page</option>
                    <option value="CLUSTER_PAGE">Cluster Page</option>
                    <option value="SUPPORTING_PAGE">Supporting Page</option>
                    <option value="LANDING_PAGE">Landing Page</option>
                    <option value="SERVICE_PAGE">Service Page</option>
                    <option value="PRODUCT_PAGE">Product Page</option>
                    <option value="COMPARISON">Comparison</option>
                    <option value="FAQ">FAQ</option>
                  </select>
                </div>

                <div>
                  <label className="font-bold text-slate-700">Priority (1-100)</label>
                  <input
                    type="number"
                    min={1}
                    max={100}
                    value={pagePriority}
                    onChange={(e) => setPagePriority(Number(e.target.value))}
                    className="input mt-1 w-full text-xs"
                  />
                </div>
              </div>

              <div>
                <label className="font-bold text-slate-700">Primary Keyword</label>
                <input
                  type="text"
                  placeholder="e.g. technical seo audit"
                  value={pagePrimaryKw}
                  onChange={(e) => setPagePrimaryKw(e.target.value)}
                  className="input mt-1 w-full text-xs"
                />
              </div>

              <div className="mt-4 flex items-center justify-end gap-2 border-t pt-4">
                <button
                  type="button"
                  onClick={() => setShowCreatePageModal(false)}
                  className="btn btn-secondary text-xs"
                >
                  Cancel
                </button>
                <button type="submit" disabled={isPending} className="btn btn-primary text-xs">
                  {isPending ? "Creating..." : "Save Planned Page"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
