"use client";

import { useEffect, useState } from "react";

import { Button } from "@/components/button";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import type {
  CanvasAnchorInput,
  CanvasAnchorType,
  CanvasArgumentInput,
  CanvasClaimInput,
} from "@/lib/api-types";

const ANCHOR_OPTIONS: Array<{ value: CanvasAnchorType; label: string }> = [
  { value: "company", label: "Company" },
  { value: "persona", label: "Persona" },
  { value: "use_case", label: "Use case" },
  { value: "alternative", label: "Alternative" },
  { value: "category", label: "Category" },
];

export interface NewClaimTarget {
  row: string;
  label: string;
  argumentId?: string;
  initialText?: string;
}

export function AnchorDialog({
  open,
  onOpenChange,
  onSubmit,
  initialAnchor,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSubmit: (data: CanvasAnchorInput) => Promise<void>;
  initialAnchor?: CanvasAnchorInput | null;
}) {
  const [anchorType, setAnchorType] = useState<CanvasAnchorType>(initialAnchor?.anchor_type ?? "company");
  const [text, setText] = useState(initialAnchor?.text ?? "");
  const [primary, setPrimary] = useState(initialAnchor?.primary ?? false);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (initialAnchor) {
      setAnchorType(initialAnchor.anchor_type);
      setText(initialAnchor.text);
      setPrimary(initialAnchor.primary);
    } else {
      setAnchorType("company");
      setText("");
      setPrimary(false);
    }
  }, [initialAnchor, open]);

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSaving(true);
    try {
      await onSubmit({ anchor_type: anchorType, text, primary });
      setText("");
      setPrimary(false);
      onOpenChange(false);
    } finally {
      setSaving(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <form onSubmit={(event) => void submit(event)} className="grid gap-4">
          <DialogHeader>
            <DialogTitle>Add anchor</DialogTitle>
            <DialogDescription>Set one of the five positioning anchors.</DialogDescription>
          </DialogHeader>
          <label className="grid gap-1 text-sm font-medium">
            Anchor
            <select
              className="h-8 rounded-lg border bg-white px-2.5 text-sm"
              value={anchorType}
              onChange={(event) => setAnchorType(event.target.value as CanvasAnchorType)}
            >
              {ANCHOR_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>{option.label}</option>
              ))}
            </select>
          </label>
          <label className="grid gap-1 text-sm font-medium">
            Text
            <Input value={text} onChange={(event) => setText(event.target.value)} autoFocus />
          </label>
          <label className="flex items-center gap-2 text-sm font-medium">
            <Checkbox checked={primary} onCheckedChange={setPrimary} />
            Primary anchor
          </label>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>Cancel</Button>
            <Button type="submit" disabled={saving || !text.trim()}>
              {saving ? "Saving…" : "Save anchor"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

export function NewClaimDialog({
  target,
  onOpenChange,
  onSubmit,
}: {
  target: NewClaimTarget | null;
  onOpenChange: (open: boolean) => void;
  onSubmit: (data: CanvasClaimInput) => Promise<void>;
}) {
  const activeTarget = target;
  const [text, setText] = useState(activeTarget?.initialText ?? "");
  const [evidence, setEvidence] = useState("");
  const [saving, setSaving] = useState(false);

  if (!activeTarget) return null;
  const { row, label, argumentId } = activeTarget;

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSaving(true);
    try {
      await onSubmit({
        row,
        text,
        evidence,
        argument_id: argumentId ?? null,
      });
      onOpenChange(false);
    } finally {
      setSaving(false);
    }
  }

  return (
    <Dialog open onOpenChange={onOpenChange}>
      <DialogContent>
        <form onSubmit={(event) => void submit(event)} className="grid gap-4">
          <DialogHeader>
            <DialogTitle>Add {label}</DialogTitle>
            <DialogDescription>This creates an unapproved claim at version 1.</DialogDescription>
          </DialogHeader>
          <label className="grid gap-1 text-sm font-medium">
            Claim text
            <textarea
              className="min-h-[120px] rounded-md border bg-white p-3 text-sm font-normal"
              value={text}
              onChange={(event) => setText(event.target.value)}
              autoFocus
            />
          </label>
          <label className="grid gap-1 text-sm font-medium">
            Evidence (optional)
            <textarea
              className="min-h-[80px] rounded-md border bg-white p-3 text-sm font-normal"
              value={evidence}
              onChange={(event) => setEvidence(event.target.value)}
            />
          </label>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>Cancel</Button>
            <Button type="submit" disabled={saving || !text.trim()}>
              {saving ? "Saving…" : "Create claim"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

export function ArgumentDialog({
  open,
  onOpenChange,
  onSubmit,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSubmit: (data: CanvasArgumentInput) => Promise<void>;
}) {
  const [fields, setFields] = useState<CanvasArgumentInput>({
    sub_problem: "",
    differentiation_pillar: "",
    capability: "",
    features: [],
    benefit: "",
  });
  const [featuresText, setFeaturesText] = useState("");
  const [saving, setSaving] = useState(false);

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSaving(true);
    try {
      await onSubmit({
        ...fields,
        features: featuresText.split("\n").map((feature) => feature.trim()).filter(Boolean),
      });
      setFields({ sub_problem: "", differentiation_pillar: "", capability: "", features: [], benefit: "" });
      setFeaturesText("");
      onOpenChange(false);
    } finally {
      setSaving(false);
    }
  }

  const field = (name: keyof Omit<CanvasArgumentInput, "features">, label: string) => (
    <label className="grid gap-1 text-sm font-medium">
      {label}
      <textarea
        className="min-h-[64px] rounded-md border bg-white p-2 text-sm font-normal"
        value={fields[name]}
        onChange={(event) => setFields((current) => ({ ...current, [name]: event.target.value }))}
      />
    </label>
  );

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[calc(100vh-2rem)] overflow-y-auto sm:max-w-[520px]">
        <form onSubmit={(event) => void submit(event)} className="grid gap-3">
          <DialogHeader>
            <DialogTitle>Add argument column</DialogTitle>
            <DialogDescription>Filled fields each create an unapproved v1 claim.</DialogDescription>
          </DialogHeader>
          {field("sub_problem", "Sub-problem")}
          {field("differentiation_pillar", "Differentiation pillar")}
          {field("capability", "Capability")}
          <label className="grid gap-1 text-sm font-medium">
            Features (one per line)
            <textarea
              className="min-h-[64px] rounded-md border bg-white p-2 text-sm font-normal"
              value={featuresText}
              onChange={(event) => setFeaturesText(event.target.value)}
            />
          </label>
          {field("benefit", "Benefit")}
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>Cancel</Button>
            <Button type="submit" disabled={saving}>{saving ? "Adding…" : "Add column"}</Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
