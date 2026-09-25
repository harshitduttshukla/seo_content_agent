"use client";

import { useState } from "react";

import type { CardDetail, G1Reason, G1Status, GateDecision } from "@/lib/api-types";

const btn =
  "rounded-[5px] border border-[var(--line)] bg-white px-[10px] py-[4px] text-[12.5px] text-[#12171A] hover:bg-[#F0F2F1] focus-visible:outline-2 focus-visible:outline-[var(--teal)] disabled:opacity-50";
const btnPrimary =
  "rounded-[5px] border border-[var(--teal)] bg-[var(--teal)] px-[10px] py-[4px] text-[12.5px] text-white focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--teal)] disabled:opacity-50";
const btnDanger =
  "rounded-[5px] border border-[var(--coral)] bg-white px-[10px] py-[4px] text-[12.5px] text-[var(--coral)] hover:bg-[#FBEFEC] focus-visible:outline-2 focus-visible:outline-[var(--coral)] disabled:opacity-50";

export const G1_STATUS_LABEL: Record<G1Status, string> = {
  not_ready: "Outline",
  awaiting_review: "G1 review",
  sent_back: "Sent back",
  approved: "G1 approved",
};
const STATUS_CHIP: Record<G1Status, string> = {
  not_ready: "r",
  awaiting_review: "c",
  sent_back: "c",
  approved: "t",
};
const REASONS: { value: G1Reason; label: string }[] = [
  { value: "writer", label: "writer" },
  { value: "claim", label: "claim" },
  { value: "tone_rule", label: "tone rule" },
  { value: "plan", label: "plan" },
];
export const REASON_LABEL: Record<string, string> = { ...Object.fromEntries(REASONS.map((r) => [r.value, r.label])), qa_rule: "QA rule" };

export function formatWhen(iso: string): string {
  return new Date(iso).toLocaleString("en-GB", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });
}

export function decisionLine(decision: GateDecision): string {
  const who = decision.reviewer_name ?? "a reviewer";
  const what = decision.action === "approve" ? "approved" : "sent back";
  return `${decision.gate} ${what} by ${who} · ${formatWhen(decision.decided_at)} · revision ${decision.card_revision}`;
}

export function G1StatusChip({ status }: { status: G1Status }) {
  return (
    <span className={`chip ${STATUS_CHIP[status]}`} data-testid="g1-status">
      {G1_STATUS_LABEL[status]}
    </span>
  );
}

interface G1ReviewPanelProps {
  detail: CardDetail;
  busy: boolean;
  onApprove: () => Promise<boolean>;
  onSendBack: (reason: G1Reason, feedback: string) => Promise<boolean>;
}

