"use client";

import { useState } from "react";

import type { CardDetail, G2Reason, G2Status } from "@/lib/api-types";

import { REASON_LABEL, decisionLine } from "./g1-review";

const btn =
  "rounded-[5px] border border-[var(--line)] bg-white px-[10px] py-[4px] text-[12.5px] text-[#12171A] hover:bg-[#F0F2F1] focus-visible:outline-2 focus-visible:outline-[var(--teal)] disabled:opacity-50";
const btnPrimary =
  "rounded-[5px] border border-[var(--teal)] bg-[var(--teal)] px-[10px] py-[4px] text-[12.5px] text-white focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--teal)] disabled:opacity-50";
const btnDanger =
  "rounded-[5px] border border-[var(--coral)] bg-white px-[10px] py-[4px] text-[12.5px] text-[var(--coral)] hover:bg-[#FBEFEC] focus-visible:outline-2 focus-visible:outline-[var(--coral)] disabled:opacity-50";

export const G2_STATUS_LABEL: Record<G2Status, string> = {
  not_ready: "G2 not ready",
  awaiting_review: "G2 review",
  sent_back: "G2 sent back",
  approved: "Approved",
};
const G2_CHIP: Record<G2Status, string> = { not_ready: "r", awaiting_review: "c", sent_back: "c", approved: "t" };
const G2_REASONS: G2Reason[] = ["writer", "claim", "tone_rule", "plan", "qa_rule"];

export function G2StatusChip({ status }: { status: G2Status }) {
  return (
    <span className={`chip ${G2_CHIP[status]}`} data-testid="g2-status">
      {G2_STATUS_LABEL[status]}
    </span>
  );
}

interface G2ReviewPanelProps {
  detail: CardDetail;
  busy: boolean;
  onApprove: () => Promise<boolean>;
  onSendBack: (reason: G2Reason, feedback: string) => Promise<boolean>;
}

/** The G2 gate in the right-hand "Checks and gate" pane (handoff §5.2, §6.1). */
export function G2ReviewPanel({ detail, busy, onApprove, onSendBack }: G2ReviewPanelProps) {
  const g2 = detail.g2;
  const [confirming, setConfirming] = useState(false);
  const [sending, setSending] = useState(false);
  const [reason, setReason] = useState<G2Reason>("writer");
  const [feedback, setFeedback] = useState("");
  if (!g2) return null;
  const visible = g2.status !== "not_ready" || detail.card.state === "qa_failed" || detail.card.state === "drafting";
  if (!visible) return null;
  const last = g2.last_decision;
  const inGate = detail.card.state === "qa_passed";

  return (
    <section aria-label="G2 review" className="mt-[10px] border-t border-[var(--line2)] pt-[10px] text-[12.6px]">
      <div className="mb-[6px] flex items-center gap-[8px]">
        <h4 className="m-0 text-[12.8px] font-medium">G2 · draft review</h4>
        <G2StatusChip status={g2.status} />
      </div>
      {last ? (
        <div className="mb-[8px] rounded-[6px] bg-[#F4F6F5] px-[9px] py-[7px]" data-testid="g2-last-decision">
          <div className="text-[11.5px] text-[var(--ink3)]">{decisionLine(last)}</div>
          {last.action === "send_back" ? (
            <>
              <div className="mt-[3px] text-[11.5px] text-[var(--ink3)]">About · {last.reason ? REASON_LABEL[last.reason] : "—"}</div>
              <p className="m-[3px_0_0] whitespace-pre-wrap">{last.feedback}</p>
            </>
          ) : null}
        </div>
      ) : null}

      {g2.status === "approved" ? (
        <p className="m-0 text-[var(--ink3)]">Approved. Publishing arrives in a later phase.</p>
      ) : !inGate ? (
        <p className="m-0 text-[var(--ink3)]">G2 opens when QA passes on the current draft.</p>
      ) : !g2.can_review ? (
        <p className="m-0 text-[var(--ink3)]">
          {g2.reviewers_restricted
            ? "Only the named G2 reviewers for this project can decide."
            : "You can see this review but not decide it; a reviewer approves or sends back."}
        </p>
      ) : (
        <>
          {g2.blockers.length ? (
            <ul className="m-[0_0_8px] pl-[16px] text-[var(--coral)]" aria-label="G2 blockers">
              {g2.blockers.map((b) => (
                <li key={b}>{b}</li>
              ))}
            </ul>
          ) : null}
          {confirming ? (
            <div role="group" aria-label="Confirm G2 approval" className="mb-[8px] rounded-[6px] border border-[var(--line)] p-[8px]">
              <p className="m-[0_0_6px]">Approve this draft at G2? It moves to Approved. Nothing is published.</p>
              <span className="flex gap-[6px]">
                <button type="button" className={btnPrimary} disabled={busy}
                  onClick={async () => { if (await onApprove()) setConfirming(false); }}>
                  {busy ? "Approving…" : "Confirm G2 approval"}
                </button>
                <button type="button" className={btn} disabled={busy} onClick={() => setConfirming(false)}>Cancel</button>
              </span>
            </div>
          ) : (
            <span className="mb-[8px] flex gap-[6px]">
              <button type="button" className={btnPrimary} disabled={!detail.actions.can_review_g2 || busy}
                onClick={() => { setConfirming(true); setSending(false); }}>
                Approve draft
              </button>
              <button type="button" className={btnDanger} disabled={busy} aria-expanded={sending}
                onClick={() => { setSending((open) => !open); setConfirming(false); }}>
                Send back to drafting
              </button>
            </span>
          )}
          {sending ? (
            <form
              aria-label="Send back to drafting"
              onSubmit={async (event) => {
                event.preventDefault();
                if (!feedback.trim()) return;
                if (await onSendBack(reason, feedback.trim())) {
                  setFeedback("");
                  setSending(false);
                }
              }}
            >
              <label className="mb-[3px] block text-[11.5px] text-[var(--ink3)]" htmlFor="g2-reason">This is about</label>
              <select id="g2-reason" className="mb-[8px] w-full rounded-[5px] border border-[var(--line)] bg-white px-[6px] py-[4px]"
                value={reason} onChange={(event) => setReason(event.target.value as G2Reason)}>
                {G2_REASONS.map((r) => (
                  <option key={r} value={r}>{REASON_LABEL[r]}</option>
                ))}
              </select>
              <label className="mb-[3px] block text-[11.5px] text-[var(--ink3)]" htmlFor="g2-feedback">Reason · required</label>
              <textarea id="g2-feedback" rows={3} required maxLength={4000}
                className="mb-[8px] w-full rounded-[5px] border border-[var(--line)] px-[6px] py-[4px]"
                placeholder="Section three reads like a case study. Two sentences, then link the webinar."
                value={feedback} onChange={(event) => setFeedback(event.target.value)} />
              <button type="submit" className={btnPrimary} disabled={busy || !feedback.trim()}>
                {busy ? "Sending…" : "Send back"}
              </button>
            </form>
          ) : null}
        </>
      )}
      {g2.history.length > 1 ? (
        <details className="mt-[8px] text-[11.5px] text-[var(--ink3)]">
          <summary>Activity · {g2.history.length} decisions</summary>
          <ul className="m-[4px_0_0] pl-[16px]">
            {g2.history.map((d) => <li key={d.id}>{decisionLine(d)}</li>)}
          </ul>
        </details>
      ) : null}
    </section>
  );
}
