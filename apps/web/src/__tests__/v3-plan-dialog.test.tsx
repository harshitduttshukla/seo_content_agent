import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { PlanDialog } from "@/components/v3/strategy/plan-dialog";
import type { PlanPreview, PlanResult } from "@/lib/api-types";
import { V3API } from "@/lib/v3-api";

vi.mock("@/lib/v3-api", () => ({
  V3API: { demand: { previewPlan: vi.fn(), confirmPlan: vi.fn() } },
}));

const scope = { organizationId: "org-1", projectId: "project-1" };
const nodeIds = ["n1", "n2", "n3"];

const preview: PlanPreview = {
  selected_count: 3,
  eligible_count: 2,
  skipped_count: 1,
  totals: { pillar: 1, cluster: 0, compare: 1, refresh: 0, secondary_demands: 1 },
  groups: [
    {
      area_id: "area-1",
      area_name: "EV Software",
      market_country: "IN",
      counts: { pillar: 1, cluster: 0, compare: 1, refresh: 0, secondary_demands: 1 },
      cards: [
        {
          kind: "pillar",
          primary_node_id: "n2",
          primary_text: "ev charging software",
          primary_type: "keyword",
          score: 0.9,
          volume: 900,
          word_budget: 2000,
          secondary_demands: [{ node_id: "n4", text: "ev charger app" }],
        },
        {
          kind: "compare",
          primary_node_id: "n1",
          primary_text: "acme vs rival",
          primary_type: "keyword",
          score: 0.95,
          volume: 100,
          word_budget: 1000,
          secondary_demands: [],
        },
      ],
    },
  ],
  skipped: [{ node_id: "n3", text: "old keyword", reason: "DemandNode already has ContentCard." }],
  deferred: ["Refresh cards are not created: no stored signal links a demand node to its best-matching imported card."],
};

describe("V3 Plan dialog", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(V3API.demand.previewPlan).mockResolvedValue(preview);
  });

  it("previews by area and market, with secondaries, skips and deferred cases, and writes nothing", async () => {
    render(
      <PlanDialog scope={scope} nodeIds={nodeIds} isOpen onOpenChange={vi.fn()} onPlanned={vi.fn()} />,
    );

    const group = await screen.findByRole("region", { name: "EV Software IN" });
    expect(within(group).getByText("Market: IN")).toBeInTheDocument();
    expect(within(group).getByText("ev charging software")).toBeInTheDocument();
    expect(within(group).getByText("secondaries: ev charger app")).toBeInTheDocument();
    expect(within(group).getByText("1 compare")).toHaveClass("chip", "t");
    expect(within(group).getByText("0 clusters")).toHaveClass("chip", "r");

    const skipped = screen.getByRole("region", { name: "Skipped nodes" });
    expect(within(skipped).getByText("1 skipped")).toHaveClass("chip", "c");
    expect(
      within(skipped).getByText("old keyword — DemandNode already has ContentCard."),
    ).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "Deferred" })).toHaveTextContent("Refresh cards");

    expect(V3API.demand.previewPlan).toHaveBeenCalledWith(scope, nodeIds);
    expect(V3API.demand.confirmPlan).not.toHaveBeenCalled();
  });

  it("creates cards only on Confirm Plan and shows what was created", async () => {
    const result: PlanResult = {
      ...preview,
      created_count: 2,
      created_card_ids: ["c1", "c2"],
      job_run_id: "job-1",
    };
    vi.mocked(V3API.demand.confirmPlan).mockResolvedValue(result);
    const onPlanned = vi.fn();
    render(
      <PlanDialog scope={scope} nodeIds={nodeIds} isOpen onOpenChange={vi.fn()} onPlanned={onPlanned} />,
    );

    fireEvent.click(await screen.findByRole("button", { name: "Confirm Plan" }));

    expect(await screen.findByText("2 cards created in planned.")).toBeInTheDocument();
    expect(V3API.demand.confirmPlan).toHaveBeenCalledWith(scope, nodeIds);
    expect(onPlanned).toHaveBeenCalledOnce();
    expect(screen.getByRole("region", { name: "EV Software IN" })).toBeInTheDocument();
    expect(screen.getByText("1 skipped")).toBeInTheDocument();
    expect(screen.queryByRole("link")).toBeNull(); // no Content Hub link yet
  });

  it("disables Confirm Plan when the selection would create nothing", async () => {
    vi.mocked(V3API.demand.previewPlan).mockResolvedValue({
      ...preview,
      eligible_count: 0,
      totals: { pillar: 0, cluster: 0, compare: 0, refresh: 0, secondary_demands: 0 },
      groups: [],
    });
    render(
      <PlanDialog scope={scope} nodeIds={nodeIds} isOpen onOpenChange={vi.fn()} onPlanned={vi.fn()} />,
    );

    expect(await screen.findByText("No cards would be created from this selection.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Confirm Plan" })).toBeDisabled();
  });

  it("reports a failed confirm without claiming anything was created", async () => {
    vi.mocked(V3API.demand.confirmPlan).mockRejectedValue(new Error("Plan failed server side"));
    render(
      <PlanDialog scope={scope} nodeIds={nodeIds} isOpen onOpenChange={vi.fn()} onPlanned={vi.fn()} />,
    );

    fireEvent.click(await screen.findByRole("button", { name: "Confirm Plan" }));

    await waitFor(() => expect(screen.getByText("Plan failed server side")).toBeInTheDocument());
    expect(screen.queryByText(/cards created/)).toBeNull();
    expect(screen.getByRole("button", { name: "Confirm Plan" })).toBeEnabled();
  });
});
