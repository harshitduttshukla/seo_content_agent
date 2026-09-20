"use client";

import { useCallback, useEffect, useState } from "react";

import { Button } from "@/components/button";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
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
import type { DemandListResponse } from "@/lib/api-types";
import { V3API, type V3Scope } from "@/lib/v3-api";

import { CsvUploadDialog } from "./csv-upload-dialog";

export function DemandTab({ scope }: { scope: V3Scope }) {
  const [result, setResult] = useState<DemandListResponse | null>(null);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [statusFilter, setStatusFilter] = useState("all");
  const [areaId, setAreaId] = useState("");
  const [showUpload, setShowUpload] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const nextResult = await V3API.demand.list(
        scope,
        statusFilter === "all" ? undefined : statusFilter,
      );
      setError(null);
      setResult(nextResult);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Demand could not be loaded.");
    }
  }, [scope, statusFilter]);

  useEffect(() => {
    void load();
  }, [load]);

  const nodes = result?.items ?? [];
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

  async function reclassify() {
    setBusy(true);
    try {
      await V3API.demand.bulkSetPendingClassify(scope, [...selectedIds]);
      setSelectedIds(new Set());
      await load();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Demand nodes could not be updated.");
    } finally {
      setBusy(false);
    }
  }

  async function reassign() {
    setBusy(true);
    try {
      await V3API.demand.bulkReassign(scope, [...selectedIds], areaId);
      setSelectedIds(new Set());
      setAreaId("");
      await load();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Demand nodes could not be reassigned.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
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
          <Button variant="outline" size="sm" className="ml-2 bg-white" disabled={busy} onClick={() => void reclassify()}>
            Reclassify
          </Button>
          <Popover>
            <PopoverTrigger
              className="inline-flex h-8 items-center rounded-md border bg-white px-3 text-sm font-medium disabled:opacity-50"
              disabled={busy}
            >
              Reassign area
            </PopoverTrigger>
            <PopoverContent className="grid gap-3">
              <p className="text-sm font-medium">Destination area ID</p>
              <Input value={areaId} onChange={(event) => setAreaId(event.target.value)} placeholder="UUID" />
              <Button variant="primary" size="sm" disabled={!areaId} onClick={() => void reassign()}>
                Confirm reassign
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
              <TableHead>Funnel</TableHead>
              <TableHead>Status</TableHead>
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
                <TableCell>{node.text}</TableCell>
                <TableCell>{node.type}</TableCell>
                <TableCell>{node.origin}</TableCell>
                <TableCell>{node.funnel ?? "—"}</TableCell>
                <TableCell>
                  <Badge
                    variant="outline"
                    className={node.status === "discarded" ? "border-[#F0D2CC] bg-[#FBEBE8] text-[#B9463A]" : "border-[#C4DEDA] bg-[#E1EFED] text-[#15706A]"}
                  >
                    {node.status.replace("_", " ")}
                  </Badge>
                </TableCell>
              </TableRow>
            ))}
            {nodes.length === 0 ? (
              <TableRow><TableCell colSpan={6} className="py-10 text-center text-muted-foreground">No demand nodes match this view.</TableCell></TableRow>
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
