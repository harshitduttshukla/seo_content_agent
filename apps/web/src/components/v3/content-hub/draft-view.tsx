"use client";

import type { ReactNode } from "react";

import type { ClaimOption, DraftRunStatus, StoredDraft } from "@/lib/api-types";

import { formatWhen } from "./g1-review";

// Same grammar as app/domains/content_cards/draft.py.
const TOKEN = /\[CLM:([0-9a-fA-F-]{36})\]|\[NEEDS-CLAIM:\s*([^\]]+?)\s*\]|\[([^\]]*)\]\((\S+?)\)/g;

/** The short claim label the canvas shows (CLM-<first id segment>). */
export function claimLabel(id: string, row?: string): string {
  return row === "pitch" ? "CLM-000" : `CLM-${id.split("-")[0].toUpperCase()}`;
}

function inline(text: string, claims: Map<string, ClaimOption>, key: string): ReactNode[] {
  const out: ReactNode[] = [];
  let last = 0;
  let n = 0;
  for (const match of text.matchAll(TOKEN)) {
    const index = match.index ?? 0;
    if (index > last) out.push(text.slice(last, index));
    const [, claimId, need, anchor, url] = match;
    const k = `${key}-${n++}`;
    if (claimId) {
      const claim = claims.get(claimId);
      out.push(
        <span
          key={k}
          className="mx-[2px] rounded-[4px] bg-[#E6F2F1] px-[4px] font-mono text-[11px] text-[var(--teal)]"
          title={claim ? `${claim.text} · v${claim.version} approved` : "Claim not in the current options"}
          data-testid="claim-marker"
        >
          [{claimLabel(claimId, claim?.row)}]
        </span>,
      );
    } else if (need) {
      out.push(
        <span
          key={k}
          className="rounded-[4px] bg-[#FBEFEC] px-[4px] font-mono text-[11px] text-[var(--coral)]"
          title="No approved claim supports this yet; resolve it in Strategy"
          data-testid="needs-claim-marker"
        >
          [NEEDS-CLAIM: {need}]
        </span>,
      );
    } else if (/^https?:\/\//i.test(url)) {
      out.push(
        <a key={k} href={url} className="text-[var(--teal)] underline" rel="noreferrer">
          {anchor || url}
        </a>,
      );
    } else {
      out.push(match[0]); // the server only stores http(s) page links; never render others
    }
    last = index + match[0].length;
  }
  if (last < text.length) out.push(text.slice(last));
  return out;
}

function Body({ body, claims, id }: { body: string; claims: Map<string, ClaimOption>; id: string }) {
  const blocks = body.split(/\n\s*\n/).filter((b) => b.trim());
  return (
    <>
      {blocks.map((block, i) => {
        const lines = block.split("\n");
        const key = `${id}-${i}`;
        if (/^#{3,6}\s/.test(block)) {
          return (
            <h5 key={key} className="m-[10px_0_4px] text-[13px] font-medium">
              {inline(block.replace(/^#{3,6}\s+/, ""), claims, key)}
            </h5>
          );
        }
        if (lines.every((line) => /^\s*[-*]\s/.test(line))) {
          return (
            <ul key={key} className="m-[0_0_8px] pl-[18px]">
              {lines.map((line, j) => (
                <li key={j}>{inline(line.replace(/^\s*[-*]\s+/, ""), claims, `${key}-${j}`)}</li>
              ))}
            </ul>
          );
        }
        return (
          <p key={key} className="m-[0_0_8px] leading-[1.55]">
            {inline(block, claims, key)}
          </p>
        );
      })}
    </>
  );
}

interface DraftViewProps {
  draft: StoredDraft | null;
  unreadable: boolean;
  lastRun: DraftRunStatus | null;
  claims: ClaimOption[];
}

/** The Draft tab: the stored draft with visible claim markers (handoff §6.1). */
export function DraftView({ draft, unreadable, lastRun, claims }: DraftViewProps) {
  const byId = new Map(claims.map((c) => [c.id, c]));
  const failedSince = lastRun && !lastRun.stored && (!draft || lastRun.created_at > draft.generated_at);
  return (
    <div className="text-[13px]">
      {unreadable ? (
        <p className="mb-[10px] text-[12.6px] text-[var(--coral)]">The stored draft no longer matches the V3 draft schema.</p>
      ) : null}
      {failedSince ? (
        <div role="status" className="mb-[10px] rounded-[6px] bg-[#FBEFEC] px-[9px] py-[7px] text-[12.4px] text-[var(--coral)]">
          The last generation ({formatWhen(lastRun.created_at)}) was not stored: {lastRun.error ?? lastRun.status}.
          {draft ? " The previous draft is unchanged." : ""}
        </div>
      ) : null}
      {!draft ? (
        <p className="m-0 text-[12.8px] text-[var(--ink3)]">No draft yet.</p>
      ) : (
        <article aria-label="Draft">
          <p className="m-[0_0_10px] text-[11.5px] text-[var(--ink3)]">
            Draft v{draft.version} · {draft.model} ({draft.prompt_version}) · {formatWhen(draft.generated_at)}. Claim markers are shown here and
            stripped on export.
          </p>
          <h2 className="m-[0_0_8px] font-serif text-[19px] font-medium">{draft.draft.title}</h2>
          {draft.draft.direct_answer ? (
            <p className="m-[0_0_10px] rounded-[6px] bg-[#F4F6F5] px-[9px] py-[7px]" data-testid="direct-answer">
              {draft.draft.direct_answer}
            </p>
          ) : null}
          {draft.draft.sections.map((section) => (
            <section key={section.section_id} aria-label={`Draft section ${section.order}`}>
              <h4 className="m-[14px_0_6px] text-[14.5px] font-medium">{section.heading}</h4>
              <Body body={section.body} claims={byId} id={section.section_id} />
            </section>
          ))}
          {draft.unresolved.length ? (
            <div className="mt-[12px] border-t border-[var(--line2)] pt-[8px]" data-testid="unresolved">
              <div className="text-[11.5px] text-[var(--coral)]">
                {draft.unresolved.length} unresolved claim need(s) · QA will not pass until they are approved claims
              </div>
              <ul className="m-[4px_0_0] pl-[18px] text-[12.4px]">
                {draft.unresolved.map((need, i) => (
                  <li key={i}>
                    {need.section_id}: {need.text}
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
        </article>
      )}
    </div>
  );
}
