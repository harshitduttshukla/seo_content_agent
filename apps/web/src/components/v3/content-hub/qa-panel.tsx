"use client";

import { useState } from "react";

import type { CardDetail, QAFinding, WarningDismissal } from "@/lib/api-types";

import { claimLabel } from "./draft-view";
import { formatWhen } from "./g1-review";

const btn =
  "rounded-[5px] border border-[var(--line)] bg-white px-[10px] py-[4px] text-[12.5px] text-[#12171A] hover:bg-[#F0F2F1] focus-visible:outline-2 focus-visible:outline-[var(--teal)] disabled:opacity-50";
const btnPrimary =
  "rounded-[5px] border border-[var(--teal)] bg-[var(--teal)] px-[10px] py-[4px] text-[12.5px] text-white focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--teal)] disabled:opacity-50";

const SEVERITY_TONE: Record<QAFinding["severity"], string> = {
  error: "border-[var(--coral)] bg-[#FBEFEC] text-[var(--coral)]",
  warning: "border-[#D9B25C] bg-[#FBF5E6] text-[#8A6A1E]",
  info: "border-[var(--line)] bg-[#F4F6F5] text-[var(--ink3)]",
};

export type QAChipState = "not_run" | "running" | "passed" | "failed" | "stale";
const CHIP: Record<QAChipState, [string, string]> = {
  not_run: ["r", "QA not run"],
  running: ["t", "QA running"],
  passed: ["t", "QA passed"],
  failed: ["c", "QA failed"],
  stale: ["c", "QA stale"],
};

export function qaChipState(detail: CardDetail, running: boolean): QAChipState {
  if (running) return "running";
  const report = detail.qa?.report;
  if (!report) return "not_run";
  // G2 approval moves the revision; an approved card keeps the QA result it was approved on.
  if (["approved", "live"].includes(detail.card.state)) return report.status;
  if (detail.qa?.stale) return "stale";
  return report.status;
}

export function QAChip({ state }: { state: QAChipState }) {
  const [tone, label] = CHIP[state];
  return (
    <span className={`chip ${tone}`} data-testid="qa-status">
      {label}
    </span>
  );
}

interface QAPanelProps {
  detail: CardDetail;
  running: boolean;
  busy: boolean;
  onRun: () => Promise<boolean>;
  onRepair: () => Promise<boolean>;
  onDismiss: (findingId: string, reason: string) => Promise<boolean>;
}

function FindingCard({
  finding,
  dismissal,
  canDismiss,
  busy,
  onDismiss,
}: {
  finding: QAFinding;
  dismissal?: WarningDismissal;
  canDismiss: boolean;
  busy: boolean;
  onDismiss: (findingId: string, reason: string) => Promise<boolean>;
}) {
  const [open, setOpen] = useState(false);
  const [reason, setReason] = useState("");
  return (
    <li className={`mb-[6px] rounded-[6px] border px-[8px] py-[6px] ${SEVERITY_TONE[finding.severity]}`} data-testid="qa-finding" data-severity={finding.severity}>
      <div className="flex items-start gap-[6px]">
        <span className="font-mono text-[10.5px] font-semibold uppercase">[{finding.severity}]</span>
        <span className="text-[12.2px] text-[#12171A]">{finding.message}</span>
      </div>
      <div className="mt-[3px] text-[11.2px] text-[var(--ink3)]">
        {finding.code.toLowerCase().replaceAll("_", " ")}
        {finding.section_id ? ` · section ${finding.section_id}` : ""}
        {finding.claim_id ? ` · ${claimLabel(finding.claim_id)}` : ""}
        {finding.layer === "model" ? " · model check" : ""}
      </div>
      {finding.url ? <div className="mt-[2px] break-all text-[11.2px] text-[var(--ink3)]">{finding.url}</div> : null}
      {finding.evidence && finding.code !== "WORD_BUDGET" ? (
        <blockquote className="m-[3px_0_0] border-l-2 border-current pl-[6px] text-[11.5px] italic text-[#5C666C]">{finding.evidence}</blockquote>
      ) : null}
      {finding.suggested_repair ? <div className="mt-[3px] text-[11.5px] text-[#5C666C]">Fix · {finding.suggested_repair}</div> : null}
      {dismissal ? (
        <div className="mt-[4px] text-[11.2px] text-[var(--ink3)]" data-testid="dismissed">
          Dismissed by {dismissal.reviewer_name ?? "a reviewer"} · {formatWhen(dismissal.dismissed_at)} · {dismissal.reason}
        </div>
      ) : canDismiss && finding.severity === "warning" ? (
        open ? (
          <form
            className="mt-[5px]"
            aria-label={`Dismiss warning ${finding.id}`}
            onSubmit={async (event) => {
              event.preventDefault();
              if (reason.trim() && (await onDismiss(finding.id, reason.trim()))) setOpen(false);
            }}
          >
            <input
              aria-label="Reason for dismissing"
              className="mb-[4px] w-full rounded-[5px] border border-[var(--line)] bg-white px-[6px] py-[3px] text-[12px] text-[#12171A]"
              placeholder="Why this is acceptable"
              value={reason}
              onChange={(event) => setReason(event.target.value)}
            />
            <span className="flex gap-[6px]">
              <button type="submit" className={btn} disabled={busy || !reason.trim()}>Dismiss warning</button>
              <button type="button" className={btn} onClick={() => setOpen(false)}>Cancel</button>
            </span>
          </form>
        ) : (
          <button type="button" className={`${btn} mt-[5px]`} disabled={busy} onClick={() => setOpen(true)}>
            Dismiss
          </button>
        )
      ) : null}
    </li>
  );
}

