"use client";

import { useEffect, useState, type FormEvent } from "react";

import { Button } from "@/components/button";
import type { Area, CanvasArgument } from "@/lib/api-types";
import { V3API, type V3Scope } from "@/lib/v3-api";

const field =
  "rounded-[5px] border border-[var(--line)] bg-white px-[8px] py-[5px] text-[12.6px] text-[#12171A] focus-visible:outline-2 focus-visible:outline-[var(--teal)]";

function argumentLabel(argument: CanvasArgument): string {
  const name = argument.differentiation_pillar || argument.capability || argument.sub_problem || "Untitled";
  return `Argument ${argument.order}: ${name}`;
}

/** Roots first, each followed by its sub-areas, so the list reads as the product tree (§4.4). */
function treeOrder(areas: Area[]): Array<{ area: Area; depth: number }> {
  const children = new Map<string | null, Area[]>();
  for (const area of areas) children.set(area.parent_id, [...(children.get(area.parent_id) ?? []), area]);
  const out: Array<{ area: Area; depth: number }> = [];
  const walk = (parentId: string | null, depth: number) => {
    for (const area of children.get(parentId) ?? []) {
      out.push({ area, depth });
      walk(area.id, depth + 1);
    }
  };
  walk(null, 0);
  return out;
}

/** Areas are the canvas's product tree; demand and cards are bucketed by them before Plan. */
export function AreasPanel({
  scope,
  canvasId,
  canvasArguments,
}: {
  scope: V3Scope;
  canvasId: string;
  canvasArguments: CanvasArgument[];
}) {
  const [areas, setAreas] = useState<Area[]>([]);
  const [name, setName] = useState("");
  const [parentId, setParentId] = useState("");
  const [argumentId, setArgumentId] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    V3API.areas.list(scope, canvasId).then(
      (items) => active && setAreas(items),
      (cause: unknown) => active && setError(cause instanceof Error ? cause.message : "Areas could not be loaded."),
    );
    return () => {
      active = false;
    };
  }, [scope, canvasId]);

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!name.trim()) return;
    setSaving(true);
    setError(null);
    try {
      const created = await V3API.areas.create(scope, canvasId, {
        name: name.trim(),
        parent_id: parentId || null,
        default_argument_id: argumentId || null,
      });
      setAreas((current) => [...current, created]);
      setName("");
      setParentId("");
      setArgumentId("");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "The area could not be created.");
    } finally {
      setSaving(false);
    }
  }

  const tree = treeOrder(areas);
  const argumentNames = new Map(canvasArguments.map((argument) => [argument.id, argumentLabel(argument)]));

  return (
    <section aria-label="Areas" className="mt-4 rounded-[8px] border border-[var(--line)] bg-white p-[12px_14px]">
      <h3 className="text-[13px] font-medium">Areas · product tree</h3>
      <p className="mb-[10px] text-[12px] text-[#5C666C]">
        Where buyers search. Demand is assigned to an area before Plan groups it into cards.
      </p>
      {tree.length ? (
        <ul className="mb-[12px] grid gap-[4px] text-[12.6px]">
          {tree.map(({ area, depth }) => (
            <li key={area.id} style={{ paddingLeft: depth * 18 }}>
              {depth ? "└ " : ""}
              {area.name}
              {area.default_argument_id ? (
                <span className="text-[#8A949A]"> · {argumentNames.get(area.default_argument_id) ?? "argument"}</span>
              ) : null}
            </li>
          ))}
        </ul>
      ) : (
        <p className="mb-[12px] text-[12.6px] text-[var(--coral)]">No areas yet. Add one so demand can be planned.</p>
      )}
      <form onSubmit={(event) => void submit(event)} className="flex flex-wrap items-center gap-[8px]">
        <input
          aria-label="Area name"
          placeholder="Area name, e.g. Leak repairs"
          value={name}
          maxLength={500}
          onChange={(event) => setName(event.target.value)}
          className={`${field} w-[240px]`}
        />
        <select aria-label="Parent area" value={parentId} onChange={(event) => setParentId(event.target.value)} className={field}>
          <option value="">No parent (top level)</option>
          {tree.map(({ area, depth }) => (
            <option key={area.id} value={area.id}>
              {"— ".repeat(depth)}
              {area.name}
            </option>
          ))}
        </select>
        {canvasArguments.length ? (
          <select
            aria-label="Default argument"
            value={argumentId}
            onChange={(event) => setArgumentId(event.target.value)}
            className={field}
          >
            <option value="">No default argument</option>
            {canvasArguments.map((argument) => (
              <option key={argument.id} value={argument.id}>
                {argumentLabel(argument)}
              </option>
            ))}
          </select>
        ) : null}
        <Button type="submit" variant="outline" disabled={saving || !name.trim()}>
          {saving ? "Adding…" : "Add area"}
        </Button>
      </form>
      {error ? (
        <p role="alert" className="mt-[8px] text-[12.6px] text-[var(--coral)]">
          {error}
        </p>
      ) : null}
    </section>
  );
}
