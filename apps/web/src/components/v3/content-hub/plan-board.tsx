"use client";

import { useCallback, useEffect, useRef, useState, type DragEvent } from "react";

import type { BoardCard, BoardColumnKey, BoardColumnView, BoardFilters, ContentHubBoard } from "@/lib/api-types";
import { V3API, type V3Scope } from "@/lib/v3-api";

import { BoardCardView, type CardActions } from "./board-card";

const TONE_HEADER: Record<BoardColumnView["tone"], string> = {
  rest: "bg-[var(--rest-bg)] text-[#5C666C]",
  system: "bg-[var(--teal-bg)] text-[var(--teal)]",
  human: "bg-[var(--coral-bg)] text-[var(--coral)]",
};

type DragSource = { cardId: string; column: BoardColumnKey; state: string };

/**
 * Whether a drag may land on `target`: Backlog ↔ Planned, and within Planned (§5.1).
 * A bundled card sits in Planned but cannot go back to Backlog (§5.2).
 */
export function canDrop(source: Pick<DragSource, "column" | "state">, target: BoardColumnKey): boolean {
  if (source.column === "backlog") return target === "planned";
  if (source.column === "planned") return target === "planned" || (target === "backlog" && source.state === "planned");
  return false;
}

function withCards(board: ContentHubBoard, update: (key: BoardColumnKey, cards: BoardCard[]) => BoardCard[]) {
  return {
    ...board,
    columns: board.columns.map((column) => {
      const cards = update(column.key, column.cards);
      return { ...column, cards, count: cards.length };
    }),
  };
}

function plannedIds(board: ContentHubBoard): string[] {
  return board.columns.find((column) => column.key === "planned")?.cards.map((card) => card.id) ?? [];
}

function errorMessage(error: unknown, fallback: string): string {
  return error instanceof Error && error.message ? error.message : fallback;
}

