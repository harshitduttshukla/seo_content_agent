"use client";

import type { BundleDemand, ClaimOption, OutlineSection, OutlineV3 } from "@/lib/api-types";

export interface PageOption {
  page_id: string;
  url: string;
  title: string | null;
}

const field =
  "w-full rounded-[5px] border border-[var(--line)] bg-white px-[8px] py-[5px] text-[12.8px] text-[#12171A] focus-visible:outline-2 focus-visible:outline-[var(--teal)]";
const small =
  "rounded-[4px] border border-[var(--line)] bg-white px-[6px] py-[1px] text-[11px] text-[#5C666C] hover:text-[#12171A] focus-visible:outline-2 focus-visible:outline-[var(--teal)] disabled:opacity-40";

export function wordCount(text: string): number {
  return text.trim() ? text.trim().split(/\s+/).length : 0;
}

/** Renumber orders 1..n in list order: the server requires it. */
function renumber(sections: OutlineSection[]): OutlineSection[] {
  return sections.map((section, index) => ({ ...section, order: index + 1 }));
}

function nextSectionId(sections: OutlineSection[]): string {
  const used = new Set(sections.map((s) => s.section_id));
  let n = sections.length + 1;
  while (used.has(`s${n}`)) n += 1;
  return `s${n}`;
}

export function blankOutline(title: string, mode: OutlineV3["primary_mode"], promptId: string | null): OutlineV3 {
  return {
    schema_version: "v3.outline.v1",
    primary_mode: mode,
    title: title || "Untitled",
    prompt_target_id: mode === "prompt" ? promptId : null,
    direct_answer: mode === "prompt" ? "" : null,
    sections: [emptySection("s1", 1)],
  };
}

function emptySection(id: string, order: number): OutlineSection {
  return {
    section_id: id,
    order,
    heading: "",
    purpose: "",
    claim_ids: [],
    target_demand_id: null,
    planned_internal_links: [],
    citable_statement: null,
    notes: "",
    needs_claim: [],
  };
}

