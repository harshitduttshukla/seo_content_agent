"use client";

import { useEffect, useMemo, useRef, useState } from "react";

import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import type { BoardCard, BoardColumnKey, ContentHubBoard } from "@/lib/api-types";
import { ApiError } from "@/lib/client-api";
import { V3API, type V3Scope } from "@/lib/v3-api";

import { BoardCardView } from "../content-hub/board-card";

/**
 * Board columns worked in Production (handoff §5.1-5.2, §6): the card is opened
 * for work from Planned (bundle) through Review (G2); Approved waits for Publish.
 * Backlog is planning, not production; Live is past this module's reach.
 */
const QUEUE_COLUMNS: { key: BoardColumnKey; note: string }[] = [
  { key: "planned", note: "Build the bundle, then outline" },
  { key: "outline", note: "Waiting at G1" },
  { key: "draft", note: "Drafting, QA and repair" },
  { key: "review", note: "Waiting at G2" },
  { key: "approved", note: "Approved; waits for Publish" },
];

/** Handoff §6.5 verbs, and where each job runs in the product today. */
const VERBS: { verb: string; does: string; writes: string; today: string | null }[] = [
  { verb: "bundle", does: "Assemble and store the context bundle", writes: "bundle_ref · JOB_RUN", today: "Writer view · Build bundle" },
  { verb: "outline", does: "Generate the outline against the bundle", writes: "outline · JOB_RUN", today: "Writer view · Generate / Save outline" },
  { verb: "draft", does: "Write against the approved outline", writes: "draft vN · JOB_RUN", today: "Writer view · Generate draft" },
  { verb: "qa", does: "Run hard and soft checks", writes: "qa_report · JOB_RUN", today: "Writer view · Run QA" },
  { verb: "approve", does: "Pass the gate the card is waiting at", writes: "state · JOB_RUN", today: "Writer view · G1 / G2 Approve" },
  { verb: "send-back", does: "Return with a typed reason", writes: "feedback · state", today: "Writer view · G1 / G2 Send back" },
  { verb: "export", does: "Markdown + JSON", writes: "—", today: null },
  { verb: "publish", does: "Export and hand to the CMS tool", writes: "—", today: null },
  { verb: "set-cms-id", does: "Write back id and URL → live", writes: "—", today: null },
  { verb: "import site", does: "Sitemap → cards", writes: "content cards · JOB_RUN", today: "Strategy · Import" },
  { verb: "cards list · card show", does: "Read the board", writes: "—", today: "Content Hub · Plan board, Writer view" },
];

function describe(error: unknown): string {
  if (error instanceof ApiError && error.status === 403) return "You do not have access to this project's cards.";
  if (error instanceof ApiError && error.status === 404) return "This project was not found.";
  return error instanceof Error && error.message ? error.message : "The cards could not be loaded.";
}

function writerHref(scope: V3Scope, card: BoardCard): string {
  return `/projects/${scope.projectId}/v3/content-hub/${card.id}?from=production`;
}

function CardList({ scope, cards, empty }: { scope: V3Scope; cards: BoardCard[]; empty: string }) {
  if (!cards.length) return <p className="m-0 text-[12.4px] text-[var(--ink3)]">{empty}</p>;
  return (
    <ul className="m-0 grid list-none gap-[8px] p-0">
      {cards.map((card) => (
        <li key={card.id}>
          <BoardCardView card={card} href={writerHref(scope, card)} draggable={false} busy={false} actions={{}} />
        </li>
      ))}
    </ul>
  );
}

function WorkQueue({ scope, board }: { scope: V3Scope; board: ContentHubBoard }) {
  const columns = new Map(board.columns.map((c) => [c.key, c]));
  return (
    <div className="grid grid-cols-1 gap-[13px] md:grid-cols-2 xl:grid-cols-5" aria-label="Production work queue">
      {QUEUE_COLUMNS.map(({ key, note }) => {
        const column = columns.get(key);
        if (!column) return null;
        return (
          <section key={key} aria-label={column.label} className="min-w-0 rounded-[8px] border border-[var(--line)] bg-[#F7F8F7] p-[10px]">
            <header className="mb-[8px]">
              <h3 className="m-0 flex items-center gap-[6px] text-[13px] font-medium">
                {column.label} <span className="text-[11.5px] text-[var(--ink3)]">{column.count}</span>
              </h3>
              <div className="text-[11.2px] text-[var(--ink3)]">{note}</div>
            </header>
            <CardList scope={scope} cards={column.cards} empty="No cards." />
          </section>
        );
      })}
    </div>
  );
}