export function PlanBoard({ scope }: { scope: V3Scope }) {
  const [board, setBoard] = useState<ContentHubBoard | null>(null);
  const [filters, setFilters] = useState<BoardFilters>({});
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [mutationError, setMutationError] = useState<string | null>(null);
  const [busyCardId, setBusyCardId] = useState<string | null>(null);
  const [locking, setLocking] = useState(false);
  const [dragging, setDragging] = useState<DragSource | null>(null);
  const requestSeq = useRef(0);

  const load = useCallback(async () => {
    const seq = ++requestSeq.current;
    try {
      const next = await V3API.contentHub.board(scope, filters);
      if (seq !== requestSeq.current) return;
      setBoard(next);
      setLoadError(null);
    } catch (error) {
      if (seq !== requestSeq.current) return;
      setLoadError(errorMessage(error, "The board could not be loaded."));
    } finally {
      if (seq === requestSeq.current) setLoading(false);
    }
  }, [scope, filters]);

  useEffect(() => {
    const seq = ++requestSeq.current;
    V3API.contentHub.board(scope, filters).then(
      (next) => {
        if (seq !== requestSeq.current) return;
        setBoard(next);
        setLoadError(null);
        setLoading(false);
      },
      (error: unknown) => {
        if (seq !== requestSeq.current) return;
        setLoadError(errorMessage(error, "The board could not be loaded."));
        setLoading(false);
      },
    );
  }, [scope, filters]);

  const filtered = Object.values(filters).some(Boolean);

  const updateFilters = (update: (current: BoardFilters) => BoardFilters) => {
    setLoading(true);
    setFilters(update);
  };

  /** Optimistic: show the change, persist it, roll back and say so on failure. */
  const mutate = useCallback(
    async (cardId: string, optimistic: ContentHubBoard, persist: () => Promise<unknown>, failure: string) => {
      if (!board) return;
      const previous = board;
      setMutationError(null);
      setBusyCardId(cardId);
      setBoard(optimistic);
      try {
        await persist();
        await load();
      } catch (error) {
        setBoard(previous);
        setMutationError(errorMessage(error, failure));
      } finally {
        setBusyCardId(null);
      }
    },
    [board, load],
  );

  const move = useCallback(
    (card: BoardCard, target: "backlog" | "planned", beforeId: string | null = null) => {
      if (!board) return;
      const moved: BoardCard = { ...card, column: target, state: target };
      const optimistic = withCards(board, (key, cards) => {
        const rest = cards.filter((item) => item.id !== card.id);
        if (key !== target) return rest;
        const index = beforeId ? rest.findIndex((item) => item.id === beforeId) : -1;
        return index < 0 ? [...rest, moved] : [...rest.slice(0, index), moved, ...rest.slice(index)];
      });
      void mutate(
        card.id,
        optimistic,
        () => V3API.contentHub.moveCard(scope, card.id, target, card.revision),
        target === "planned" ? "The card could not be planned." : "The card could not be moved to Backlog.",
      );
    },
    [board, mutate, scope],
  );

  const reorder = useCallback(
    (cardId: string, order: string[]) => {
      if (!board) return;
      const byId = new Map(board.columns.find((c) => c.key === "planned")?.cards.map((c) => [c.id, c]));
      const optimistic = withCards(board, (key, cards) =>
        key === "planned" ? order.map((id) => byId.get(id)).filter((c): c is BoardCard => Boolean(c)) : cards,
      );
      void mutate(cardId, optimistic, () => V3API.contentHub.reorderPlanned(scope, order), "The Planned order could not be saved.");
    },
    [board, mutate, scope],
  );

  const shift = (cardId: string, delta: -1 | 1) => {
    if (!board) return;
    const order = plannedIds(board);
    const from = order.indexOf(cardId);
    const to = from + delta;
    if (from < 0 || to < 0 || to >= order.length) return;
    [order[from], order[to]] = [order[to], order[from]];
    reorder(cardId, order);
  };

  const dropOn = (target: BoardColumnKey, beforeId: string | null) => {
    const source = dragging;
    setDragging(null);
    if (!board || !source || !canDrop(source, target)) return;
    const card = board.columns.flatMap((column) => column.cards).find((item) => item.id === source.cardId);
    if (!card) return;
    if (source.column === "planned" && target === "planned") {
      if (filtered || beforeId === card.id) return;
      const order = plannedIds(board).filter((id) => id !== card.id);
      const index = beforeId ? order.indexOf(beforeId) : -1;
      order.splice(index < 0 ? order.length : index, 0, card.id);
      reorder(card.id, order);
    } else {
      move(card, target as "backlog" | "planned", target === "planned" ? beforeId : null);
    }
  };

  const allowDrop = (target: BoardColumnKey) => (event: DragEvent<HTMLElement>) => {
    if (!dragging || !canDrop(dragging, target)) return; // no preventDefault → no drop
    if (dragging.column === "planned" && target === "planned" && filtered) return;
    event.preventDefault();
    event.dataTransfer.dropEffect = "move";
  };

  const lockPlan = async () => {
    setLocking(true);
    setMutationError(null);
    try {
      await V3API.planLock.lock(scope);
      await load();
    } catch (error) {
      setMutationError(errorMessage(error, "The plan could not be locked."));
    } finally {
      setLocking(false);
    }
  };

  if (loadError && !board) {
    return (
      <div role="alert" className="flex items-center gap-[10px] text-sm text-[var(--coral)]">
        {loadError}
        <button type="button" onClick={() => {
            setLoading(true);
            void load();
          }} className="rounded-[5px] border border-[var(--line)] bg-white px-[9px] py-[3px] text-[12px] text-[#12171A]">
          Retry
        </button>
      </div>
    );
  }

  if (!board) {
    return <p aria-label="Loading the plan board" className="h-[260px] animate-pulse rounded-[8px] bg-[#EDF0EF]" />;
  }

  const planned = board.columns.find((column) => column.key === "planned");
  const newCount = planned?.cards.filter((card) => card.is_new_after_plan_lock).length ?? 0;
  const options = board.filter_options;

  return (
    <div>
      {board.plan_locked_at === null ? (
        <div className="mb-[15px] flex flex-wrap items-center gap-[12px] rounded-[8px] border border-[var(--coral-br)] bg-[var(--coral-bg)] px-[15px] py-[11px] text-[13px] text-[var(--coral)]">
          <b className="font-medium">H2 · plan is unlocked.</b>
          <span>
            {planned?.count ?? 0} card{planned?.count === 1 ? "" : "s"} in Planned.
          </span>
          <button
            type="button"
            onClick={() => void lockPlan()}
            disabled={locking}
            className="ml-auto rounded-[5px] border border-[var(--line)] bg-white px-[10px] py-[4px] text-[12.5px] text-[#12171A] disabled:opacity-50"
          >
            {locking ? "Locking…" : "Lock plan"}
          </button>
        </div>
      ) : (
        <div className="mb-[15px] flex flex-wrap items-center gap-[12px] rounded-[8px] border border-[var(--rest-br)] bg-[var(--rest-bg)] px-[15px] py-[11px] text-[13px] text-[#5C666C]">
          <b className="font-medium">H2 · plan locked {new Date(board.plan_locked_at).toLocaleString("en-GB")}.</b>
          <span>
            {newCount} card{newCount === 1 ? "" : "s"} added to Planned since, marked new.
          </span>
        </div>
      )}

      <div className="mb-[13px] flex flex-wrap items-center gap-[8px]" aria-busy={loading || undefined}>
        <FilterSelect label="Area" value={filters.area_id} onChange={(v) => updateFilters((f) => ({ ...f, area_id: v }))}
          options={options.areas.map((ref) => [ref.id, ref.name])} />
        <FilterSelect label="Kind" value={filters.kind} onChange={(v) => updateFilters((f) => ({ ...f, kind: v }))}
          options={options.kinds.map((kind) => [kind, kind])} />
        <FilterSelect label="Owner" value={filters.owner_id} onChange={(v) => updateFilters((f) => ({ ...f, owner_id: v }))}
          options={options.owners.map((ref) => [ref.id, ref.name])} />
        <FilterSelect label="Argument" value={filters.argument_id} onChange={(v) => updateFilters((f) => ({ ...f, argument_id: v }))}
          options={options.arguments.map((ref) => [ref.id, ref.name])} />
        <FilterSelect label="Market" value={filters.market} onChange={(v) => updateFilters((f) => ({ ...f, market: v }))}
          options={options.markets.map((market) => [market, market])} />
        {filtered ? (
          <button type="button" onClick={() => updateFilters(() => ({}))} className="text-[12px] text-[#5C666C] underline">
            Clear filters
          </button>
        ) : null}
        {loading ? <span className="text-[11.5px] text-[var(--ink3)]">Loading…</span> : null}
        {filtered ? <span className="text-[11.5px] text-[var(--ink3)]">Clear filters to reorder Planned.</span> : null}
      </div>

      {mutationError ? (
        <p role="alert" className="mb-[10px] text-[12.6px] text-[var(--coral)]">
          {mutationError}
        </p>
      ) : null}
      {loadError ? (
        <p role="alert" className="mb-[10px] text-[12.6px] text-[var(--coral)]">
          {loadError}
        </p>
      ) : null}

      {board.total_count === 0 ? (
        <p className="mb-[10px] text-[13px] text-[#5C666C]">
          {filtered ? "No cards match these filters." : "No content cards yet. Cards appear here when Strategy plans demand or a site import runs."}
        </p>
      ) : null}

      <div className="overflow-x-auto pb-[6px]">
        <div className="grid min-w-[1230px] grid-cols-[repeat(7,minmax(172px,1fr))] gap-[9px]">
          {board.columns.map((column) => {
            const droppable = dragging !== null && canDrop(dragging, column.key);
            return (
              <section
                key={column.key}
                aria-label={`${column.label} column`}
                data-testid={`column-${column.key}`}
                data-drop-disabled={dragging !== null && !droppable ? "true" : undefined}
                onDragOver={allowDrop(column.key)}
                onDrop={(event) => {
                  event.preventDefault();
                  dropOn(column.key, null);
                }}
                className={`flex flex-col rounded-[8px] border bg-[#F5F7F6] ${
                  droppable ? "border-[var(--teal)]" : "border-[var(--line)]"
                } ${dragging !== null && !droppable ? "opacity-60" : ""}`}
              >
                <h3 className={`flex items-center gap-[7px] rounded-t-[8px] border-b border-[var(--line)] px-[11px] py-[9px] text-[12.5px] font-medium ${TONE_HEADER[column.tone]}`}>
                  {column.label}
                  <span className="ml-auto font-mono text-[11.5px]" data-testid={`count-${column.key}`}>
                    {column.count}
                  </span>
                </h3>
                <div className="flex flex-col gap-[8px] p-[9px]">
                  {column.cards.length === 0 ? <p className="px-[2px] text-[11.5px] text-[var(--ink3)]">No cards</p> : null}
                  {column.cards.map((card, index) => {
                    const movable = column.key === "backlog" || column.key === "planned";
                    const actions: CardActions = {};
                    if (column.key === "backlog") actions.onPlan = () => move(card, "planned");
                    if (column.key === "planned" && card.state === "planned") actions.onUnplan = () => move(card, "backlog");
                    if (column.key === "planned" && !filtered) {
                      if (index > 0) actions.onMoveUp = () => shift(card.id, -1);
                      if (index < column.cards.length - 1) actions.onMoveDown = () => shift(card.id, 1);
                    }
                    return (
                      <BoardCardView
                        key={card.id}
                        card={card}
                        href={`/projects/${scope.projectId}/v3/content-hub/${card.id}`}
                        busy={busyCardId === card.id}
                        draggable={movable && busyCardId === null}
                        actions={busyCardId === null ? actions : {}}
                        onDragStart={(event) => {
                          event.dataTransfer.effectAllowed = "move";
                          event.dataTransfer.setData("text/plain", card.id);
                          setDragging({ cardId: card.id, column: column.key, state: card.state });
                        }}
                        onDragEnd={() => setDragging(null)}
                        onDragOver={column.key === "planned" ? allowDrop("planned") : undefined}
                        onDrop={
                          column.key === "planned"
                            ? (event) => {
                                event.preventDefault();
                                event.stopPropagation();
                                dropOn("planned", card.id);
                              }
                            : undefined
                        }
                      />
                    );
                  })}
                </div>
              </section>
            );
          })}
        </div>
      </div>
    </div>
  );
}

function FilterSelect({
  label,
  value,
  options,
  onChange,
}: {
  label: string;
  value: string | undefined;
  options: [string, string][];
  onChange: (value: string | undefined) => void;
}) {
  return (
    <label className="flex items-center">
      <span className="sr-only">{label}</span>
      <select
        aria-label={label}
        value={value ?? ""}
        onChange={(event) => onChange(event.target.value || undefined)}
        className="rounded-[5px] border border-[var(--line)] bg-white px-[8px] py-[4px] text-[12.5px] text-[#12171A] focus-visible:outline-2 focus-visible:outline-[var(--teal)]"
      >
        <option value="">{label}: all</option>
        {options.map(([optionValue, text]) => (
          <option key={optionValue} value={optionValue}>
            {text}
          </option>
        ))}
      </select>
    </label>
  );
}
