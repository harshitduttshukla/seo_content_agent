"use client";

import React, { useState, useEffect, useRef } from "react";
import type {
  ContentDocument,
  ContentDocumentVersion,
  ChatMessage,
  SEOQualityReport,
} from "@/lib/api-types";
import { clientApi } from "@/lib/client-api";
import {
  AlertCircle,
  Bot,
  Check,
  ChevronRight,
  History,
  ListOrdered,
  RotateCcw,
  Send,
  Sparkles,
  TrendingUp,
  X,
  Zap,
} from "lucide-react";

interface EditorSidebarProps {
  document: ContentDocument;
  selectedBlockId?: string | null;
  onApplyProposal: (proposalId: string) => void;
  onRejectProposal: (proposalId: string) => void;
  onSelectBlock: (blockId: string) => void;
  onRestoreVersion: (versionNum: number) => void;
}

type SidebarTab = "chat" | "outline" | "seo" | "links" | "history";

export function EditorSidebar({
  document: doc,
  selectedBlockId,
  onApplyProposal,
  onRejectProposal,
  onSelectBlock,
  onRestoreVersion,
}: EditorSidebarProps) {
  const [activeTab, setActiveTab] = useState<SidebarTab>("chat");

  // Chat State
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [inputMessage, setInputMessage] = useState("");
  const [isSending, setIsSending] = useState(false);
  const [chatError, setChatError] = useState<string | null>(null);

  // SEO Quality State
  const [qualityReport, setQualityReport] = useState<SEOQualityReport | null>(null);
  const [isLoadingQuality, setIsLoadingQuality] = useState(false);

  // Versions State
  const [versions, setVersions] = useState<ContentDocumentVersion[]>([]);
  const [isLoadingVersions, setIsLoadingVersions] = useState(false);
  const nextTemporaryMessageId = useRef(0);

  // Load SEO Quality Report when SEO tab active or document changes
  useEffect(() => {
    async function loadQuality() {
      setIsLoadingQuality(true);
      try {
        const report = await clientApi<SEOQualityReport>(
          `/content-documents/${doc.id}/quality-check`
        );
        setQualityReport(report);
      } catch (err) {
        console.error("Failed to load SEO quality report:", err);
      } finally {
        setIsLoadingQuality(false);
      }
    }
    loadQuality();
  }, [doc.id, doc.lock_version]);

  // Load Versions when History tab active
  useEffect(() => {
    if (activeTab === "history") {
      async function loadVersions() {
        setIsLoadingVersions(true);
        try {
          const result = await clientApi<{ items: ContentDocumentVersion[] }>(
            `/content-documents/${doc.id}/versions`
          );
          setVersions(result.items);
        } catch (err) {
          console.error("Failed to load document versions:", err);
        } finally {
          setIsLoadingVersions(false);
        }
      }
      loadVersions();
    }
  }, [activeTab, doc.id, doc.current_version]);

  // Handle Chat Message Submit
  const handleSendMessage = async (customPrompt?: string) => {
    const textToSend = customPrompt || inputMessage;
    if (!textToSend.trim() || isSending) return;

    setIsSending(true);
    setChatError(null);

    // Optimistic user message
    nextTemporaryMessageId.current += 1;
    const userMsg: ChatMessage = {
      id: `temp_${nextTemporaryMessageId.current}`,
      session_id: "active",
      document_id: doc.id,
      role: "user",
      content: textToSend,
      context_snapshot: {},
      token_usage: {},
      created_at: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, userMsg]);
    setInputMessage("");

    try {
      const responseMessage = await clientApi<ChatMessage>(`/content-documents/${doc.id}/chat`, {
        method: "POST",
        body: JSON.stringify({
          message: textToSend,
          selected_block_id: selectedBlockId || undefined,
        }),
      });
      setMessages((prev) => [...prev, responseMessage]);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to process AI chat turn";
      setChatError(msg);
    } finally {
      setIsSending(false);
    }
  };

  // Quick Action Chips
  const quickChips = [
    "Rewrite concisely",
    "Expand technical depth",
    "Add FAQ section",
    "Incorporate keywords",
  ];

  // Headings for Outline
  const headings = doc.content_blocks?.filter(
    (b) => b.type === "DOCUMENT_TITLE" || b.type === "HEADING"
  ) || [];

  return (
    <div
      className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl flex flex-col h-[750px] shadow-sm overflow-hidden"
      data-testid="editor-sidebar"
    >
      {/* Sidebar Tabs */}
      <div className="flex items-center border-b border-slate-200 dark:border-slate-800 bg-slate-50/70 dark:bg-slate-800/40 p-1.5 text-xs font-semibold gap-1">
        <button
          onClick={() => setActiveTab("chat")}
          className={`flex-1 py-2 rounded-lg flex items-center justify-center gap-1.5 transition-colors ${
            activeTab === "chat"
              ? "bg-white dark:bg-slate-800 text-blue-600 dark:text-blue-400 shadow-xs"
              : "text-slate-600 dark:text-slate-400 hover:text-slate-900"
          }`}
          data-testid="tab-chat"
        >
          <Bot className="w-3.5 h-3.5" /> AI Chat
        </button>

        <button
          onClick={() => setActiveTab("outline")}
          className={`flex-1 py-2 rounded-lg flex items-center justify-center gap-1.5 transition-colors ${
            activeTab === "outline"
              ? "bg-white dark:bg-slate-800 text-blue-600 dark:text-blue-400 shadow-xs"
              : "text-slate-600 dark:text-slate-400 hover:text-slate-900"
          }`}
          data-testid="tab-outline"
        >
          <ListOrdered className="w-3.5 h-3.5" /> Outline
        </button>

        <button
          onClick={() => setActiveTab("seo")}
          className={`flex-1 py-2 rounded-lg flex items-center justify-center gap-1.5 transition-colors ${
            activeTab === "seo"
              ? "bg-white dark:bg-slate-800 text-blue-600 dark:text-blue-400 shadow-xs"
              : "text-slate-600 dark:text-slate-400 hover:text-slate-900"
          }`}
          data-testid="tab-seo"
        >
          <TrendingUp className="w-3.5 h-3.5" /> SEO
          {qualityReport && (
            <span className="ml-0.5 text-[10px] px-1.5 py-0.2 rounded-full bg-emerald-100 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-400 font-bold">
              {qualityReport.score_percentage}%
            </span>
          )}
        </button>

        <button
          onClick={() => setActiveTab("history")}
          className={`flex-1 py-2 rounded-lg flex items-center justify-center gap-1.5 transition-colors ${
            activeTab === "history"
              ? "bg-white dark:bg-slate-800 text-blue-600 dark:text-blue-400 shadow-xs"
              : "text-slate-600 dark:text-slate-400 hover:text-slate-900"
          }`}
          data-testid="tab-history"
        >
          <History className="w-3.5 h-3.5" /> History
        </button>
      </div>

      {/* Tab 1: AI Chat & Proposal Engine */}
      {activeTab === "chat" && (
        <div className="flex-1 flex flex-col p-4 overflow-hidden" data-testid="chat-tab-content">
          {/* Quick Action Chips */}
          <div className="flex flex-wrap gap-1.5 mb-3">
            {quickChips.map((chip, idx) => (
              <button
                key={idx}
                onClick={() => handleSendMessage(chip)}
                disabled={isSending}
                className="text-[11px] px-2.5 py-1 rounded-full bg-slate-100 hover:bg-slate-200 dark:bg-slate-800 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-300 font-medium transition-colors"
              >
                ⚡ {chip}
              </button>
            ))}
          </div>

          {selectedBlockId && (
            <div className="mb-2 px-2.5 py-1 rounded-md bg-blue-50 dark:bg-blue-950/40 border border-blue-200 dark:border-blue-900 text-[11px] text-blue-700 dark:text-blue-300 flex items-center justify-between">
              <span>Targeting: <strong className="font-mono">{selectedBlockId}</strong></span>
              <button
                onClick={() => onSelectBlock("")}
                className="text-blue-400 hover:text-blue-600"
              >
                Clear
              </button>
            </div>
          )}

          {/* Messages Feed */}
          <div className="flex-1 overflow-y-auto space-y-4 pr-1 text-xs">
            {messages.length === 0 ? (
              <div className="text-center py-12 text-slate-400 space-y-2">
                <Sparkles className="w-8 h-8 mx-auto text-blue-400 opacity-60" />
                <p className="font-medium text-slate-600 dark:text-slate-300">
                  Chat-Native AI Editor
                </p>
                <p className="text-[11px] max-w-xs mx-auto">
                  Ask to rewrite, expand, or add sections. The AI proposes safe block patches with human review.
                </p>
              </div>
            ) : (
              messages.map((msg) => (
                <div
                  key={msg.id}
                  className={`flex flex-col ${
                    msg.role === "user" ? "items-end" : "items-start"
                  }`}
                >
                  <div
                    className={`max-w-[88%] p-3 rounded-xl ${
                      msg.role === "user"
                        ? "bg-blue-600 text-white rounded-br-none"
                        : "bg-slate-100 dark:bg-slate-800 text-slate-800 dark:text-slate-200 rounded-bl-none"
                    }`}
                  >
                    <p className="whitespace-pre-wrap leading-relaxed">{msg.content}</p>
                  </div>

                  {/* Proposal Review Card if attached to assistant message */}
                  {msg.proposal && (
                    <div
                      className="mt-2 w-full p-3 rounded-xl bg-amber-50/80 dark:bg-amber-950/30 border border-amber-200 dark:border-amber-800 space-y-2 text-xs"
                      data-testid="proposal-card"
                    >
                      <div className="flex items-center justify-between">
                        <span className="font-semibold text-amber-800 dark:text-amber-300 flex items-center gap-1">
                          <Zap className="w-3.5 h-3.5 text-amber-500" />
                          Proposed {msg.proposal.operation_type}
                        </span>
                        <span className="font-mono text-[10px] text-slate-400">
                          {msg.proposal.target_block_ids?.join(", ")}
                        </span>
                      </div>

                      {msg.proposal.reason && (
                        <p className="text-slate-600 dark:text-slate-300 italic text-[11px]">
                          {msg.proposal.reason}
                        </p>
                      )}

                      {/* Old vs New Diff Summary */}
                      {Boolean(msg.proposal.old_content) && (
                        <div className="space-y-1">
                          <div className="p-2 rounded bg-red-50 dark:bg-red-950/40 border border-red-200 dark:border-red-900 text-red-700 dark:text-red-300 font-mono text-[11px] line-through">
                            {typeof msg.proposal.old_content === "string"
                              ? (msg.proposal.old_content as string)
                              : JSON.stringify(msg.proposal.old_content)}
                          </div>
                          <div className="p-2 rounded bg-emerald-50 dark:bg-emerald-950/40 border border-emerald-200 dark:border-emerald-900 text-emerald-700 dark:text-emerald-300 font-mono text-[11px]">
                            {typeof msg.proposal.proposed_content === "string"
                              ? (msg.proposal.proposed_content as string)
                              : JSON.stringify(msg.proposal.proposed_content)}
                          </div>
                        </div>
                      )}

                      {/* Apply / Reject Actions */}
                      {msg.proposal.status === "PROPOSED" ? (
                        <div className="flex items-center gap-2 pt-1">
                          <button
                            onClick={() => onApplyProposal(msg.proposal!.id)}
                            className="flex-1 py-1.5 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg text-xs font-semibold flex items-center justify-center gap-1 shadow-xs transition-colors"
                            data-testid="apply-proposal-btn"
                          >
                            <Check className="w-3.5 h-3.5" /> Apply Proposal
                          </button>
                          <button
                            onClick={() => onRejectProposal(msg.proposal!.id)}
                            className="py-1.5 px-3 bg-slate-200 hover:bg-slate-300 dark:bg-slate-700 dark:hover:bg-slate-600 text-slate-700 dark:text-slate-200 rounded-lg text-xs font-medium transition-colors"
                            data-testid="reject-proposal-btn"
                          >
                            <X className="w-3.5 h-3.5" /> Reject
                          </button>
                        </div>
                      ) : (
                        <div className="pt-1 text-[11px] font-semibold text-slate-500">
                          Status: <span className="uppercase">{msg.proposal.status}</span>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              ))
            )}

            {isSending && (
              <div className="flex items-center gap-2 text-slate-400 text-xs py-2">
                <Bot className="w-4 h-4 animate-pulse text-blue-500" />
                <span>AI is analyzing context and formulating patch...</span>
              </div>
            )}
          </div>

          {chatError && (
            <div className="mt-2 p-2 rounded bg-red-50 dark:bg-red-950/40 text-red-600 text-[11px] flex items-center gap-1">
              <AlertCircle className="w-3.5 h-3.5" /> {chatError}
            </div>
          )}

          {/* Chat Input Box */}
          <div className="pt-3 border-t border-slate-100 dark:border-slate-800 flex gap-2">
            <textarea
              rows={2}
              value={inputMessage}
              onChange={(e) => setInputMessage(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  handleSendMessage();
                }
              }}
              placeholder="Ask AI to edit, expand, or refine blocks..."
              className="flex-1 p-2.5 text-xs rounded-xl border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 text-slate-900 dark:text-white resize-none focus:outline-none focus:ring-1 focus:ring-blue-500"
              data-testid="chat-input"
            />
            <button
              onClick={() => handleSendMessage()}
              disabled={isSending || !inputMessage.trim()}
              className="px-3.5 bg-blue-600 hover:bg-blue-700 text-white rounded-xl flex items-center justify-center transition-colors disabled:opacity-50"
              data-testid="send-chat-btn"
            >
              <Send className="w-4 h-4" />
            </button>
          </div>
        </div>
      )}

      {/* Tab 2: Outline Navigation */}
      {activeTab === "outline" && (
        <div className="flex-1 p-4 overflow-y-auto space-y-2 text-xs" data-testid="outline-tab-content">
          <p className="text-slate-400 text-[11px] mb-3">
            Click any heading to jump to and highlight that block on the canvas.
          </p>

          {headings.length === 0 ? (
            <p className="text-slate-400 italic">No headings in document.</p>
          ) : (
            headings.map((h) => (
              <button
                key={h.id}
                onClick={() => onSelectBlock(h.id)}
                className={`w-full text-left p-2 rounded-lg transition-colors flex items-center justify-between ${
                  selectedBlockId === h.id
                    ? "bg-blue-50 dark:bg-blue-950/40 text-blue-700 dark:text-blue-300 font-semibold"
                    : "hover:bg-slate-50 dark:hover:bg-slate-800/60 text-slate-700 dark:text-slate-300"
                }`}
              >
                <span
                  className={`${
                    h.type === "DOCUMENT_TITLE"
                      ? "font-bold text-sm"
                      : h.level === 2
                      ? "pl-3 font-semibold"
                      : "pl-6 text-slate-500"
                  } truncate`}
                >
                  {h.text || "Untitled Heading"}
                </span>
                <ChevronRight className="w-3.5 h-3.5 text-slate-400 flex-shrink-0" />
              </button>
            ))
          )}
        </div>
      )}

      {/* Tab 3: SEO Quality Checklist */}
      {activeTab === "seo" && (
        <div className="flex-1 p-4 overflow-y-auto space-y-4 text-xs" data-testid="seo-tab-content">
          {isLoadingQuality ? (
            <div className="text-center py-8 text-slate-400">
              <RotateCcw className="w-5 h-5 animate-spin mx-auto mb-2" />
              Evaluating SEO quality rules...
            </div>
          ) : qualityReport ? (
            <div className="space-y-4">
              {/* Score Header */}
              <div className="p-4 rounded-xl bg-slate-50 dark:bg-slate-800/60 border border-slate-200 dark:border-slate-800 flex items-center justify-between">
                <div>
                  <p className="text-[11px] font-semibold uppercase tracking-wider text-slate-400">
                    Deterministic SEO Score
                  </p>
                  <p className="text-2xl font-black text-slate-900 dark:text-white mt-0.5">
                    {qualityReport.score_percentage}%
                  </p>
                </div>
                <div className="text-right">
                  <p className="text-[11px] text-slate-400">Word Count Progress</p>
                  <p className="text-xs font-semibold text-slate-700 dark:text-slate-300 mt-0.5">
                    {qualityReport.word_count.toLocaleString()} / {qualityReport.target_word_count.toLocaleString()}
                  </p>
                </div>
              </div>

              {/* Checks List */}
              <div className="space-y-2">
                {qualityReport.checks?.map((check, idx) => (
                  <div
                    key={idx}
                    className="p-3 rounded-lg border border-slate-100 dark:border-slate-800 bg-white dark:bg-slate-800/40 space-y-1"
                  >
                    <div className="flex items-center justify-between">
                      <span className="font-semibold text-slate-800 dark:text-slate-200">
                        {check.name}
                      </span>
                      <span
                        className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                          check.status === "PASS"
                            ? "bg-emerald-100 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-400"
                            : check.status === "WARNING"
                            ? "bg-amber-100 text-amber-700 dark:bg-amber-950 dark:text-amber-400"
                            : "bg-red-100 text-red-700 dark:bg-red-950 dark:text-red-400"
                        }`}
                      >
                        {check.status}
                      </span>
                    </div>
                    <p className="text-slate-500 dark:text-slate-400 text-[11px]">
                      {check.message}
                    </p>
                    {check.recommendation && (
                      <p className="text-blue-600 dark:text-blue-400 text-[11px] pt-1">
                        💡 {check.recommendation}
                      </p>
                    )}
                  </div>
                ))}
              </div>
            </div>
          ) : (
            <p className="text-slate-400 italic">No quality report available.</p>
          )}
        </div>
      )}

      {/* Tab 4: Version History */}
      {activeTab === "history" && (
        <div className="flex-1 p-4 overflow-y-auto space-y-3 text-xs" data-testid="history-tab-content">
          <p className="text-slate-400 text-[11px]">
            Every major edit, AI patch apply, or manual save creates an immutable version checkpoint.
          </p>

          {isLoadingVersions ? (
            <div className="text-center py-8 text-slate-400">
              <RotateCcw className="w-5 h-5 animate-spin mx-auto mb-2" />
              Loading versions...
            </div>
          ) : versions.length === 0 ? (
            <p className="text-slate-400 italic">No prior versions recorded yet.</p>
          ) : (
            <div className="space-y-2">
              {versions.map((ver) => (
                <div
                  key={ver.id}
                  className="p-3 rounded-xl border border-slate-100 dark:border-slate-800 bg-white dark:bg-slate-800/40 space-y-2"
                >
                  <div className="flex items-center justify-between">
                    <span className="font-bold text-slate-900 dark:text-white">
                      Version {ver.version}
                    </span>
                    <span className="text-[10px] text-slate-400">
                      {new Date(ver.created_at).toLocaleDateString()} {new Date(ver.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                    </span>
                  </div>

                  <p className="text-slate-600 dark:text-slate-300 text-[11px]">
                    {ver.change_summary || "Automated version checkpoint"}
                  </p>

                  <div className="flex items-center justify-between pt-1">
                    <span className="text-[10px] text-slate-400">
                      {ver.word_count.toLocaleString()} words • {ver.change_type}
                    </span>
                    {ver.version !== doc.current_version && (
                      <button
                        onClick={() => onRestoreVersion(ver.version)}
                        className="px-2.5 py-1 bg-slate-100 hover:bg-slate-200 dark:bg-slate-700 dark:hover:bg-slate-600 text-slate-700 dark:text-slate-200 rounded font-semibold text-[11px] flex items-center gap-1 transition-colors"
                        data-testid={`restore-ver-${ver.version}`}
                      >
                        <RotateCcw className="w-3 h-3" /> Restore
                      </button>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
