"use client";

import React, { useState, useEffect, useRef } from "react";
import type {
  AIProposal,
  ContentDocument,
  ContentDocumentVersion,
  ChatMessage,
  ChatSession,
  WorkflowDetail,
} from "@/lib/api-types";
import { clientApi } from "@/lib/client-api";
import {
  AlertCircle,
  Bot,
  Check,
  ChevronRight,
  Copy,
  History,
  ListOrdered,
  Loader2,
  Pencil,
  RotateCcw,
  Send,
  Sparkles,
  X,
  Zap,
} from "lucide-react";
import { WorkflowActivity } from "./workflow-activity";

interface EditorSidebarProps {
  document: ContentDocument;
  selectedBlockId?: string | null;
  onApplyProposal: (proposalId: string) => Promise<void> | void;
  onRejectProposal: (proposalId: string) => Promise<void> | void;
  onSelectBlock: (blockId: string) => void;
  onRestoreVersion: (versionNum: number) => void;
  onProposalCreated?: (proposal: AIProposal) => void;
  lastAppliedProposalId?: string | null;
  lastRejectedProposalId?: string | null;
}

type SidebarTab = "chat" | "workflows" | "outline" | "links" | "history";

function formatDiffContent(content: unknown, isOld: boolean = false): string {
  if (!content) return "";
  if (typeof content === "string") return content;
  if (typeof content === "object") {
    const obj = content as Record<string, unknown>;
    if (typeof obj.text === "string" && obj.text.trim()) {
      return obj.text;
    }
    if (Array.isArray(obj.operations) && obj.operations.length > 0) {
      const op = obj.operations[0] as Record<string, unknown>;
      if (isOld) {
        if (typeof op.old_content === "string") return op.old_content;
      } else {
        if (typeof op.new_content === "string") return op.new_content;
        if (op.anchor_text && op.url) return `[${op.anchor_text}](${op.url})`;
      }
    }
    if (Array.isArray(content) && content.length > 0) {
      const first = content[0] as Record<string, unknown>;
      if (typeof first.text === "string") return first.text;
      if (isOld && typeof first.old_content === "string") return first.old_content;
      if (!isOld && typeof first.new_content === "string") return first.new_content;
    }
    if (!isOld && obj.url && obj.anchor_text) {
      return `[${obj.anchor_text}](${obj.url})`;
    }
  }
  return JSON.stringify(content);
}

function formatChatContent(content: string, isAssistantMessage: boolean = false): string {
  const trimmed = content.trim();
  if (!trimmed.startsWith("{")) return content;

  try {
    const parsed: unknown = JSON.parse(trimmed);
    if (
      parsed &&
      typeof parsed === "object" &&
      typeof (parsed as Record<string, unknown>).message === "string"
    ) {
      return (parsed as Record<string, string>).message;
    }
  } catch {
    if (isAssistantMessage) {
      return "This earlier AI response was incomplete, so no document changes were created.";
    }
  }

  return isAssistantMessage
    ? "This earlier AI response could not be converted into a reviewable proposal. No document changes were created."
    : content;
}

