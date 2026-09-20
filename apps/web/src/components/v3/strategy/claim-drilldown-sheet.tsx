"use client";

import { useEffect, useState } from "react";

import { Button } from "@/components/button";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetFooter,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import type { ClaimBase, ClaimDrilldown } from "@/lib/api-types";
import { V3API, type V3Scope } from "@/lib/v3-api";

interface ClaimDrilldownSheetProps {
  scope: V3Scope;
  claim: ClaimBase;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onConfirmed: () => Promise<void>;
}

export function ClaimDrilldownSheet({
  scope,
  claim,
  open,
  onOpenChange,
  onConfirmed,
}: ClaimDrilldownSheetProps) {
  const [text, setText] = useState(claim.text);
  const [evidence, setEvidence] = useState(claim.evidence);
  const [citationCount, setCitationCount] = useState<number | null>(null);
  const [drilldown, setDrilldown] = useState<ClaimDrilldown | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    async function load() {
      try {
        const [check, detail] = await Promise.all([
          V3API.canvas.checkClaimEdit(scope, claim.id),
          V3API.canvas.getClaimDrilldown(scope, claim.id),
        ]);
        if (!active) return;
        setCitationCount(check.citation_count);
        setDrilldown(detail);
      } catch (cause) {
        if (active) setError(cause instanceof Error ? cause.message : "Claim details failed to load.");
      }
    }
    void load();
    return () => {
      active = false;
    };
  }, [claim.id, scope]);

  async function confirmEdit() {
    setSaving(true);
    setError(null);
    try {
      await V3API.canvas.confirmClaimEdit(scope, claim.id, { text, evidence });
      await onConfirmed();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "The claim could not be updated.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent className="w-full overflow-y-auto sm:max-w-[560px]">
        <SheetHeader>
          <SheetTitle>{claim.clm_number || "Claim"} · v{claim.version}</SheetTitle>
          <SheetDescription>
            Editing creates a new version. The approved source row is never overwritten.
          </SheetDescription>
        </SheetHeader>
        <div className="flex flex-col gap-4 px-4 pb-6">
          <Alert>
            <AlertTitle>Citation check complete</AlertTitle>
            <AlertDescription>
              {citationCount === null
                ? "Checking live citations…"
                : `${citationCount} content card${citationCount === 1 ? "" : "s"} cite this claim.`}
            </AlertDescription>
          </Alert>
          {error ? (
            <Alert variant="destructive">
              <AlertTitle>Unable to continue</AlertTitle>
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          ) : null}
          <label className="grid gap-1 text-sm font-medium">
            Claim text
            <textarea
              className="min-h-[120px] rounded-md border bg-white p-3 text-sm font-normal"
              value={text}
              onChange={(event) => setText(event.target.value)}
            />
          </label>
          <label className="grid gap-1 text-sm font-medium">
            Evidence
            <textarea
              className="min-h-[80px] rounded-md border bg-white p-3 text-sm font-normal"
              value={evidence}
              onChange={(event) => setEvidence(event.target.value)}
            />
          </label>
          <Collapsible>
            <CollapsibleTrigger className="text-sm font-medium text-[#15706A]">
              View argument chain and linked work
            </CollapsibleTrigger>
            <CollapsibleContent className="mt-3 grid gap-3 text-sm">
              <div>
                <p className="font-medium">Argument chain</p>
                {drilldown?.argument_chain.map((item) => (
                  <p key={item.id} className="mt-1 text-muted-foreground">{item.text}</p>
                ))}
              </div>
              <div>
                <p className="font-medium">Demand</p>
                <p className="text-muted-foreground">{drilldown?.demand_nodes.length ?? 0} linked nodes</p>
              </div>
              <div>
                <p className="font-medium">Content cards</p>
                <p className="text-muted-foreground">{drilldown?.content_cards.length ?? 0} citing cards</p>
              </div>
            </CollapsibleContent>
          </Collapsible>
        </div>
        <SheetFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>Cancel</Button>
          <Button variant="primary" disabled={saving || !text.trim()} onClick={() => void confirmEdit()}>
            {saving ? "Creating version…" : "Confirm new version"}
          </Button>
        </SheetFooter>
      </SheetContent>
    </Sheet>
  );
}
