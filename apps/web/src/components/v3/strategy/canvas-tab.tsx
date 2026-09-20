"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import { Button } from "@/components/button";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import type { CanvasArgument, CanvasDetail, CanvasListItem, ClaimBase } from "@/lib/api-types";
import { V3API, type V3Scope } from "@/lib/v3-api";

import { ClaimDrilldownSheet } from "./claim-drilldown-sheet";

const ROWS: Array<{ key: string; label: string }> = [
  { key: "sub_problem", label: "Sub-problem" },
  { key: "pillar", label: "Differentiation" },
  { key: "capability", label: "Capability" },
  { key: "feature", label: "Features" },
  { key: "benefit", label: "Benefit" },
];

function claimFor(argument: CanvasArgument, row: string): ClaimBase | undefined {
  return argument.claims.find((claim) => claim.row === row);
}

function fallbackText(argument: CanvasArgument, row: string): string {
  if (row === "sub_problem") return argument.sub_problem ?? "";
  if (row === "pillar") return argument.differentiation_pillar ?? "";
  if (row === "capability") return argument.capability ?? "";
  if (row === "feature") return argument.features.join(" · ");
  return argument.benefit ?? "";
}

export function CanvasTab({ scope }: { scope: V3Scope }) {
  const [canvases, setCanvases] = useState<CanvasListItem[]>([]);
  const [selectedCanvasId, setSelectedCanvasId] = useState("");
  const [canvas, setCanvas] = useState<CanvasDetail | null>(null);
  const [selectedClaim, setSelectedClaim] = useState<ClaimBase | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadCanvas = useCallback(
    async (canvasId: string) => {
      setLoading(true);
      setError(null);
      try {
        setCanvas(await V3API.canvas.get(scope, canvasId));
      } catch (cause) {
        setError(cause instanceof Error ? cause.message : "Canvas could not be loaded.");
      } finally {
        setLoading(false);
      }
    },
    [scope],
  );

  useEffect(() => {
    let active = true;
    async function load() {
      setLoading(true);
      try {
        const result = await V3API.canvas.list(scope);
        if (!active) return;
        const items = [
          ...(result.company_canvas ? [result.company_canvas] : []),
          ...result.product_lines,
        ];
        setCanvases(items);
        const firstId = items[0]?.id ?? "";
        setSelectedCanvasId(firstId);
        if (firstId) await loadCanvas(firstId);
        else setLoading(false);
      } catch (cause) {
        if (!active) return;
        setError(cause instanceof Error ? cause.message : "Canvases could not be loaded.");
        setLoading(false);
      }
    }
    void load();
    return () => {
      active = false;
    };
  }, [loadCanvas, scope]);

  const unapprovedCount = useMemo(
    () =>
      (canvas?.pitch_claim && !canvas.pitch_claim.approved ? 1 : 0) +
      (canvas?.arguments.flatMap((argument) => argument.claims).filter((claim) => !claim.approved)
        .length ?? 0),
    [canvas],
  );

  async function selectCanvas(canvasId: string) {
    setSelectedCanvasId(canvasId);
    await loadCanvas(canvasId);
  }

  if (error) {
    return (
      <Alert variant="destructive">
        <AlertTitle>Canvas unavailable</AlertTitle>
        <AlertDescription>{error}</AlertDescription>
      </Alert>
    );
  }

  return (
    <>
      <div className="mb-[13px] flex flex-wrap items-center gap-[8px]">
        <Select
          value={selectedCanvasId}
          onValueChange={(value) => value && void selectCanvas(value)}
        >
          <SelectTrigger className="w-[280px] bg-white">
            <SelectValue placeholder={loading ? "Loading canvases…" : "Select canvas"} />
          </SelectTrigger>
          <SelectContent>
            {canvases.map((item) => (
              <SelectItem key={item.id} value={item.id}>
                {item.name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Badge variant="outline" className="border-[#C4DEDA] bg-[#E1EFED] text-[#15706A]">
          {canvas?.arguments.length ?? 0} arguments
        </Badge>
        <Badge variant="outline" className="border-[#F0D2CC] bg-[#FBEBE8] text-[#B9463A]">
          {unapprovedCount} cells unapproved
        </Badge>
        <Button variant="outline" className="ml-auto" disabled>
          + column
        </Button>
        <Button variant="outline" disabled>
          Version history
        </Button>
      </div>

      {!loading && !canvas ? (
        <Alert>
          <AlertTitle>No canvas yet</AlertTitle>
          <AlertDescription>
            Create the company canvas before adding product-line positioning.
          </AlertDescription>
        </Alert>
      ) : null}

      {canvas?.pitch_claim ? (
        <button
          type="button"
          className="mb-[14px] block w-full rounded-r-[8px] border border-l-[3px] border-[#D6DBD9] border-l-[#15706A] bg-white p-[14px_17px] text-left hover:bg-[#FAFBFA]"
          onClick={() => setSelectedClaim(canvas.pitch_claim)}
        >
          <div className="mb-[6px] flex flex-wrap items-center gap-[8px]">
            <span className="text-[11.5px] text-[#8A949A]">Elevator pitch · claim cell</span>
            <Badge variant="outline">{canvas.pitch_claim.clm_number} · v{canvas.pitch_claim.version}</Badge>
            <Badge variant="outline" className="border-[#C4DEDA] bg-[#E1EFED] text-[#15706A]">
              {canvas.pitch_claim.approved ? "approved" : "draft"}
            </Badge>
          </div>
          <p className="m-0 max-w-[76ch] font-serif text-[16.5px] leading-relaxed">
            {canvas.pitch_claim.text}
          </p>
        </button>
      ) : null}

      {canvas && canvas.arguments.length > 0 ? (
        <div className="overflow-x-auto">
          <div
            className="grid min-w-[900px] gap-px overflow-hidden rounded-[8px] border border-[#D6DBD9] bg-[#D6DBD9]"
            style={{ gridTemplateColumns: `120px repeat(${canvas.arguments.length}, minmax(215px, 1fr))` }}
          >
            <div className="bg-[#FAFBFA] p-[9px_11px] text-[11.5px] text-[#8A949A]">Argument</div>
            {canvas.arguments.map((argument) => (
              <div key={argument.id} className="bg-[#FAFBFA] p-[9px_11px] text-[12px] font-medium">
                Argument {argument.order + 1}
              </div>
            ))}
            {ROWS.flatMap((row) => [
              <div key={`${row.key}-label`} className="bg-[#FAFBFA] p-[9px_11px] text-[11.5px] text-[#8A949A]">
                {row.label}
              </div>,
              ...canvas.arguments.map((argument) => {
                const claim = claimFor(argument, row.key);
                return (
                  <button
                    type="button"
                    key={`${argument.id}-${row.key}`}
                    className="min-h-[82px] bg-white p-[9px_11px] text-left text-[12.6px] transition-colors hover:bg-slate-50 disabled:cursor-default"
                    onClick={() => claim && setSelectedClaim(claim)}
                    disabled={!claim}
                  >
                    <span>{claim?.text || fallbackText(argument, row.key) || "—"}</span>
                    {claim ? (
                      <div className="mt-[6px] flex flex-wrap items-center gap-[5px]">
                        <Badge variant="outline">{claim.clm_number} · v{claim.version}</Badge>
                        <Badge
                          variant="outline"
                          className={claim.approved ? "border-[#C4DEDA] bg-[#E1EFED] text-[#15706A]" : "border-[#F0D2CC] bg-[#FBEBE8] text-[#B9463A]"}
                        >
                          {claim.approved ? "approved" : "draft"}
                        </Badge>
                      </div>
                    ) : null}
                  </button>
                );
              }),
            ])}
          </div>
        </div>
      ) : null}

      {selectedClaim ? (
        <ClaimDrilldownSheet
          key={selectedClaim.id}
          scope={scope}
          claim={selectedClaim}
          open
          onOpenChange={(open) => !open && setSelectedClaim(null)}
          onConfirmed={async () => {
            setSelectedClaim(null);
            if (selectedCanvasId) await loadCanvas(selectedCanvasId);
          }}
        />
      ) : null}
    </>
  );
}
