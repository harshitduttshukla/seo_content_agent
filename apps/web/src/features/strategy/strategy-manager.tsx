"use client";

import { useEffect, useRef, useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import {
  History,
  Save,
  Plus,
  Trash2,
  CheckCircle2,
  AlertCircle,
  Sparkles,
  Loader2,
} from "lucide-react";
import type { components } from "@seo-content/shared-types";
import { Card } from "@/components/card";
import type { SEOStrategy, SEOStrategyVersion, StrategyData } from "@/lib/api-types";
import { clientApi } from "@/lib/client-api";

type ProductServiceItem = components["schemas"]["ProductServiceSchema"];
type PersonaItem = components["schemas"]["PersonaSchema"];
type MarketItem = components["schemas"]["MarketSchema"];
type GoalItem = components["schemas"]["SEOGoalSchema"];
type CompetitorItem = components["schemas"]["CompetitorSchema"];

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
  const [currentStrategy, setCurrentStrategy] = useState<SEOStrategy>(initialStrategy);
  const [versionList, setVersionList] = useState<SEOStrategyVersion[]>(versions);
  const [strategyData, setStrategyData] = useState<StrategyData>(initialStrategy.strategy_data);
  const [changeSummary, setChangeSummary] = useState("");
  const [showHistory, setShowHistory] = useState(false);
  const [selectedVersion, setSelectedVersion] = useState<SEOStrategyVersion | null>(null);
  const [saveStatus, setSaveStatus] = useState<"idle" | "success" | "error">("idle");
  const [errorMessage, setErrorMessage] = useState("");
  const [isSaving, setIsSaving] = useState(false);
  const isSavingRef = useRef(false);

  useEffect(() => {
    setCurrentStrategy(initialStrategy);
  }, [initialStrategy]);

  useEffect(() => {
    setVersionList(versions);
  }, [versions]);

  // AI Generation State
  const [isGenerating, setIsGenerating] = useState(false);
  const [aiStatus, setAiStatus] = useState<"idle" | "generating" | "success" | "error">("idle");
  const [aiErrorMessage, setAiErrorMessage] = useState("");

  const isInitialDraft =
    versionList.length === 0 ||
    (versionList.length === 1 &&
      (versionList[0].change_summary === "Initial strategy template initialized" ||
        currentStrategy.status === "draft"));

  const handleGenerateWithAi = async () => {
    setIsGenerating(true);
    setAiStatus("idle");
    setAiErrorMessage("");

    try {
      const draft = await clientApi<StrategyData>(`/projects/${projectId}/strategy/generate`, {
        method: "POST",
      });
      setStrategyData(draft);
      setAiStatus("success");
      if (!changeSummary.trim()) {
        setChangeSummary("Initial SEO strategy generated with AI and reviewed by user.");
      }
    } catch (err: unknown) {
      setAiStatus("error");
      setAiErrorMessage(
        err instanceof Error ? err.message : "Failed to generate initial SEO strategy draft."
      );
    } finally {
      setIsGenerating(false);
    }
  };

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    if (isSavingRef.current || isSaving || isPending || isGenerating) {
      return;
    }
    isSavingRef.current = true;
    setIsSaving(true);
    setSaveStatus("idle");
    setErrorMessage("");

    try {
      const defaultSummary = isInitialDraft
        ? "Initial SEO strategy reviewed and saved as Version 1"
        : "Saved strategy updates";
      const finalSummary = changeSummary.trim() || defaultSummary;

      const payloadStrategyData = {
        business_context: {
          business_name: strategyData.business_context?.business_name ?? "",
          description: strategyData.business_context?.description ?? "",
          industry: strategyData.business_context?.industry ?? "",
          locations: Array.isArray(strategyData.business_context?.locations)
            ? strategyData.business_context.locations
            : [],
        },
        audience: {
          segments: Array.isArray(strategyData.audience?.segments)
            ? strategyData.audience.segments
            : [],
          personas: Array.isArray(strategyData.audience?.personas)
            ? strategyData.audience.personas.map((p) => ({
                name: p.name ?? "",
                description: p.description ?? "",
                problems: Array.isArray(p.problems) ? p.problems : [],
                goals: Array.isArray(p.goals) ? p.goals : [],
                funnel_stage: p.funnel_stage ?? "TOFU",
              }))
            : [],
          needs: Array.isArray(strategyData.audience?.needs)
            ? strategyData.audience.needs
            : [],
          buying_stages: Array.isArray(strategyData.audience?.buying_stages)
            ? strategyData.audience.buying_stages
            : [],
        },
        products: Array.isArray(strategyData.products)
          ? strategyData.products.map((prod) => ({
              name: prod.name ?? "",
              description: prod.description ?? "",
              category: prod.category ?? "Core Product",
              url: prod.url ?? null,
              priority: typeof prod.priority === "number" ? prod.priority : 1,
            }))
          : [],
        services: Array.isArray(strategyData.services)
          ? strategyData.services.map((srv) => ({
              name: srv.name ?? "",
              description: srv.description ?? "",
              category: srv.category ?? "Service",
              url: srv.url ?? null,
              priority: typeof srv.priority === "number" ? srv.priority : 1,
            }))
          : [],
        markets: Array.isArray(strategyData.markets)
          ? strategyData.markets.map((m) => ({
              name: m.name ?? "",
              code: m.code ?? "",
              is_primary: Boolean(m.is_primary),
            }))
          : [],
        goals: Array.isArray(strategyData.goals)
          ? strategyData.goals.map((g) => ({
              type: g.type ?? "LEAD_GENERATION",
              description: g.description ?? "",
              priority: typeof g.priority === "number" ? g.priority : 1,
            }))
          : [],
        competitors: Array.isArray(strategyData.competitors)
          ? strategyData.competitors.map((c) => ({
              name: c.name ?? "",
              domain: c.domain ?? "",
              strengths: Array.isArray(c.strengths) ? c.strengths : [],
            }))
          : [],
        seo_objectives: Array.isArray(strategyData.seo_objectives)
          ? strategyData.seo_objectives
          : [],
        content_objectives: Array.isArray(strategyData.content_objectives)
          ? strategyData.content_objectives
          : [],
        priority_topics: Array.isArray(strategyData.priority_topics)
          ? strategyData.priority_topics
          : [],
      };

      const updatedStrategy = await clientApi<SEOStrategy>(`/projects/${projectId}/strategy`, {
        method: "PUT",
        body: JSON.stringify({
          change_summary: finalSummary,
          strategy_data: payloadStrategyData,
        }),
      });

      const versionsRes = await clientApi<{ items: SEOStrategyVersion[] }>(
        `/projects/${projectId}/strategy/versions`
      ).catch(() => null);

      setCurrentStrategy(updatedStrategy);
      if (versionsRes?.items) {
        setVersionList(versionsRes.items);
      }
      setSaveStatus("success");
      setChangeSummary("");
      startTransition(() => {
        router.refresh();
      });
    } catch (err: unknown) {
      setSaveStatus("error");
      setErrorMessage(err instanceof Error ? err.message : "Failed to save strategy");
    } finally {
      isSavingRef.current = false;
      setIsSaving(false);
    }
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

  const addService = () => {
    const currentServices = (strategyData.services || []) as ProductServiceItem[];
    setStrategyData({
      ...strategyData,
      services: [
        ...currentServices,
        { name: "", description: "", category: "Service", priority: 1, url: null },
      ],
    });
  };

  const removeService = (index: number) => {
    const next = [...((strategyData.services || []) as ProductServiceItem[])];
    next.splice(index, 1);
    setStrategyData({ ...strategyData, services: next });
  };

  const addPersona = () => {
    const personas = (strategyData.audience?.personas || []) as PersonaItem[];
    setStrategyData({
      ...strategyData,
      audience: {
        ...strategyData.audience,
        personas: [
          ...personas,
          {
            name: "",
            description: "",
            problems: [],
            goals: [],
            funnel_stage: "TOFU",
          },
        ],
      },
    });
  };

  const removePersona = (index: number) => {
    const personas = [...((strategyData.audience?.personas || []) as PersonaItem[])];
    personas.splice(index, 1);
    setStrategyData({
      ...strategyData,
      audience: { ...strategyData.audience, personas },
    });
  };

  const addCompetitor = () => {
    const competitors = (strategyData.competitors || []) as CompetitorItem[];
    setStrategyData({
      ...strategyData,
      competitors: [
        ...competitors,
        { name: "", domain: "", strengths: [] },
      ],
    });
  };

  const removeCompetitor = (index: number) => {
    const competitors = [...((strategyData.competitors || []) as CompetitorItem[])];
    competitors.splice(index, 1);
    setStrategyData({ ...strategyData, competitors });
  };

  return (
    <div className="grid gap-6">
      {/* Header & Status Bar */}
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <span className="rounded-full bg-[var(--surface-soft)] px-2.5 py-0.5 text-xs font-semibold text-[var(--accent)]">
              Version {currentStrategy.current_version}
            </span>
            <span className="rounded-full bg-emerald-50 px-2.5 py-0.5 text-xs font-semibold text-emerald-700 capitalize">
              {isInitialDraft ? "Draft" : currentStrategy.status}
            </span>
          </div>
          <p className="mt-1 text-sm text-[var(--muted)]">
            Last updated: {new Date(currentStrategy.updated_at).toLocaleString()}
          </p>
        </div>

        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={handleGenerateWithAi}
            disabled={isGenerating || isPending || isSaving}
            className="inline-flex items-center gap-2 rounded-lg bg-[var(--accent)] px-3.5 py-2 text-sm font-semibold text-white hover:opacity-90 disabled:opacity-50 transition cursor-pointer shadow-xs"
          >
            {isGenerating ? (
              <>
                <Loader2 className="animate-spin" size={16} /> Generating V1 Draft...
              </>
            ) : (
              <>
                <Sparkles size={16} /> {isInitialDraft ? "Generate Strategy with AI" : "Regenerate Draft with AI"}
              </>
            )}
          </button>

          <button
            type="button"
            onClick={() => setShowHistory(!showHistory)}
            disabled={isGenerating || isPending || isSaving}
            className="inline-flex items-center gap-2 rounded-lg border border-[var(--border)] bg-white px-3.5 py-2 text-sm font-semibold hover:bg-slate-50 disabled:opacity-50 transition cursor-pointer"
          >
            <History size={16} /> Version History ({versionList.length})
          </button>
        </div>
      </div>

      {/* AI Kickstart Alert for new / uncommitted strategy */}
      {isInitialDraft && aiStatus === "idle" && (
        <Card className="p-5 border-indigo-200 bg-gradient-to-r from-indigo-50/70 via-sky-50/40 to-white">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
            <div>
              <div className="flex items-center gap-2">
                <Sparkles className="text-[var(--accent)]" size={18} />
                <h3 className="text-sm font-bold text-[var(--ink)]">AI Strategy Kickstart</h3>
                <span className="rounded-full bg-indigo-100 px-2 py-0.5 text-[10px] font-semibold text-indigo-700">
                  Version 1 Ready
                </span>
              </div>
              <p className="text-xs text-slate-600 mt-1 max-w-2xl">
                Automatically generate an authoritative initial SEO Strategy draft using your project information, crawled website pages, and keywords. You can review, edit, and enhance every field before saving as Version 1.
              </p>
            </div>
            <button
              type="button"
              onClick={handleGenerateWithAi}
              disabled={isGenerating}
              className="inline-flex items-center justify-center gap-1.5 rounded-lg bg-[var(--accent)] px-4 py-2 text-xs font-bold text-white shadow-xs hover:opacity-90 disabled:opacity-50 transition cursor-pointer shrink-0"
            >
              {isGenerating ? <Loader2 className="animate-spin" size={14} /> : <Sparkles size={14} />}
              Generate with AI
            </button>
          </div>
        </Card>
      )}

      {/* AI status alerts */}
      {aiStatus === "generating" && (
        <div className="flex items-center gap-2 rounded-lg bg-indigo-50 p-4 text-sm font-medium text-indigo-800 border border-indigo-200">
          <Loader2 className="animate-spin" size={18} /> Generating your initial SEO strategy draft using project intelligence...
        </div>
      )}

      {aiStatus === "success" && (
        <div className="flex items-center gap-2 rounded-lg bg-emerald-50 p-4 text-sm font-medium text-emerald-800 border border-emerald-200">
          <CheckCircle2 size={18} /> Initial SEO Strategy draft generated by AI! Review and edit the fields below, then click &quot;Save as Version 1&quot; to activate.
        </div>
      )}

      {aiStatus === "error" && (
        <div className="flex items-center gap-2 rounded-lg bg-rose-50 p-4 text-sm font-medium text-rose-800 border border-rose-200">
          <AlertCircle size={18} /> {aiErrorMessage || "Failed to generate initial SEO strategy draft. You can retry or fill out the form manually."}
        </div>
      )}

      {saveStatus === "success" && (
        <div className="flex items-center gap-2 rounded-lg bg-emerald-50 p-4 text-sm font-medium text-emerald-800 border border-emerald-200">
          <CheckCircle2 size={18} /> Strategy successfully updated and immutable version recorded.
        </div>
      )}

      {saveStatus === "error" && (
        <div className="flex items-center gap-2 rounded-lg bg-rose-50 p-4 text-sm font-medium text-rose-800 border border-rose-200">
          <AlertCircle size={18} /> {errorMessage || "An error occurred while saving."}
        </div>
      )}

      {/* Version History Drawer */}
      {showHistory && (
        <Card className="p-5 border-indigo-100 bg-slate-50/70">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-base font-bold">Immutable Version History</h3>
            <button
              type="button"
              onClick={() => setShowHistory(false)}
              className="text-xs text-[var(--muted)] hover:text-[var(--ink)] cursor-pointer"
            >
              Close
            </button>
          </div>
          <div className="grid gap-2 max-h-60 overflow-y-auto">
            {versionList.map((v) => (
              <div
                key={v.id}
                onClick={() => setSelectedVersion(v)}
                className={`p-3 rounded-lg border text-sm cursor-pointer transition flex items-center justify-between ${
                  selectedVersion?.id === v.id
                    ? "border-[var(--accent)] bg-white shadow-sm"
                    : "bg-white border-[var(--border)] hover:bg-slate-50"
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
        {/* Section 1: Business Context & Positioning */}
        <Card className="p-6">
          <h2 className="text-lg font-bold text-[var(--ink)] mb-4">1. Business Context & Positioning</h2>
          <div className="grid gap-4 md:grid-cols-2">
            <div>
              <label className="block text-xs font-bold uppercase tracking-wider text-[var(--muted)] mb-1">
                Business Name
              </label>
              <input
                type="text"
                className="w-full rounded-lg border border-[var(--border)] p-2.5 text-sm bg-white"
                placeholder="e.g. Acme Fleet Intelligence"
                value={strategyData.business_context?.business_name || ""}
                onChange={(e) =>
                  setStrategyData({
                    ...strategyData,
                    business_context: {
                      business_name: e.target.value,
                      industry: strategyData.business_context?.industry || "",
                      description: strategyData.business_context?.description || "",
                      locations: strategyData.business_context?.locations || [],
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
                placeholder="e.g. B2B SaaS / Vehicle Fleet Telematics"
                value={strategyData.business_context?.industry || ""}
                onChange={(e) =>
                  setStrategyData({
                    ...strategyData,
                    business_context: {
                      business_name: strategyData.business_context?.business_name || "",
                      description: strategyData.business_context?.description || "",
                      industry: e.target.value,
                      locations: strategyData.business_context?.locations || [],
                    },
                  })
                }
              />
            </div>
            <div className="md:col-span-2">
              <label className="block text-xs font-bold uppercase tracking-wider text-[var(--muted)] mb-1">
                Business Description & Core Value Proposition
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
                      locations: strategyData.business_context?.locations || [],
                    },
                  })
                }
              />
            </div>
          </div>
        </Card>

        {/* Section 2: Products & Services */}
        <Card className="p-6">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h2 className="text-lg font-bold text-[var(--ink)]">2. Products & Offerings</h2>
              <p className="text-xs text-[var(--muted)] mt-0.5">Used for deterministic business value keyword scoring</p>
            </div>
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={addProduct}
                className="inline-flex items-center gap-1.5 rounded-md border border-[var(--border)] px-2.5 py-1 text-xs font-bold hover:bg-slate-50 transition cursor-pointer"
              >
                <Plus size={14} /> Add Product
              </button>
              <button
                type="button"
                onClick={addService}
                className="inline-flex items-center gap-1.5 rounded-md border border-[var(--border)] px-2.5 py-1 text-xs font-bold hover:bg-slate-50 transition cursor-pointer"
              >
                <Plus size={14} /> Add Service
              </button>
            </div>
          </div>

          <div className="grid gap-4">
            {/* Products list */}
            {((strategyData.products || []) as ProductServiceItem[]).map((prod, idx) => (
              <div key={`prod-${idx}`} className="flex gap-3 items-start p-3 bg-slate-50 rounded-lg border border-[var(--border)]">
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
                  className="text-slate-400 hover:text-rose-600 p-2 cursor-pointer"
                  title="Remove Product"
                >
                  <Trash2 size={16} />
                </button>
              </div>
            ))}

            {/* Services list */}
            {((strategyData.services || []) as ProductServiceItem[]).map((srv, idx) => (
              <div key={`srv-${idx}`} className="flex gap-3 items-start p-3 bg-slate-50 rounded-lg border border-[var(--border)]">
                <span className="rounded bg-sky-100 text-sky-800 text-[10px] font-bold px-2 py-1 mt-1.5">Service</span>
                <input
                  type="text"
                  placeholder="Service name"
                  className="flex-1 rounded-md border border-[var(--border)] p-2 text-sm bg-white"
                  value={srv.name || ""}
                  onChange={(e) => {
                    const next = [...((strategyData.services || []) as ProductServiceItem[])];
                    next[idx] = { ...next[idx], name: e.target.value };
                    setStrategyData({ ...strategyData, services: next });
                  }}
                />
                <input
                  type="text"
                  placeholder="Service description"
                  className="flex-[2] rounded-md border border-[var(--border)] p-2 text-sm bg-white"
                  value={srv.description || ""}
                  onChange={(e) => {
                    const next = [...((strategyData.services || []) as ProductServiceItem[])];
                    next[idx] = { ...next[idx], description: e.target.value };
                    setStrategyData({ ...strategyData, services: next });
                  }}
                />
                <button
                  type="button"
                  onClick={() => removeService(idx)}
                  className="text-slate-400 hover:text-rose-600 p-2 cursor-pointer"
                  title="Remove Service"
                >
                  <Trash2 size={16} />
                </button>
              </div>
            ))}
          </div>
        </Card>

        {/* Section 3: Target Audience & Personas */}
        <Card className="p-6">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h2 className="text-lg font-bold text-[var(--ink)]">3. Target Audience & Personas</h2>
              <p className="text-xs text-[var(--muted)] mt-0.5">Identifies buyer intent and search journeys</p>
            </div>
            <button
              type="button"
              onClick={addPersona}
              className="inline-flex items-center gap-1.5 rounded-md border border-[var(--border)] px-2.5 py-1 text-xs font-bold hover:bg-slate-50 transition cursor-pointer"
            >
              <Plus size={14} /> Add Persona
            </button>
          </div>

          <div className="grid gap-4">
            <div>
              <label className="block text-xs font-bold uppercase tracking-wider text-[var(--muted)] mb-1">
                Target Audience Segments (Comma-separated)
              </label>
              <input
                type="text"
                className="w-full rounded-lg border border-[var(--border)] p-2.5 text-sm bg-white"
                placeholder="e.g. Enterprise Fleet Managers, Independent Repair Shops, Logistics Directors"
                value={(strategyData.audience?.segments || []).join(", ")}
                onChange={(e) => {
                  const segments = e.target.value.split(",").map((s) => s.trim()).filter(Boolean);
                  setStrategyData({
                    ...strategyData,
                    audience: { ...strategyData.audience, segments },
                  });
                }}
              />
            </div>

            {/* Personas cards */}
            <div className="grid gap-3 sm:grid-cols-2">
              {((strategyData.audience?.personas || []) as PersonaItem[]).map((persona, idx) => (
                <div key={`persona-${idx}`} className="p-4 bg-slate-50 rounded-lg border border-[var(--border)] relative">
                  <button
                    type="button"
                    onClick={() => removePersona(idx)}
                    className="absolute top-3 right-3 text-slate-400 hover:text-rose-600 cursor-pointer"
                    title="Remove Persona"
                  >
                    <Trash2 size={16} />
                  </button>
                  <div className="grid gap-2">
                    <input
                      type="text"
                      placeholder="Persona Title (e.g. Fleet Director)"
                      className="font-bold rounded-md border border-[var(--border)] p-1.5 text-sm bg-white"
                      value={persona.name || ""}
                      onChange={(e) => {
                        const personas = [...((strategyData.audience?.personas || []) as PersonaItem[])];
                        personas[idx] = { ...personas[idx], name: e.target.value };
                        setStrategyData({
                          ...strategyData,
                          audience: { ...strategyData.audience, personas },
                        });
                      }}
                    />
                    <textarea
                      rows={2}
                      placeholder="Persona description & challenges"
                      className="rounded-md border border-[var(--border)] p-1.5 text-xs bg-white"
                      value={persona.description || ""}
                      onChange={(e) => {
                        const personas = [...((strategyData.audience?.personas || []) as PersonaItem[])];
                        personas[idx] = { ...personas[idx], description: e.target.value };
                        setStrategyData({
                          ...strategyData,
                          audience: { ...strategyData.audience, personas },
                        });
                      }}
                    />
                  </div>
                </div>
              ))}
            </div>
          </div>
        </Card>

        {/* Section 4: Competitors */}
        <Card className="p-6">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h2 className="text-lg font-bold text-[var(--ink)]">4. Market & Competitors</h2>
              <p className="text-xs text-[var(--muted)] mt-0.5">Defines competitor search share and differentiation</p>
            </div>
            <button
              type="button"
              onClick={addCompetitor}
              className="inline-flex items-center gap-1.5 rounded-md border border-[var(--border)] px-2.5 py-1 text-xs font-bold hover:bg-slate-50 transition cursor-pointer"
            >
              <Plus size={14} /> Add Competitor
            </button>
          </div>

          <div className="grid gap-3">
            {((strategyData.competitors || []) as CompetitorItem[]).map((comp, idx) => (
              <div key={`comp-${idx}`} className="flex gap-3 items-center p-3 bg-slate-50 rounded-lg border border-[var(--border)]">
                <input
                  type="text"
                  placeholder="Competitor Name"
                  className="flex-1 rounded-md border border-[var(--border)] p-2 text-sm bg-white"
                  value={comp.name || ""}
                  onChange={(e) => {
                    const comps = [...((strategyData.competitors || []) as CompetitorItem[])];
                    comps[idx] = { ...comps[idx], name: e.target.value };
                    setStrategyData({ ...strategyData, competitors: comps });
                  }}
                />
                <input
                  type="text"
                  placeholder="Domain (e.g. competitor.com)"
                  className="flex-1 rounded-md border border-[var(--border)] p-2 text-sm bg-white"
                  value={comp.domain || ""}
                  onChange={(e) => {
                    const comps = [...((strategyData.competitors || []) as CompetitorItem[])];
                    comps[idx] = { ...comps[idx], domain: e.target.value };
                    setStrategyData({ ...strategyData, competitors: comps });
                  }}
                />
                <button
                  type="button"
                  onClick={() => removeCompetitor(idx)}
                  className="text-slate-400 hover:text-rose-600 p-2 cursor-pointer"
                  title="Remove Competitor"
                >
                  <Trash2 size={16} />
                </button>
              </div>
            ))}
          </div>
        </Card>

        {/* Section 5: SEO Goals & Strategic Topics */}
        <Card className="p-6">
          <h2 className="text-lg font-bold text-[var(--ink)] mb-4">5. SEO Objectives & Priority Topics</h2>
          <div className="grid gap-4 md:grid-cols-2">
            <div>
              <label className="block text-xs font-bold uppercase tracking-wider text-[var(--muted)] mb-1">
                SEO Objectives (Comma-separated)
              </label>
              <textarea
                rows={3}
                className="w-full rounded-lg border border-[var(--border)] p-2.5 text-xs bg-white"
                placeholder="e.g. Build topical authority in vehicle diagnostics, Rank top 3 for fleet telematics software"
                value={(strategyData.seo_objectives || []).join(", ")}
                onChange={(e) => {
                  const seo_objectives = e.target.value.split(",").map((s) => s.trim()).filter(Boolean);
                  setStrategyData({ ...strategyData, seo_objectives });
                }}
              />
            </div>
            <div>
              <label className="block text-xs font-bold uppercase tracking-wider text-[var(--muted)] mb-1">
                Priority Content Topics (Comma-separated)
              </label>
              <textarea
                rows={3}
                className="w-full rounded-lg border border-[var(--border)] p-2.5 text-xs bg-white"
                placeholder="e.g. OBD2 Diagnostic Standards, Fleet Maintenance Best Practices, Telematics Hardware"
                value={(strategyData.priority_topics || []).join(", ")}
                onChange={(e) => {
                  const priority_topics = e.target.value.split(",").map((s) => s.trim()).filter(Boolean);
                  setStrategyData({ ...strategyData, priority_topics });
                }}
              />
            </div>
          </div>
        </Card>

        {/* Change Summary & Save Bar */}
        <Card className="p-6 bg-slate-50 border-slate-200">
          <div className="flex flex-col sm:flex-row gap-4 items-end">
            <div className="flex-1 w-full">
              <label className="block text-xs font-bold uppercase tracking-wider text-[var(--muted)] mb-1">
                Version Change Summary
              </label>
              <input
                type="text"
                className="w-full rounded-lg border border-[var(--border)] p-2.5 text-sm bg-white"
                placeholder={
                  isInitialDraft
                    ? "Initial SEO strategy generated with AI and reviewed by user."
                    : "Explain what was changed in this version (e.g. Added enterprise product line)"
                }
                value={changeSummary}
                onChange={(e) => setChangeSummary(e.target.value)}
              />
            </div>
            <button
              type="submit"
              disabled={isSaving || isPending || isGenerating}
              className="inline-flex items-center justify-center gap-2 rounded-lg bg-[var(--accent)] px-5 py-2.5 text-sm font-bold text-white shadow-sm hover:opacity-90 disabled:opacity-50 transition cursor-pointer"
            >
              {isSaving || isPending ? (
                <Loader2 className="animate-spin" size={16} />
              ) : (
                <Save size={16} />
              )}
              {isSaving || isPending
                ? isInitialDraft
                  ? "Saving Version 1..."
                  : "Saving Version..."
                : isInitialDraft
                ? "Save as Version 1"
                : "Save New Version"}
            </button>
          </div>
        </Card>
      </form>
    </div>
  );
}
