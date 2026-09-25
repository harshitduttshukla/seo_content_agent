import { fireEvent, render, screen, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { CardDetailView } from "@/components/v3/content-hub/card-detail";
import { Production } from "@/components/v3/production/production";
import { V3Shell } from "@/components/v3/v3-shell";
import type { BoardCard, BoardColumnKey, ContentHubBoard } from "@/lib/api-types";
import { ApiError } from "@/lib/client-api";
import { V3API } from "@/lib/v3-api";

vi.mock("next/navigation", () => ({
  usePathname: () => "/projects/project-1/v3/production",
  useRouter: () => ({ push: vi.fn(), refresh: vi.fn() }),
}));

vi.mock("@/lib/v3-api", () => ({
  V3API: { contentHub: { board: vi.fn(), card: vi.fn() } },
}));

const scope = { organizationId: "org-1", projectId: "project-1" };

function card(id: string, state: string, column: BoardColumnKey, title: string): BoardCard {
  return {
    id, title, kind: "cluster", state, column, origin: "plan", area: null, argument: null, owner: null,
    market: "en-US", due: null, priority: 0, primary_demand: null, primary_prompt: null,
    secondary_demand_count: 0, score: null, has_qa_report: false, url: null, cms_id: null,
    published_at: null, stale_claim_count: 0, planned_at: null, is_new_after_plan_lock: false,
    revision: 1, updated_at: "2026-09-25T00:00:00Z",
  } as BoardCard;
}

const COLUMNS: [BoardColumnKey, string, BoardCard[]][] = [
  ["backlog", "Backlog", [card("c-backlog", "backlog", "backlog", "Backlog idea")]],
  ["planned", "Planned", [card("c-bundled", "bundled", "planned", "Bundled card")]],
  ["outline", "Outline", [card("c-outlined", "outlined", "outline", "Outlined card")]],
  ["draft", "Draft", [card("c-qafail", "qa_failed", "draft", "Failing card")]],
  ["review", "Review", [card("c-review", "qa_passed", "review", "Review card")]],
  ["approved", "Approved", [card("c-approved", "approved", "approved", "Approved card")]],
  ["live", "Live", [card("c-live", "live", "live", "Live page")]],
];

const board: ContentHubBoard = {
  project_id: "project-1",
  plan_locked_at: null,
  total_count: COLUMNS.length,
  columns: COLUMNS.map(([key, label, cards]) => ({ key, label, tone: "rest", count: cards.length, cards })),
  filter_options: { areas: [], kinds: [], owners: [], arguments: [], markets: [] },
};

async function renderProduction() {
  render(<Production organizationId="org-1" projectId="project-1" />);
  await screen.findByLabelText("Production work queue");
}

describe("V3 Production module", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(V3API.contentHub.board).mockResolvedValue(board);
  });

  it("renders the module header and the three tabs from the handoff", async () => {
    render(<Production organizationId="org-1" projectId="project-1" />);
    expect(screen.getByRole("heading", { level: 1, name: "Production" })).toBeInTheDocument();
    expect(screen.getByText("Module · executed")).toBeInTheDocument();
    expect(screen.getByText(/The card opened for work/)).toBeInTheDocument();
    expect(screen.getAllByRole("tab").map((t) => t.textContent)).toEqual(["Writer view", "Publish", "CLI and MCP"]);
    expect(screen.getByLabelText("Loading cards")).toBeInTheDocument();
    await screen.findByText("Bundled card");
    expect(V3API.contentHub.board).toHaveBeenCalledWith(scope);
  });

  it("queues real cards by board column and opens them in the existing writer view", async () => {
    await renderProduction();
    await screen.findByText("Bundled card");
    const queue = screen.getByLabelText("Production work queue");
    const columns = within(queue).getAllByRole("region").map((r) => r.getAttribute("aria-label"));
    expect(columns).toEqual(["Planned", "Outline", "Draft", "Review", "Approved"]);
    expect(within(queue).queryByText("Backlog idea")).not.toBeInTheDocument(); // planning, not production
    expect(within(queue).queryByText("Live page")).not.toBeInTheDocument();
    expect(within(queue).getByRole("link", { name: "Failing card" })).toHaveAttribute(
      "href",
      "/projects/project-1/v3/content-hub/c-qafail?from=production",
    );
    // Opening a card never moves it: no move or drag controls here.
    expect(within(queue).queryByRole("button")).not.toBeInTheDocument();
    expect(queue.querySelector("[draggable=true]")).toBeNull();
  });

  it("shows approved cards on Publish without any publishing action", async () => {
    await renderProduction();
    await screen.findByText("Bundled card");
    fireEvent.mouseDown(screen.getByRole("tab", { name: "Publish" }));
    fireEvent.click(screen.getByRole("tab", { name: "Publish" }));
    const approved = await screen.findByRole("region", { name: "Approved cards" });
    expect(within(approved).getByText("1 approved card")).toBeInTheDocument();
    expect(within(approved).getByRole("link", { name: "Approved card" })).toBeInTheDocument();
    expect(within(approved).queryByText("Review card")).not.toBeInTheDocument();
    expect(screen.getByText(/Nothing here publishes/)).toBeInTheDocument();
    for (const name of [/publish/i, /export/i, /cms/i, /live/i]) {
      expect(screen.queryByRole("button", { name })).not.toBeInTheDocument();
    }
  });

  it("maps CLI and MCP verbs to the UI without faking execution", async () => {
    await renderProduction();
    fireEvent.mouseDown(screen.getByRole("tab", { name: "CLI and MCP" }));
    fireEvent.click(screen.getByRole("tab", { name: "CLI and MCP" }));
    expect(await screen.findByText(/The CLI and the MCP server are not built yet/)).toBeInTheDocument();
    const rows = screen.getAllByRole("row").slice(1) as HTMLTableRowElement[];
    const byVerb = Object.fromEntries(rows.map((r) => [r.cells[0].textContent, r.cells[3].textContent]));
    expect(byVerb.qa).toBe("Writer view · Run QA");
    for (const verb of ["export", "publish", "set-cms-id"]) expect(byVerb[verb]).toBe("not available yet");
    expect(document.querySelector("pre")).toBeNull(); // no fake terminal output
    expect(screen.queryByText(/^\$ /)).not.toBeInTheDocument();
    expect(screen.queryByRole("button")).toBeNull();
  });

  it("explains a failed load instead of showing an empty queue", async () => {
    vi.mocked(V3API.contentHub.board).mockRejectedValueOnce(new ApiError("no", "PERMISSION_DENIED", "r", 403));
    render(<Production organizationId="org-1" projectId="project-1" />);
    expect(await screen.findByRole("alert")).toHaveTextContent("You do not have access to this project's cards.");
    expect(screen.queryByLabelText("Production work queue")).not.toBeInTheDocument();
  });
});

