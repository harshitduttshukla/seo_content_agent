"use client";

import React, { useState } from "react";
import type {
  ContentBrief,
  ContentDocument,
  PlannedContentPage,
  AIProposal,
} from "@/lib/api-types";
import { ContentBriefView } from "@/features/briefs/content-brief-view";
import { ContentEditor } from "@/features/editor/content-editor";
import { EditorSidebar } from "@/features/editor/editor-sidebar";
import {
  ArrowLeft,
  CheckCircle2,
  FileText,
  Sparkles,
} from "lucide-react";
import Link from "next/link";
import { clientApi } from "@/lib/client-api";

interface ContentPageWorkspaceProps {
  projectId: string;
  page: PlannedContentPage;
  initialBrief: ContentBrief;
  initialDocument: ContentDocument;
}

export function ContentPageWorkspace({
  projectId,
  page,
  initialBrief,
  initialDocument,
}: ContentPageWorkspaceProps) {
  const [workspaceTab, setWorkspaceTab] = useState<"brief" | "editor">("editor");
  const [brief, setBrief] = useState<ContentBrief>(initialBrief);
  const [document, setDocument] = useState<ContentDocument>(initialDocument);
  const [selectedBlockId, setSelectedBlockId] = useState<string | null>(null);
  const [activeProposal, setActiveProposal] = useState<AIProposal | null>(null);
  const [actionNotification, setActionNotification] = useState<string | null>(null);

  const showNotification = (msg: string) => {
    setActionNotification(msg);
    setTimeout(() => setActionNotification(null), 4000);
  };

  // Apply Proposal Handler
  const handleApplyProposal = async (proposalId: string) => {
    try {
      const updatedDocument = await clientApi<ContentDocument>(
        `/content-documents/${document.id}/patches/${proposalId}/apply`,
        { method: "POST" }
      );
      setDocument(updatedDocument);
      setActiveProposal(null);
      showNotification("AI Proposal applied successfully! Version incremented.");
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to apply AI proposal";
      alert(msg);
    }
  };

  // Reject Proposal Handler
  const handleRejectProposal = async (proposalId: string) => {
    try {
      await clientApi<AIProposal>(
        `/content-documents/${document.id}/patches/${proposalId}/reject`,
        { method: "POST" }
      );
      setActiveProposal(null);
      showNotification("AI Proposal rejected.");
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to reject AI proposal";
      alert(msg);
    }
  };

  // Restore Version Handler
  const handleRestoreVersion = async (versionNum: number) => {
    if (!confirm(`Are you sure you want to restore document version ${versionNum}? A new version will be created.`)) {
      return;
    }

    try {
      const restoredDocument = await clientApi<ContentDocument>(
        `/content-documents/${document.id}/restore/${versionNum}`,
        {
          method: "POST",
          body: JSON.stringify({ change_summary: `Restored to version ${versionNum}` }),
        }
      );
      setDocument(restoredDocument);
      showNotification(`Version ${versionNum} restored as v${restoredDocument.current_version}!`);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to restore version";
      alert(msg);
    }
  };

  return (
    <div className="space-y-6" data-testid="content-page-workspace">
      {/* Top Breadcrumb & Metadata Header */}
      <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-6 shadow-sm">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2 text-xs text-slate-500 dark:text-slate-400 mb-1">
              <Link
                href={`/projects/${projectId}/content-map`}
                className="hover:text-blue-600 flex items-center gap-1 transition-colors"
              >
                <ArrowLeft className="w-3.5 h-3.5" /> Back to Content Map
              </Link>
              <span>/</span>
              <span className="font-mono">{page.slug}</span>
            </div>

            <h1 className="text-2xl font-black text-slate-900 dark:text-white tracking-tight">
              {document.title || page.title}
            </h1>

            <div className="flex flex-wrap items-center gap-3 mt-2 text-xs">
              <span className="px-2.5 py-0.5 rounded-full bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 font-medium">
                {page.content_type}
              </span>
              <span className="px-2.5 py-0.5 rounded-full bg-blue-50 text-blue-700 dark:bg-blue-950/50 dark:text-blue-300 font-medium">
                Target: <strong>{page.primary_keyword}</strong>
              </span>
              <span className="text-slate-400">
                Word Goal: {brief.target_word_count.toLocaleString()} words
              </span>
              {brief.status === "APPROVED" && (
                <span className="px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-400 border border-emerald-200 dark:border-emerald-800 font-semibold flex items-center gap-1">
                  <CheckCircle2 className="w-3 h-3" /> Brief Approved
                </span>
              )}
            </div>
          </div>

          {/* Segmented Tab Controller */}
          <div className="flex items-center p-1 bg-slate-100 dark:bg-slate-800/80 rounded-xl border border-slate-200 dark:border-slate-700 text-xs font-semibold">
            <button
              onClick={() => setWorkspaceTab("brief")}
              className={`px-4 py-2 rounded-lg flex items-center gap-1.5 transition-all ${
                workspaceTab === "brief"
                  ? "bg-white dark:bg-slate-900 text-blue-600 dark:text-blue-400 shadow-sm"
                  : "text-slate-600 dark:text-slate-400 hover:text-slate-900"
              }`}
              data-testid="tab-brief-view"
            >
              <FileText className="w-3.5 h-3.5" /> Content Brief
            </button>

            <button
              onClick={() => setWorkspaceTab("editor")}
              className={`px-4 py-2 rounded-lg flex items-center gap-1.5 transition-all ${
                workspaceTab === "editor"
                  ? "bg-white dark:bg-slate-900 text-blue-600 dark:text-blue-400 shadow-sm"
                  : "text-slate-600 dark:text-slate-400 hover:text-slate-900"
              }`}
              data-testid="tab-editor-view"
            >
              <Sparkles className="w-3.5 h-3.5 text-blue-500" /> AI Document Editor
            </button>
          </div>
        </div>

        {actionNotification && (
          <div className="mt-4 p-3 rounded-lg bg-emerald-50 dark:bg-emerald-950/40 border border-emerald-200 dark:border-emerald-800 text-xs text-emerald-800 dark:text-emerald-300 flex items-center gap-2">
            <CheckCircle2 className="w-4 h-4 flex-shrink-0" />
            <span>{actionNotification}</span>
          </div>
        )}
      </div>

      {/* Main Workspace Body */}
      {workspaceTab === "brief" ? (
        <ContentBriefView
          brief={brief}
          onUpdate={(updated) => setBrief(updated)}
          onApprove={() => setBrief((prev) => ({ ...prev, status: "APPROVED" }))}
        />
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 items-start">
          {/* Left Canvas: Block Content Editor */}
          <div className="lg:col-span-2">
            <ContentEditor
              key={`${document.id}:${document.lock_version}`}
              document={document}
              activeProposal={activeProposal}
              selectedBlockId={selectedBlockId}
              onSelectBlock={(id) => setSelectedBlockId(id)}
              onUpdateDocument={(updated) => setDocument(updated)}
              onApplyProposal={handleApplyProposal}
              onRejectProposal={handleRejectProposal}
            />
          </div>

          {/* Right Sidebar: AI Chat, Outline, SEO, and History */}
          <div className="lg:col-span-1 sticky top-6">
            <EditorSidebar
              document={document}
              selectedBlockId={selectedBlockId}
              onApplyProposal={handleApplyProposal}
              onRejectProposal={handleRejectProposal}
              onSelectBlock={(id) => setSelectedBlockId(id)}
              onRestoreVersion={handleRestoreVersion}
            />
          </div>
        </div>
      )}
    </div>
  );
}
