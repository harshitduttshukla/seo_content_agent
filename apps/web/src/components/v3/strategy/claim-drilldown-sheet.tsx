"use client";

import { useCallback, useEffect, useState } from "react";

import { Button } from "@/components/button";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
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
import type { ClaimBase, ClaimDrilldown, ContentCardStub } from "@/lib/api-types";
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
  const [approved, setApproved] = useState(claim.approved);
  const [citationCount, setCitationCount] = useState<number | null>(null);
  const [drilldown, setDrilldown] = useState<ClaimDrilldown | null>(null);
  const [linkedWorkOpen, setLinkedWorkOpen] = useState(false);
  const [drilldownLoading, setDrilldownLoading] = useState(false);
  const [drilldownError, setDrilldownError] = useState<string | null>(null);
  const [availableCards, setAvailableCards] = useState<ContentCardStub[]>([]);
  const [selectedCardId, setSelectedCardId] = useState<string>("");
  const [testCardTitle, setTestCardTitle] = useState<string>("");
  const [linking, setLinking] = useState(false);
  const [approving, setApproving] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    async function load() {
      try {
        const [check, cards] = await Promise.all([
          V3API.canvas.checkClaimEdit(scope, claim.id),
          V3API.canvas.listContentCards(scope).catch(() => []),
        ]);
        if (!active) return;
        setCitationCount(check.citation_count);
        setAvailableCards(cards);
      } catch (cause) {
        if (active) setError(cause instanceof Error ? cause.message : "Claim details failed to load.");
      }
    }
    void load();
    return () => {
      active = false;
    };
  }, [claim.id, scope]);

  const loadDrilldown = useCallback(async () => {
    setDrilldownLoading(true);
    setDrilldownError(null);
    try {
      setDrilldown(await V3API.canvas.getClaimDrilldown(scope, claim.id));
    } catch (cause) {
      setDrilldownError(
        cause instanceof Error ? cause.message : "Argument chain and linked work failed to load.",
      );
    } finally {
      setDrilldownLoading(false);
    }
  }, [claim.id, scope]);

  function handleLinkedWorkOpenChange(nextOpen: boolean) {
    setLinkedWorkOpen(nextOpen);
    if (nextOpen && drilldown === null && !drilldownLoading) {
      void loadDrilldown();
    }
  }

  async function handleApprove() {
    setApproving(true);
    setError(null);
    try {
      const updated = await V3API.canvas.approveClaim(scope, claim.id);
      setApproved(updated.approved);
      await onConfirmed();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Failed to approve claim.");
    } finally {
      setApproving(false);
    }
  }

  async function handleLinkExistingCard() {
    if (!selectedCardId) return;
    setLinking(true);
    setError(null);
    try {
      const updatedDrilldown = await V3API.canvas.addCitation(scope, claim.id, {
        content_card_id: selectedCardId,
      });
      setDrilldown(updatedDrilldown);
      const check = await V3API.canvas.checkClaimEdit(scope, claim.id);
      setCitationCount(check.citation_count);
      setSelectedCardId("");
      await onConfirmed();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Failed to link citation.");
    } finally {
      setLinking(false);
    }
  }

  async function handleCreateTestCard() {
    if (!testCardTitle.trim()) return;
    setLinking(true);
    setError(null);
    try {
      const updatedDrilldown = await V3API.canvas.addCitation(scope, claim.id, {
        title: testCardTitle.trim(),
      });
      setDrilldown(updatedDrilldown);
      const [check, cards] = await Promise.all([
        V3API.canvas.checkClaimEdit(scope, claim.id),
        V3API.canvas.listContentCards(scope).catch(() => []),
      ]);
      setCitationCount(check.citation_count);
      setAvailableCards(cards);
      setTestCardTitle("");
      await onConfirmed();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Failed to create test card.");
    } finally {
      setLinking(false);
    }
  }

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
          <div className="flex flex-wrap items-center justify-between gap-2">
            <SheetTitle>{claim.clm_number || "Claim"} · v{claim.version}</SheetTitle>
            <div className="flex items-center gap-2">
              <Badge
                variant="outline"
                className={
                  approved
                    ? "border-[#C4DEDA] bg-[#E1EFED] text-[#15706A]"
                    : "border-[#F0D2CC] bg-[#FBEBE8] text-[#B9463A]"
                }
              >
                {approved ? "approved" : "unapproved"}
              </Badge>
              {!approved && (
                <Button
                  size="sm"
                  variant="outline"
                  className="border-[#C4DEDA] bg-[#E1EFED] text-[#15706A] hover:bg-[#d0e6e3]"
                  disabled={approving}
                  onClick={() => void handleApprove()}
                >
                  {approving ? "Approving…" : "Approve"}
                </Button>
              )}
            </div>
          </div>
          <SheetDescription>
            Editing creates a new version. The approved source row is never overwritten.
          </SheetDescription>
        </SheetHeader>
        <div className="flex flex-col gap-4 px-4 pb-6">
          {citationCount !== null && citationCount > 0 ? (
            <Alert className="border-[#F0D2CC] bg-[#FBEBE8] text-[#B9463A]">
              <AlertTitle className="font-semibold text-[#B9463A]">Live citation warning</AlertTitle>
              <AlertDescription className="text-[#B9463A]">
                {citationCount} live page{citationCount === 1 ? "" : "s"} cite {claim.clm_number || "this claim"} v{claim.version}. Saving creates v{claim.version + 1} and raises a stale-claim scan with {citationCount} refresh card{citationCount === 1 ? "" : "s"}.
              </AlertDescription>
            </Alert>
          ) : (
            <Alert>
              <AlertTitle>Citation check complete</AlertTitle>
              <AlertDescription>
                {citationCount === null
                  ? "Checking live citations…"
                  : `${citationCount} content card${citationCount === 1 ? "" : "s"} cite this claim.`}
              </AlertDescription>
            </Alert>
          )}
          {error ? (
            <Alert variant="destructive">
              <AlertTitle>Unable to continue</AlertTitle>
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          ) : null}
          <label className="grid gap-1 text-sm font-medium">
            Claim text
            <textarea
              id="claim-text"
              name="claim_text"
              className="min-h-[120px] rounded-md border bg-white p-3 text-sm font-normal"
              value={text}
              onChange={(event) => setText(event.target.value)}
            />
          </label>
          <label className="grid gap-1 text-sm font-medium">
            Evidence
            <textarea
              id="claim-evidence"
              name="claim_evidence"
              className="min-h-[80px] rounded-md border bg-white p-3 text-sm font-normal"
              value={evidence}
              onChange={(event) => setEvidence(event.target.value)}
            />
          </label>
          <Collapsible open={linkedWorkOpen} onOpenChange={handleLinkedWorkOpenChange}>
            <CollapsibleTrigger className="text-sm font-medium text-[#15706A] hover:underline">
              View argument chain and linked work
            </CollapsibleTrigger>
            <CollapsibleContent className="mt-3 grid gap-3 text-sm">
              {drilldownLoading ? (
                <p className="text-muted-foreground">Loading argument chain and linked work…</p>
              ) : drilldownError ? (
                <p className="text-destructive" role="alert">{drilldownError}</p>
              ) : drilldown ? (
                <>
                  <div>
                    <p className="font-medium">Argument chain</p>
                    {drilldown.argument_chain.length > 0 ? (
                      drilldown.argument_chain.map((item) => (
                        <p key={item.id} className="mt-1 text-muted-foreground">{item.text}</p>
                      ))
                    ) : (
                      <p className="mt-1 text-muted-foreground">No argument chain linked.</p>
                    )}
                  </div>
                  <div>
                    <p className="font-medium">Demand</p>
                    <p className="text-muted-foreground">{drilldown.demand_nodes.length} linked nodes</p>
                  </div>
                  <div className="rounded-md border p-3">
                    <div className="mb-2 flex items-center justify-between">
                      <p className="font-medium">Content cards</p>
                      <Badge variant="outline">{drilldown.content_cards.length}</Badge>
                    </div>
                    {drilldown.content_cards.length > 0 ? (
                      <div className="space-y-1.5 max-h-36 overflow-y-auto">
                        {drilldown.content_cards.map((card) => (
                          <div key={card.id} className="flex items-center justify-between rounded border bg-slate-50 p-2 text-xs">
                            <span className="font-medium text-slate-800 truncate max-w-[280px]" title={card.title}>
                              {card.title}
                            </span>
                            <div className="flex items-center gap-1.5">
                              <Badge variant="outline" className="text-[10px]">{card.kind}</Badge>
                              <Badge variant="outline" className="border-[#C4DEDA] bg-[#E1EFED] text-[#15706A] text-[10px]">
                                {card.state}
                              </Badge>
                            </div>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <p className="text-muted-foreground text-xs">No content cards cite this claim yet.</p>
                    )}

                    <div className="mt-3 border-t pt-3 space-y-2">
                  <label htmlFor="claim-content-card" className="text-xs font-medium text-slate-700">
                    Link a content card citation
                  </label>
                  {availableCards.length > 0 ? (
                    <div className="flex items-center gap-2">
                      <select
                        id="claim-content-card"
                        name="content_card_id"
                        className="h-8 flex-1 rounded border bg-white px-2 text-xs text-slate-800"
                        value={selectedCardId}
                        onChange={(e) => setSelectedCardId(e.target.value)}
                      >
                        <option value="">Select a content card to link…</option>
                        {availableCards.map((c) => (
                          <option key={c.id} value={c.id}>
                            {c.title} ({c.kind} · {c.state})
                          </option>
                        ))}
                      </select>
                      <Button
                        type="button"
                        size="sm"
                        variant="outline"
                        disabled={!selectedCardId || linking}
                        onClick={() => void handleLinkExistingCard()}
                      >
                        {linking ? "Linking…" : "Link card"}
                      </Button>
                    </div>
                  ) : null}

                  <div className="rounded border border-dashed border-amber-300 bg-amber-50/50 p-2.5">
                    <div className="flex items-center gap-1.5 text-xs font-semibold text-amber-800">
                      <span className="bg-amber-200 text-amber-900 px-1 py-0.5 rounded text-[10px] uppercase tracking-wide">
                        Test / Dev
                      </span>
                      <span>Create test card</span>
                    </div>
                    <p className="mt-0.5 text-[11px] text-amber-700">
                      Creates a live card stub to test citation counts, stale-claim triggers, and versioning warnings.
                    </p>
                    <div className="mt-2 flex gap-2">
                      <input
                        id="test-card-title"
                        name="test_card_title"
                        aria-label="Create test card"
                        type="text"
                        className="h-8 flex-1 rounded border border-amber-300 bg-white px-2 text-xs text-slate-800 placeholder:text-slate-400"
                        placeholder="e.g. Glopal vs Global-e comparison"
                        value={testCardTitle}
                        onChange={(e) => setTestCardTitle(e.target.value)}
                      />
                      <Button
                        type="button"
                        size="sm"
                        variant="outline"
                        className="border-amber-400 bg-amber-100 text-amber-900 hover:bg-amber-200"
                        disabled={!testCardTitle.trim() || linking}
                        onClick={() => void handleCreateTestCard()}
                      >
                        {linking ? "Creating…" : "Create test card"}
                      </Button>
                    </div>
                  </div>
                    </div>
                  </div>
                </>
              ) : null}
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
