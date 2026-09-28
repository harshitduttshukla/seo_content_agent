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
import type {
  CanvasAnchorInput,
  CanvasArgument,
  CanvasArgumentInput,
  CanvasClaimInput,
  CanvasDetail,
  CanvasListItem,
  ClaimBase,
} from "@/lib/api-types";
import { V3API, type V3Scope } from "@/lib/v3-api";

import { AreasPanel } from "./areas-panel";
import { ClaimDrilldownSheet } from "./claim-drilldown-sheet";
import {
  AnchorDialog,
  ArgumentDialog,
  NewClaimDialog,
  type NewClaimTarget,
} from "./canvas-authoring-dialogs";

const ROWS: Array<{ key: string; label: string }> = [
  { key: "sub_problem", label: "Sub-problem" },
  { key: "pillar", label: "Differentiation pillar" },
  { key: "capability", label: "Capability" },
  { key: "feature", label: "Features" },
  { key: "benefit", label: "Benefit" },
];

const ANCHOR_LABELS: Record<string, string> = {
  company: "Company",
  persona: "Persona",
  use_case: "Use case",
  alternative: "Alternative",
  category: "Category",
};

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

function ClaimMetadata({
  claim,
  onApprove,
}: {
  claim: ClaimBase;
  onApprove?: () => void;
}) {
  return (
    <div className="mt-[6px] flex flex-wrap items-center gap-[6px]">
      <Badge variant="outline">{claim.clm_number} · v{claim.version}</Badge>
      <Badge
        variant="outline"
        className={
          claim.approved
            ? "border-[#C4DEDA] bg-[#E1EFED] text-[#15706A]"
            : "border-[#F0D2CC] bg-[#FBEBE8] text-[#B9463A]"
        }
      >
        {claim.approved ? "approved" : "unapproved"}
      </Badge>
      {claim.evidence ? (
        <span
          className="max-w-[180px] truncate text-[11px] text-[#8A949A]"
          title={claim.evidence}
        >
          evidence: {claim.evidence}
        </span>
      ) : null}
      {!claim.approved && onApprove ? (
        <button
          type="button"
          className="ml-auto text-[11px] font-medium text-[#15706A] hover:underline"
          onClick={(e) => {
            e.stopPropagation();
            onApprove();
          }}
        >
          Approve
        </button>
      ) : null}
    </div>
  );
}

/** "{organization} — company canvas" for the company row; every other canvas keeps its name. */
function canvasLabel(item: CanvasListItem, organizationName: string): string {
  if (item.product_line === null && organizationName) return `${organizationName} — company canvas`;
  return item.name;
}

