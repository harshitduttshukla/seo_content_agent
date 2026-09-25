import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ContentHub } from "@/components/v3/content-hub/content-hub";
import { PlanBoard, canDrop } from "@/components/v3/content-hub/plan-board";
import type { BoardCard, BoardColumnKey, BoardColumnView, ContentHubBoard } from "@/lib/api-types";
import { V3API } from "@/lib/v3-api";

vi.mock("@/lib/v3-api", () => ({
  V3API: {
    contentHub: { board: vi.fn(), moveCard: vi.fn(), reorderPlanned: vi.fn() },
    planLock: { lock: vi.fn() },
  },
}));

const scope = { organizationId: "org-1", projectId: "project-1" };

const COLUMNS: [BoardColumnKey, string, BoardColumnView["tone"]][] = [
  ["backlog", "Backlog", "rest"],
  ["planned", "Planned", "rest"],
  ["outline", "Outline", "system"],
  ["draft", "Draft", "system"],
  ["review", "Review", "human"],
  ["approved", "Approved", "rest"],
  ["live", "Live", "rest"],
];

const STATE_COLUMN: Record<string, BoardColumnKey> = {
  backlog: "backlog",
  planned: "planned",
  bundled: "planned",
  outlined: "outline",
  drafting: "draft",
  qa_failed: "draft",
  qa_passed: "review",
  approved: "approved",
  live: "live",
};

function card(id: string, state: string, overrides: Partial<BoardCard> = {}): BoardCard {
  return {
    id,
    title: `Card ${id}`,
    kind: "cluster",
    state,
    column: STATE_COLUMN[state],
    origin: "plan",
    area: null,
    argument: null,
    owner: null,
    market: "en-GB",
    due: null,
    priority: 0,
    primary_demand: null,
    primary_prompt: null,
    secondary_demand_count: 0,
    score: null,
    has_qa_report: false,
    url: null,
    cms_id: null,
    published_at: null,
    stale_claim_count: 0,
    planned_at: null,
    is_new_after_plan_lock: false,
    revision: 1,
    updated_at: "2026-09-24T10:00:00Z",
    ...overrides,
  };
}

function board(cards: BoardCard[], overrides: Partial<ContentHubBoard> = {}): ContentHubBoard {
  return {
    project_id: "project-1",
    plan_locked_at: null,
    total_count: cards.length,
    columns: COLUMNS.map(([key, label, tone]) => {
      const inColumn = cards.filter((item) => item.column === key);
      return { key, label, tone, count: inColumn.length, cards: inColumn };
    }),
    filter_options: {
      areas: [{ id: "area-1", name: "Landed cost" }],
      kinds: ["cluster", "compare"],
      owners: [{ id: "user-1", name: "Patrice" }],
      arguments: [{ id: "arg-1", name: "Deemed supplier" }],
      markets: ["en-GB", "fr-FR"],
    },
    ...overrides,
  };
}

const column = (key: BoardColumnKey) => screen.getByTestId(`column-${key}`);

async function renderBoard(data: ContentHubBoard) {
  vi.mocked(V3API.contentHub.board).mockResolvedValue(data);
  render(<PlanBoard scope={scope} />);
  await screen.findByTestId("column-backlog");
}

