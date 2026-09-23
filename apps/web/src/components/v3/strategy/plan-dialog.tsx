"use client";

import { useEffect, useState } from "react";

import { Button } from "@/components/button";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import type { PlanKindCounts, PlanPreview, PlanResult } from "@/lib/api-types";
import { V3API, type V3Scope } from "@/lib/v3-api";

/**
 * Plan (handoff §4.5): kept demand nodes → planned content cards.
 *
 * Mounted only while open, so every opening starts fresh. It fetches a read-only
 * preview; nothing is written until the human presses "Confirm Plan". Chips follow the Strategy colour rule: teal is a
 * system fact (what will be created), coral needs a human (skipped nodes), grey
 * is a resting label (deferred cases).
 */

type PlanDialogProps = {
  scope: V3Scope;
  nodeIds: string[];
  isOpen: boolean;
  onOpenChange: (open: boolean) => void;
  onPlanned: () => void | Promise<void>;
};

const KIND_LABELS: [keyof PlanKindCounts, string, string][] = [
  ["pillar", "pillar", "pillars"],
  ["cluster", "cluster", "clusters"],
  ["compare", "compare", "compares"],
  ["refresh", "refresh", "refreshes"],
  ["secondary_demands", "secondary demand", "secondary demands"],
];

function CountChips({ counts }: { counts: PlanKindCounts }) {
  return (
    <span className="flex flex-wrap gap-[6px]">
      {KIND_LABELS.map(([key, one, many]) => (
        <span key={key} className={`chip ${counts[key] > 0 ? "t" : "r"}`}>
          {counts[key]} {counts[key] === 1 ? one : many}
        </span>
      ))}
    </span>
  );
}

function PlanBody({ plan }: { plan: PlanPreview }) {
  return (
    <div className="grid max-h-[55vh] gap-[14px] overflow-y-auto pr-1 text-[13px]">
      <p className="text-[#5C666C]">
        {plan.selected_count} selected · {plan.eligible_count} eligible · {plan.skipped_count}{" "}
        skipped
      </p>

      {plan.groups.length === 0 ? (
        <p className="text-[#5C666C]">No cards would be created from this selection.</p>
      ) : (
        plan.groups.map((group) => (
          <section
            key={`${group.area_id}-${group.market_country ?? "none"}`}
            aria-label={`${group.area_name} ${group.market_country ?? "no market"}`}
            className="rounded-[7px] border border-[var(--line2)] p-[10px_12px]"
          >
            <header className="mb-[7px] flex flex-wrap items-center gap-[8px]">
              <b className="font-medium text-[#12171A]">{group.area_name || "Area"}</b>
              <span className="text-[11.5px] text-[var(--ink3)]">
                Market: {group.market_country ?? "none"}
              </span>
            </header>
            <CountChips counts={group.counts} />
            <ul className="mt-[8px] grid gap-[5px]">
              {group.cards.map((card) => (
                <li key={card.primary_node_id}>
                  <span className="mr-[6px] text-[11.5px] uppercase tracking-wide text-[var(--ink3)]">
                    {card.kind}
                  </span>
                  {card.primary_text}
                  <span className="ml-[6px] text-[11.5px] text-[var(--ink3)]">
                    {card.word_budget} words
                  </span>
                  {card.secondary_demands.length > 0 ? (
                    <p className="ml-[14px] text-[12px] text-[#5C666C]">
                      secondaries: {card.secondary_demands.map((item) => item.text).join(", ")}
                    </p>
                  ) : null}
                </li>
              ))}
            </ul>
          </section>
        ))
      )}

      {plan.skipped.length > 0 ? (
        <section aria-label="Skipped nodes">
          <p className="mb-[5px] flex items-center gap-[7px] font-medium">
            <span className="chip c">{plan.skipped_count} skipped</span>
          </p>
          <ul className="grid gap-[3px] text-[12.6px] text-[#5C666C]">
            {plan.skipped.map((skip) => (
              <li key={skip.node_id}>
                {skip.text ?? skip.node_id} — {skip.reason}
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      {plan.deferred.length > 0 ? (
        <section aria-label="Deferred">
          <p className="mb-[5px]">
            <span className="chip r">deferred</span>
          </p>
          <ul className="grid gap-[3px] text-[12.6px] text-[#5C666C]">
            {plan.deferred.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </section>
      ) : null}
    </div>
  );
}

export function PlanDialog({ scope, nodeIds, isOpen, onOpenChange, onPlanned }: PlanDialogProps) {
  const [preview, setPreview] = useState<PlanPreview | null>(null);
  const [result, setResult] = useState<PlanResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [confirming, setConfirming] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    V3API.demand
      .previewPlan(scope, nodeIds)
      .then((value) => {
        if (active) setPreview(value);
      })
      .catch((cause: unknown) => {
        if (active) setError(cause instanceof Error ? cause.message : "Plan preview failed.");
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [scope, nodeIds]);

  async function confirm() {
    setConfirming(true);
    setError(null);
    try {
      setResult(await V3API.demand.confirmPlan(scope, nodeIds));
      await onPlanned();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Plan failed. No cards were created.");
    } finally {
      setConfirming(false);
    }
  }

  const creatable = preview
    ? preview.groups.reduce((sum, group) => sum + group.cards.length, 0)
    : 0;

  return (
    <Dialog open={isOpen} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[620px]">
        <DialogHeader>
          <DialogTitle>{result ? "Plan created" : "Plan preview"}</DialogTitle>
          <DialogDescription>
            {result
              ? `${result.created_count} ${result.created_count === 1 ? "card" : "cards"} created in planned.`
              : "Kept nodes become planned content cards, grouped by area and market. Nothing is written until you confirm."}
          </DialogDescription>
        </DialogHeader>

        {error ? (
          <Alert variant="destructive">
            <AlertTitle>Plan failed</AlertTitle>
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        ) : null}

        {loading ? (
          <div aria-busy="true" aria-label="Loading plan preview" className="grid gap-[8px]">
            {["70%", "52%", "61%"].map((width) => (
              <div
                key={width}
                className="h-[13px] animate-pulse rounded-[3px] bg-[#EDF0EF]"
                style={{ width }}
              />
            ))}
          </div>
        ) : null}

        {result ? (
          <>
            <CountChips counts={result.totals} />
            <PlanBody plan={result} />
          </>
        ) : preview ? (
          <>
            <CountChips counts={preview.totals} />
            <PlanBody plan={preview} />
          </>
        ) : null}

        <DialogFooter>
          {result ? (
            <Button variant="primary" size="sm" onClick={() => onOpenChange(false)}>
              Done
            </Button>
          ) : (
            <>
              <Button variant="outline" size="sm" onClick={() => onOpenChange(false)}>
                Cancel
              </Button>
              <Button
                variant="primary"
                size="sm"
                disabled={!preview || creatable === 0 || confirming}
                onClick={() => void confirm()}
              >
                {confirming ? "Planning…" : "Confirm Plan"}
              </Button>
            </>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