export function CanvasTab({
  scope,
  organizationName = "",
}: {
  scope: V3Scope;
  /** The project's own organization name, read server-side; "" keeps "Company canvas". */
  organizationName?: string;
}) {
  const [canvases, setCanvases] = useState<CanvasListItem[]>([]);
  const [selectedCanvasId, setSelectedCanvasId] = useState("");
  const [canvas, setCanvas] = useState<CanvasDetail | null>(null);
  const [selectedClaim, setSelectedClaim] = useState<ClaimBase | null>(null);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [anchorDialogOpen, setAnchorDialogOpen] = useState(false);
  const [selectedAnchor, setSelectedAnchor] = useState<CanvasAnchorInput | null>(null);
  const [argumentDialogOpen, setArgumentDialogOpen] = useState(false);
  const [newClaimTarget, setNewClaimTarget] = useState<NewClaimTarget | null>(null);
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
      (canvas?.problem_summary_claim && !canvas.problem_summary_claim.approved ? 1 : 0) +
      (canvas?.differentiation_summary_claim && !canvas.differentiation_summary_claim.approved ? 1 : 0) +
      (canvas?.arguments.flatMap((argument) => argument.claims).filter((claim) => !claim.approved)
        .length ?? 0),
    [canvas],
  );

  async function selectCanvas(canvasId: string) {
    setSelectedCanvasId(canvasId);
    await loadCanvas(canvasId);
  }

  async function createCompanyCanvas() {
    setCreating(true);
    setError(null);
    try {
      const created = await V3API.canvas.createCompany(scope);
      setCanvases([
        {
          id: created.id,
          product_line: created.product_line,
          name: created.name,
          argument_count: created.arguments.length,
        },
      ]);
      setSelectedCanvasId(created.id);
      setCanvas(created);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Company canvas could not be created.");
    } finally {
      setCreating(false);
    }
  }

  async function saveAnchor(data: CanvasAnchorInput) {
    if (!selectedCanvasId) return;
    setCanvas(await V3API.canvas.upsertAnchor(scope, selectedCanvasId, data));
  }

  async function addArgument(data: CanvasArgumentInput) {
    if (!selectedCanvasId) return;
    setCanvas(await V3API.canvas.createArgument(scope, selectedCanvasId, data));
  }

  async function addClaim(data: CanvasClaimInput) {
    if (!selectedCanvasId) return;
    setCanvas(await V3API.canvas.createClaim(scope, selectedCanvasId, data));
  }

  async function handleApprove(claim: ClaimBase) {
    setError(null);
    try {
      await V3API.canvas.approveClaim(scope, claim.id);
      if (selectedCanvasId) await loadCanvas(selectedCanvasId);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Failed to approve claim.");
    }
  }

  function openCell(row: string, label: string, claim?: ClaimBase, argumentId?: string) {
    if (claim) {
      setSelectedClaim(claim);
      return;
    }
    setNewClaimTarget({ row, label, argumentId });
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
            <SelectValue placeholder={loading ? "Loading canvases…" : "Select canvas"}>
              {(() => {
                const selected = canvases.find((item) => item.id === selectedCanvasId);
                return selected ? canvasLabel(selected, organizationName) : null;
              })()}
            </SelectValue>
          </SelectTrigger>
          <SelectContent>
            {canvases.map((item) => (
              <SelectItem key={item.id} value={item.id}>
                {canvasLabel(item, organizationName)}
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
        <Button
          variant="outline"
          className="ml-auto"
          disabled={!canvas}
          onClick={() => setArgumentDialogOpen(true)}
        >
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
          <div className="mt-2">
            <Button
              type="button"
              size="sm"
              onClick={() => void createCompanyCanvas()}
              disabled={creating}
            >
              {creating ? "Creating…" : "Create company canvas"}
            </Button>
          </div>
        </Alert>
      ) : null}

      {/* Elevator Pitch Row */}
      {canvas ? (
        canvas.pitch_claim ? (
          <div className="mb-[14px] rounded-r-[8px] border border-l-[3px] border-[#D6DBD9] border-l-[#15706A] bg-white p-[14px_17px]">
            <div className="mb-[6px] flex flex-wrap items-center gap-[8px]">
              <span className="text-[11.5px] text-[#8A949A]">
                Elevator pitch · a claim cell (row: pitch) · line one of every bundle once approved
              </span>
              <Badge variant="outline">
                {canvas.pitch_claim.clm_number} · v{canvas.pitch_claim.version}
              </Badge>
              <Badge
                variant="outline"
                className={
                  canvas.pitch_claim.approved
                    ? "border-[#C4DEDA] bg-[#E1EFED] text-[#15706A]"
                    : "border-[#F0D2CC] bg-[#FBEBE8] text-[#B9463A]"
                }
              >
                {canvas.pitch_claim.approved ? "approved" : "unapproved"}
              </Badge>
              <span className="ml-auto text-[11.5px] text-[#8A949A]">
                cited by {canvas.pitch_claim.citation_count ?? 0} live pages
              </span>
            </div>
            <p className="m-0 max-w-[76ch] font-serif text-[16.5px] leading-relaxed">
              {canvas.pitch_claim.text}
            </p>
            {canvas.pitch_claim.evidence ? (
              <div className="mt-1 text-[12px] text-[#8A949A]">
                evidence: {canvas.pitch_claim.evidence}
              </div>
            ) : null}
            <div className="mt-[9px] flex items-center gap-2">
              <Button
                type="button"
                size="sm"
                variant="outline"
                id="pitch-edit"
                onClick={() => setSelectedClaim(canvas.pitch_claim)}
              >
                Edit cell
              </Button>
              {!canvas.pitch_claim.approved ? (
                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  className="border-[#C4DEDA] bg-[#E1EFED] text-[#15706A] hover:bg-[#d0e6e3]"
                  onClick={() => void handleApprove(canvas.pitch_claim!)}
                >
                  Approve
                </Button>
              ) : null}
            </div>
          </div>
        ) : (
          <div className="mb-[14px] flex items-center justify-between rounded-r-[8px] border border-l-[3px] border-[#D6DBD9] border-l-[#15706A] bg-white p-[14px_17px]">
            <div>
              <div className="text-[11.5px] text-[#8A949A]">
                Elevator pitch · a claim cell (row: pitch) · line one of every bundle once approved
              </div>
              <p className="m-0 mt-1 text-sm text-[#8A949A]">No elevator pitch defined yet.</p>
            </div>
            <Button
              type="button"
              size="sm"
              variant="outline"
              onClick={() => openCell("pitch", "Elevator pitch")}
            >
              Write pitch
            </Button>
          </div>
        )
      ) : null}

      {/* Grid */}
      {canvas ? (
        <div className="overflow-x-auto">
          <div
            className="grid min-w-[900px] gap-px overflow-hidden rounded-[8px] border border-[#D6DBD9] bg-[#D6DBD9]"
            style={{
              gridTemplateColumns: `120px repeat(${Math.max(canvas.arguments.length, 1)}, minmax(215px, 1fr))`,
            }}
          >
            {/* Anchors row */}
            <div className="bg-[#FAFBFA] p-[9px_11px] text-[11.5px] text-[#8A949A]">
              Anchors
            </div>
            <div
              className="bg-white p-[9px_11px] text-left text-[12.6px]"
              style={{ gridColumn: "2 / -1" }}
            >
              {canvas.anchors.length > 0 ? (
                <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
                  {canvas.anchors.map((anchor, idx) => (
                    <span key={`${anchor.anchor_type ?? "anchor"}-${idx}`} className="inline-flex items-center gap-1">
                      {idx > 0 && <span className="text-[#8A949A] mr-1">·</span>}
                      <button
                        type="button"
                        className="inline-flex items-center gap-1 text-left hover:underline"
                        onClick={() => {
                          if (anchor.anchor_type) {
                            setSelectedAnchor({
                              anchor_type: anchor.anchor_type,
                              text: anchor.text,
                              primary: anchor.primary,
                            });
                            setAnchorDialogOpen(true);
                          }
                        }}
                      >
                        <b>
                          {anchor.anchor_type
                            ? ANCHOR_LABELS[anchor.anchor_type] || anchor.anchor_type
                            : "Anchor"}
                        </b>
                        <span>{anchor.text}</span>
                        {anchor.primary ? (
                          <Badge
                            variant="outline"
                            className="h-4 border-[#C4DEDA] bg-[#E1EFED] px-1 py-0 text-[10px] text-[#15706A]"
                          >
                            primary
                          </Badge>
                        ) : null}
                      </button>
                    </span>
                  ))}
                  <button
                    type="button"
                    className="ml-2 font-medium text-[#15706A] hover:underline"
                    onClick={() => {
                      setSelectedAnchor(null);
                      setAnchorDialogOpen(true);
                    }}
                  >
                    + Add anchor
                  </button>
                </div>
              ) : (
                <div>
                  <span className="text-[#8A949A]">No anchors yet.</span>
                  <button
                    type="button"
                    className="ml-2 font-medium text-[#15706A] hover:underline"
                    onClick={() => {
                      setSelectedAnchor(null);
                      setAnchorDialogOpen(true);
                    }}
                  >
                    + Add anchor
                  </button>
                </div>
              )}
              <div className="mt-1.5 text-[11.5px] text-[#8A949A]">
                Each primary anchor passes the stands-on-its-own rule
              </div>
            </div>

            {/* Problem summary row */}
            <div className="bg-[#FAFBFA] p-[9px_11px] text-[11.5px] text-[#8A949A]">
              Problem summary
            </div>
            <div
              className="bg-white p-[9px_11px] text-left text-[12.6px]"
              style={{ gridColumn: "2 / -1" }}
            >
              {canvas.problem_summary_claim || canvas.problem_summary ? (
                <div
                  className="cursor-pointer"
                  onClick={() =>
                    openCell(
                      "problem_summary",
                      "Problem summary",
                      canvas.problem_summary_claim ?? undefined,
                    )
                  }
                >
                  <div>
                    <span className="mr-1.5 font-semibold text-[#15706A]">✓</span>
                    <span>{canvas.problem_summary_claim?.text || canvas.problem_summary}</span>
                  </div>
                  {canvas.problem_summary_claim ? (
                    <ClaimMetadata
                      claim={canvas.problem_summary_claim}
                      onApprove={() => void handleApprove(canvas.problem_summary_claim!)}
                    />
                  ) : null}
                </div>
              ) : (
                <button
                  type="button"
                  className="font-medium text-[#15706A] hover:underline"
                  onClick={() => openCell("problem_summary", "Problem summary")}
                >
                  + Add problem summary
                </button>
              )}
            </div>

            {/* Argument columns header */}
            <div className="bg-[#FAFBFA] p-[9px_11px] text-[11.5px] text-[#8A949A]">Argument</div>
            {canvas.arguments.length > 0 ? (
              canvas.arguments.map((argument) => (
                <div key={argument.id} className="bg-[#FAFBFA] p-[9px_11px] text-[12px] font-medium">
                  Argument {argument.order + 1}
                </div>
              ))
            ) : (
              <div className="bg-[#FAFBFA] p-[9px_11px] text-[12px] text-[#8A949A]">
                No arguments yet
              </div>
            )}

            {/* Main grid rows */}
            {ROWS.flatMap((row) => [
              <div key={`${row.key}-label`} className="bg-[#FAFBFA] p-[9px_11px] text-[11.5px] text-[#8A949A]">
                {row.label}
              </div>,
              ...(canvas.arguments.length > 0
                ? canvas.arguments.map((argument) => {
                    const claim = claimFor(argument, row.key);
                    return (
                      <button
                        type="button"
                        key={`${argument.id}-${row.key}`}
                        className="min-h-[82px] bg-white p-[9px_11px] text-left text-[12.6px] transition-colors hover:bg-slate-50 disabled:cursor-default"
                        onClick={() => openCell(row.key, row.label, claim, argument.id)}
                      >
                        <span>{claim?.text || fallbackText(argument, row.key) || "—"}</span>
                        {claim ? (
                          <ClaimMetadata
                            claim={claim}
                            onApprove={() => void handleApprove(claim)}
                          />
                        ) : null}
                      </button>
                    );
                  })
                : [
                    <button
                      type="button"
                      key={`${row.key}-empty`}
                      className="min-h-[82px] bg-white p-[9px_11px] text-left text-[12.6px] text-[#8A949A] hover:bg-slate-50"
                      onClick={() => setArgumentDialogOpen(true)}
                    >
                      Add an argument to create cells
                    </button>,
                  ]),
            ])}

            {/* Differentiation summary row */}
            <div className="bg-[#FAFBFA] p-[9px_11px] text-[11.5px] text-[#8A949A]">
              Differentiation summary
            </div>
            <div
              className="bg-white p-[9px_11px] text-left text-[12.6px]"
              style={{ gridColumn: "2 / -1" }}
            >
              {canvas.differentiation_summary_claim || canvas.differentiation_summary ? (
                <div
                  className="cursor-pointer"
                  onClick={() =>
                    openCell(
                      "differentiation_summary",
                      "Differentiation summary",
                      canvas.differentiation_summary_claim ?? undefined,
                    )
                  }
                >
                  <div>
                    <span className="mr-1.5 font-semibold text-[#15706A]">✓</span>
                    <span>{canvas.differentiation_summary_claim?.text || canvas.differentiation_summary}</span>
                  </div>
                  {canvas.differentiation_summary_claim ? (
                    <ClaimMetadata
                      claim={canvas.differentiation_summary_claim}
                      onApprove={() => void handleApprove(canvas.differentiation_summary_claim!)}
                    />
                  ) : null}
                </div>
              ) : (
                <button
                  type="button"
                  className="font-medium text-[#15706A] hover:underline"
                  onClick={() => openCell("differentiation_summary", "Differentiation summary")}
                >
                  + Add differentiation summary
                </button>
              )}
            </div>
          </div>
        </div>
      ) : null}

      {canvas ? <AreasPanel key={canvas.id} scope={scope} canvasId={canvas.id} canvasArguments={canvas.arguments} /> : null}

      {/* Helper notes */}
      <div className="mt-4 grid gap-3 md:grid-cols-2 text-[12.5px] text-[#556066]">
        <div className="rounded-md border border-[#C4DEDA] bg-[#E1EFED]/40 p-3">
          <b className="text-[#15706A]">Editing an approved cell creates a new version and runs the stale-claim job.</b> Click &ldquo;Edit cell&rdquo; above — the system reports how many live pages cite it before you confirm.
        </div>
        <div className="rounded-md border border-[#D6DBD9] bg-[#FAFBFA] p-3">
          <b className="text-slate-800">Grain is no longer QA&apos;s problem.</b> The writer cites claim IDs inline; QA verifies IDs and hunts for unmarked assertions.
        </div>
      </div>

      {selectedClaim ? (
        <ClaimDrilldownSheet
          key={selectedClaim.id}
          scope={scope}
          claim={selectedClaim}
          open
          onOpenChange={(open) => !open && setSelectedClaim(null)}
          onConfirmed={async () => {
            if (selectedCanvasId) await loadCanvas(selectedCanvasId);
          }}
        />
      ) : null}

      <AnchorDialog
        open={anchorDialogOpen}
        onOpenChange={setAnchorDialogOpen}
        onSubmit={saveAnchor}
        initialAnchor={selectedAnchor}
      />
      <ArgumentDialog
        open={argumentDialogOpen}
        onOpenChange={setArgumentDialogOpen}
        onSubmit={addArgument}
      />
      {newClaimTarget ? (
        <NewClaimDialog
          key={`${newClaimTarget.argumentId ?? "canvas"}-${newClaimTarget.row}`}
          target={newClaimTarget}
          onOpenChange={(open) => !open && setNewClaimTarget(null)}
          onSubmit={addClaim}
        />
      ) : null}
    </>
  );
}