/** The G1 gate in the right-hand "Checks and gate" pane (handoff §6.1). */
export function G1ReviewPanel({ detail, busy, onApprove, onSendBack }: G1ReviewPanelProps) {
  const { review, card } = detail;
  const [confirming, setConfirming] = useState(false);
  const [sending, setSending] = useState(false);
  const [reason, setReason] = useState<G1Reason>("writer");
  const [feedback, setFeedback] = useState("");
  const inGate = card.state === "outlined";
  const last = review.last_decision;

  return (
    <section aria-label="G1 review" className="mt-[10px] border-t border-[var(--line2)] pt-[10px] text-[12.6px]">
      <div className="mb-[6px] flex items-center gap-[8px]">
        <h4 className="m-0 text-[12.8px] font-medium">G1 · outline review</h4>
        <G1StatusChip status={review.status} />
      </div>

      {last ? (
        <div className="mb-[8px] rounded-[6px] bg-[#F4F6F5] px-[9px] py-[7px]" data-testid="g1-last-decision">
          <div className="text-[11.5px] text-[var(--ink3)]">{decisionLine(last)}</div>
          {last.action === "send_back" ? (
            <>
              <div className="mt-[3px] text-[11.5px] text-[var(--ink3)]">About · {last.reason ? REASON_LABEL[last.reason] : "—"}</div>
              <p className="m-[3px_0_0] whitespace-pre-wrap">{last.feedback}</p>
            </>
          ) : null}
        </div>
      ) : null}

      {review.status === "approved" ? (
        <p className="m-0 text-[var(--ink3)]">The draft may not introduce a claim absent from the approved outline.</p>
      ) : !inGate ? (
        <p className="m-0 text-[var(--ink3)]">Save an outline to send the card to G1.</p>
      ) : !review.can_review ? (
        <p className="m-0 text-[var(--ink3)]">
          {review.reviewers_restricted
            ? "Only the named G1 reviewers for this project can decide."
            : "You can see this review but not decide it; a reviewer approves or sends back."}
        </p>
      ) : (
        <>
          {!review.ready ? (
            <p className="m-[0_0_8px] text-[var(--coral)]">Approve enables when every check above passes.</p>
          ) : null}
          {confirming ? (
            <div role="group" aria-label="Confirm G1 approval" className="mb-[8px] rounded-[6px] border border-[var(--line)] p-[8px]">
              <p className="m-[0_0_6px]">Approve this outline at G1? Drafting starts from it and it can no longer be edited.</p>
              <span className="flex gap-[6px]">
                <button
                  type="button"
                  className={btnPrimary}
                  disabled={busy}
                  onClick={async () => {
                    if (await onApprove()) setConfirming(false);
                  }}
                >
                  {busy ? "Approving…" : "Confirm approval"}
                </button>
                <button type="button" className={btn} disabled={busy} onClick={() => setConfirming(false)}>
                  Cancel
                </button>
              </span>
            </div>
          ) : (
            <span className="mb-[8px] flex gap-[6px]">
              <button
                type="button"
                className={btnPrimary}
                disabled={!detail.actions.can_review_g1 || busy}
                onClick={() => {
                  setConfirming(true);
                  setSending(false);
                }}
              >
                Approve
              </button>
              <button
                type="button"
                className={btnDanger}
                disabled={busy}
                aria-expanded={sending}
                onClick={() => {
                  setSending((open) => !open);
                  setConfirming(false);
                }}
              >
                Send back
              </button>
            </span>
          )}
          {sending ? (
            <form
              aria-label="Send back to outline"
              onSubmit={async (event) => {
                event.preventDefault();
                if (!feedback.trim()) return;
                if (await onSendBack(reason, feedback.trim())) {
                  setFeedback("");
                  setSending(false);
                }
              }}
            >
              <label className="mb-[3px] block text-[11.5px] text-[var(--ink3)]" htmlFor="g1-reason">This is about</label>
              <select
                id="g1-reason"
                className="mb-[8px] w-full rounded-[5px] border border-[var(--line)] bg-white px-[6px] py-[4px]"
                value={reason}
                onChange={(event) => setReason(event.target.value as G1Reason)}
              >
                {REASONS.map((r) => (
                  <option key={r.value} value={r.value}>{r.label}</option>
                ))}
              </select>
              <label className="mb-[3px] block text-[11.5px] text-[var(--ink3)]" htmlFor="g1-feedback">Reason · required</label>
              <textarea
                id="g1-feedback"
                rows={3}
                required
                maxLength={4000}
                className="mb-[8px] w-full rounded-[5px] border border-[var(--line)] px-[6px] py-[4px]"
                placeholder="Section two needs the duty claim; lead with the calculation."
                value={feedback}
                onChange={(event) => setFeedback(event.target.value)}
              />
              <button type="submit" className={btnPrimary} disabled={busy || !feedback.trim()}>
                {busy ? "Sending…" : "Send back to outline"}
              </button>
            </form>
          ) : null}
        </>
      )}

      {review.history.length > 1 ? (
        <details className="mt-[8px] text-[11.5px] text-[var(--ink3)]">
          <summary>Activity · {review.history.length} decisions</summary>
          <ul className="m-[4px_0_0] pl-[16px]">
            {review.history.map((d) => (
              <li key={d.id}>{decisionLine(d)}</li>
            ))}
          </ul>
        </details>
      ) : null}
    </section>
  );
}
