"use client";

import { useState } from "react";

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
import type { DemandImportItem } from "@/lib/api-types";
import { V3API, type V3Scope } from "@/lib/v3-api";

interface CsvUploadDialogProps {
  scope: V3Scope;
  isOpen: boolean;
  onOpenChange: (open: boolean) => void;
  onImported: () => Promise<void>;
}

function splitCsvLine(line: string): string[] {
  const values: string[] = [];
  let current = "";
  let quoted = false;
  for (let index = 0; index < line.length; index += 1) {
    const character = line[index];
    if (character === '"' && line[index + 1] === '"' && quoted) {
      current += '"';
      index += 1;
    } else if (character === '"') {
      quoted = !quoted;
    } else if (character === "," && !quoted) {
      values.push(current.trim());
      current = "";
    } else {
      current += character;
    }
  }
  values.push(current.trim());
  return values;
}

function parseOptionalNumber(value: string, row: number, column: string): number | null {
  if (!value) return null;
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) {
    throw new Error(`Row ${row}: ${column} must be a number.`);
  }
  return parsed;
}

function parseCsv(source: string): DemandImportItem[] {
  const lines = source.split(/\r?\n/).filter((line) => line.trim());
  if (lines.length < 2) throw new Error("CSV must include a header and at least one row.");
  const headers = splitCsvLine(lines[0]).map((header) => header.toLowerCase());
  const textIndex = headers.indexOf("text");
  const typeIndex = headers.indexOf("type");
  if (textIndex < 0 || typeIndex < 0) throw new Error("CSV headers must include text and type.");
  const volumeIndex = headers.indexOf("volume");
  const countryIndex = headers.indexOf("country");
  const areaIndex = headers.indexOf("area");
  const funnelIndex = headers.indexOf("funnel");
  const originIndex = headers.indexOf("origin");
  const competitorIndex = headers.indexOf("competitor");
  const confidenceIndex = headers.indexOf("confidence");
  const scoreIndex = headers.indexOf("score");
  const statusIndex = headers.indexOf("status");
  return lines.slice(1).map((line, rowIndex) => {
    const values = splitCsvLine(line);
    const type = values[typeIndex]?.toLowerCase();
    if (type !== "keyword" && type !== "prompt") {
      throw new Error(`Row ${rowIndex + 2}: type must be keyword or prompt.`);
    }
    const text = values[textIndex]?.trim();
    if (!text) throw new Error(`Row ${rowIndex + 2}: text is required.`);
    const row = rowIndex + 2;
    const volume = parseOptionalNumber(volumeIndex >= 0 ? values[volumeIndex] : "", row, "volume");
    if (volume !== null && (!Number.isInteger(volume) || volume < 0)) {
      throw new Error(`Row ${row}: volume must be a non-negative whole number.`);
    }
    const funnelText = funnelIndex >= 0 ? values[funnelIndex]?.toLowerCase() : "";
    if (funnelText && !["tofu", "mofu", "bofu"].includes(funnelText)) {
      throw new Error(`Row ${row}: funnel must be tofu, mofu, or bofu.`);
    }
    const statusText = statusIndex >= 0 ? values[statusIndex]?.toLowerCase() : "";
    if (statusText && !["pending", "kept", "discarded", "pending_classify"].includes(statusText)) {
      throw new Error(`Row ${row}: status must be pending, kept, discarded, or pending_classify.`);
    }
    return {
      text,
      type,
      volume,
      country: countryIndex >= 0 ? values[countryIndex]?.toUpperCase() || null : null,
      area: areaIndex >= 0 ? values[areaIndex]?.trim() || null : null,
      funnel: (funnelText || null) as DemandImportItem["funnel"],
      origin: (originIndex >= 0 ? values[originIndex]?.toLowerCase() : "upload") as DemandImportItem["origin"],
      competitor: competitorIndex >= 0 ? values[competitorIndex]?.trim() || null : null,
      confidence: parseOptionalNumber(confidenceIndex >= 0 ? values[confidenceIndex] : "", row, "confidence"),
      score: parseOptionalNumber(scoreIndex >= 0 ? values[scoreIndex] : "", row, "score"),
      status: (statusText || "pending") as DemandImportItem["status"],
    };
  });
}

export function CsvUploadDialog({ scope, isOpen, onOpenChange, onImported }: CsvUploadDialogProps) {
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function upload() {
    if (!file) return;
    setBusy(true);
    setError(null);
    try {
      const items = parseCsv(await file.text());
      await V3API.demand.importCsv(scope, items);
      await onImported();
      onOpenChange(false);
      setFile(null);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "CSV import failed.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Dialog open={isOpen} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[480px]">
        <DialogHeader>
          <DialogTitle>Upload demand CSV</DialogTitle>
          <DialogDescription>
            Required headers: text, type. Optional: area (exact name or UUID), origin, volume, country,
            funnel, competitor, confidence, score, status.
          </DialogDescription>
        </DialogHeader>
        <label className="grid cursor-pointer gap-2 rounded-[8px] border border-dashed border-[#D6DBD9] bg-[#FAFBFA] p-8 text-center">
          <span className="text-[13px] text-[#8A949A]">{file?.name ?? "Choose a CSV file"}</span>
          <input
            className="sr-only"
            type="file"
            accept=".csv,text/csv"
            onChange={(event) => setFile(event.target.files?.[0] ?? null)}
          />
        </label>
        {error ? (
          <Alert variant="destructive"><AlertTitle>Import rejected</AlertTitle><AlertDescription>{error}</AlertDescription></Alert>
        ) : null}
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>Cancel</Button>
          <Button variant="primary" disabled={!file || busy} onClick={() => void upload()}>
            {busy ? "Importing…" : "Import"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
