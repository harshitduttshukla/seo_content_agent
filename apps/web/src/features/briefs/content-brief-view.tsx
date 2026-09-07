"use client";

import React, { useState } from "react";
import type { ContentBrief } from "@/lib/api-types";
import { clientApi } from "@/lib/client-api";
import {
  CheckCircle2,
  Clock,
  Edit3,
  ExternalLink,
  FileText,
  Hash,
  Link2,
  Save,
  ShieldAlert,
  Sparkles,
  Target,
} from "lucide-react";

interface ContentBriefViewProps {
  brief: ContentBrief;
  onUpdate?: (updatedBrief: ContentBrief) => void;
  onApprove?: () => void;
}

export function ContentBriefView({
  brief,
  onUpdate,
  onApprove,
}: ContentBriefViewProps) {
  const [isEditing, setIsEditing] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [isApproving, setIsApproving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [formData, setFormData] = useState({
    recommended_title: brief.recommended_title || "",
    recommended_url: brief.recommended_url || "",
    meta_title: brief.meta_title || "",
    meta_description: brief.meta_description || "",
    target_audience: brief.target_audience || "",
    business_goal: brief.business_goal || "",
    search_intent: brief.search_intent || "INFORMATIONAL",
    target_word_count: brief.target_word_count || 1500,
    required_topics: brief.required_topics || [],
    secondary_keywords: brief.secondary_keywords || [],
    newTopic: "",
    newKeyword: "",
  });

  const handleSave = async () => {
    setIsSaving(true);
    setError(null);
    try {
      const updatedBrief = await clientApi<ContentBrief>(`/content-briefs/${brief.id}`, {
        method: "PUT",
        body: JSON.stringify({
          recommended_title: formData.recommended_title,
          recommended_url: formData.recommended_url,
          meta_title: formData.meta_title,
          meta_description: formData.meta_description,
          target_audience: formData.target_audience,
          business_goal: formData.business_goal,
          search_intent: formData.search_intent,
          target_word_count: Number(formData.target_word_count),
          required_topics: formData.required_topics,
          secondary_keywords: formData.secondary_keywords,
        }),
      });
      setIsEditing(false);
      onUpdate?.(updatedBrief);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to update content brief";
      setError(msg);
    } finally {
      setIsSaving(false);
    }
  };

  const handleApprove = async () => {
    setIsApproving(true);
    setError(null);
    try {
      const approvedBrief = await clientApi<ContentBrief>(`/content-briefs/${brief.id}/approve`, {
        method: "POST",
        body: JSON.stringify({ change_summary: "Content brief approved for production" }),
      });
      onApprove?.();
      onUpdate?.(approvedBrief);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to approve content brief";
      setError(msg);
    } finally {
      setIsApproving(false);
    }
  };

  const isApproved = brief.status === "APPROVED";

  return (
    <div className="max-w-5xl mx-auto space-y-6 pb-12" data-testid="content-brief-view">
      {/* Header Banner */}
      <div className="bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800 p-6 shadow-sm">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-3">
              <span className="text-xs font-semibold px-2.5 py-0.5 rounded-full bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300">
                Brief v{brief.version}
              </span>
              <span
                className={`text-xs font-semibold px-2.5 py-0.5 rounded-full flex items-center gap-1 ${
                  isApproved
                    ? "bg-emerald-50 text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-400 border border-emerald-200 dark:border-emerald-800"
                    : "bg-amber-50 text-amber-700 dark:bg-amber-950/40 dark:text-amber-400 border border-amber-200 dark:border-amber-800"
                }`}
                data-testid="brief-status-badge"
              >
                {isApproved ? <CheckCircle2 className="w-3.5 h-3.5" /> : <Clock className="w-3.5 h-3.5" />}
                {brief.status}
              </span>
            </div>
            <h2 className="text-2xl font-bold text-slate-900 dark:text-white mt-2">
              {brief.recommended_title || "Content Brief"}
            </h2>
            <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
              Governed SEO & brand brief. All blocks generated or edited by AI adhere to these rules.
            </p>
          </div>

          <div className="flex items-center gap-2">
            {!isApproved && (
              <button
                onClick={handleApprove}
                disabled={isApproving}
                className="px-4 py-2 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg text-sm font-medium shadow-sm flex items-center gap-1.5 transition-colors disabled:opacity-50"
                data-testid="approve-brief-btn"
              >
                <CheckCircle2 className="w-4 h-4" />
                {isApproving ? "Approving..." : "Approve Brief"}
              </button>
            )}

            {isEditing ? (
              <div className="flex items-center gap-2">
                <button
                  onClick={() => setIsEditing(false)}
                  className="px-3 py-2 border border-slate-300 dark:border-slate-700 text-slate-700 dark:text-slate-300 rounded-lg text-sm font-medium hover:bg-slate-50 dark:hover:bg-slate-800 transition-colors"
                >
                  Cancel
                </button>
                <button
                  onClick={handleSave}
                  disabled={isSaving}
                  className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-sm font-medium shadow-sm flex items-center gap-1.5 transition-colors disabled:opacity-50"
                  data-testid="save-brief-btn"
                >
                  <Save className="w-4 h-4" />
                  {isSaving ? "Saving..." : "Save Changes"}
                </button>
              </div>
            ) : (
              <button
                onClick={() => setIsEditing(true)}
                className="px-3.5 py-2 border border-slate-300 dark:border-slate-700 text-slate-700 dark:text-slate-200 rounded-lg text-sm font-medium hover:bg-slate-50 dark:hover:bg-slate-800 flex items-center gap-1.5 transition-colors"
                data-testid="edit-brief-btn"
              >
                <Edit3 className="w-4 h-4" />
                Edit Brief
              </button>
            )}
          </div>
        </div>

        {error && (
          <div className="mt-4 p-3 bg-red-50 dark:bg-red-950/40 border border-red-200 dark:border-red-900 rounded-lg text-sm text-red-600 dark:text-red-400 flex items-center gap-2">
            <ShieldAlert className="w-4 h-4 flex-shrink-0" />
            <span>{error}</span>
          </div>
        )}
      </div>

      {/* Grid Content */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {/* Left 2 Columns: Core Brief Details */}
        <div className="md:col-span-2 space-y-6">
          {/* Metadata Card */}
          <div className="bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800 p-5 shadow-sm space-y-4">
            <h3 className="text-sm font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400 flex items-center gap-2">
              <FileText className="w-4 h-4 text-blue-500" />
              SEO Title & URL
            </h3>

            {isEditing ? (
              <div className="space-y-4">
                <div>
                  <label className="block text-xs font-medium text-slate-700 dark:text-slate-300 mb-1">
                    Recommended H1 / Title
                  </label>
                  <input
                    type="text"
                    value={formData.recommended_title}
                    onChange={(e) => setFormData({ ...formData, recommended_title: e.target.value })}
                    className="w-full px-3 py-2 border rounded-lg text-sm bg-slate-50 dark:bg-slate-800 border-slate-200 dark:border-slate-700 text-slate-900 dark:text-white"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-slate-700 dark:text-slate-300 mb-1">
                    Recommended URL Path
                  </label>
                  <input
                    type="text"
                    value={formData.recommended_url}
                    onChange={(e) => setFormData({ ...formData, recommended_url: e.target.value })}
                    className="w-full px-3 py-2 border rounded-lg text-sm bg-slate-50 dark:bg-slate-800 border-slate-200 dark:border-slate-700 text-slate-900 dark:text-white"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-slate-700 dark:text-slate-300 mb-1">
                    Meta Description
                  </label>
                  <textarea
                    rows={2}
                    value={formData.meta_description}
                    onChange={(e) => setFormData({ ...formData, meta_description: e.target.value })}
                    className="w-full px-3 py-2 border rounded-lg text-sm bg-slate-50 dark:bg-slate-800 border-slate-200 dark:border-slate-700 text-slate-900 dark:text-white"
                  />
                </div>
              </div>
            ) : (
              <div className="space-y-3">
                <div>
                  <span className="text-xs text-slate-400">Target Title:</span>
                  <p className="font-medium text-slate-900 dark:text-white text-base">
                    {brief.recommended_title}
                  </p>
                </div>
                <div>
                  <span className="text-xs text-slate-400">Target URL Slug:</span>
                  <p className="text-sm font-mono text-blue-600 dark:text-blue-400">
                    {brief.recommended_url || "/"}
                  </p>
                </div>
                <div>
                  <span className="text-xs text-slate-400">Meta Description:</span>
                  <p className="text-sm text-slate-600 dark:text-slate-300 mt-0.5">
                    {brief.meta_description || "No meta description specified."}
                  </p>
                </div>
              </div>
            )}
          </div>

          {/* Required Topics Checklist */}
          <div className="bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800 p-5 shadow-sm space-y-4">
            <h3 className="text-sm font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400 flex items-center gap-2">
              <Target className="w-4 h-4 text-emerald-500" />
              Required Topics & Core Architecture
            </h3>
            <p className="text-xs text-slate-500 dark:text-slate-400">
              The AI content generator must address these specific themes to satisfy depth criteria.
            </p>

            <div className="space-y-2" data-testid="brief-required-topics">
              {formData.required_topics.map((topic, idx) => (
                <div
                  key={idx}
                  className="flex items-center justify-between p-2.5 rounded-lg bg-slate-50 dark:bg-slate-800/60 border border-slate-100 dark:border-slate-700/60 text-sm text-slate-800 dark:text-slate-200"
                >
                  <div className="flex items-center gap-2.5">
                    <span className="w-5 h-5 rounded-full bg-blue-100 dark:bg-blue-900/50 text-blue-700 dark:text-blue-300 flex items-center justify-center text-xs font-bold">
                      {idx + 1}
                    </span>
                    <span>{topic}</span>
                  </div>
                  {isEditing && (
                    <button
                      onClick={() =>
                        setFormData({
                          ...formData,
                          required_topics: formData.required_topics.filter((_, i) => i !== idx),
                        })
                      }
                      className="text-xs text-red-500 hover:text-red-700"
                    >
                      Remove
                    </button>
                  )}
                </div>
              ))}

              {isEditing && (
                <div className="flex gap-2 pt-2">
                  <input
                    type="text"
                    placeholder="Add required topic..."
                    value={formData.newTopic}
                    onChange={(e) => setFormData({ ...formData, newTopic: e.target.value })}
                    className="flex-1 px-3 py-1.5 border rounded-lg text-sm bg-slate-50 dark:bg-slate-800 border-slate-200 dark:border-slate-700 text-slate-900 dark:text-white"
                  />
                  <button
                    onClick={() => {
                      if (formData.newTopic.trim()) {
                        setFormData({
                          ...formData,
                          required_topics: [...formData.required_topics, formData.newTopic.trim()],
                          newTopic: "",
                        });
                      }
                    }}
                    className="px-3 py-1.5 bg-slate-800 dark:bg-slate-700 text-white rounded-lg text-xs font-semibold"
                  >
                    Add
                  </button>
                </div>
              )}
            </div>
          </div>

          {/* Internal Link Opportunities Table */}
          <div className="bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800 p-5 shadow-sm space-y-3">
            <h3 className="text-sm font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400 flex items-center gap-2">
              <Link2 className="w-4 h-4 text-purple-500" />
              Approved Internal Link Targets
            </h3>
            <p className="text-xs text-slate-500 dark:text-slate-400">
              Verified graph links recommended for outbound context from this document.
            </p>

            {brief.internal_link_targets && brief.internal_link_targets.length > 0 ? (
              <div className="divide-y divide-slate-100 dark:divide-slate-800 border border-slate-100 dark:border-slate-800 rounded-lg overflow-hidden">
                {brief.internal_link_targets.map((link, idx) => (
                  <div
                    key={idx}
                    className="p-3 flex items-center justify-between text-xs bg-slate-50/50 dark:bg-slate-800/30"
                  >
                    <div>
                      <p className="font-semibold text-slate-800 dark:text-slate-200">{link.title}</p>
                      <p className="text-slate-400 font-mono mt-0.5">{link.url}</p>
                    </div>
                    <span className="text-slate-400 flex items-center gap-1">
                      Target Link <ExternalLink className="w-3 h-3" />
                    </span>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-xs text-slate-400 italic py-2">
                No strict link targets specified. The AI Editor will suggest contextual links from the site graph.
              </p>
            )}
          </div>
        </div>

        {/* Right Column: Parameters & Brand Rules */}
        <div className="space-y-6">
          {/* Target Metrics */}
          <div className="bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800 p-5 shadow-sm space-y-4">
            <h3 className="text-sm font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400 flex items-center gap-2">
              <Hash className="w-4 h-4 text-amber-500" />
              Strategy Parameters
            </h3>

            <div className="space-y-3">
              <div>
                <span className="text-xs text-slate-400">Primary Keyword:</span>
                <div className="mt-1 inline-flex items-center px-2.5 py-1 rounded-md bg-blue-50 dark:bg-blue-950/60 border border-blue-200 dark:border-blue-800 text-blue-700 dark:text-blue-300 font-medium text-sm">
                  {brief.primary_keyword}
                </div>
              </div>

              <div>
                <span className="text-xs text-slate-400">Target Word Count:</span>
                {isEditing ? (
                  <input
                    type="number"
                    value={formData.target_word_count}
                    onChange={(e) => setFormData({ ...formData, target_word_count: Number(e.target.value) })}
                    className="w-full mt-1 px-3 py-1.5 border rounded-lg text-sm bg-slate-50 dark:bg-slate-800 border-slate-200 dark:border-slate-700 text-slate-900 dark:text-white"
                  />
                ) : (
                  <p className="text-sm font-semibold text-slate-900 dark:text-white mt-0.5">
                    {brief.target_word_count.toLocaleString()} words
                  </p>
                )}
              </div>

              <div>
                <span className="text-xs text-slate-400">Search Intent:</span>
                <p className="text-xs font-semibold px-2 py-0.5 rounded bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 inline-block mt-1">
                  {brief.search_intent}
                </p>
              </div>

              <div>
                <span className="text-xs text-slate-400">Target Audience:</span>
                <p className="text-xs text-slate-700 dark:text-slate-300 mt-1">
                  {brief.target_audience || "Enterprise professionals and technical decision makers"}
                </p>
              </div>
            </div>
          </div>

          {/* Secondary Keywords */}
          <div className="bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800 p-5 shadow-sm space-y-3">
            <h3 className="text-sm font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400 flex items-center gap-2">
              <Sparkles className="w-4 h-4 text-pink-500" />
              Secondary Keywords
            </h3>

            <div className="flex flex-wrap gap-1.5">
              {formData.secondary_keywords.map((kw, i) => (
                <span
                  key={i}
                  className="text-xs px-2 py-1 rounded bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 border border-slate-200 dark:border-slate-700 flex items-center gap-1"
                >
                  {kw}
                  {isEditing && (
                    <button
                      onClick={() =>
                        setFormData({
                          ...formData,
                          secondary_keywords: formData.secondary_keywords.filter((_, idx) => idx !== i),
                        })
                      }
                      className="text-slate-400 hover:text-red-500"
                    >
                      ×
                    </button>
                  )}
                </span>
              ))}
            </div>

            {isEditing && (
              <div className="flex gap-2 pt-1">
                <input
                  type="text"
                  placeholder="Add keyword..."
                  value={formData.newKeyword}
                  onChange={(e) => setFormData({ ...formData, newKeyword: e.target.value })}
                  className="flex-1 px-2.5 py-1 border rounded text-xs bg-slate-50 dark:bg-slate-800 border-slate-200 dark:border-slate-700 text-slate-900 dark:text-white"
                />
                <button
                  onClick={() => {
                    if (formData.newKeyword.trim()) {
                      setFormData({
                        ...formData,
                        secondary_keywords: [...formData.secondary_keywords, formData.newKeyword.trim()],
                        newKeyword: "",
                      });
                    }
                  }}
                  className="px-2.5 py-1 bg-slate-800 dark:bg-slate-700 text-white rounded text-xs"
                >
                  Add
                </button>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
