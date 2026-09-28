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
import type { Area, DemandImportItem } from "@/lib/api-types";
import { V3API, type V3Scope } from "@/lib/v3-api";

interface CsvUploadDialogProps {
  scope: V3Scope;
  isOpen: boolean;
  onOpenChange: (open: boolean) => void;
  onImported: () => Promise<void>;
  /** Project areas, so every row can be put in one area when the CSV has no area column. */
  areas?: Area[];
}

export type DemandField =
  | "text"
  | "type"
  | "volume"
  | "country"
  | "area"
  | "funnel"
  | "origin"
  | "competitor"
  | "confidence"
  | "score"
  | "status";

export const FIELDS: Array<{ key: DemandField; label: string; required?: boolean; aliases: string[] }> = [
  { key: "text", label: "Keyword or prompt", required: true, aliases: ["text", "keyword", "query", "search term", "prompt", "term"] },
  { key: "type", label: "Type", required: true, aliases: ["type", "kind"] },
  { key: "volume", label: "Volume", aliases: ["volume", "search volume", "avg. monthly searches", "monthly searches", "sv"] },
  { key: "country", label: "Country", aliases: ["country", "location", "market"] },
  { key: "area", label: "Area", aliases: ["area", "topic", "category"] },
  { key: "funnel", label: "Funnel", aliases: ["funnel", "stage"] },
  { key: "origin", label: "Origin", aliases: ["origin", "source"] },
  { key: "competitor", label: "Competitor", aliases: ["competitor", "competitors"] },
  { key: "confidence", label: "Confidence", aliases: ["confidence"] },
  { key: "score", label: "Score", aliases: ["score"] },
  { key: "status", label: "Status", aliases: ["status"] },
];

/** A field reads a CSV column (`col:`), takes one value for every row (`all:`), or is left out (""). */
export type FieldChoice = string;
export type Choices = Record<DemandField, FieldChoice>;