function PublishTab({ scope, board }: { scope: V3Scope; board: ContentHubBoard }) {
  const approved = board.columns.find((c) => c.key === "approved")?.cards ?? [];
  return (
    <div className="grid gap-[13px] lg:grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)]">
      <section aria-label="Approved cards" className="rounded-[8px] border border-[var(--line)] bg-white p-[13px]">
        <h3 className="m-[0_0_4px] text-[13px] font-medium">
          {approved.length} approved card{approved.length === 1 ? "" : "s"}
        </h3>
        <p className="m-[0_0_10px] text-[12.4px] text-[#5C666C]">
          These passed G2. Nothing here publishes: export, the CMS hand-off and the move to Live are not built yet.
        </p>
        <CardList scope={scope} cards={approved} empty="No approved cards yet." />
      </section>
      <section aria-label="How publishing will work" className="rounded-[8px] border border-[var(--line)] bg-white p-[13px] text-[12.4px] text-[#5C666C]">
        <h3 className="m-[0_0_6px] text-[13px] font-medium text-[#12171A]">Not available yet</h3>
        <p className="m-[0_0_6px]">
          Publish produces the export (Markdown + JSON: title, meta, slug, headings, links, schema, claim IDs) with claim markers
          stripped, and hands it to the CMS tool. The returned CMS id and URL move the card to Live.
        </p>
        <p className="m-0">No publish adapter is configured, so no card can be published, exported or given a CMS id from here.</p>
      </section>
    </div>
  );
}

function CliTab() {
  return (
    <section aria-label="CLI and MCP" className="rounded-[8px] border border-[var(--line)] bg-white p-[13px]">
      <h3 className="m-[0_0_4px] text-[13px] font-medium">Same jobs, three surfaces</h3>
      <p className="m-[0_0_10px] text-[12.4px] text-[#5C666C]">
        The CLI and the MCP server are not built yet. Each job below already runs from the web UI and writes a JOB_RUN; the table
        shows where. When the CLI and MCP arrive they call the same services, and <code>approve</code> will need a per-user key.
      </p>
      <table className="w-full border-collapse text-left text-[12.4px]">
        <thead>
          <tr className="border-b border-[var(--line2)] text-[11.5px] text-[var(--ink3)]">
            <th className="py-[5px] pr-[10px] font-normal">Verb</th>
            <th className="py-[5px] pr-[10px] font-normal">Does</th>
            <th className="py-[5px] pr-[10px] font-normal">Writes</th>
            <th className="py-[5px] font-normal">In the product today</th>
          </tr>
        </thead>
        <tbody>
          {VERBS.map((v) => (
            <tr key={v.verb} className="border-b border-[var(--line2)] last:border-b-0">
              <td className="py-[5px] pr-[10px] font-mono text-[12px]">{v.verb}</td>
              <td className="py-[5px] pr-[10px]">{v.does}</td>
              <td className="py-[5px] pr-[10px] text-[var(--ink3)]">{v.writes}</td>
              <td className="py-[5px]">
                {v.today ?? <span className="chip r">not available yet</span>}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}

export function Production({ organizationId, projectId }: { organizationId: string; projectId: string }) {
  const scope = useMemo<V3Scope>(() => ({ organizationId, projectId }), [organizationId, projectId]);
  const [board, setBoard] = useState<ContentHubBoard | null>(null);
  const [error, setError] = useState<string | null>(null);
  const seq = useRef(0);

  useEffect(() => {
    const current = ++seq.current;
    V3API.contentHub.board(scope).then(
      (next) => current === seq.current && setBoard(next),
      (cause: unknown) => current === seq.current && setError(describe(cause)),
    );
  }, [scope]);

  return (
    <section className="animate-in fade-in duration-150">
      <div className="min-w-[280px]">
        <div className="mb-[6px] text-[11.5px] text-[#8A949A]">Module · executed</div>
        <h1 className="m-0 font-serif text-[25px] font-medium tracking-tight text-[#12171A]">Production</h1>
        <p className="m-[5px_0_0] max-w-[74ch] text-[13.4px] text-[#5C666C]">
          The card opened for work. This stays the review surface; the CLI and MCP will run the same jobs once they are built.
        </p>
      </div>
      <Tabs defaultValue="writer" className="mt-[18px]">
        <TabsList variant="line" className="w-full justify-start rounded-none border-b border-[#D6DBD9] bg-transparent p-0">
          <TabsTrigger value="writer">Writer view</TabsTrigger>
          <TabsTrigger value="publish">Publish</TabsTrigger>
          <TabsTrigger value="cli">CLI and MCP</TabsTrigger>
        </TabsList>
        {error ? (
          <p role="alert" className="mt-[14px] text-sm text-[var(--coral)]">{error}</p>
        ) : !board ? (
          <p aria-label="Loading cards" className="mt-[14px] h-[220px] animate-pulse rounded-[8px] bg-[#EDF0EF]" />
        ) : (
          <>
            <TabsContent value="writer" className="mt-[18px]">
              <p className="m-[0_0_12px] text-[12.6px] text-[#5C666C]">
                Open a card to work on it in the writer view: context, outline and draft, checks and gates.
              </p>
              <WorkQueue scope={scope} board={board} />
            </TabsContent>
            <TabsContent value="publish" className="mt-[18px]">
              <PublishTab scope={scope} board={board} />
            </TabsContent>
          </>
        )}
        <TabsContent value="cli" className="mt-[18px]">
          <CliTab />
        </TabsContent>
      </Tabs>
    </section>
  );
}
