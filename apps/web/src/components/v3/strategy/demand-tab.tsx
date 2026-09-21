"use client";

import { useCallback, useEffect, useState } from "react";

import { Button } from "@/components/button";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Checkbox } from "@/components/ui/checkbox";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import type { Area, DemandListResponse } from "@/lib/api-types";
import { V3API, type V3Scope } from "@/lib/v3-api";

import { CsvUploadDialog } from "./csv-upload-dialog";

export function DemandTab({ scope }: { scope: V3Scope }) {
  const [result, setResult] = useState<DemandListResponse | null>(null);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [statusFilter, setStatusFilter] = useState("all");
  const [filters, setFilters] = useState({ origin: "", area_id: "", argument_id: "", type: "", funnel: "" });
  const [areaId, setAreaId] = useState("");
  const [argumentId, setArgumentId] = useState("");
  const [areas, setAreas] = useState<Area[]>([]);
  const [argumentsById, setArgumentsById] = useState<Array<{ id: string; label: string }>>([]);
  const [showUpload, setShowUpload] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const [nextResult, canvasList, nextAreas] = await Promise.all([
        V3API.demand.list(
          scope,
          { status: statusFilter === "all" ? "" : statusFilter, sort: "confidence_asc", ...filters },
        ),
        V3API.canvas.list(scope).catch(() => null),
        V3API.areas.list(scope),
      ]);
      const canvases = canvasList
        ? [canvasList.company_canvas, ...canvasList.product_lines].filter(
            (canvas): canvas is NonNullable<typeof canvas> => canvas !== null,
          )
        : [];
      const canvasDetails = await Promise.all(
        canvases.map((canvas) => V3API.canvas.get(scope, canvas.id)),
      );
      setError(null);
      setResult(nextResult);
      setAreas(nextAreas);
      setArgumentsById(
        canvasDetails.flatMap((canvas) =>
          canvas.arguments.map((argument) => ({
            id: argument.id,
            label: `${canvas.name} · Argument ${argument.order}: ${argument.differentiation_pillar ?? argument.capability ?? argument.sub_problem ?? argument.benefit ?? "Untitled argument"}`,
          })),
        ),
      );
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Demand could not be loaded.");
    }
  }, [scope, statusFilter, filters]);

  useEffect(() => {
    void load();
  }, [load]);

  const nodes = result?.items ?? [];
  const areaNames = new Map(areas.map((area) => [area.id, area.name]));
  const areaLabel = (area: Area): string => {
    const parent = area.parent_id ? areaNames.get(area.parent_id) : null;
    return parent ? `${parent} / ${area.name}` : area.name;
  };
  const allSelected = nodes.length > 0 && nodes.every((node) => selectedIds.has(node.id));

  function toggleAll(checked: boolean) {
    setSelectedIds(checked ? new Set(nodes.map((node) => node.id)) : new Set());
  }

  function toggleNode(id: string, checked: boolean) {
    setSelectedIds((current) => {
      const next = new Set(current);
      if (checked) next.add(id);
      else next.delete(id);
      return next;
    });
  }

  async function bulkAction(
    action: "keep" | "discard" | "reassign_area" | "set_argument",
    targetId?: string,
  ) {
    setBusy(true);
    try {
      await V3API.demand.bulkAction(scope, [...selectedIds], action, targetId);
      setSelectedIds(new Set());
      setAreaId("");
      setArgumentId("");
      await load();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Demand nodes could not be updated.");
    } finally { setBusy(false); }
  }

  return (
    <>
      <div className="mb-3 flex flex-wrap gap-2 rounded-md border border-[#F0D2CC] bg-[#FBEBE8] p-3 text-sm text-[#B9463A]"><b>H1 · review queue.</b><span>Default view: all nodes ordered by confidence, lowest first.</span><span className="ml-auto text-xs">{result?.summary.total_kept ?? 0} kept · {result?.summary.total_discarded ?? 0} discarded · {result?.summary.gsc_striking_distance_count ?? 0} GSC</span></div>
      <div className="mb-[12px] flex flex-wrap gap-[7px]">
        <Select
          value={statusFilter}
          onValueChange={(value) => value && setStatusFilter(value)}
        >
          <SelectTrigger className="w-[220px] bg-white">
            <SelectValue placeholder="Status" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">Status: all</SelectItem>
            <SelectItem value="discarded">Status: discarded</SelectItem>
            <SelectItem value="kept">Status: kept</SelectItem>
            <SelectItem value="pending">Status: pending</SelectItem>
            <SelectItem value="pending_classify">Status: pending classify</SelectItem>
          </SelectContent>
        </Select>
        {(["origin", "area_id", "argument_id", "type", "funnel"] as const).map((key) => {
          const options = key === "origin" ? ["upload", "gsc_striking_distance", "insight"] : key === "type" ? ["keyword", "prompt"] : key === "funnel" ? ["tofu", "mofu", "bofu"] : key === "area_id" ? areas.map((area) => ({ value: area.id, label: areaLabel(area) })) : [...new Set(nodes.map((node) => String(node[key] ?? "")).filter(Boolean))];
          return <Select key={key} value={filters[key] || "all"} onValueChange={(value) => setFilters((current) => ({ ...current, [key]: value === "all" ? "" : value ?? "" }))}><SelectTrigger className="w-[140px] bg-white"><SelectValue placeholder={key.replace("_id", "")} /></SelectTrigger><SelectContent><SelectItem value="all">{key.replace("_id", "")}: all</SelectItem>{options.map((option) => <SelectItem key={typeof option === "string" ? option : option.value} value={typeof option === "string" ? option : option.value}>{typeof option === "string" ? option : option.label}</SelectItem>)}</SelectContent></Select>;
        })}
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          <Badge variant="outline">{result?.summary.total_kept ?? 0} kept</Badge>
          <Badge variant="outline">{result?.summary.total_discarded ?? 0} discarded</Badge>
          <Badge variant="outline">{result?.summary.gsc_striking_distance_count ?? 0} GSC</Badge>
        </div>
        <Button variant="outline" size="sm" className="ml-auto" onClick={() => setShowUpload(true)}>
          Upload CSV
        </Button>
      </div>

      {error ? (
        <Alert variant="destructive" className="mb-3">
          <AlertTitle>Demand action failed</AlertTitle>
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      ) : null}

      {selectedIds.size > 0 ? (
        <div className="mb-[12px] flex flex-wrap items-center gap-[8px] rounded-[7px] border border-[#F0D2CC] bg-[#FBEBE8] p-[9px_13px] text-[13px] text-[#B9463A]">
          <b className="font-medium">{selectedIds.size}</b><span>selected</span>
          <Button variant="outline" size="sm" className="ml-2 bg-white" disabled={busy} onClick={() => void bulkAction("keep")}>
            Keep
          </Button>
          <Button variant="outline" size="sm" className="bg-white" disabled={busy} onClick={() => void bulkAction("discard")}>Discard</Button>
          <Popover>
            <PopoverTrigger
              className="inline-flex h-8 items-center rounded-md border bg-white px-3 text-sm font-medium disabled:opacity-50"
              disabled={busy}
            >
              Reassign area
            </PopoverTrigger>
            <PopoverContent className="grid gap-3">
              <p className="text-sm font-medium">Destination area</p>
              <Select value={areaId} onValueChange={(value) => setAreaId(value ?? "")}>
                <SelectTrigger><SelectValue placeholder="Choose an area" /></SelectTrigger>
                <SelectContent>
                  {areas.map((area) => (
                    <SelectItem key={area.id} value={area.id}>{areaLabel(area)}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <Button variant="primary" size="sm" disabled={!areaId} onClick={() => void bulkAction("reassign_area", areaId)}>
                Confirm reassign
              </Button>
            </PopoverContent>
          </Popover>
          <Popover>
            <PopoverTrigger className="inline-flex h-8 items-center rounded-md border bg-white px-3 text-sm font-medium">
              Set argument
            </PopoverTrigger>
            <PopoverContent className="grid gap-3">
              <p className="text-sm font-medium">Argument</p>
              <Select value={argumentId} onValueChange={(value) => setArgumentId(value ?? "")}>
                <SelectTrigger><SelectValue placeholder="Choose an argument" /></SelectTrigger>
                <SelectContent>
                  {argumentsById.map((argument) => (
                    <SelectItem key={argument.id} value={argument.id}>{argument.label}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <Button size="sm" disabled={!argumentId} onClick={() => void bulkAction("set_argument", argumentId)}>
                Confirm argument
              </Button>
            </PopoverContent>
          </Popover>
          <Button variant="outline" size="sm" className="ml-auto bg-white" onClick={() => setSelectedIds(new Set())}>
            Clear
          </Button>
        </div>
      ) : null}

      <div className="overflow-hidden rounded-md border bg-white">
        <Table>
          <TableHeader className="bg-slate-50">
            <TableRow>
              <TableHead className="w-[40px]">
                <Checkbox checked={allSelected} onCheckedChange={(checked) => toggleAll(checked === true)} />
              </TableHead>
              <TableHead>Text</TableHead>
              <TableHead>Type</TableHead>
              <TableHead>Origin</TableHead>
              <TableHead className="text-right">Vol</TableHead><TableHead>Area</TableHead><TableHead>Argument</TableHead><TableHead>Competitor</TableHead>
              <TableHead>Funnel</TableHead>
              <TableHead>Status</TableHead>
              <TableHead className="text-right" title="Raw score: keyword and prompt scales differ.">Score ⓘ</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {nodes.map((node) => (
              <TableRow key={node.id}>
                <TableCell>
                  <Checkbox
                    checked={selectedIds.has(node.id)}
                    onCheckedChange={(checked) => toggleNode(node.id, checked === true)}
                  />
                </TableCell>
                <TableCell>{node.text}{node.status === "discarded" ? <div className="text-xs text-muted-foreground">reason: {node.discard_reason ?? "—"} · conf {node.confidence ?? "—"}</div> : null}</TableCell>
                <TableCell>{node.type}</TableCell>
                <TableCell>{node.origin}</TableCell>
                <TableCell className="text-right">{node.type === "prompt" ? "—" : node.volume?.toLocaleString() ?? "—"}</TableCell><TableCell>{node.area_id ? areaNames.get(node.area_id) ?? "—" : "—"}</TableCell><TableCell>{node.argument_id ?? "—"}</TableCell><TableCell>{node.competitor_names?.join(", ") || "—"}</TableCell>
                <TableCell>{node.funnel ?? "—"}</TableCell>
                <TableCell>
                  <Badge
                    variant="outline"
                    className={node.status === "discarded" ? "border-[#F0D2CC] bg-[#FBEBE8] text-[#B9463A]" : "border-[#C4DEDA] bg-[#E1EFED] text-[#15706A]"}
                  >
                    {node.status.replace("_", " ")}
                  </Badge>
                </TableCell>
                <TableCell className="text-right">{node.score ?? "—"}</TableCell>
              </TableRow>
            ))}
            {nodes.length === 0 ? (
              <TableRow><TableCell colSpan={11} className="py-10 text-center text-muted-foreground">No demand nodes match this view.</TableCell></TableRow>
            ) : null}
          </TableBody>
        </Table>
      </div>

      <CsvUploadDialog
        scope={scope}
        isOpen={showUpload}
        onOpenChange={setShowUpload}
        onImported={load}
      />
    </>
  );
}