describe("V3 Content Hub plan board", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders the Content Hub header, tabs and board", async () => {
    vi.mocked(V3API.contentHub.board).mockResolvedValue(board([]));
    render(<ContentHub organizationId="org-1" projectId="project-1" />);
    expect(screen.getByRole("heading", { name: "Content Hub" })).toBeInTheDocument();
    expect(screen.getByText("Module · planned")).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "Plan board" })).toBeInTheDocument();
    expect(await screen.findByTestId("column-live")).toBeInTheDocument();
    expect(V3API.contentHub.board).toHaveBeenCalledWith(scope, {});
  });

  it("shows seven columns with counts, qa_passed in Review and qa_failed in Draft", async () => {
    await renderBoard(
      board([
        card("b1", "backlog"),
        card("p1", "planned"),
        card("p2", "bundled"),
        card("o1", "outlined"),
        card("d1", "drafting"),
        card("d2", "qa_failed"),
        card("r1", "qa_passed"),
        card("a1", "approved"),
        card("l1", "live"),
      ]),
    );
    expect(screen.getAllByRole("region").map((region) => region.getAttribute("aria-label"))).toEqual(
      COLUMNS.map(([, label]) => `${label} column`),
    );
    expect(screen.getByTestId("count-planned")).toHaveTextContent("2");
    expect(screen.getByTestId("count-draft")).toHaveTextContent("2");
    expect(screen.getByTestId("count-review")).toHaveTextContent("1");
    expect(within(column("review")).getByText("Card r1")).toBeInTheDocument();
    expect(within(column("draft")).getByText("Card d2")).toBeInTheDocument();
    expect(within(column("draft")).getByText("QA fail")).toBeInTheDocument();
    expect(within(column("review")).getByRole("heading").className).toContain("coral");
    expect(within(column("outline")).getByRole("heading").className).toContain("teal");
  });

  it("moves Backlog → Planned with the card's revision and reloads", async () => {
    await renderBoard(board([card("b1", "backlog", { revision: 4 })]));
    vi.mocked(V3API.contentHub.moveCard).mockResolvedValue(card("b1", "planned", { revision: 5 }));
    vi.mocked(V3API.contentHub.board).mockResolvedValue(board([card("b1", "planned", { revision: 5 })]));

    fireEvent.click(screen.getByRole("button", { name: "Move Card b1 to Planned" }));

    expect(within(column("planned")).getByText("Card b1")).toBeInTheDocument(); // optimistic
    await waitFor(() => expect(V3API.contentHub.moveCard).toHaveBeenCalledWith(scope, "b1", "planned", 4));
    await waitFor(() => expect(V3API.contentHub.board).toHaveBeenCalledTimes(2));
    expect(screen.getByTestId("count-planned")).toHaveTextContent("1");
  });

  it("moves Planned → Backlog, but offers no Backlog move for a bundled card", async () => {
    await renderBoard(board([card("p1", "planned"), card("p2", "bundled")]));
    vi.mocked(V3API.contentHub.moveCard).mockResolvedValue(card("p1", "backlog"));

    expect(screen.queryByRole("button", { name: "Move Card p2 to Backlog" })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Move Card p1 to Backlog" }));
    await waitFor(() => expect(V3API.contentHub.moveCard).toHaveBeenCalledWith(scope, "p1", "backlog", 1));
  });

  it("reorders Planned with the keyboard buttons, sending the whole column", async () => {
    await renderBoard(board([card("p1", "planned"), card("p2", "planned"), card("p3", "bundled")]));
    vi.mocked(V3API.contentHub.reorderPlanned).mockResolvedValue(board([]));

    expect(screen.queryByRole("button", { name: "Move Card p1 up" })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Move Card p1 down" }));

    await waitFor(() =>
      expect(V3API.contentHub.reorderPlanned).toHaveBeenCalledWith(scope, ["p2", "p1", "p3"]),
    );
  });

  it("reorders Planned by drag and drop onto another Planned card", async () => {
    await renderBoard(board([card("p1", "planned"), card("p2", "planned"), card("p3", "planned")]));
    vi.mocked(V3API.contentHub.reorderPlanned).mockResolvedValue(board([]));
    const dataTransfer = { setData: vi.fn(), effectAllowed: "", dropEffect: "" };

    fireEvent.dragStart(screen.getByTestId("board-card-p3"), { dataTransfer });
    fireEvent.drop(screen.getByTestId("board-card-p1"), { dataTransfer });

    await waitFor(() =>
      expect(V3API.contentHub.reorderPlanned).toHaveBeenCalledWith(scope, ["p3", "p1", "p2"]),
    );
  });

  it("drags Backlog onto Planned, and ignores drops on Production columns", async () => {
    await renderBoard(board([card("b1", "backlog"), card("b2", "backlog")]));
    vi.mocked(V3API.contentHub.moveCard).mockResolvedValue(card("b1", "planned"));
    const dataTransfer = { setData: vi.fn(), effectAllowed: "", dropEffect: "" };

    fireEvent.dragStart(screen.getByTestId("board-card-b2"), { dataTransfer });
    expect(column("outline")).toHaveAttribute("data-drop-disabled", "true");
    expect(column("planned")).not.toHaveAttribute("data-drop-disabled");
    fireEvent.drop(column("outline"), { dataTransfer });
    expect(V3API.contentHub.moveCard).not.toHaveBeenCalled();

    fireEvent.dragStart(screen.getByTestId("board-card-b1"), { dataTransfer });
    fireEvent.drop(column("planned"), { dataTransfer });
    await waitFor(() => expect(V3API.contentHub.moveCard).toHaveBeenCalledWith(scope, "b1", "planned", 1));
  });

  it("makes only Backlog and Planned cards draggable", async () => {
    await renderBoard(
      board([card("b1", "backlog"), card("p1", "planned"), card("o1", "outlined"), card("r1", "qa_passed"), card("l1", "live")]),
    );
    expect(screen.getByTestId("board-card-b1")).toHaveAttribute("draggable", "true");
    expect(screen.getByTestId("board-card-p1")).toHaveAttribute("draggable", "true");
    for (const id of ["o1", "r1", "l1"]) {
      expect(screen.getByTestId(`board-card-${id}`)).toHaveAttribute("draggable", "false");
      expect(within(screen.getByTestId(`board-card-${id}`)).queryByRole("button")).not.toBeInTheDocument();
    }
  });

  it("allows only Backlog ↔ Planned and Planned reorder", () => {
    const targets: BoardColumnKey[] = ["backlog", "planned", "outline", "draft", "review", "approved", "live"];
    const allowed = (column: BoardColumnKey, state: string) =>
      targets.filter((target) => canDrop({ column, state }, target));
    expect(allowed("backlog", "backlog")).toEqual(["planned"]);
    expect(allowed("planned", "planned")).toEqual(["backlog", "planned"]);
    expect(allowed("planned", "bundled")).toEqual(["planned"]);
    for (const [column, state] of [["outline", "outlined"], ["draft", "drafting"], ["review", "qa_passed"], ["approved", "approved"], ["live", "live"]] as const) {
      expect(allowed(column, state)).toEqual([]);
    }
  });

  it("rolls back and reports a failed move", async () => {
    await renderBoard(board([card("b1", "backlog")]));
    vi.mocked(V3API.contentHub.moveCard).mockRejectedValue(new Error("The card changed; refresh and retry."));

    fireEvent.click(screen.getByRole("button", { name: "Move Card b1 to Planned" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("The card changed; refresh and retry.");
    expect(within(column("backlog")).getByText("Card b1")).toBeInTheDocument();
    expect(within(column("planned")).queryByText("Card b1")).not.toBeInTheDocument();
  });

  it("shows the unlocked H2 banner and locks through the existing lock endpoint", async () => {
    await renderBoard(board([card("p1", "planned")]));
    vi.mocked(V3API.planLock.lock).mockResolvedValue({
      project_id: "project-1",
      plan_locked_at: "2026-09-24T10:00:00Z",
      locked_now: true,
    });
    vi.mocked(V3API.contentHub.board).mockResolvedValue(
      board([card("p1", "planned")], { plan_locked_at: "2026-09-24T10:00:00Z" }),
    );

    expect(screen.getByText("H2 · plan is unlocked.")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Lock plan" }));

    await waitFor(() => expect(V3API.planLock.lock).toHaveBeenCalledWith(scope));
    expect(await screen.findByText(/H2 · plan locked/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Lock plan" })).not.toBeInTheDocument();
  });

  it("shows the server's new chip only on cards it marks new", async () => {
    await renderBoard(
      board(
        [card("p1", "planned", { is_new_after_plan_lock: true }), card("p2", "planned")],
        { plan_locked_at: "2026-09-24T10:00:00Z" },
      ),
    );
    expect(within(screen.getByTestId("board-card-p1")).getByText("new")).toBeInTheDocument();
    expect(within(screen.getByTestId("board-card-p2")).queryByText("new")).not.toBeInTheDocument();
    expect(screen.getByText(/1 card added to Planned since/)).toBeInTheDocument();
  });

  it("renders the card face from stored data and chips for GEO, refresh and stale", async () => {
    await renderBoard(
      board([
        card("p1", "planned", {
          kind: "refresh",
          area: { id: "area-1", name: "Landed cost" },
          argument: { id: "arg-1", name: "Deemed supplier" },
          owner: { id: "user-1", name: "Patrice" },
          primary_prompt: { id: "n1", text: "who handles duties", volume: null, citation_gap: 1, platform_count: 3 },
          secondary_demand_count: 2,
          stale_claim_count: 1,
          score: 0.71,
        }),
      ]),
    );
    const face = screen.getByTestId("board-card-p1");
    expect(face).toHaveTextContent("refresh · Landed cost · en-GB");
    expect(face).toHaveTextContent("prompt primary · gap 1.0 · 3 platforms");
    expect(face).toHaveTextContent("+2 secondary · Deemed supplier · Patrice");
    for (const chip of ["GEO", "refresh", "stale · 1", "0.71"]) {
      expect(within(face).getByText(chip)).toBeInTheDocument();
    }
  });

  it("sends combined filters to the server and disables reorder while filtered", async () => {
    await renderBoard(board([card("p1", "planned"), card("p2", "planned")]));

    fireEvent.change(screen.getByLabelText("Area"), { target: { value: "area-1" } });
    fireEvent.change(screen.getByLabelText("Kind"), { target: { value: "compare" } });
    fireEvent.change(screen.getByLabelText("Market"), { target: { value: "en-GB" } });

    await waitFor(() =>
      expect(V3API.contentHub.board).toHaveBeenLastCalledWith(scope, {
        area_id: "area-1",
        kind: "compare",
        market: "en-GB",
      }),
    );
    expect(screen.getByLabelText("Owner")).toBeInTheDocument();
    expect(screen.getByLabelText("Argument")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Move Card p1 down" })).not.toBeInTheDocument();
  });

  it("shows an empty state for an empty board and each empty column", async () => {
    await renderBoard(board([]));
    expect(screen.getByText(/No content cards yet/)).toBeInTheDocument();
    expect(screen.getAllByText("No cards")).toHaveLength(7);
    expect(screen.queryByText(/content gap/i)).not.toBeInTheDocument();
  });

  it("shows a loading state, then an error with retry when the board fails", async () => {
    vi.mocked(V3API.contentHub.board).mockRejectedValueOnce(new Error("Board unavailable"));
    render(<PlanBoard scope={scope} />);
    expect(screen.getByLabelText("Loading the plan board")).toBeInTheDocument();

    expect(await screen.findByRole("alert")).toHaveTextContent("Board unavailable");
    vi.mocked(V3API.contentHub.board).mockResolvedValue(board([]));
    fireEvent.click(screen.getByRole("button", { name: "Retry" }));
    expect(await screen.findByTestId("column-backlog")).toBeInTheDocument();
  });
});