export function splitCsvLine(line: string): string[] {
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

export function readCsv(source: string): { headers: string[]; rows: string[][] } {
  const lines = source.replace(/^﻿/, "").split(/\r?\n/).filter((line) => line.trim());
  if (lines.length < 2) throw new Error("CSV must include a header and at least one row.");
  return { headers: splitCsvLine(lines[0]), rows: lines.slice(1).map(splitCsvLine) };
}

/** Saved mapping first, then a header whose name matches a known alias. */
export function initialChoices(headers: string[], saved: Record<string, string>): Choices {
  const lower = headers.map((header) => header.toLowerCase());
  const choices = {} as Choices;
  for (const field of FIELDS) {
    const savedHeader = saved[field.key];
    const index = savedHeader && headers.includes(savedHeader) ? headers.indexOf(savedHeader) : lower.findIndex((h) => field.aliases.includes(h));
    choices[field.key] = index >= 0 ? `col:${headers[index]}` : "";
  }
  if (!choices.type) choices.type = "all:keyword";
  return choices;
}

/** The header mapping that is stored for the next upload; per-row constants are not. */
export function columnMapping(choices: Choices): Record<string, string> {
  return Object.fromEntries(
    Object.entries(choices)
      .filter(([, choice]) => choice.startsWith("col:"))
      .map(([field, choice]) => [field, choice.slice(4)]),
  );
}

function parseOptionalNumber(value: string, row: number, column: string): number | null {
  if (!value) return null;
  const parsed = Number(value.replace(/,/g, ""));
  if (!Number.isFinite(parsed)) throw new Error(`Row ${row}: ${column} must be a number.`);
  return parsed;
}

export function buildItems(headers: string[], rows: string[][], choices: Choices): DemandImportItem[] {
  if (!choices.text) throw new Error("Choose the column that holds the keyword or prompt.");
  const value = (field: DemandField, cells: string[]): string => {
    const choice = choices[field];
    if (choice.startsWith("all:")) return choice.slice(4);
    if (choice.startsWith("col:")) return cells[headers.indexOf(choice.slice(4))]?.trim() ?? "";
    return "";
  };
  return rows.map((cells, index) => {
    const row = index + 2;
    const text = value("text", cells);
    if (!text) throw new Error(`Row ${row}: text is required.`);
    const type = value("type", cells).toLowerCase();
    if (type !== "keyword" && type !== "prompt") throw new Error(`Row ${row}: type must be keyword or prompt.`);
    const volume = parseOptionalNumber(value("volume", cells), row, "volume");
    if (volume !== null && (!Number.isInteger(volume) || volume < 0)) {
      throw new Error(`Row ${row}: volume must be a non-negative whole number.`);
    }
    const funnel = value("funnel", cells).toLowerCase();
    if (funnel && !["tofu", "mofu", "bofu"].includes(funnel)) throw new Error(`Row ${row}: funnel must be tofu, mofu, or bofu.`);
    const status = value("status", cells).toLowerCase();
    if (status && !["pending", "kept", "discarded", "pending_classify"].includes(status)) {
      throw new Error(`Row ${row}: status must be pending, kept, discarded, or pending_classify.`);
    }
    return {
      text,
      type,
      volume,
      country: value("country", cells).toUpperCase() || null,
      area: value("area", cells) || null,
      funnel: (funnel || null) as DemandImportItem["funnel"],
      origin: (value("origin", cells).toLowerCase() || "upload") as DemandImportItem["origin"],
      competitor: value("competitor", cells) || null,
      confidence: parseOptionalNumber(value("confidence", cells), row, "confidence"),
      score: parseOptionalNumber(value("score", cells), row, "score"),
      status: (status || "pending") as DemandImportItem["status"],
    };
  });
}

const select =
  "w-full rounded-[5px] border border-[var(--line)] bg-white px-[7px] py-[4px] text-[12.6px] text-[#12171A] focus-visible:outline-2 focus-visible:outline-[var(--teal)]";

export function CsvUploadDialog({ scope, isOpen, onOpenChange, onImported, areas = [] }: CsvUploadDialogProps) {
  const [file, setFile] = useState<File | null>(null);
  const [csv, setCsv] = useState<{ headers: string[]; rows: string[][] } | null>(null);
  const [choices, setChoices] = useState<Choices | null>(null);
  const [saved, setSaved] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!isOpen) return;
    let active = true;
    V3API.demand.csvMapping(scope).then(
      (result) => active && setSaved(result.column_mapping),
      () => undefined, // No saved mapping is not an error; aliases still match.
    );
    return () => {
      active = false;
    };
  }, [isOpen, scope]);

  function reset() {
    setFile(null);
    setCsv(null);
    setChoices(null);
    setError(null);
  }

  async function choose(next: File | null) {
    reset();
    setFile(next);
    if (!next) return;
    try {
      const parsed = readCsv(await next.text());
      setCsv(parsed);
      setChoices(initialChoices(parsed.headers, saved));
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "The CSV could not be read.");
    }
  }

  async function upload() {
    if (!csv || !choices) return;
    setBusy(true);
    setError(null);
    try {
      const items = buildItems(csv.headers, csv.rows, choices);
      await V3API.demand.importCsv(scope, items, columnMapping(choices));
      await onImported();
      onOpenChange(false);
      reset();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "CSV import failed.");
    } finally {
      setBusy(false);
    }
  }

  const constants: Partial<Record<DemandField, Array<[string, string]>>> = {
    type: [["all:keyword", "All rows: keyword"], ["all:prompt", "All rows: prompt"]],
    area: areas.map((area) => [`all:${area.id}`, `All rows: ${area.name}`]),
  };

  return (
    <Dialog
      open={isOpen}
      onOpenChange={(open) => {
        if (!open) reset();
        onOpenChange(open);
      }}
    >
      <DialogContent className="sm:max-w-[560px]">
        <DialogHeader>
          <DialogTitle>Upload demand CSV</DialogTitle>
          <DialogDescription>
            Choose a CSV from any keyword tool, then match its columns. Your matching is saved for the next upload.
          </DialogDescription>
        </DialogHeader>
        <label className="grid cursor-pointer gap-2 rounded-[8px] border border-dashed border-[#D6DBD9] bg-[#FAFBFA] p-6 text-center">
          <span className="text-[13px] text-[#8A949A]">{file?.name ?? "Choose a CSV file"}</span>
          <input
            className="sr-only"
            type="file"
            accept=".csv,text/csv"
            onChange={(event) => void choose(event.target.files?.[0] ?? null)}
          />
        </label>
        {csv && choices ? (
          <div aria-label="Column mapping" role="group" className="grid gap-[6px]">
            <p className="text-[12.6px] text-[#5C666C]">
              {csv.rows.length} row{csv.rows.length === 1 ? "" : "s"} found. Match each field to a column:
            </p>
            <div className="grid max-h-[300px] grid-cols-[150px_1fr] items-center gap-x-[10px] gap-y-[6px] overflow-y-auto pr-1">
              {FIELDS.map((field) => (
                <label key={field.key} className="contents">
                  <span className="text-[12.6px]">
                    {field.label}
                    {field.required ? <span className="text-[var(--coral)]"> *</span> : null}
                  </span>
                  <select
                    aria-label={field.label}
                    className={select}
                    value={choices[field.key]}
                    onChange={(event) => setChoices({ ...choices, [field.key]: event.target.value })}
                  >
                    {field.key !== "type" ? <option value="">{field.required ? "Choose a column" : "Not in this file"}</option> : null}
                    {(constants[field.key] ?? []).map(([value, text]) => (
                      <option key={value} value={value}>
                        {text}
                      </option>
                    ))}
                    {csv.headers.map((header) => (
                      <option key={header} value={`col:${header}`}>
                        Column: {header}
                      </option>
                    ))}
                  </select>
                </label>
              ))}
            </div>
            {!choices.area && areas.length ? (
              <p className="text-[12px] text-[#8A949A]">Rows without an area can be assigned one later with Reassign area.</p>
            ) : null}
          </div>
        ) : null}
        {error ? (
          <Alert variant="destructive"><AlertTitle>Import rejected</AlertTitle><AlertDescription>{error}</AlertDescription></Alert>
        ) : null}
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>Cancel</Button>
          <Button variant="primary" disabled={!csv || !choices?.text || busy} onClick={() => void upload()}>
            {busy ? "Importing…" : "Import"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
