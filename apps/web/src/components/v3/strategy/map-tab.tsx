"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import type { MapAreaNode, MapCanvasNode, StrategyMap } from "@/lib/api-types";
import { V3API, type V3Scope } from "@/lib/v3-api";

/**
 * Read-only orientation view of the whole strategy graph (handoff §4.4).
 *
 * A nested list, not a graph visualisation: §1.2 principle 1 says flat views and
 * linked data, and the mockup's `.tree` markup is the design. Nothing here edits.
 * The only interaction is a filter carried in the URL to another tab.
 */

function plural(count: number, word: string): string {
  return `${count} ${word}${count === 1 ? "" : "s"}`;
}

/** "inherits A1, A2 · 1 override · adds A4", from inherited_from and override. */
function inheritanceSummary(canvas: MapCanvasNode): string {
  const parts: string[] = [];
  if (canvas.inherits.length > 0) parts.push(`inherits ${canvas.inherits.join(", ")}`);
  if (canvas.override_count > 0) parts.push(plural(canvas.override_count, "override"));
  if (canvas.adds.length > 0) parts.push(`adds ${canvas.adds.join(", ")}`);
  return parts.join(" · ");
}

/** Card states in workflow order (§5.2); listed as they are, never collapsed into one. */
const CARD_STATE_ORDER = [
  "backlog",
  "planned",
  "bundled",
  "outlined",
  "drafting",
  "qa_failed",
  "qa_passed",
  "approved",
  "live",
];

/** "2 planned · 1 drafting · 1 qa passed" from a per-state count map. */
function stateSummary(states: Record<string, number>): string {
  const known = CARD_STATE_ORDER.filter((state) => states[state]);
  const other = Object.keys(states).filter(
    (state) => !CARD_STATE_ORDER.includes(state) && states[state],
  );
  return [...known, ...other]
    .map((state) => `${states[state]} ${state.replace("_", " ")}`)
    .join(" · ");
}

function AreaRow({ area, projectId }: { area: MapAreaNode; projectId: string }) {
  const [open, setOpen] = useState(true); // default all expanded
  const hasChildren = area.children.length > 0;

  return (
    <li>
      <div className="n">
        {hasChildren ? (
          <button
            type="button"
            onClick={() => setOpen((current) => !current)}
            aria-expanded={open}
            aria-label={`${open ? "Collapse" : "Expand"} ${area.name}`}
            className="h-[15px] w-[15px] rounded-[3px] border border-[var(--line)] bg-white text-[10px] leading-none text-[var(--ink3)] hover:text-[#12171A]"
          >
            {open ? "−" : "+"}
          </button>
        ) : (
          <span aria-hidden="true" className="inline-block w-[15px]" />
        )}

        {/* Selecting an area is a filter, not a navigation (§4): the Demand tab
            opens with this area and status=kept applied, so the count clicked here
            is the count landed on. */}
        <Link
          href={`/projects/${projectId}/v3/demand?area=${area.id}&status=kept`}
          className="text-[#12171A] underline decoration-transparent underline-offset-2 hover:decoration-[var(--teal)] hover:text-[var(--teal)]"
        >
          {area.name}
        </Link>

        <span className="text-[11.5px] text-[var(--ink3)]">
          {area.demand_count} demand · {/* TODO: link to the Content Hub Plan board
          filtered by this area (/projects/{projectId}/v3/content-hub?area={area.id})
          once that board exists. Plain text until then. */}
          <span>{plural(area.card_count, "card")}</span>
        </span>

        {area.default_argument_pillar ? (
          <span className="chip t">{area.default_argument_pillar}</span>
        ) : null}

        {hasChildren && Object.keys(area.descendant_card_states).length > 0 ? (
          <span className="text-[11.5px] text-[var(--ink3)]">
            sub-areas: {stateSummary(area.descendant_card_states)}
          </span>
        ) : null}

        {area.content_gap ? <span className="chip c">content gap</span> : null}
      </div>

      {hasChildren && open ? (
        <ul>
          {area.children.map((child) => (
            <AreaRow key={child.id} area={child} projectId={projectId} />
          ))}
        </ul>
      ) : null}
    </li>
  );
}

