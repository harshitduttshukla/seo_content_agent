"use client";

import { useEffect, useMemo, useState } from "react";

import { Button } from "@/components/button";
import { Card } from "@/components/card";
import { Input } from "@/components/input";
import { clientApi } from "@/lib/client-api";
import { V3API } from "@/lib/v3-api";

type HarnessMode = "outline" | "draft" | "qa" | "repair";

interface HarnessRun {
  id: string;
  name: string;
  status: string;
  score: number | null;
  prompt_version: string;
  provider: string;
  model: string;
  input_data: Record<string, unknown>;
  evaluation_data: Record<string, unknown>;
  output_data?: Record<string, unknown>;
  context_data?: Record<string, unknown>;
  error_message?: string | null;
  created_at: string;
}

export function V3ContentHarnessView({
  organizationId,
  projectId,
}: {
  organizationId: string;
  projectId: string;
}) {
  const [cards, setCards] = useState<Array<{ id: string; title: string; state: string }>>([]);
  const [runs, setRuns] = useState<HarnessRun[]>([]);
  const [cardId, setCardId] = useState("");
  const [mode, setMode] = useState<HarnessMode>("outline");
  const [model, setModel] = useState("gemini-flash-latest");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  const [selected, setSelected] = useState<HarnessRun | null>(null);

  const scope = useMemo(() => ({ organizationId, projectId }), [organizationId, projectId]);

  async function loadRuns() {
    const data = await clientApi<HarnessRun[]>(
      `/v3/content-harness/runs?project_id=${encodeURIComponent(projectId)}&limit=50`,
    );
    setRuns(data);
  }

  useEffect(() => {
    const initialLoad = window.setTimeout(() => {
      void Promise.all([
        V3API.contentHub.board(scope).then((board) => {
          const next = board.columns.flatMap((column) => column.cards);
          setCards(next);
          setCardId((current) => current || next[0]?.id || "");
        }),
        clientApi<HarnessRun[]>(
          `/v3/content-harness/runs?project_id=${encodeURIComponent(projectId)}&limit=50`,
        ).then(setRuns),
      ]).catch((caught: unknown) => setError(caught instanceof Error ? caught.message : "Could not load Harness data."));
    }, 0);
    return () => window.clearTimeout(initialLoad);
  }, [scope, projectId]);

  async function runHarness() {
    if (!cardId) return;
    setPending(true);
    setError("");
    try {
      const endpoint = mode === "outline" ? "v3-outline-runs" : mode === "draft" ? "v3-draft-runs" : "v3-production-runs";
      const body = mode === "qa" || mode === "repair"
        ? { project_id: projectId, card_id: cardId, name: `V3 ${mode.toUpperCase()} validation`, model, mode }
        : { project_id: projectId, card_id: cardId, name: `V3 ${mode} validation`, model };
      const run = await clientApi<HarnessRun>(`/v3/content-harness/${endpoint}`, {
        method: "POST",
        body: JSON.stringify(body),
      });
      setSelected(run);
      await loadRuns();
    } catch (caught: unknown) {
      setError(caught instanceof Error ? caught.message : "Harness run failed.");
    } finally {
      setPending(false);
    }
  }

  return (
    <div className="grid gap-5">
      <div>
        <p className="eyebrow">Development &amp; validation</p>
        <h1 className="text-2xl font-semibold">Content Agent Harness</h1>
        <p className="mt-1 text-sm text-[var(--muted)]">
          Runs the production bundle, prompt, generation, claim validation and QA contracts without changing the selected card.
        </p>
      </div>

      <Card className="grid gap-4 p-5 md:grid-cols-4">
        <label className="grid gap-1 text-xs font-semibold">
          Pipeline stage
          <select className="rounded-lg border p-2 text-sm" onChange={(event) => setMode(event.target.value as HarnessMode)} value={mode}>
            <option value="outline">Outline</option>
            <option value="draft">Draft</option>
            <option value="qa">QA</option>
            <option value="repair">Repair</option>
          </select>
        </label>
        <label className="grid gap-1 text-xs font-semibold md:col-span-2">
          Content card
          <select className="rounded-lg border p-2 text-sm" onChange={(event) => setCardId(event.target.value)} value={cardId}>
            {cards.map((card) => <option key={card.id} value={card.id}>{card.title} · {card.state}</option>)}
          </select>
        </label>
        <Input label="Model" onChange={(event) => setModel(event.target.value)} value={model} />
        <div className="md:col-span-4 flex items-center gap-3">
          <Button disabled={pending || !cardId} onClick={runHarness}>{pending ? "Running…" : "Run validation"}</Button>
          {error && <p className="text-sm text-red-600">{error}</p>}
        </div>
      </Card>

      {selected && (
        <Card className="p-5">
          <h2 className="font-semibold">Latest result · {selected.status}</h2>
          <p className="text-sm">Score: {selected.score ?? "—"} · {selected.provider}/{selected.model}</p>
          <pre className="mt-3 max-h-96 overflow-auto rounded-lg bg-slate-950 p-4 text-xs text-slate-100">
            {JSON.stringify({ evaluation: selected.evaluation_data, output: selected.output_data, error: selected.error_message }, null, 2)}
          </pre>
        </Card>
      )}

      <Card className="overflow-hidden p-0">
        <div className="border-b p-4 font-semibold">Run history</div>
        <div className="divide-y">
          {runs.map((run) => (
            <button className="grid w-full grid-cols-[1fr_auto_auto] gap-4 p-4 text-left text-sm hover:bg-slate-50" key={run.id} onClick={() => setSelected(run)} type="button">
              <span>{run.name}<small className="block text-[var(--muted)]">{run.prompt_version}</small></span>
              <span>{run.status}</span><span>{run.score ?? "—"}</span>
            </button>
          ))}
          {!runs.length && <p className="p-5 text-sm text-[var(--muted)]">No Harness runs yet.</p>}
        </div>
      </Card>
    </div>
  );
}