export function EditorSidebar({
  document: doc,
  selectedBlockId,
  onApplyProposal,
  onRejectProposal,
  onSelectBlock,
  onRestoreVersion,
  onProposalCreated,
  lastAppliedProposalId,
  lastRejectedProposalId,
}: EditorSidebarProps) {
  const [activeTab, setActiveTab] = useState<SidebarTab>("chat");

  // Chat State
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [inputMessage, setInputMessage] = useState("");
  const [isSending, setIsSending] = useState(false);
  const [chatError, setChatError] = useState<string | null>(null);
  const [processingProposalId, setProcessingProposalId] = useState<string | null>(null);
  const [copiedMessageId, setCopiedMessageId] = useState<string | null>(null);
  const [editingMessageId, setEditingMessageId] = useState<string | null>(null);
  const [editingMessageContent, setEditingMessageContent] = useState("");

  useEffect(() => {
    if (lastAppliedProposalId) {
      setMessages((prev) =>
        prev.map((m) =>
          m.proposal?.id === lastAppliedProposalId
            ? { ...m, proposal: { ...m.proposal, status: "APPLIED" } }
            : m
        )
      );
    }
  }, [lastAppliedProposalId]);

  useEffect(() => {
    if (lastRejectedProposalId) {
      setMessages((prev) =>
        prev.map((m) =>
          m.proposal?.id === lastRejectedProposalId
            ? { ...m, proposal: { ...m.proposal, status: "REJECTED" } }
            : m
        )
      );
    }
  }, [lastRejectedProposalId]);

  const handleApplyProposalAction = async (proposalId: string) => {
    if (processingProposalId) return;
    try {
      setProcessingProposalId(proposalId);
      await onApplyProposal(proposalId);
      setMessages((prev) =>
        prev.map((m) =>
          m.proposal?.id === proposalId
            ? { ...m, proposal: { ...m.proposal, status: "APPLIED" } }
            : m
        )
      );
    } catch (err: unknown) {
      const errMsg = err instanceof Error ? err.message : "";
      if (errMsg.toLowerCase().includes("already been applied")) {
        setMessages((prev) =>
          prev.map((m) =>
            m.proposal?.id === proposalId
              ? { ...m, proposal: { ...m.proposal, status: "APPLIED" } }
              : m
          )
        );
      }
    } finally {
      setProcessingProposalId(null);
    }
  };

  const handleRejectProposalAction = async (proposalId: string) => {
    if (processingProposalId) return;
    try {
      setProcessingProposalId(proposalId);
      await onRejectProposal(proposalId);
      setMessages((prev) =>
        prev.map((m) =>
          m.proposal?.id === proposalId
            ? { ...m, proposal: { ...m.proposal, status: "REJECTED" } }
            : m
        )
      );
    } finally {
      setProcessingProposalId(null);
    }
  };


  // Versions State
  const [versions, setVersions] = useState<ContentDocumentVersion[]>([]);
  const [isLoadingVersions, setIsLoadingVersions] = useState(false);
  const nextTemporaryMessageId = useRef(0);

  useEffect(() => {
    let cancelled = false;

    async function loadChatHistory() {
      try {
        const session = await clientApi<ChatSession>(`/content-documents/${doc.id}/chat`);
        if (cancelled) return;
        if (Array.isArray(session?.messages)) {
          const historicalMessages = session.messages.map((message) => ({
            ...message,
            role: message.role.toLowerCase() as ChatMessage["role"],
          }));
          setMessages((prev) => {
            const historicalIds = new Set(historicalMessages.map((message) => message.id));
            const newerLocalMessages = prev.filter((message) => !historicalIds.has(message.id));
            return [...historicalMessages, ...newerLocalMessages];
          });
        }
      } catch (err) {
        if (!cancelled) console.error("Failed to load chat history:", err);
      }
    }

    void loadChatHistory();
    return () => {
      cancelled = true;
    };
  }, [doc.id]);

  // Orchestrator State (Phase 6)
  const [activeWorkflow, setActiveWorkflow] = useState<WorkflowDetail | null>(null);
  const [workflowInput, setWorkflowInput] = useState("");
  const [isOrchestrating, setIsOrchestrating] = useState(false);
  const [workflowError, setWorkflowError] = useState<string | null>(null);

  const handleExecuteWorkflow = async (customMessage?: string) => {
    const textToSend = customMessage || workflowInput;
    if (!textToSend.trim() || isOrchestrating) return;

    setIsOrchestrating(true);
    setWorkflowError(null);

    try {
      const result = await clientApi<WorkflowDetail>("/orchestrator/workflows", {
        method: "POST",
        body: JSON.stringify({
          message: textToSend,
          document_id: doc.id,
          project_id: doc.project_id,
        }),
      });
      setActiveWorkflow(result);
      setWorkflowInput("");
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to execute agent workflow";
      setWorkflowError(msg);
    } finally {
      setIsOrchestrating(false);
    }
  };

  const handleApproveStep = async (stepId: string) => {
    if (!activeWorkflow) return;
    try {
      const updated = await clientApi<WorkflowDetail>(
        `/orchestrator/workflows/${activeWorkflow.id}/steps/${stepId}/approve`,
        { method: "POST" }
      );
      setActiveWorkflow(updated);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to approve step";
      setWorkflowError(msg);
    }
  };

  const handleRejectStep = async (stepId: string) => {
    if (!activeWorkflow) return;
    try {
      const updated = await clientApi<WorkflowDetail>(
        `/orchestrator/workflows/${activeWorkflow.id}/steps/${stepId}/reject`,
        { method: "POST" }
      );
      setActiveWorkflow(updated);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to reject step";
      setWorkflowError(msg);
    }
  };

  const handleRetryStep = async () => {
    if (!activeWorkflow) return;
    try {
      const updated = await clientApi<WorkflowDetail>(
        `/orchestrator/workflows/${activeWorkflow.id}/resume`,
        { method: "POST" }
      );
      setActiveWorkflow(updated);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to resume workflow";
      setWorkflowError(msg);
    }
  };

  const handleCancelWorkflow = async () => {
    if (!activeWorkflow) return;
    try {
      const updated = await clientApi<WorkflowDetail>(
        `/orchestrator/workflows/${activeWorkflow.id}/cancel`,
        { method: "POST" }
      );
      setActiveWorkflow(updated);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to cancel workflow";
      setWorkflowError(msg);
    }
  };

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
  const handleCopyMessage = async (message: ChatMessage) => {
    const content = formatChatContent(message.content, message.role === "assistant");
    try {
      await navigator.clipboard.writeText(content);
      setCopiedMessageId(message.id);
      window.setTimeout(() => {
        setCopiedMessageId((current) => (current === message.id ? null : current));
      }, 1500);
    } catch {
      setChatError("Could not copy this message. Please check clipboard permissions.");
    }
  };

  const startEditingMessage = (message: ChatMessage) => {
    setEditingMessageId(message.id);
    setEditingMessageContent(message.content);
    setChatError(null);
  };

  const cancelEditingMessage = () => {
    setEditingMessageId(null);
    setEditingMessageContent("");
  };

  const handleSendMessage = async (customPrompt?: string, editedMessageId?: string) => {
    const textToSend = customPrompt || inputMessage;
    if (!textToSend.trim() || isSending) return;

    setIsSending(true);
    setChatError(null);

    if (editedMessageId) {
      setMessages((prev) => {
        const editedIndex = prev.findIndex((message) => message.id === editedMessageId);
        if (editedIndex < 0) return prev;
        const editedMessage = { ...prev[editedIndex], content: textToSend };
        return [...prev.slice(0, editedIndex), editedMessage];
      });
      cancelEditingMessage();
    } else {
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
    }
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
      if (responseMessage.proposal && onProposalCreated) {
        onProposalCreated(responseMessage.proposal);
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to process AI chat turn";
      setChatError(msg);
    } finally {
      setIsSending(false);
    }
  };

  const saveEditedMessage = () => {
    if (!editingMessageId || !editingMessageContent.trim()) return;
    void handleSendMessage(editingMessageContent, editingMessageId);
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
      className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl flex flex-col h-[750px] lg:h-[calc(100vh-2rem)] lg:max-h-[750px] shadow-sm overflow-hidden"
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
          onClick={() => setActiveTab("workflows")}
          className={`flex-1 py-2 rounded-lg flex items-center justify-center gap-1.5 transition-colors ${
            activeTab === "workflows"
              ? "bg-white dark:bg-slate-800 text-blue-600 dark:text-blue-400 shadow-xs"
              : "text-slate-600 dark:text-slate-400 hover:text-slate-900"
          }`}
          data-testid="tab-workflows"
        >
          <Sparkles className="w-3.5 h-3.5" /> Agent
          {activeWorkflow?.status === "WAITING_FOR_APPROVAL" && (
            <span className="w-2 h-2 rounded-full bg-amber-500 animate-pulse" />
          )}
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
                  className={`group/message flex flex-col ${
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
                    {editingMessageId === msg.id ? (
                      <div className="space-y-2 min-w-64">
                        <textarea
                          value={editingMessageContent}
                          onChange={(event) => setEditingMessageContent(event.target.value)}
                          onKeyDown={(event) => {
                            if (event.key === "Enter" && !event.shiftKey) {
                              event.preventDefault();
                              saveEditedMessage();
                            }
                            if (event.key === "Escape") cancelEditingMessage();
                          }}
                          rows={3}
                          autoFocus
                          className="w-full rounded-lg border border-blue-300 bg-white p-2 text-xs text-slate-900 resize-y focus:outline-none focus:ring-2 focus:ring-blue-200"
                          aria-label="Edit message"
                          data-testid={`edit-message-input-${msg.id}`}
                        />
                        <div className="flex justify-end gap-1.5">
                          <button
                            type="button"
                            onClick={cancelEditingMessage}
                            className="rounded-md bg-blue-500 px-2 py-1 text-[10px] font-medium text-white hover:bg-blue-400"
                            data-testid={`cancel-edit-message-${msg.id}`}
                          >
                            Cancel
                          </button>
                          <button
                            type="button"
                            onClick={saveEditedMessage}
                            disabled={!editingMessageContent.trim() || isSending}
                            className="rounded-md bg-white px-2 py-1 text-[10px] font-semibold text-blue-700 hover:bg-blue-50 disabled:opacity-50"
                            data-testid={`save-edit-message-${msg.id}`}
                          >
                            Send
                          </button>
                        </div>
                      </div>
                    ) : (
                      <p className="whitespace-pre-wrap leading-relaxed">
                        {formatChatContent(msg.content, msg.role === "assistant")}
                      </p>
                    )}
                  </div>

                  {editingMessageId !== msg.id && (
                    <div
                      className={`mt-1 flex items-center gap-0.5 text-slate-400 opacity-0 transition-opacity group-hover/message:opacity-100 focus-within:opacity-100 ${
                        msg.role === "user" ? "flex-row-reverse" : ""
                      }`}
                    >
                      <button
                        type="button"
                        onClick={() => void handleCopyMessage(msg)}
                        className="rounded-md p-1 hover:bg-slate-100 hover:text-slate-700 dark:hover:bg-slate-800 dark:hover:text-slate-200"
                        aria-label={copiedMessageId === msg.id ? "Message copied" : "Copy message"}
                        title={copiedMessageId === msg.id ? "Copied" : "Copy"}
                        data-testid={`copy-message-${msg.id}`}
                      >
                        {copiedMessageId === msg.id ? (
                          <Check className="h-3.5 w-3.5 text-emerald-500" />
                        ) : (
                          <Copy className="h-3.5 w-3.5" />
                        )}
                      </button>
                      {msg.role === "user" && (
                        <button
                          type="button"
                          onClick={() => startEditingMessage(msg)}
                          className="rounded-md p-1 hover:bg-slate-100 hover:text-slate-700 dark:hover:bg-slate-800 dark:hover:text-slate-200"
                          aria-label="Edit message"
                          title="Edit"
                          data-testid={`edit-message-${msg.id}`}
                        >
                          <Pencil className="h-3.5 w-3.5" />
                        </button>
                      )}
                    </div>
                  )}

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
                      {Boolean(msg.proposal.old_content || msg.proposal.proposed_content) && (() => {
                        const oldDisplay =
                          formatDiffContent(msg.proposal.old_content, true) ||
                          (typeof msg.proposal.diff_summary?.old === "string" ? msg.proposal.diff_summary.old : "");
                        const proposedDisplay =
                          formatDiffContent(msg.proposal.proposed_content, false) ||
                          (typeof msg.proposal.diff_summary?.new === "string" ? msg.proposal.diff_summary.new : "");

                        return (
                          <div className="space-y-1">
                            {oldDisplay ? (
                              <div className="p-2 rounded bg-red-50 dark:bg-red-950/40 border border-red-200 dark:border-red-900 text-red-700 dark:text-red-300 font-mono text-[11px] line-through">
                                {oldDisplay}
                              </div>
                            ) : null}
                            {proposedDisplay ? (
                              <div className="p-2 rounded bg-emerald-50 dark:bg-emerald-950/40 border border-emerald-200 dark:border-emerald-900 text-emerald-700 dark:text-emerald-300 font-mono text-[11px]">
                                {proposedDisplay}
                              </div>
                            ) : null}
                          </div>
                        );
                      })()}

                      {/* Apply / Reject Actions */}
                      {msg.proposal.status === "PROPOSED" ? (
                        <div className="flex items-center gap-2 pt-1">
                          <button
                            onClick={() => handleApplyProposalAction(msg.proposal!.id)}
                            disabled={Boolean(processingProposalId)}
                            className={`flex-1 py-1.5 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg text-xs font-semibold flex items-center justify-center gap-1 shadow-xs transition-colors ${
                              processingProposalId ? "opacity-60 cursor-not-allowed" : ""
                            }`}
                            data-testid="apply-proposal-btn"
                          >
                            {processingProposalId === msg.proposal.id ? (
                              <>
                                <Loader2 className="w-3.5 h-3.5 animate-spin" /> Applying...
                              </>
                            ) : (
                              <>
                                <Check className="w-3.5 h-3.5" /> Apply Proposal
                              </>
                            )}
                          </button>
                          <button
                            onClick={() => handleRejectProposalAction(msg.proposal!.id)}
                            disabled={Boolean(processingProposalId)}
                            className={`py-1.5 px-3 bg-slate-200 hover:bg-slate-300 dark:bg-slate-700 dark:hover:bg-slate-600 text-slate-700 dark:text-slate-200 rounded-lg text-xs font-medium transition-colors ${
                              processingProposalId ? "opacity-60 cursor-not-allowed" : ""
                            }`}
                            data-testid="reject-proposal-btn"
                          >
                            <X className="w-3.5 h-3.5" /> Reject
                          </button>
                        </div>
                      ) : msg.proposal.status === "APPLIED" ? (
                        <div className="pt-1 flex items-center gap-1 text-[11px] font-semibold text-emerald-600 dark:text-emerald-400">
                          <Check className="w-3.5 h-3.5" /> Applied to Document
                        </div>
                      ) : msg.proposal.status === "REJECTED" ? (
                        <div className="pt-1 flex items-center gap-1 text-[11px] font-semibold text-slate-500">
                          <X className="w-3.5 h-3.5" /> Proposal Rejected
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

      {/* Tab: AI Agent Workflows */}
      {activeTab === "workflows" && (
        <div className="flex-1 flex flex-col p-3 overflow-hidden space-y-2.5" data-testid="workflows-tab-content">
          {/* Quick recipe chips */}
          <div className="space-y-1">
            <span className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider">
              Agent Actions
            </span>
            <div className="grid grid-cols-2 gap-1.5">
              {[
                { label: "Optimize Document", query: "Perform a comprehensive content and SEO optimization" },
                { label: "Audit & Fix SEO", query: "Audit content quality and propose SEO enhancements" },
                { label: "Inject Links", query: "Analyze document and insert relevant internal links" },
                { label: "Expand Depth", query: "Deepen technical depth and add architectural details" },
              ].map((recipe, idx) => (
                <button
                  key={idx}
                  onClick={() => handleExecuteWorkflow(recipe.query)}
                  disabled={isOrchestrating}
                  className="p-1.5 rounded-lg bg-slate-50 hover:bg-slate-100 dark:bg-slate-800 dark:hover:bg-slate-700/80 border border-slate-200 dark:border-slate-800 text-left transition-colors disabled:opacity-50"
                  data-testid={`recipe-btn-${idx}`}
                >
                  <div className="text-[10px] font-semibold text-slate-800 dark:text-slate-200 flex items-center gap-1">
                    <Zap className="w-3 h-3 text-amber-500" />
                    {recipe.label}
                  </div>
                  <div className="text-[9px] text-slate-400 truncate">
                    {recipe.query}
                  </div>
                </button>
              ))}
            </div>
          </div>

          {/* Activity / Timeline Area */}
          <div className="flex-1 overflow-y-auto border border-slate-100 dark:border-slate-800/80 rounded-xl bg-slate-50/50 dark:bg-slate-900/40">
            <WorkflowActivity
              workflow={activeWorkflow}
              isLoading={isOrchestrating}
              onApproveStep={handleApproveStep}
              onRejectStep={handleRejectStep}
              onRetryStep={handleRetryStep}
              onCancelWorkflow={handleCancelWorkflow}
            />
          </div>

          {workflowError && (
            <div className="p-2 rounded bg-red-50 dark:bg-red-950/40 text-red-600 text-[11px] flex items-center gap-1">
              <AlertCircle className="w-3.5 h-3.5 shrink-0" />
              <span>{workflowError}</span>
            </div>
          )}

          {/* Workflow Input Box */}
          <div className="pt-2 border-t border-slate-100 dark:border-slate-800 flex gap-2">
            <textarea
              rows={2}
              value={workflowInput}
              onChange={(e) => setWorkflowInput(e.target.value)}
              placeholder="Give the orchestrator instructions..."
              disabled={isOrchestrating}
              className="flex-1 p-2 rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-xs text-slate-900 dark:text-white placeholder:text-slate-400 focus:outline-hidden focus:ring-1 focus:ring-blue-500 resize-none disabled:opacity-50"
              data-testid="workflow-input"
            />
            <button
              onClick={() => handleExecuteWorkflow()}
              disabled={!workflowInput.trim() || isOrchestrating}
              className="px-3 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white rounded-xl flex items-center justify-center transition-colors shadow-xs"
              data-testid="workflow-submit-btn"
            >
              {isOrchestrating ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <Send className="w-4 h-4" />
              )}
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