function CanvasRow({ canvas, projectId }: { canvas: MapCanvasNode; projectId: string }) {
  const [open, setOpen] = useState(true);
  const hasChildren = canvas.areas.length > 0 || canvas.product_lines.length > 0;
  const summary = inheritanceSummary(canvas);

  return (
    <li>
      <div className="n">
        {hasChildren ? (
          <button
            type="button"
            onClick={() => setOpen((current) => !current)}
            aria-expanded={open}
            aria-label={`${open ? "Collapse" : "Expand"} ${canvas.name}`}
            className="h-[15px] w-[15px] rounded-[3px] border border-[var(--line)] bg-white text-[10px] leading-none text-[var(--ink3)] hover:text-[#12171A]"
          >
            {open ? "−" : "+"}
          </button>
        ) : (
          <span aria-hidden="true" className="inline-block w-[15px]" />
        )}

        <b className="font-medium text-[#12171A]">{canvas.name}</b>

        {canvas.is_company ? (
          <span className="text-[11.5px] text-[var(--ink3)]">
            {plural(canvas.argument_count, "argument")} · {plural(canvas.cell_count, "cell")}
          </span>
        ) : (
          <>
            <span className="chip r">line canvas</span>
            {summary ? (
              <span className="text-[11.5px] text-[var(--ink3)]">{summary}</span>
            ) : null}
          </>
        )}
      </div>

      {hasChildren && open ? (
        <ul>
          {canvas.areas.map((area) => (
            <AreaRow key={area.id} area={area} projectId={projectId} />
          ))}
          {canvas.product_lines.map((child) => (
            <CanvasRow key={child.id} canvas={child} projectId={projectId} />
          ))}
        </ul>
      ) : null}
    </li>
  );
}

function SkeletonRows() {
  const widths = ["58%", "42%", "34%", "38%", "30%", "36%"];
  return (
    <div aria-busy="true" aria-label="Loading the combined tree" className="space-y-[9px]">
      {widths.map((width, index) => (
        <div
          key={width + index}
          className="h-[13px] animate-pulse rounded-[3px] bg-[#EDF0EF]"
          style={{ width, marginLeft: `${index === 0 ? 0 : 17 * (index > 2 ? 2 : 1)}px` }}
        />
      ))}
    </div>
  );
}

export function MapTab({ scope }: { scope: V3Scope }) {
  const [map, setMap] = useState<StrategyMap | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setMap(await V3API.strategyMap.get(scope));
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "The map could not be loaded.");
    } finally {
      setLoading(false);
    }
  }, [scope]);

  useEffect(() => {
    void load();
  }, [load]);

  if (error) {
    return (
      <p role="alert" className="text-sm text-[#B9463A]">
        {error}
      </p>
    );
  }

  // No canvas yet: one line pointing at the Canvas tab, not an empty card.
  if (!loading && map && map.company_canvas === null) {
    return (
      <p className="text-[13.2px] text-[#5C666C]">
        There is no canvas yet. Build the company canvas on the{" "}
        <Link
          href={`/projects/${scope.projectId}/v3/canvas`}
          className="text-[var(--teal)] underline underline-offset-2"
        >
          Canvas tab
        </Link>{" "}
        and the graph appears here.
      </p>
    );
  }

  return (
    <div>
      <div className="rounded-[8px] border border-[var(--line)] bg-white">
        <header className="flex flex-wrap items-center gap-[10px] border-b border-[var(--line2)] px-[15px] py-[11px]">
          <h3 className="m-0 min-w-[140px] flex-1 font-serif text-[14.5px] font-medium text-[#12171A]">
            Combined tree
          </h3>
          <span className="chip r">read-only</span>
          <span className="ml-auto text-[11.5px] text-[var(--ink3)]">
            canvas → product lines → areas → demand
          </span>
        </header>

        <div className="tree p-[15px]">
          {loading ? (
            <SkeletonRows />
          ) : map?.company_canvas ? (
            <>
              <ul>
                <CanvasRow canvas={map.company_canvas} projectId={scope.projectId} />
              </ul>
              {/* State the counting choice so the reader is not guessing. */}
              <p className="m-[13px_0_0] text-[11.5px] text-[var(--ink3)]">
                Demand counts kept nodes for that area alone, never rolled up from
                sub-areas. Card counts include every state, imported live pages included.
                “Content gap” means kept demand with no card on the area or below it.
                {map.unassigned_card_count > 0
                  ? ` ${plural(map.unassigned_card_count, "card")} ${
                      map.unassigned_card_count === 1 ? "is" : "are"
                    } not classified to any area and appear${
                      map.unassigned_card_count === 1 ? "s" : ""
                    } nowhere in this tree.`
                  : ""}
              </p>
            </>
          ) : null}
        </div>
      </div>

      <div className="mt-[13px] rounded-[0_6px_6px_0] border border-[var(--line2)] border-l-2 border-l-[var(--ink3)] bg-[#FAFBFA] px-[13px] py-[10px] text-[12.6px] text-[#5C666C]">
        Orientation only. Everything here is reachable from the flat tabs; nothing is
        edited in this view.
      </div>
    </div>
  );
}