describe("V3 navigation and writer view entry", () => {
  beforeEach(() => vi.clearAllMocks());

  it("lists Production in the V3 shell next to Strategy and Content Hub", () => {
    render(
      <V3Shell projectId="project-1">
        <div />
      </V3Shell>,
    );
    const hrefs = Object.fromEntries(screen.getAllByRole("link").map((l) => [l.textContent, l.getAttribute("href")]));
    expect(hrefs.Production).toBe("/projects/project-1/v3/production");
    expect(hrefs["Content Hub"]).toBe("/projects/project-1/v3/content-hub");
    expect(hrefs.Strategy).toBe("/projects/project-1/v3/canvas");
  });

  it("returns to Production from a writer view opened there, and to the Content Hub otherwise", async () => {
    vi.mocked(V3API.contentHub.card).mockReturnValue(new Promise(() => {}));
    vi.mocked(V3API.contentHub.card).mockRejectedValueOnce(new ApiError("x", "NOT_FOUND", "r", 404));
    const { unmount } = render(<CardDetailView scope={scope} cardId="c-1" backTo="production" />);
    expect(await screen.findByRole("link", { name: "← Back to Production" })).toHaveAttribute(
      "href",
      "/projects/project-1/v3/production",
    );
    unmount();
    vi.mocked(V3API.contentHub.card).mockRejectedValueOnce(new ApiError("x", "NOT_FOUND", "r", 404));
    render(<CardDetailView scope={scope} cardId="c-1" />);
    expect(await screen.findByRole("link", { name: "← Back to Content Hub" })).toHaveAttribute(
      "href",
      "/projects/project-1/v3/content-hub",
    );
  });
});
