"use client";

import React, { useState } from "react";
import type {
  WorkflowDetail,
  WorkflowStepDetail,
  RiskLevel,
  StepStatus,
} from "@/lib/api-types";
import {
  AlertCircle,
  AlertTriangle,
  ArrowRight,
  Check,
  CheckCircle2,
  Clock,
  ExternalLink,
  Layers,
  Loader2,
  Play,
  RotateCcw,
  Shield,
  Sparkles,
  X,
  XCircle,
  Zap,
} from "lucide-react";

interface WorkflowActivityProps {
  workflow: WorkflowDetail | null;
  isLoading?: boolean;
  onApproveStep?: (stepId: string) => Promise<void>;
  onRejectStep?: (stepId: string) => Promise<void>;
  onRetryStep?: () => Promise<void>;
  onCancelWorkflow?: () => Promise<void>;
}

export function WorkflowActivity({
  workflow,
  isLoading = false,
  onApproveStep,
  onRejectStep,
  onRetryStep,
  onCancelWorkflow,
}: WorkflowActivityProps) {
  const [actionInProgress, setActionInProgress] = useState<string | null>(null);
  const [expandedSteps, setExpandedSteps] = useState<Record<string, boolean>>({});

  if (isLoading && !workflow) {
    return (
      <div className="flex flex-col items-center justify-center p-8 text-slate-400 space-y-3">
        <Loader2 className="w-6 h-6 animate-spin text-blue-500" />
        <p className="text-xs font-medium">Orchestrating agent workflow...</p>
      </div>
    );
  }

  if (!workflow) {
    return (
      <div className="text-center py-12 text-slate-400 space-y-2 p-4">
        <Layers className="w-8 h-8 mx-auto text-blue-400 opacity-60" />
        <p className="font-medium text-slate-600 dark:text-slate-300 text-xs">
          No Active Workflow
        </p>
        <p className="text-[11px] max-w-xs mx-auto text-slate-500">
          Run an optimization or multi-step command to see the AI agent plan and execute governed tools.
        </p>
      </div>
    );
  }

  const toggleExpand = (stepId: string) => {
    setExpandedSteps((prev) => ({
      ...prev,
      [stepId]: !prev[stepId],
    }));
  };

  const handleApprove = async (stepId: string) => {
    if (!onApproveStep || actionInProgress) return;
    setActionInProgress(`approve-${stepId}`);
    try {
      await onApproveStep(stepId);
    } finally {
      setActionInProgress(null);
    }
  };

  const handleReject = async (stepId: string) => {
    if (!onRejectStep || actionInProgress) return;
    setActionInProgress(`reject-${stepId}`);
    try {
      await onRejectStep(stepId);
    } finally {
      setActionInProgress(null);
    }
  };

  const handleRetry = async () => {
    if (!onRetryStep || actionInProgress) return;
    setActionInProgress("retry");
    try {
      await onRetryStep();
    } finally {
      setActionInProgress(null);
    }
  };

  const handleCancel = async () => {
    if (!onCancelWorkflow || actionInProgress) return;
    setActionInProgress("cancel");
    try {
      await onCancelWorkflow();
    } finally {
      setActionInProgress(null);
    }
  };

  const getRiskBadge = (risk: RiskLevel) => {
    switch (risk) {
      case "READ":
        return (
          <span className="px-1.5 py-0.5 rounded text-[10px] font-semibold bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-800">
            READ
          </span>
        );
      case "SUGGEST":
        return (
          <span className="px-1.5 py-0.5 rounded text-[10px] font-semibold bg-blue-100 text-blue-800 dark:bg-blue-950 dark:text-blue-300 border border-blue-200 dark:border-blue-800">
            SUGGEST
          </span>
        );
      case "WRITE":
        return (
          <span className="px-1.5 py-0.5 rounded text-[10px] font-semibold bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-300 border border-amber-200 dark:border-amber-800">
            WRITE
          </span>
        );
      case "DESTRUCTIVE":
        return (
          <span className="px-1.5 py-0.5 rounded text-[10px] font-semibold bg-red-100 text-red-800 dark:bg-red-950 dark:text-red-300 border border-red-200 dark:border-red-800">
            DESTRUCTIVE
          </span>
        );
      default:
        return null;
    }
  };

  const getStatusIcon = (status: StepStatus) => {
    switch (status) {
      case "COMPLETED":
        return <CheckCircle2 className="w-4 h-4 text-emerald-500 shrink-0" />;
      case "RUNNING":
        return <Loader2 className="w-4 h-4 text-blue-500 animate-spin shrink-0" />;
      case "WAITING_FOR_APPROVAL":
        return <AlertTriangle className="w-4 h-4 text-amber-500 shrink-0 animate-pulse" />;
      case "FAILED":
        return <XCircle className="w-4 h-4 text-red-500 shrink-0" />;
      case "SKIPPED":
        return <X className="w-4 h-4 text-slate-400 shrink-0" />;
      case "PENDING":
      default:
        return <Clock className="w-4 h-4 text-slate-400 shrink-0" />;
    }
  };

  const completedStepsCount = workflow.steps.filter((s) => s.status === "COMPLETED").length;
  const totalSteps = workflow.steps.length || 1;
  const progressPercent = Math.round((completedStepsCount / totalSteps) * 100);

  return (
    <div className="flex flex-col h-full space-y-3 p-3 overflow-y-auto text-xs" data-testid="workflow-activity">
      {/* Workflow Header Banner */}
      <div className="p-3 rounded-xl bg-slate-50 dark:bg-slate-800/60 border border-slate-200 dark:border-slate-800 space-y-2">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-1.5">
            <Sparkles className="w-4 h-4 text-blue-500" />
            <span className="font-semibold text-slate-900 dark:text-white">
              {workflow.intent.replace(/_/g, " ")}
            </span>
          </div>
          <span
            className={`px-2 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider ${
              workflow.status === "COMPLETED"
                ? "bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300"
                : workflow.status === "WAITING_FOR_APPROVAL"
                ? "bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-300 animate-pulse"
                : workflow.status === "FAILED"
                ? "bg-red-100 text-red-800 dark:bg-red-950 dark:text-red-300"
                : "bg-blue-100 text-blue-800 dark:bg-blue-950 dark:text-blue-300"
            }`}
            data-testid="workflow-status-badge"
          >
            {workflow.status.replace(/_/g, " ")}
          </span>
        </div>

        {/* Progress Bar */}
        <div className="space-y-1">
          <div className="flex justify-between text-[10px] text-slate-500">
            <span>Progress: {completedStepsCount} of {totalSteps} steps</span>
            <span>{progressPercent}%</span>
          </div>
          <div className="w-full bg-slate-200 dark:bg-slate-700 h-1.5 rounded-full overflow-hidden">
            <div
              className={`h-full transition-all duration-300 ${
                workflow.status === "COMPLETED"
                  ? "bg-emerald-500"
                  : workflow.status === "WAITING_FOR_APPROVAL"
                  ? "bg-amber-500"
                  : workflow.status === "FAILED"
                  ? "bg-red-500"
                  : "bg-blue-500"
              }`}
              style={{ width: `${progressPercent}%` }}
            />
          </div>
        </div>

        {/* Action Controls for Workflow */}
        <div className="flex items-center justify-end gap-2 pt-1">
          {workflow.status === "FAILED" && (
            <button
              onClick={handleRetry}
              disabled={Boolean(actionInProgress)}
              className="px-2.5 py-1 rounded-lg bg-red-600 hover:bg-red-700 text-white font-medium text-[11px] flex items-center gap-1 transition-colors disabled:opacity-50"
              data-testid="workflow-retry-btn"
            >
              {actionInProgress === "retry" ? (
                <Loader2 className="w-3 h-3 animate-spin" />
              ) : (
                <RotateCcw className="w-3 h-3" />
              )}
              Retry Failed Step
            </button>
          )}

          {(workflow.status === "RUNNING" || workflow.status === "WAITING_FOR_APPROVAL") && (
            <button
              onClick={handleCancel}
              disabled={Boolean(actionInProgress)}
              className="px-2.5 py-1 rounded-lg bg-slate-200 hover:bg-slate-300 dark:bg-slate-700 dark:hover:bg-slate-600 text-slate-700 dark:text-slate-300 font-medium text-[11px] flex items-center gap-1 transition-colors disabled:opacity-50"
              data-testid="workflow-cancel-btn"
            >
              {actionInProgress === "cancel" ? (
                <Loader2 className="w-3 h-3 animate-spin" />
              ) : (
                <X className="w-3 h-3" />
              )}
              Cancel Workflow
            </button>
          )}
        </div>
      </div>

      {/* Step Timeline */}
      <div className="space-y-2.5" data-testid="workflow-step-list">
        {workflow.steps.map((step, idx) => {
          const planItem = workflow.plan.find((p) => p.step_index === step.step_index);
          const execution = workflow.executions?.find(
            (e) => e.tool_name === step.tool_name
          );
          const isWaitingApproval = step.status === "WAITING_FOR_APPROVAL";
          const isExpanded = expandedSteps[step.id];

          return (
            <div
              key={step.id || idx}
              className={`rounded-xl border p-3 transition-all ${
                isWaitingApproval
                  ? "bg-amber-50/70 dark:bg-amber-950/20 border-amber-300 dark:border-amber-800 shadow-xs"
                  : step.status === "RUNNING"
                  ? "bg-blue-50/50 dark:bg-blue-950/20 border-blue-200 dark:border-blue-900"
                  : "bg-white dark:bg-slate-900 border-slate-200 dark:border-slate-800"
              }`}
              data-testid={`step-card-${step.step_index}`}
            >
              {/* Step Header */}
              <div className="flex items-center justify-between gap-2">
                <div className="flex items-center gap-2 min-w-0">
                  {getStatusIcon(step.status)}
                  <span className="font-semibold text-slate-800 dark:text-slate-200 truncate font-mono text-[11px]">
                    {step.tool_name}
                  </span>
                </div>
                <div className="flex items-center gap-1.5 shrink-0">
                  {planItem && getRiskBadge(planItem.risk_level)}
                  {execution?.duration_ms != null && (
                    <span className="text-[10px] text-slate-400 font-mono">
                      {execution.duration_ms}ms
                    </span>
                  )}
                </div>
              </div>

              {/* Rationale */}
              {planItem?.rationale && (
                <p className="mt-1 text-[11px] text-slate-500 dark:text-slate-400">
                  {planItem.rationale}
                </p>
              )}

              {/* Error Banner */}
              {step.error_message && (
                <div className="mt-2 p-2 rounded bg-red-50 dark:bg-red-950/40 border border-red-200 dark:border-red-900 text-red-700 dark:text-red-300 text-[11px] flex items-start gap-1.5">
                  <AlertCircle className="w-3.5 h-3.5 mt-0.5 shrink-0" />
                  <span>{step.error_message}</span>
                </div>
              )}

              {/* Approval Gate Card */}
              {isWaitingApproval && (
                <div
                  className="mt-3 p-3 rounded-lg bg-amber-100/70 dark:bg-amber-900/30 border border-amber-300 dark:border-amber-700 space-y-2"
                  data-testid={`approval-gate-${step.id}`}
                >
                  <div className="flex items-center gap-1.5 text-amber-900 dark:text-amber-200 font-semibold text-[11px]">
                    <Shield className="w-3.5 h-3.5 text-amber-600 dark:text-amber-400" />
                    <span>Human Approval Required for Write Action</span>
                  </div>

                  <p className="text-[11px] text-amber-800 dark:text-amber-300">
                    The agent formulated a structured patch. Review and approve to apply modifications.
                  </p>

                  {Boolean(step.output?.proposal_id) && (
                    <div className="text-[10px] text-amber-700 dark:text-amber-400 font-mono">
                      Proposal: {String(step.output?.proposal_id)}
                    </div>
                  )}

                  <div className="flex items-center gap-2 pt-1">
                    <button
                      onClick={() => handleApprove(step.id)}
                      disabled={Boolean(actionInProgress)}
                      className="flex-1 py-1.5 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg text-xs font-semibold flex items-center justify-center gap-1 shadow-xs transition-colors disabled:opacity-50"
                      data-testid="approve-step-btn"
                    >
                      {actionInProgress === `approve-${step.id}` ? (
                        <Loader2 className="w-3.5 h-3.5 animate-spin" />
                      ) : (
                        <Check className="w-3.5 h-3.5" />
                      )}
                      Approve & Apply
                    </button>
                    <button
                      onClick={() => handleReject(step.id)}
                      disabled={Boolean(actionInProgress)}
                      className="py-1.5 px-3 bg-slate-200 hover:bg-slate-300 dark:bg-slate-700 dark:hover:bg-slate-600 text-slate-700 dark:text-slate-200 rounded-lg text-xs font-medium transition-colors disabled:opacity-50"
                      data-testid="reject-step-btn"
                    >
                      {actionInProgress === `reject-${step.id}` ? (
                        <Loader2 className="w-3.5 h-3.5 animate-spin" />
                      ) : (
                        <X className="w-3.5 h-3.5" />
                      )}
                      Reject
                    </button>
                  </div>
                </div>
              )}

              {/* Step Output / Details Collapsible */}
              {step.output && !isWaitingApproval && (
                <div className="mt-2">
                  <button
                    onClick={() => toggleExpand(step.id)}
                    className="text-[10px] text-blue-600 dark:text-blue-400 font-medium hover:underline flex items-center gap-0.5"
                  >
                    {isExpanded ? "Hide Output" : "View Output"}
                  </button>
                  {isExpanded && (
                    <pre className="mt-1.5 p-2 rounded bg-slate-100 dark:bg-slate-800 text-[10px] font-mono text-slate-700 dark:text-slate-300 max-h-36 overflow-auto whitespace-pre-wrap">
                      {JSON.stringify(step.output, null, 2)}
                    </pre>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