export function OutlineEditor({
  outline,
  onChange,
  claims,
  demand,
  pages,
  disabled,
}: {
  outline: OutlineV3;
  onChange: (next: OutlineV3) => void;
  claims: ClaimOption[];
  demand: BundleDemand[];
  pages: PageOption[];
  disabled: boolean;
}) {
  const prompt = outline.primary_mode === "prompt";
  const claimById = new Map(claims.map((claim) => [claim.id, claim]));
  const setSections = (sections: OutlineSection[]) => onChange({ ...outline, sections: renumber(sections) });
  const update = (index: number, patch: Partial<OutlineSection>) =>
    setSections(outline.sections.map((s, i) => (i === index ? { ...s, ...patch } : s)));
  const move = (index: number, delta: -1 | 1) => {
    const next = [...outline.sections];
    [next[index], next[index + delta]] = [next[index + delta], next[index]];
    setSections(next);
  };
  const answerWords = wordCount(outline.direct_answer ?? "");

  return (
    <div className="flex flex-col gap-[12px]">
      <label className="block text-[11.5px] text-[var(--ink3)]">
        Title
        <input className={field} value={outline.title} disabled={disabled}
          onChange={(e) => onChange({ ...outline, title: e.target.value })} />
      </label>

      {prompt ? (
        <div className="rounded-[6px] border border-[var(--teal-br)] bg-[var(--teal-bg)] p-[10px]">
          <label className="block text-[11.5px] text-[var(--teal)]">
            Prompt target
            <select className={field} aria-label="Prompt target" disabled={disabled}
              value={outline.prompt_target_id ?? ""}
              onChange={(e) => onChange({ ...outline, prompt_target_id: e.target.value || null })}>
              <option value="">Choose a prompt</option>
              {demand.filter((d) => d.type === "prompt").map((d) => (
                <option key={d.id} value={d.id}>{d.text}</option>
              ))}
            </select>
          </label>
          <label className="mt-[8px] block text-[11.5px] text-[var(--teal)]">
            Direct answer · under 60 words
            <textarea className={field} rows={2} aria-label="Direct answer" disabled={disabled}
              value={outline.direct_answer ?? ""}
              onChange={(e) => onChange({ ...outline, direct_answer: e.target.value })} />
          </label>
          <span className={`text-[11px] ${answerWords > 60 ? "text-[var(--coral)]" : "text-[var(--ink3)]"}`}>
            {answerWords} / 60 words
          </span>
        </div>
      ) : null}

      {outline.sections.map((section, index) => {
        const label = `Section ${index + 1}`;
        const unused = claims.filter((c) => !section.claim_ids.includes(c.id));
        const unlinked = pages.filter((p) => !section.planned_internal_links.some((l) => l.page_id === p.page_id));
        return (
          <section key={section.section_id} aria-label={label}
            className="rounded-[6px] border border-[var(--line)] bg-white p-[10px]">
            <div className="mb-[6px] flex items-center gap-[5px]">
              <span className="font-mono text-[11px] text-[var(--ink3)]">{section.section_id}</span>
              <span className="ml-auto flex gap-[3px]">
                <button type="button" className={small} aria-label={`Move ${label} up`}
                  disabled={disabled || index === 0} onClick={() => move(index, -1)}>↑</button>
                <button type="button" className={small} aria-label={`Move ${label} down`}
                  disabled={disabled || index === outline.sections.length - 1} onClick={() => move(index, 1)}>↓</button>
                <button type="button" className={small} aria-label={`Remove ${label}`}
                  disabled={disabled || outline.sections.length === 1}
                  onClick={() => setSections(outline.sections.filter((_, i) => i !== index))}>Remove</button>
              </span>
            </div>
            <input className={`${field} font-medium`} aria-label={`${label} heading`} disabled={disabled}
              placeholder={prompt ? "Question-led heading?" : "Heading"} value={section.heading}
              onChange={(e) => update(index, { heading: e.target.value })} />
            <input className={`${field} mt-[6px]`} aria-label={`${label} purpose`} disabled={disabled}
              placeholder="Purpose / argument" value={section.purpose}
              onChange={(e) => update(index, { purpose: e.target.value })} />

            <div className="mt-[7px] flex flex-wrap items-center gap-[5px]">
              {section.claim_ids.map((id) => (
                <span key={id} className={`chip ${claimById.has(id) ? "r" : "c"}`} title={claimById.get(id)?.text ?? "Not an approved, current claim"}>
                  {claimById.get(id)?.text.slice(0, 48) ?? `unknown ${id.slice(0, 8)}`}
                  <button type="button" aria-label={`Remove claim ${claimById.get(id)?.text ?? id} from ${label}`}
                    disabled={disabled} className="ml-[3px]"
                    onClick={() => update(index, { claim_ids: section.claim_ids.filter((c) => c !== id) })}>×</button>
                </span>
              ))}
              <select className="rounded-[5px] border border-[var(--line)] bg-white px-[6px] py-[2px] text-[11.5px]"
                aria-label={`Attach claim to ${label}`} disabled={disabled || !unused.length} value=""
                onChange={(e) => e.target.value && update(index, { claim_ids: [...section.claim_ids, e.target.value] })}>
                <option value="">{unused.length ? "+ claim" : "No more approved claims"}</option>
                {unused.map((c) => (
                  <option key={c.id} value={c.id}>{c.text.slice(0, 80)} · v{c.version}</option>
                ))}
              </select>
            </div>

            <select className={`${field} mt-[6px]`} aria-label={`${label} target demand`} disabled={disabled}
              value={section.target_demand_id ?? ""}
              onChange={(e) => update(index, { target_demand_id: e.target.value || null })}>
              <option value="">No target demand</option>
              {demand.map((d) => (
                <option key={d.id} value={d.id}>{d.text} · {d.role}</option>
              ))}
            </select>

            <div className="mt-[6px] flex flex-wrap items-center gap-[5px]">
              {section.planned_internal_links.map((link) => (
                <span key={link.page_id} className="chip o">
                  → {link.url}
                  <button type="button" aria-label={`Remove link ${link.url} from ${label}`} disabled={disabled} className="ml-[3px]"
                    onClick={() => update(index, { planned_internal_links: section.planned_internal_links.filter((l) => l.page_id !== link.page_id) })}>×</button>
                </span>
              ))}
              <select className="rounded-[5px] border border-[var(--line)] bg-white px-[6px] py-[2px] text-[11.5px]"
                aria-label={`Add internal link to ${label}`} disabled={disabled || !unlinked.length} value=""
                onChange={(e) => {
                  const page = pages.find((p) => p.page_id === e.target.value);
                  if (page) update(index, { planned_internal_links: [...section.planned_internal_links, { page_id: page.page_id, url: page.url, anchor_text: "" }] });
                }}>
                <option value="">{unlinked.length ? "+ internal link" : "No stored pages to link"}</option>
                {unlinked.map((p) => (
                  <option key={p.page_id} value={p.page_id}>{p.title || p.url}</option>
                ))}
              </select>
            </div>

            <textarea className={`${field} mt-[6px]`} rows={2} aria-label={`${label} citable statement`} disabled={disabled}
              placeholder={prompt ? "Citable statement (required)" : "Citable statement (optional)"}
              value={section.citable_statement ?? ""}
              onChange={(e) => update(index, { citable_statement: e.target.value || null })} />
            <textarea className={`${field} mt-[6px]`} rows={2} aria-label={`${label} notes`} disabled={disabled}
              placeholder="Notes" value={section.notes}
              onChange={(e) => update(index, { notes: e.target.value })} />
            {section.needs_claim.length ? (
              <p className="mt-[6px] text-[11.5px] text-[var(--coral)]">Needs claim: {section.needs_claim.join("; ")}</p>
            ) : null}
          </section>
        );
      })}

      <button type="button" className={`${small} self-start px-[10px] py-[4px] text-[12px]`} disabled={disabled}
        onClick={() => setSections([...outline.sections, emptySection(nextSectionId(outline.sections), outline.sections.length + 1)])}>
        + Add section
      </button>
    </div>
  );
}