/** QA in the right-hand "Checks and gate" pane (handoff §6.1, §6.4). */
export function QAPanel({ detail, running, busy, onRun, onRepair, onDismiss }: QAPanelProps) {
  const report = detail.qa?.report ?? null;
  const state = qaChipState(detail, running);
  const dismissals = new Map((report?.dismissals ?? []).map((d) => [d.finding_id, d]));
  const errors = report?.findings.filter((f) => f.severity === "error") ?? [];
  const others = report?.findings.filter((f) => f.severity !== "error") ?? [];
  const showQA = ["drafting", "qa_failed", "qa_passed", "approved", "live"].includes(detail.card.state);
  if (!showQA) return null;

  return (
    <section aria-label="QA" className="mt-[10px] border-t border-[var(--line2)] pt-[10px] text-[12.6px]">
      <div className="mb-[6px] flex items-center gap-[8px]">
        <h4 className="m-0 text-[12.8px] font-medium">QA</h4>
        <QAChip state={state} />
        {report ? (
          <span className="text-[11.2px] text-[var(--ink3)]">
            {report.error_count} error(s) · {report.warning_count} warning(s)
          </span>
        ) : null}
      </div>
      {report ? (
        <p className="m-[0_0_6px] text-[11.2px] text-[var(--ink3)]">
          Draft v{report.draft_version} · {formatWhen(report.run_at)} · {report.model_layer === "ran" ? `model check ${report.model ?? ""}` : report.model_note}
        </p>
      ) : null}
      {detail.qa?.stale ? (
        <p className="m-[0_0_6px] text-[var(--coral)]">The draft changed after this QA run; run QA again before G2.</p>
      ) : null}
      <span className="mb-[8px] flex gap-[6px]">
        {detail.actions.can_run_qa || running ? (
          <button type="button" className={btnPrimary} disabled={!detail.actions.can_run_qa || busy} onClick={onRun}>
            {running ? "Running QA…" : report ? "Run QA again" : "Run QA"}
          </button>
        ) : null}
        {detail.actions.can_repair ? (
          <button type="button" className={btn} disabled={busy} onClick={onRepair}>
            Repair {errors.length} error(s)
          </button>
        ) : null}
      </span>
      {errors.length ? (
        <ul className="m-0 list-none p-0" aria-label="QA errors">
          {errors.map((f) => (
            <FindingCard key={f.id} finding={f} canDismiss={false} busy={busy} onDismiss={onDismiss} />
          ))}
        </ul>
      ) : null}
      {others.length ? (
        <ul className="m-0 list-none p-0" aria-label="QA warnings">
          {others.map((f) => (
            <FindingCard
              key={f.id}
              finding={f}
              dismissal={dismissals.get(f.id)}
              canDismiss={detail.actions.can_dismiss_warnings}
              busy={busy}
              onDismiss={onDismiss}
            />
          ))}
        </ul>
      ) : null}
    </section>
  );
}
