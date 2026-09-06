"use client";

import { useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import {
  BookOpen,
  CheckCircle2,
  AlertCircle,
  Save,
  Clock,
  Sparkles,
  ArrowLeft,
  Search,
  Plus,
  Trash2,
  ChevronUp,
  ChevronDown,
  Layers,
  History,
  X,
  FileText,
  Tag,
  ShieldCheck,
  Globe,
  Sliders,
} from "lucide-react";
import { Card } from "@/components/card";
import type {
  PlannedContentPage,
  SEOGuide,
  SEOGuideOutlineSection,
  SEOGuideVersion,
  PageKeyword,
} from "@/lib/api-types";
import { clientApi } from "@/lib/client-api";

interface SEOGuideViewProps {
  projectId: string;
  page: PlannedContentPage;
  initialGuide: SEOGuide;
  initialVersions: SEOGuideVersion[];
  assignedKeywords?: PageKeyword[];
}

export function SEOGuideView({
  projectId,
  page,
  initialGuide,
  initialVersions,
  assignedKeywords = [],
}: SEOGuideViewProps) {
  const router = useRouter();
  const [isPending, startTransition] = useTransition();

  // Guide state
  const [guide, setGuide] = useState<SEOGuide>(initialGuide);
  const [versions, setVersions] = useState<SEOGuideVersion[]>(initialVersions);

  // Outline state
  const [outline, setOutline] = useState<SEOGuideOutlineSection[]>(
    initialGuide.outline && initialGuide.outline.length > 0
      ? initialGuide.outline
      : [
          { level: 1, title: initialGuide.recommended_title || page.title, required: true },
          { level: 2, title: "Executive Summary / Overview", required: true },
          { level: 2, title: "Core Concepts & Architecture", required: true },
          { level: 3, title: "Key Components Explained", required: false },
          { level: 2, title: "Best Practices & Implementation Steps", required: true },
          { level: 2, title: "Common Pitfalls to Avoid", required: false },
          { level: 2, title: "Conclusion & Strategic Next Steps", required: true },
        ]
  );

  // Tags states (Secondary keywords, Required topics, Key entities, Content requirements)
  const [secondaryKeywords, setSecondaryKeywords] = useState<string[]>(initialGuide.secondary_keywords || []);
  const [newSecKeyword, setNewSecKeyword] = useState("");

  const [requiredTopics, setRequiredTopics] = useState<string[]>(initialGuide.required_topics || []);
  const [newTopic, setNewTopic] = useState("");

  const [keyEntities, setKeyEntities] = useState<string[]>(initialGuide.key_entities || []);
  const [newEntity, setNewEntity] = useState("");

  const [contentReqs, setContentReqs] = useState<string[]>(initialGuide.content_requirements || []);
  const [newReq, setNewReq] = useState("");

  // Modals
  const [showVersionHistory, setShowVersionHistory] = useState(false);
  const [showApproveModal, setShowApproveModal] = useState(false);
  const [approveChangelog, setApproveChangelog] = useState("Finalized outline, metadata, and topical specifications.");
  const [notification, setNotification] = useState<{ type: "success" | "error"; message: string } | null>(null);

  // New section inputs for outline
  const [newSectionLevel, setNewSectionLevel] = useState<number>(2);
  const [newSectionTitle, setNewSectionTitle] = useState("");

  // Character counts
  const titleLength = guide.meta_title ? guide.meta_title.length : 0;
  const descLength = guide.meta_description ? guide.meta_description.length : 0;

  const handleSaveGuide = async (statusOverride?: string) => {
    startTransition(async () => {
      try {
        const updated = await clientApi<SEOGuide>(
          `/content-pages/${page.id}/seo-guide`,
          {
            method: "PUT",
            body: JSON.stringify({
              primary_keyword: guide.primary_keyword,
              secondary_keywords: secondaryKeywords,
              search_intent: guide.search_intent,
              target_audience: guide.target_audience,
              recommended_title: guide.recommended_title,
              meta_title: guide.meta_title,
              meta_description: guide.meta_description,
              recommended_url: guide.recommended_url,
              content_type: guide.content_type,
              word_count_target: Number(guide.word_count_target),
              required_topics: requiredTopics,
              key_entities: keyEntities,
              serp_notes: guide.serp_notes,
              content_requirements: contentReqs,
              outline: outline,
              status: statusOverride || guide.status,
            }),
          }
        );
        setGuide(updated);
        setNotification({ type: "success", message: "SEO Guide changes saved successfully!" });
        router.refresh();
      } catch (err) {
        setNotification({ type: "error", message: err instanceof Error ? err.message : "Failed to save SEO Guide" });
      }
    });
  };

  const handleApproveGuide = async (e: React.FormEvent) => {
    e.preventDefault();
    startTransition(async () => {
      try {
        // Save latest state first
        await clientApi(`/content-pages/${page.id}/seo-guide`, {
          method: "PUT",
          body: JSON.stringify({
            primary_keyword: guide.primary_keyword,
            secondary_keywords: secondaryKeywords,
            search_intent: guide.search_intent,
            target_audience: guide.target_audience,
            recommended_title: guide.recommended_title,
            meta_title: guide.meta_title,
            meta_description: guide.meta_description,
            recommended_url: guide.recommended_url,
            content_type: guide.content_type,
            word_count_target: Number(guide.word_count_target),
            required_topics: requiredTopics,
            key_entities: keyEntities,
            serp_notes: guide.serp_notes,
            content_requirements: contentReqs,
            outline: outline,
            status: "approved",
          }),
        });

        // Call approve endpoint to generate immutable snapshot
        const approvedGuide = await clientApi<SEOGuide>(
          `/content-pages/${page.id}/seo-guide/approve`,
          {
            method: "POST",
          }
        );

        setGuide(approvedGuide);
        setShowApproveModal(false);
        setNotification({
          type: "success",
          message: `SEO Guide approved and locked as immutable Revision ${approvedGuide.version}!`,
        });
        router.refresh();
      } catch (err) {
        setNotification({ type: "error", message: err instanceof Error ? err.message : "Failed to approve guide" });
      }
    });
  };

  // Outline helper functions
  const addSection = (e: React.FormEvent) => {
    e.preventDefault();
    if (!newSectionTitle.trim()) return;
    setOutline((prev) => [
      ...prev,
      { level: newSectionLevel, title: newSectionTitle.trim(), required: true },
    ]);
    setNewSectionTitle("");
  };

  const removeSection = (index: number) => {
    setOutline((prev) => prev.filter((_, i) => i !== index));
  };

  const moveSection = (index: number, direction: "up" | "down") => {
    if (
      (direction === "up" && index === 0) ||
      (direction === "down" && index === outline.length - 1)
    )
      return;
    const targetIndex = direction === "up" ? index - 1 : index + 1;
    const newOutline = [...outline];
    const temp = newOutline[index];
    newOutline[index] = newOutline[targetIndex];
    newOutline[targetIndex] = temp;
    setOutline(newOutline);
  };

  const updateSectionTitle = (index: number, title: string) => {
    setOutline((prev) => {
      const copy = [...prev];
      copy[index] = { ...copy[index], title };
      return copy;
    });
  };

  const updateSectionLevel = (index: number, level: number) => {
    setOutline((prev) => {
      const copy = [...prev];
      copy[index] = { ...copy[index], level };
      return copy;
    });
  };

  const toggleSectionRequired = (index: number) => {
    setOutline((prev) => {
      const copy = [...prev];
      copy[index] = { ...copy[index], required: !copy[index].required };
      return copy;
    });
  };

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

      {/* Header bar */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 bg-white p-5 rounded-2xl border border-[var(--border)] shadow-xs">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <Link
              href={`/projects/${projectId}/content`}
              className="inline-flex items-center gap-1 text-xs font-semibold text-[var(--muted)] hover:text-[var(--ink)]"
            >
              <ArrowLeft size={14} /> Back to Content Planning
            </Link>
            <span className="text-gray-300">/</span>
            <span className="text-xs font-mono text-gray-500">/{page.slug}</span>
          </div>
          <div className="flex items-center gap-3">
            <h1 className="text-xl font-bold text-[var(--ink)]">{page.title}</h1>
            <span
              className={`inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-bold uppercase tracking-wider ${
                guide.status === "approved"
                  ? "bg-emerald-100 text-emerald-800 border border-emerald-300"
                  : guide.status === "reviewed"
                  ? "bg-blue-100 text-blue-800 border border-blue-300"
                  : "bg-amber-100 text-amber-800 border border-amber-300"
              }`}
            >
              <ShieldCheck size={12} />
              {guide.status}
            </span>
            <span className="text-xs font-semibold text-gray-500 bg-gray-100 px-2 py-0.5 rounded-md">
              v{guide.version}
            </span>
          </div>
        </div>

        <div className="flex items-center gap-2.5">
          <button
            onClick={() => setShowVersionHistory(true)}
            className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg border border-[var(--border)] bg-white text-xs font-semibold text-[var(--ink)] hover:bg-gray-50 shadow-2xs"
          >
            <History size={14} />
            Version History ({versions.length})
          </button>

          <button
            onClick={() => handleSaveGuide()}
            disabled={isPending}
            className="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg border border-[var(--border)] bg-white text-xs font-semibold text-[var(--ink)] hover:bg-gray-50 shadow-2xs disabled:opacity-50"
          >
            <Save size={14} />
            {isPending ? "Saving..." : "Save Draft"}
          </button>

          {guide.status !== "approved" && (
            <button
              onClick={() => setShowApproveModal(true)}
              className="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg bg-emerald-600 text-white text-xs font-semibold hover:bg-emerald-700 shadow-2xs transition"
            >
              <CheckCircle2 size={15} />
              Approve Guide
            </button>
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* LEFT COLUMN: Outline Builder (Span 2) */}
        <div className="lg:col-span-2 space-y-6">
          {/* SECTION 1: SERP Preview & Meta Tags */}
          <Card className="p-5 border border-[var(--border)] bg-white shadow-xs">
            <div className="flex items-center justify-between mb-4">
              <div>
                <h3 className="font-bold text-sm text-[var(--ink)]">Search Snippet & Metadata</h3>
                <p className="text-xs text-[var(--muted)]">Preview how Google renders your page in search results</p>
              </div>
              <div className="flex items-center gap-2 text-xs">
                <span
                  className={`font-semibold ${
                    titleLength >= 50 && titleLength <= 60 ? "text-emerald-600" : "text-amber-600"
                  }`}
                >
                  Title: {titleLength}/60
                </span>
                <span className="text-gray-300">·</span>
                <span
                  className={`font-semibold ${
                    descLength >= 140 && descLength <= 160 ? "text-emerald-600" : "text-amber-600"
                  }`}
                >
                  Meta: {descLength}/160
                </span>
              </div>
            </div>

            {/* Google SERP Card Preview */}
            <div className="p-4 rounded-xl bg-gray-50/70 border border-gray-200 mb-5">
              <p className="text-[10px] font-mono text-gray-500 flex items-center gap-1.5 truncate">
                <Globe size={11} className="text-emerald-600" />
                https://yoursite.com/{guide.recommended_url || page.slug}
              </p>
              <h4 className="text-base font-semibold text-blue-800 hover:underline cursor-pointer mt-1 truncate">
                {guide.meta_title || guide.recommended_title || page.title}
              </h4>
              <p className="text-xs text-gray-700 mt-1 line-clamp-2 leading-relaxed">
                {guide.meta_description ||
                  "No meta description set. Write an engaging, search-optimized meta description containing the target keywords and compelling call to action."}
              </p>
            </div>

            <div className="space-y-3">
              <div>
                <label className="block text-xs font-bold text-gray-700 mb-1">Recommended H1 Title</label>
                <input
                  type="text"
                  value={guide.recommended_title || ""}
                  onChange={(e) => setGuide({ ...guide, recommended_title: e.target.value })}
                  className="w-full text-xs rounded-lg border border-[var(--border)] px-3 py-2"
                />
              </div>

              <div>
                <label className="block text-xs font-bold text-gray-700 mb-1">SERP Meta Title (Title Tag)</label>
                <input
                  type="text"
                  value={guide.meta_title || ""}
                  onChange={(e) => setGuide({ ...guide, meta_title: e.target.value })}
                  placeholder="Primary Keyword - Compelling Value Hook | Brand"
                  className="w-full text-xs rounded-lg border border-[var(--border)] px-3 py-2 font-medium"
                />
              </div>

              <div>
                <label className="block text-xs font-bold text-gray-700 mb-1">SERP Meta Description</label>
                <textarea
                  rows={3}
                  value={guide.meta_description || ""}
                  onChange={(e) => setGuide({ ...guide, meta_description: e.target.value })}
                  placeholder="Clear overview answering search intent with primary and secondary keyword inclusion..."
                  className="w-full text-xs rounded-lg border border-[var(--border)] px-3 py-2 leading-relaxed"
                />
              </div>
            </div>
          </Card>

          {/* SECTION 2: Structured Outline Builder */}
          <Card className="p-5 border border-[var(--border)] bg-white shadow-xs">
            <div className="flex items-center justify-between mb-4">
              <div>
                <h3 className="font-bold text-sm text-[var(--ink)]">Structured Heading Hierarchy & Content Outline</h3>
                <p className="text-xs text-[var(--muted)]">
                  Governed sections, sub-topics, and mandatory SEO headings required for this content piece
                </p>
              </div>
              <span className="text-xs font-semibold bg-gray-100 text-gray-700 px-2.5 py-1 rounded-md">
                {outline.length} Sections
              </span>
            </div>

            {/* Outline items list */}
            <div className="space-y-2 mb-4">
              {outline.map((sec, index) => (
                <div
                  key={index}
                  className={`flex items-center gap-2 p-2.5 rounded-xl border transition ${
                    sec.level === 1
                      ? "bg-purple-50/50 border-purple-200"
                      : sec.level === 2
                      ? "bg-blue-50/30 border-blue-100"
                      : "bg-gray-50 border-gray-200 ml-6"
                  }`}
                >
                  {/* Reorder buttons */}
                  <div className="flex flex-col gap-0.5">
                    <button
                      onClick={() => moveSection(index, "up")}
                      disabled={index === 0}
                      className="text-gray-400 hover:text-gray-700 disabled:opacity-20 p-0.5"
                    >
                      <ChevronUp size={12} />
                    </button>
                    <button
                      onClick={() => moveSection(index, "down")}
                      disabled={index === outline.length - 1}
                      className="text-gray-400 hover:text-gray-700 disabled:opacity-20 p-0.5"
                    >
                      <ChevronDown size={12} />
                    </button>
                  </div>

                  {/* Level dropdown */}
                  <select
                    value={sec.level}
                    onChange={(e) => updateSectionLevel(index, Number(e.target.value))}
                    className="text-xs font-bold font-mono px-2 py-1 rounded border border-[var(--border)] bg-white"
                  >
                    <option value={1}>H1</option>
                    <option value={2}>H2</option>
                    <option value={3}>H3</option>
                    <option value={4}>H4</option>
                  </select>

                  {/* Title input */}
                  <input
                    type="text"
                    value={sec.title}
                    onChange={(e) => updateSectionTitle(index, e.target.value)}
                    className="flex-1 text-xs font-medium bg-transparent border-0 px-2 py-1 focus:bg-white focus:ring-1 focus:ring-[var(--accent)] rounded"
                  />

                  {/* Required toggle */}
                  <button
                    onClick={() => toggleSectionRequired(index)}
                    className={`px-2 py-0.5 rounded text-[10px] font-semibold uppercase tracking-wider transition ${
                      sec.required
                        ? "bg-emerald-100 text-emerald-800"
                        : "bg-gray-200 text-gray-600"
                    }`}
                  >
                    {sec.required ? "Required" : "Optional"}
                  </button>

                  {/* Delete button */}
                  <button
                    onClick={() => removeSection(index)}
                    className="text-gray-400 hover:text-rose-600 p-1"
                    title="Delete section"
                  >
                    <Trash2 size={13} />
                  </button>
                </div>
              ))}
            </div>

            {/* Add Section Form */}
            <form onSubmit={addSection} className="flex items-center gap-2 pt-3 border-t border-[var(--border)]">
              <select
                value={newSectionLevel}
                onChange={(e) => setNewSectionLevel(Number(e.target.value))}
                className="text-xs font-bold font-mono px-2.5 py-1.5 rounded-lg border border-[var(--border)] bg-white"
              >
                <option value={2}>H2</option>
                <option value={3}>H3</option>
                <option value={1}>H1</option>
                <option value={4}>H4</option>
              </select>

              <input
                type="text"
                placeholder="New section title e.g. Step-by-Step Architecture Guide..."
                value={newSectionTitle}
                onChange={(e) => setNewSectionTitle(e.target.value)}
                className="flex-1 text-xs rounded-lg border border-[var(--border)] px-3 py-1.5"
              />

              <button
                type="submit"
                className="inline-flex items-center gap-1 px-3 py-1.5 rounded-lg bg-[var(--accent)] text-white text-xs font-semibold hover:bg-opacity-90"
              >
                <Plus size={14} /> Add Section
              </button>
            </form>
          </Card>

          {/* SECTION 3: Content Requirements & Strategic Directives */}
          <Card className="p-5 border border-[var(--border)] bg-white shadow-xs">
            <h3 className="font-bold text-sm text-[var(--ink)] mb-1">Editorial & SEO Directives</h3>
            <p className="text-xs text-[var(--muted)] mb-3">
              Mandatory editorial rules that the copywriter or AI drafting engine must adhere to
            </p>

            <div className="space-y-2 mb-3">
              {contentReqs.map((req, i) => (
                <div key={i} className="flex items-center justify-between p-2 rounded-lg bg-gray-50 text-xs text-gray-800">
                  <div className="flex items-center gap-2">
                    <CheckCircle2 size={14} className="text-emerald-600 shrink-0" />
                    <span>{req}</span>
                  </div>
                  <button
                    onClick={() => setContentReqs(contentReqs.filter((_, idx) => idx !== i))}
                    className="text-gray-400 hover:text-rose-600 ml-2"
                  >
                    <Trash2 size={12} />
                  </button>
                </div>
              ))}
            </div>

            <form
              onSubmit={(e) => {
                e.preventDefault();
                if (!newReq.trim()) return;
                setContentReqs([...contentReqs, newReq.trim()]);
                setNewReq("");
              }}
              className="flex items-center gap-2"
            >
              <input
                type="text"
                placeholder="e.g. Include original comparison table comparing AWS vs GCP architectures..."
                value={newReq}
                onChange={(e) => setNewReq(e.target.value)}
                className="flex-1 text-xs rounded-lg border border-[var(--border)] px-3 py-1.5"
              />
              <button
                type="submit"
                className="px-3 py-1.5 rounded-lg border border-[var(--border)] text-xs font-semibold text-gray-700 hover:bg-gray-50"
              >
                Add Rule
              </button>
            </form>
          </Card>
        </div>

        {/* RIGHT COLUMN: Target Specifications & Keywords (Span 1) */}
        <div className="space-y-6">
          {/* Specifications Card */}
          <Card className="p-5 border border-[var(--border)] bg-white shadow-xs space-y-4">
            <h3 className="font-bold text-sm text-[var(--ink)]">Target Specifications</h3>

            <div>
              <label className="block text-xs font-bold text-gray-700 mb-1">Primary Keyword</label>
              <input
                type="text"
                value={guide.primary_keyword || ""}
                onChange={(e) => setGuide({ ...guide, primary_keyword: e.target.value })}
                className="w-full text-xs rounded-lg border border-[var(--border)] px-3 py-2 font-bold text-[var(--accent)]"
              />
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-bold text-gray-700 mb-1">Target Words</label>
                <input
                  type="number"
                  value={guide.word_count_target || 1500}
                  onChange={(e) => setGuide({ ...guide, word_count_target: Number(e.target.value) })}
                  className="w-full text-xs rounded-lg border border-[var(--border)] px-3 py-2"
                />
              </div>

              <div>
                <label className="block text-xs font-bold text-gray-700 mb-1">Search Intent</label>
                <select
                  value={guide.search_intent}
                  onChange={(e) => setGuide({ ...guide, search_intent: e.target.value })}
                  className="w-full text-xs rounded-lg border border-[var(--border)] px-3 py-2 bg-white capitalize"
                >
                  <option value="INFORMATIONAL">Informational</option>
                  <option value="COMMERCIAL">Commercial</option>
                  <option value="TRANSACTIONAL">Transactional</option>
                  <option value="NAVIGATIONAL">Navigational</option>
                </select>
              </div>
            </div>

            <div>
              <label className="block text-xs font-bold text-gray-700 mb-1">Target Audience</label>
              <input
                type="text"
                value={guide.target_audience || ""}
                onChange={(e) => setGuide({ ...guide, target_audience: e.target.value })}
                placeholder="e.g. Senior DevOps and Security Architects"
                className="w-full text-xs rounded-lg border border-[var(--border)] px-3 py-2"
              />
            </div>

            <div>
              <label className="block text-xs font-bold text-gray-700 mb-1">SERP & Competitor Notes</label>
              <textarea
                rows={3}
                value={guide.serp_notes || ""}
                onChange={(e) => setGuide({ ...guide, serp_notes: e.target.value })}
                placeholder="Competitor benchmark angles, missing depth in top 3 rankings..."
                className="w-full text-xs rounded-lg border border-[var(--border)] px-3 py-2 text-xs"
              />
            </div>
          </Card>

          {/* Secondary Keywords Card */}
          <Card className="p-5 border border-[var(--border)] bg-white shadow-xs">
            <h3 className="font-bold text-sm text-[var(--ink)] mb-1">Secondary Target Keywords</h3>
            <p className="text-xs text-[var(--muted)] mb-3">Include naturally across subheadings and body paragraphs</p>

            <div className="flex flex-wrap gap-1.5 mb-3">
              {secondaryKeywords.map((kw, i) => (
                <span
                  key={i}
                  className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs bg-blue-50 text-blue-700 border border-blue-200"
                >
                  {kw}
                  <button
                    onClick={() => setSecondaryKeywords(secondaryKeywords.filter((_, idx) => idx !== i))}
                    className="hover:text-rose-600 ml-1"
                  >
                    <X size={12} />
                  </button>
                </span>
              ))}
            </div>

            <form
              onSubmit={(e) => {
                e.preventDefault();
                if (!newSecKeyword.trim()) return;
                setSecondaryKeywords([...secondaryKeywords, newSecKeyword.trim()]);
                setNewSecKeyword("");
              }}
              className="flex items-center gap-2"
            >
              <input
                type="text"
                placeholder="Add secondary keyword..."
                value={newSecKeyword}
                onChange={(e) => setNewSecKeyword(e.target.value)}
                className="flex-1 text-xs rounded-lg border border-[var(--border)] px-3 py-1.5"
              />
              <button
                type="submit"
                className="px-3 py-1.5 rounded-lg border border-[var(--border)] text-xs font-semibold hover:bg-gray-50"
              >
                Add
              </button>
            </form>
          </Card>

          {/* Key Entities & Topics */}
          <Card className="p-5 border border-[var(--border)] bg-white shadow-xs space-y-4">
            <div>
              <h3 className="font-bold text-sm text-[var(--ink)] mb-1">Required Knowledge Entities</h3>
              <p className="text-xs text-[var(--muted)] mb-2">Semantic entities required for topical authority</p>

              <div className="flex flex-wrap gap-1.5 mb-2">
                {keyEntities.map((ent, i) => (
                  <span
                    key={i}
                    className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs bg-purple-50 text-purple-700 border border-purple-200 font-mono"
                  >
                    {ent}
                    <button
                      onClick={() => setKeyEntities(keyEntities.filter((_, idx) => idx !== i))}
                      className="hover:text-rose-600 ml-0.5"
                    >
                      <X size={11} />
                    </button>
                  </span>
                ))}
              </div>

              <form
                onSubmit={(e) => {
                  e.preventDefault();
                  if (!newEntity.trim()) return;
                  setKeyEntities([...keyEntities, newEntity.trim()]);
                  setNewEntity("");
                }}
                className="flex items-center gap-2"
              >
                <input
                  type="text"
                  placeholder="Entity e.g. Zero Trust Architecture"
                  value={newEntity}
                  onChange={(e) => setNewEntity(e.target.value)}
                  className="flex-1 text-xs rounded-lg border border-[var(--border)] px-3 py-1.5"
                />
                <button type="submit" className="px-3 py-1.5 rounded-lg border border-[var(--border)] text-xs font-semibold">
                  Add
                </button>
              </form>
            </div>
          </Card>
        </div>
      </div>

      {/* MODAL: APPROVE GUIDE */}
      {showApproveModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-xs p-4">
          <div className="bg-white rounded-2xl shadow-xl border border-[var(--border)] w-full max-w-md overflow-hidden animate-in fade-in zoom-in-95 duration-150">
            <div className="flex items-center justify-between px-6 py-4 border-b border-[var(--border)]">
              <h3 className="font-bold text-base text-[var(--ink)]">Approve SEO Guide</h3>
              <button onClick={() => setShowApproveModal(false)} className="text-gray-400 hover:text-gray-700 p-1">
                <X size={18} />
              </button>
            </div>

            <form onSubmit={handleApproveGuide} className="p-6 space-y-4">
              <p className="text-xs text-gray-600 leading-relaxed">
                Approving this SEO Guide locks the outline, target keywords, and metadata into an immutable version snapshot (v{guide.version + 1}). Content writers will follow these guidelines.
              </p>

              <div>
                <label className="block text-xs font-bold text-gray-700 mb-1">Approval Notes / Changelog</label>
                <textarea
                  rows={3}
                  required
                  value={approveChangelog}
                  onChange={(e) => setApproveChangelog(e.target.value)}
                  className="w-full text-xs rounded-lg border border-[var(--border)] px-3 py-2"
                />
              </div>

              <div className="pt-3 border-t border-[var(--border)] flex justify-end gap-2">
                <button
                  type="button"
                  onClick={() => setShowApproveModal(false)}
                  className="px-4 py-2 rounded-lg border border-[var(--border)] text-xs font-semibold text-gray-700 hover:bg-gray-50"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isPending}
                  className="px-5 py-2 rounded-lg bg-emerald-600 text-white text-xs font-semibold hover:bg-emerald-700 disabled:opacity-50"
                >
                  {isPending ? "Approving..." : "Confirm & Snapshot"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* DRAWER: VERSION HISTORY */}
      {showVersionHistory && (
        <div className="fixed inset-0 z-50 flex justify-end bg-black/40 backdrop-blur-xs">
          <div className="bg-white w-full max-w-md h-full shadow-2xl border-l border-[var(--border)] flex flex-col animate-in slide-in-from-right duration-200">
            <div className="flex items-center justify-between px-6 py-4 border-b border-[var(--border)]">
              <div>
                <h3 className="font-bold text-base text-[var(--ink)]">Immutable Versions</h3>
                <p className="text-xs text-[var(--muted)]">Audit trail of approved SEO Guide iterations</p>
              </div>
              <button onClick={() => setShowVersionHistory(false)} className="text-gray-400 hover:text-gray-700 p-1">
                <X size={18} />
              </button>
            </div>

            <div className="flex-1 overflow-y-auto p-6 space-y-4">
              {versions.length === 0 ? (
                <div className="py-12 text-center text-[var(--muted)]">
                  <History size={32} className="mx-auto mb-2 opacity-40 text-gray-400" />
                  <p className="font-semibold text-sm">No locked versions yet</p>
                  <p className="text-xs mt-1">Approve your draft guide to produce an immutable snapshot.</p>
                </div>
              ) : (
                versions.map((ver) => (
                  <div key={ver.id} className="p-4 rounded-xl border border-[var(--border)] bg-gray-50/70 space-y-2">
                    <div className="flex items-center justify-between">
                      <span className="inline-flex px-2.5 py-0.5 rounded-full text-xs font-bold bg-emerald-100 text-emerald-800">
                        Version {ver.version}
                      </span>
                      <span className="text-[11px] text-gray-500 font-mono">
                        {new Date(ver.created_at).toLocaleDateString()}
                      </span>
                    </div>

                    <p className="text-xs font-medium text-gray-800 mt-1">
                      {ver.change_summary || "Snapshot created upon guide approval."}
                    </p>

                    <div className="text-[11px] text-gray-500 pt-2 border-t border-gray-200 flex items-center justify-between">
                      <span>Immutable Record</span>
                      <span className="font-mono text-[10px]">{ver.id.slice(0, 8)}...</span>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
