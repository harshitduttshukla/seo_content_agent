"use client";

import React, { useState, useRef } from "react";
import type { ContentBlock, ContentDocument, AIProposal } from "@/lib/api-types";
import { ApiError, clientApi } from "@/lib/client-api";
import {
  ArrowDown,
  ArrowUp,
  Check,
  CheckCircle2,
  RefreshCw,
  Trash2,
  X,
  Zap,
} from "lucide-react";

interface ContentEditorProps {
  document: ContentDocument;
  activeProposal?: AIProposal | null;
  selectedBlockId?: string | null;
  onSelectBlock?: (blockId: string | null) => void;
  onUpdateDocument?: (doc: ContentDocument) => void;
  onApplyProposal?: (proposalId: string) => void;
  onRejectProposal?: (proposalId: string) => void;
}

export function ContentEditor({
  document: initialDoc,
  activeProposal,
  selectedBlockId,
  onSelectBlock,
  onUpdateDocument,
  onApplyProposal,
  onRejectProposal,
}: ContentEditorProps) {
  const doc = initialDoc;
  const [blocks, setBlocks] = useState<ContentBlock[]>(initialDoc.content_blocks || []);
  const [saveStatus, setSaveStatus] = useState<"SAVED" | "SAVING" | "UNSAVED" | "CONFLICT">("SAVED");
  const [lockVersion, setLockVersion] = useState<number>(initialDoc.lock_version || 1);
  const [conflictMessage, setConflictMessage] = useState<string | null>(null);
  const nextLocalBlockId = useRef(initialDoc.content_blocks?.length ?? 0);

  // Debounced Autosave
  const saveTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  const triggerAutosave = (newBlocks: ContentBlock[]) => {
    setSaveStatus("UNSAVED");
    if (saveTimeoutRef.current) clearTimeout(saveTimeoutRef.current);

    saveTimeoutRef.current = setTimeout(async () => {
      setSaveStatus("SAVING");
      try {
        const updatedDocument = await clientApi<ContentDocument>(`/content-documents/${doc.id}`, {
          method: "PUT",
          body: JSON.stringify({
            lock_version: lockVersion,
            content_blocks: newBlocks,
            create_version_snapshot: false,
          }),
        });
        setSaveStatus("SAVED");
        setLockVersion(updatedDocument.lock_version);
        onUpdateDocument?.(updatedDocument);
      } catch (err: unknown) {
        if (err instanceof ApiError && err.status === 409) {
          setSaveStatus("CONFLICT");
          setConflictMessage(err.message);
          return;
        }
        setSaveStatus("UNSAVED");
        console.error("Autosave error:", err);
      }
    }, 1500);
  };

  const handleUpdateBlockText = (id: string, text: string) => {
    const updated = blocks.map((b) => (b.id === id ? { ...b, text } : b));
    setBlocks(updated);
    triggerAutosave(updated);
  };

  const handleInsertBlock = (afterId: string, type: ContentBlock["type"], level: number = 2) => {
    const idx = blocks.findIndex((b) => b.id === afterId);
    nextLocalBlockId.current += 1;
    const newId = `block_local_${nextLocalBlockId.current}`;
    const newBlock: ContentBlock = {
      id: newId,
      type,
      text: "",
      level: type === "HEADING" ? level : undefined,
    };
    const updated = [...blocks];
    updated.splice(idx + 1, 0, newBlock);
    setBlocks(updated);
    triggerAutosave(updated);
    if (onSelectBlock) onSelectBlock(newId);
  };

  const handleDeleteBlock = (id: string) => {
    if (blocks.length <= 1) return;
    const updated = blocks.filter((b) => b.id !== id);
    setBlocks(updated);
    triggerAutosave(updated);
    if (selectedBlockId === id && onSelectBlock) onSelectBlock(null);
  };

  const handleMoveBlock = (idx: number, direction: "UP" | "DOWN") => {
    if ((direction === "UP" && idx === 0) || (direction === "DOWN" && idx === blocks.length - 1)) {
      return;
    }
    const targetIdx = direction === "UP" ? idx - 1 : idx + 1;
    const updated = [...blocks];
    const [moved] = updated.splice(idx, 1);
    updated.splice(targetIdx, 0, moved);
    setBlocks(updated);
    triggerAutosave(updated);
  };

  // Check if a block is targeted by activeProposal
  const isBlockProposed = (blockId: string) => {
    if (!activeProposal || activeProposal.status !== "PROPOSED") return false;
    return activeProposal.target_block_ids?.includes(blockId);
  };

  const currentWordCount = blocks.reduce((acc, b) => acc + (b.text?.split(/\s+/).filter(Boolean).length || 0), 0);

  return (
    <div className="max-w-4xl mx-auto space-y-6" data-testid="content-editor">
      {/* Editor Status Bar */}
      <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3 sticky top-4 z-20 shadow-sm backdrop-blur-md bg-white/90 dark:bg-slate-900/90">
        <div className="flex items-center gap-3">
          <span className="text-xs font-bold px-2.5 py-0.5 rounded-full bg-blue-50 text-blue-700 dark:bg-blue-950/50 dark:text-blue-300 border border-blue-200 dark:border-blue-800">
            v{doc.current_version}
          </span>
          <span className="text-xs text-slate-500 dark:text-slate-400">
            Lock v{lockVersion} • {currentWordCount.toLocaleString()} words
          </span>
        </div>

        <div className="flex items-center gap-2">
          {saveStatus === "SAVING" && (
            <span className="text-xs text-blue-600 dark:text-blue-400 flex items-center gap-1">
              <RefreshCw className="w-3.5 h-3.5 animate-spin" /> Saving...
            </span>
          )}
          {saveStatus === "SAVED" && (
            <span className="text-xs text-emerald-600 dark:text-emerald-400 flex items-center gap-1 font-medium" data-testid="save-status-saved">
              <CheckCircle2 className="w-3.5 h-3.5" /> Saved
            </span>
          )}
          {saveStatus === "UNSAVED" && (
            <span className="text-xs text-amber-600 dark:text-amber-400 flex items-center gap-1 font-medium">
              • Unsaved changes
            </span>
          )}
          {saveStatus === "CONFLICT" && (
            <span className="text-xs text-red-600 dark:text-red-400 flex items-center gap-1 font-bold" data-testid="lock-conflict-indicator">
              Conflict! Reload to merge
            </span>
          )}
        </div>
      </div>

      {conflictMessage && (
        <div className="p-4 bg-red-50 dark:bg-red-950/50 border border-red-200 dark:border-red-900 rounded-xl text-sm text-red-700 dark:text-red-300 flex items-center justify-between">
          <span>{conflictMessage}</span>
          <button
            onClick={() => window.location.reload()}
            className="px-3 py-1 bg-red-600 text-white rounded-lg text-xs font-semibold hover:bg-red-700"
          >
            Reload Page
          </button>
        </div>
      )}

      {/* Structured Blocks Canvas */}
      <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-8 sm:p-12 shadow-sm space-y-4 min-h-[650px]" data-testid="blocks-canvas">
        {blocks.map((block, idx) => {
          const isSelected = selectedBlockId === block.id;
          const isProposed = isBlockProposed(block.id);

          return (
            <div
              key={block.id}
              onClick={() => onSelectBlock && onSelectBlock(block.id)}
              className={`group relative rounded-xl transition-all duration-200 p-2 sm:p-3 ${
                isSelected
                  ? "ring-2 ring-blue-500 bg-blue-50/30 dark:bg-blue-950/20"
                  : "hover:bg-slate-50 dark:hover:bg-slate-800/40"
              } ${isProposed ? "border-2 border-dashed border-amber-400 dark:border-amber-500 bg-amber-50/20" : ""}`}
              data-testid={`block-${block.id}`}
            >
              {/* Block Header ID badge & actions toolbar on hover */}
              <div className="opacity-0 group-hover:opacity-100 transition-opacity absolute -top-3 right-3 flex items-center gap-1 bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg px-2 py-0.5 shadow-sm text-[11px] text-slate-500 dark:text-slate-400 z-10">
                <span className="font-mono text-[10px] text-slate-400 mr-1">{block.id}</span>
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    handleMoveBlock(idx, "UP");
                  }}
                  title="Move Up"
                  className="hover:text-slate-900 dark:hover:text-white p-0.5"
                >
                  <ArrowUp className="w-3 h-3" />
                </button>
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    handleMoveBlock(idx, "DOWN");
                  }}
                  title="Move Down"
                  className="hover:text-slate-900 dark:hover:text-white p-0.5"
                >
                  <ArrowDown className="w-3 h-3" />
                </button>
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    handleDeleteBlock(block.id);
                  }}
                  title="Delete Block"
                  className="hover:text-red-600 p-0.5"
                >
                  <Trash2 className="w-3 h-3" />
                </button>
              </div>

              {/* Block Content by Type */}
              {block.type === "DOCUMENT_TITLE" ? (
                <input
                  type="text"
                  value={block.text}
                  onChange={(e) => handleUpdateBlockText(block.id, e.target.value)}
                  placeholder="Document Title (H1)..."
                  className="w-full text-2xl sm:text-3xl font-extrabold text-slate-900 dark:text-white bg-transparent border-none focus:outline-none focus:ring-0 tracking-tight"
                />
              ) : block.type === "HEADING" && block.level === 2 ? (
                <input
                  type="text"
                  value={block.text}
                  onChange={(e) => handleUpdateBlockText(block.id, e.target.value)}
                  placeholder="Heading 2..."
                  className="w-full text-xl sm:text-2xl font-bold text-slate-800 dark:text-slate-100 bg-transparent border-none focus:outline-none focus:ring-0 mt-2"
                />
              ) : block.type === "HEADING" ? (
                <input
                  type="text"
                  value={block.text}
                  onChange={(e) => handleUpdateBlockText(block.id, e.target.value)}
                  placeholder="Heading 3..."
                  className="w-full text-lg sm:text-xl font-semibold text-slate-700 dark:text-slate-200 bg-transparent border-none focus:outline-none focus:ring-0 mt-2"
                />
              ) : block.type === "QUOTE" ? (
                <div className="border-l-4 border-blue-500 pl-4 py-1 italic">
                  <textarea
                    rows={2}
                    value={block.text}
                    onChange={(e) => handleUpdateBlockText(block.id, e.target.value)}
                    placeholder="Enter quote..."
                    className="w-full text-slate-600 dark:text-slate-300 bg-transparent border-none focus:outline-none focus:ring-0 resize-none"
                  />
                </div>
              ) : (
                <textarea
                  rows={Math.max(2, Math.ceil((block.text?.length || 0) / 75))}
                  value={block.text}
                  onChange={(e) => handleUpdateBlockText(block.id, e.target.value)}
                  placeholder="Write content or type prompt in AI sidebar..."
                  className="w-full text-slate-700 dark:text-slate-300 bg-transparent border-none focus:outline-none focus:ring-0 resize-none leading-relaxed text-base"
                />
              )}

              {/* Proposal Diff Overlay Banner if block is targeted */}
              {isProposed && activeProposal && (
                <div className="mt-3 p-3 rounded-lg bg-amber-50 dark:bg-amber-950/40 border border-amber-200 dark:border-amber-800 text-xs space-y-2" data-testid="proposal-diff-overlay">
                  <div className="flex items-center justify-between font-semibold text-amber-800 dark:text-amber-300">
                    <span className="flex items-center gap-1.5">
                      <Zap className="w-3.5 h-3.5 text-amber-500" />
                      AI Proposed Changes
                    </span>
                    <div className="flex items-center gap-2">
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          if (onApplyProposal) onApplyProposal(activeProposal.id);
                        }}
                        className="px-2 py-1 bg-emerald-600 hover:bg-emerald-700 text-white rounded font-medium flex items-center gap-1 shadow-xs"
                        data-testid="inline-apply-btn"
                      >
                        <Check className="w-3 h-3" /> Apply
                      </button>
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          if (onRejectProposal) onRejectProposal(activeProposal.id);
                        }}
                        className="px-2 py-1 bg-slate-200 dark:bg-slate-700 hover:bg-slate-300 text-slate-700 dark:text-slate-300 rounded font-medium flex items-center gap-1"
                        data-testid="inline-reject-btn"
                      >
                        <X className="w-3 h-3" /> Dismiss
                      </button>
                    </div>
                  </div>

                  {activeProposal.reason && (
                    <p className="text-slate-600 dark:text-slate-400 italic">{activeProposal.reason}</p>
                  )}
                </div>
              )}

              {/* Add Block Dropdown on Hover between blocks */}
              <div className="opacity-0 group-hover:opacity-100 transition-opacity flex justify-center py-1">
                <div className="flex items-center gap-1 bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-full px-2 py-0.5 shadow-sm text-xs text-slate-600 dark:text-slate-300">
                  <span className="text-[10px] text-slate-400 mr-1">Add:</span>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      handleInsertBlock(block.id, "PARAGRAPH");
                    }}
                    className="hover:text-blue-600 px-1 font-medium"
                  >
                    + Paragraph
                  </button>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      handleInsertBlock(block.id, "HEADING", 2);
                    }}
                    className="hover:text-blue-600 px-1 font-medium"
                  >
                    + H2
                  </button>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      handleInsertBlock(block.id, "HEADING", 3);
                    }}
                    className="hover:text-blue-600 px-1 font-medium"
                  >
                    + H3
                  </button>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      handleInsertBlock(block.id, "QUOTE");
                    }}
                    className="hover:text-blue-600 px-1 font-medium"
                  >
                    + Quote
                  </button>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
