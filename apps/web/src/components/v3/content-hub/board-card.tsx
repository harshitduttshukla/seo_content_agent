"use client";

import type { DragEvent } from "react";

import type { BoardCard } from "@/lib/api-types";

/** What the card may do on the board: only Backlog ↔ Planned and Planned reorder (§5.1). */
export interface CardActions {
  onPlan?: () => void;
  onUnplan?: () => void;
  onMoveUp?: () => void;
  onMoveDown?: () => void;
}

const numberFormat = new Intl.NumberFormat("en-US");

function demandLine(card: BoardCard): string | null {
  if (card.primary_demand) {
    const volume = card.primary_demand.volume;
    return volume === null
      ? card.primary_demand.text
      : `${card.primary_demand.text} · ${numberFormat.format(volume)}`;
  }
  if (card.primary_prompt) {
    const parts = ["prompt primary"];
    if (card.primary_prompt.citation_gap !== null) parts.push(`gap ${card.primary_prompt.citation_gap.toFixed(1)}`);
    if (card.primary_prompt.platform_count) {
      parts.push(`${card.primary_prompt.platform_count} platform${card.primary_prompt.platform_count === 1 ? "" : "s"}`);
    }
    return parts.join(" · ");
  }
  return null;
}

/** A second-line state label where one column holds several states. */
function stateNote(card: BoardCard): string | null {
  if (card.state === "bundled") return "bundled";
  if (card.column === "draft" || card.column === "review" || card.column === "outline") return card.state;
  if (card.state === "live" && card.published_at) {
    return `published ${new Date(card.published_at).toLocaleDateString("en-GB", { day: "2-digit", month: "short" })}`;
  }
  return null;
}

export function BoardCardView({
  card,
  draggable,
  busy,
  actions,
  onDragStart,
  onDragEnd,
  onDragOver,
  onDrop,
}: {
  card: BoardCard;
  draggable: boolean;
  busy: boolean;
  actions: CardActions;
  onDragStart?: (event: DragEvent<HTMLElement>) => void;
  onDragEnd?: () => void;
  onDragOver?: (event: DragEvent<HTMLElement>) => void;
  onDrop?: (event: DragEvent<HTMLElement>) => void;
}) {
  const meta = [card.kind, card.area?.name ?? (card.origin === "import" ? "Unmapped" : null), card.market]
    .filter(Boolean)
    .join(" · ");
  const detail = [demandLine(card), stateNote(card)].filter(Boolean).join(" · ");
  const extra = [
    card.secondary_demand_count ? `+${card.secondary_demand_count} secondary` : null,
    card.argument?.name ?? null,
    card.owner?.name ?? null,
    card.due ? `due ${card.due}` : null,
  ].filter(Boolean);

  return (
    <article
      data-testid={`board-card-${card.id}`}
      aria-busy={busy || undefined}
      draggable={draggable && !busy}
      onDragStart={onDragStart}
      onDragEnd={onDragEnd}
      onDragOver={onDragOver}
      onDrop={onDrop}
      className={`rounded-[6px] border border-[var(--line)] bg-white px-[10px] py-[9px] text-[12.4px] ${
        draggable ? "cursor-grab active:cursor-grabbing" : ""
      } ${busy ? "opacity-60" : ""}`}
    >
      <b className="mb-[4px] block text-[13px] font-medium">{card.title || card.url || "Untitled card"}</b>
      <div className="text-[11.2px] leading-[1.45] text-[var(--ink3)]">
        {meta}
        {detail ? (
          <>
            <br />
            {detail}
          </>
        ) : null}
        {extra.length ? (
          <>
            <br />
            {extra.join(" · ")}
          </>
        ) : null}
      </div>
      <div className="mt-[7px] flex flex-wrap items-center gap-[5px]">
        {card.is_new_after_plan_lock ? <span className="chip r">new</span> : null}
        {card.primary_prompt ? <span className="chip t">GEO</span> : null}
        {card.kind === "refresh" ? <span className="chip r">refresh</span> : null}
        {card.state === "qa_failed" ? <span className="chip c">QA fail</span> : null}
        {card.stale_claim_count ? <span className="chip c">stale · {card.stale_claim_count}</span> : null}
        {card.origin === "import" ? <span className="chip r">imported</span> : null}
        {card.score !== null ? <span className="chip o">{card.score.toFixed(2)}</span> : null}
        <CardButtons title={card.title} actions={actions} busy={busy} />
      </div>
    </article>
  );
}

function CardButtons({ title, actions, busy }: { title: string; actions: CardActions; busy: boolean }) {
  const buttons: { label: string; text: string; run: () => void }[] = [];
  if (actions.onPlan) buttons.push({ label: `Move ${title} to Planned`, text: "→ Planned", run: actions.onPlan });
  if (actions.onMoveUp) buttons.push({ label: `Move ${title} up`, text: "↑", run: actions.onMoveUp });
  if (actions.onMoveDown) buttons.push({ label: `Move ${title} down`, text: "↓", run: actions.onMoveDown });
  if (actions.onUnplan) buttons.push({ label: `Move ${title} to Backlog`, text: "← Backlog", run: actions.onUnplan });
  if (!buttons.length) return null;
  return (
    <span className="ml-auto flex gap-[3px]">
      {buttons.map((button) => (
        <button
          key={button.label}
          type="button"
          aria-label={button.label}
          title={button.label}
          disabled={busy}
          onClick={button.run}
          className="rounded-[4px] border border-[var(--line)] bg-white px-[5px] py-[1px] text-[10.5px] text-[#5C666C] hover:text-[#12171A] focus-visible:outline-2 focus-visible:outline-[var(--teal)] disabled:opacity-50"
        >
          {button.text}
        </button>
      ))}
    </span>
  );
}
