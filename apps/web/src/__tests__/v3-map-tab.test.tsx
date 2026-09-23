import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { MapTab } from "@/components/v3/strategy/map-tab";
import type { MapAreaNode, MapCanvasNode, StrategyMap } from "@/lib/api-types";
import { V3API } from "@/lib/v3-api";

vi.mock("@/lib/v3-api", () => ({
  V3API: { strategyMap: { get: vi.fn() } },
}));

const scope = { organizationId: "org-1", projectId: "project-1" };

function area(overrides: Partial<MapAreaNode> & { id: string; name: string }): MapAreaNode {
  return {
    parent_id: null,
    default_argument_id: null,
    default_argument_pillar: null,
    demand_count: 0,
    card_count: 0,
    card_states: {},
    descendant_card_states: {},
    is_unmapped: false,
    content_gap: false,
    children: [],
    ...overrides,
  };
}

function canvasNode(
  overrides: Partial<MapCanvasNode> & { id: string; name: string },
): MapCanvasNode {
  return {
    product_line: null,
    is_company: false,
    argument_count: 0,
    cell_count: 0,
    inherits: [],
    override_count: 0,
    adds: [],
    areas: [],
    product_lines: [],
    ...overrides,
  };
}

function resolve(map: StrategyMap) {
  vi.mocked(V3API.strategyMap.get).mockResolvedValue(map);
}

describe("V3 Strategy Map", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("shows a skeleton while loading, not a spinner over an empty card", async () => {
    vi.mocked(V3API.strategyMap.get).mockReturnValue(new Promise(() => {}));
    render(<MapTab scope={scope} />);

    expect(screen.getByLabelText("Loading the combined tree")).toBeInTheDocument();
    expect(screen.getByText("Combined tree")).toBeInTheDocument();
  });

  it("points at the Canvas tab when no canvas exists, instead of an empty card", async () => {
    resolve({ company_canvas: null, unassigned_card_count: 0 });
    render(<MapTab scope={scope} />);

    await waitFor(() => expect(screen.getByRole("link", { name: "Canvas tab" })).toBeInTheDocument());
    expect(screen.getByRole("link", { name: "Canvas tab" })).toHaveAttribute(
      "href",
      "/projects/project-1/v3/canvas",
    );
    expect(screen.queryByText("Combined tree")).not.toBeInTheDocument();
  });

  it("renders the company canvas alone with its counts when it has no areas", async () => {
    resolve({
      company_canvas: canvasNode({
        id: "canvas-1",
        name: "Company canvas",
        is_company: true,
        argument_count: 3,
        cell_count: 41,
      }),
      unassigned_card_count: 0,
    });
    render(<MapTab scope={scope} />);

    await waitFor(() => expect(screen.getByText("Company canvas")).toBeInTheDocument());
    expect(screen.getByText("3 arguments · 41 cells")).toBeInTheDocument();
  });

  it("nests sub-areas to arbitrary depth", async () => {
    resolve({
      company_canvas: canvasNode({
        id: "canvas-1",
        name: "Company canvas",
        is_company: true,
        areas: [
          area({
            id: "a1",
            name: "Duties & Taxes",
            children: [
              area({
                id: "a2",
                name: "Landed cost",
                parent_id: "a1",
                children: [
                  area({
                    id: "a3",
                    name: "Item-level",
                    parent_id: "a2",
                    children: [area({ id: "a4", name: "HS codes", parent_id: "a3", card_count: 2 })],
                  }),
                ],
              }),
            ],
          }),
        ],
      }),
      unassigned_card_count: 0,
    });
    render(<MapTab scope={scope} />);

    await waitFor(() => expect(screen.getByText("HS codes")).toBeInTheDocument());
    for (const name of ["Duties & Taxes", "Landed cost", "Item-level", "HS codes"]) {
      expect(screen.getByText(name)).toBeInTheDocument();
    }
    expect(screen.getByText("2 cards")).toBeInTheDocument();
  });

  it("shows the content-gap chip only where the server marks it", async () => {
    resolve({
      company_canvas: canvasNode({
        id: "canvas-1",
        name: "Company canvas",
        is_company: true,
        areas: [
          area({ id: "a1", name: "Landed cost", demand_count: 412, card_count: 4 }),
          area({ id: "a2", name: "Returns of duty", demand_count: 61, content_gap: true }),
        ],
      }),
      unassigned_card_count: 0,
    });
    render(<MapTab scope={scope} />);

    await waitFor(() => expect(screen.getByText("Returns of duty")).toBeInTheDocument());
    const chips = screen.getAllByText("content gap");
    expect(chips).toHaveLength(1);
    expect(chips[0]).toHaveClass("chip", "c");
    expect(screen.queryByText("no content")).toBeNull();
  });

  it("shows a parent's sub-area card states in workflow order instead of a gap", async () => {
    resolve({
      company_canvas: canvasNode({
        id: "canvas-1",
        name: "Company canvas",
        is_company: true,
        areas: [
          area({
            id: "p1",
            name: "Duties & Taxes",
            demand_count: 61,
            descendant_card_states: { qa_passed: 1, planned: 2, drafting: 1 },
            children: [area({ id: "c1", name: "Landed cost", parent_id: "p1", card_count: 4 })],
          }),
        ],
      }),
      unassigned_card_count: 0,
    });
    render(<MapTab scope={scope} />);

    expect(
      await screen.findByText("sub-areas: 2 planned · 1 drafting · 1 qa passed"),
    ).toBeInTheDocument();
    expect(screen.queryByText("content gap")).toBeNull();
  });

  it("renders the teal argument chip from the area's default argument", async () => {
    resolve({
      company_canvas: canvasNode({
        id: "canvas-1",
        name: "Company canvas",
        is_company: true,
        areas: [
          area({
            id: "a1",
            name: "Landed cost",
            default_argument_id: "arg-1",
            default_argument_pillar: "Item-level landed cost",
            card_count: 4,
          }),
          area({ id: "a2", name: "Deemed supplier / IOSS", card_count: 3 }),
        ],
      }),
      unassigned_card_count: 0,
    });
    render(<MapTab scope={scope} />);

    await waitFor(() => expect(screen.getByText("Item-level landed cost")).toBeInTheDocument());
    expect(screen.getByText("Item-level landed cost")).toHaveClass("chip", "t");
  });

  it("renders the inheritance summary as inherits, override and adds", async () => {
    resolve({
      company_canvas: canvasNode({
        id: "canvas-1",
        name: "Company canvas",
        is_company: true,
        argument_count: 3,
        cell_count: 41,
        product_lines: [
          canvasNode({
            id: "c2",
            name: "Duties & Taxes",
            product_line: "Duties & Taxes",
            inherits: ["A1"],
            adds: ["A4"],
          }),
          canvasNode({
            id: "c3",
            name: "Localization",
            product_line: "Localization",
            inherits: ["A2"],
            override_count: 1,
          }),
          canvasNode({
            id: "c4",
            name: "Performance Marketing",
            product_line: "Performance Marketing",
            inherits: ["A3"],
          }),
          canvasNode({
            id: "c5",
            name: "Multi",
            product_line: "Multi",
            inherits: ["A1", "A2"],
            override_count: 2,
            adds: ["A5", "A6"],
          }),
        ],
      }),
      unassigned_card_count: 0,
    });
    render(<MapTab scope={scope} />);

    await waitFor(() => expect(screen.getByText("Duties & Taxes")).toBeInTheDocument());
    expect(screen.getByText("inherits A1 · adds A4")).toBeInTheDocument();
    expect(screen.getByText("inherits A2 · 1 override")).toBeInTheDocument();
    expect(screen.getByText("inherits A3")).toBeInTheDocument();
    expect(screen.getByText("inherits A1, A2 · 2 overrides · adds A5, A6")).toBeInTheDocument();
    expect(screen.getAllByText("line canvas")).toHaveLength(4);
    expect(screen.getAllByText("line canvas")[0]).toHaveClass("chip", "r");
  });

  it("carries area and status=kept to Demand, and renders the card count as plain text", async () => {
    resolve({
      company_canvas: canvasNode({
        id: "canvas-1",
        name: "Company canvas",
        is_company: true,
        areas: [area({ id: "area-9", name: "Landed cost", demand_count: 412, card_count: 4 })],
      }),
      unassigned_card_count: 0,
    });
    render(<MapTab scope={scope} />);

    await waitFor(() => expect(screen.getByText("Landed cost")).toBeInTheDocument());
    expect(screen.getByRole("link", { name: "Landed cost" })).toHaveAttribute(
      "href",
      "/projects/project-1/v3/demand?area=area-9&status=kept",
    );
    // The Plan board does not exist yet, so the card count links nowhere.
    expect(screen.getByText("4 cards")).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "4 cards" })).toBeNull();
  });

  it("pluralises a single card", async () => {
    resolve({
      company_canvas: canvasNode({
        id: "canvas-1",
        name: "Company canvas",
        is_company: true,
        areas: [area({ id: "a1", name: "International SEO", demand_count: 502, card_count: 1 })],
      }),
      unassigned_card_count: 0,
    });
    render(<MapTab scope={scope} />);

    await waitFor(() => expect(screen.getByText("International SEO")).toBeInTheDocument());
    expect(screen.getByText("1 card")).toBeInTheDocument();
  });

  it("marks the view read-only and states how the counts are decided", async () => {
    resolve({
      company_canvas: canvasNode({
        id: "canvas-1",
        name: "Company canvas",
        is_company: true,
        areas: [area({ id: "a1", name: "Landed cost", card_count: 4 })],
      }),
      unassigned_card_count: 0,
    });
    render(<MapTab scope={scope} />);

    await waitFor(() => expect(screen.getByText("read-only")).toBeInTheDocument());
    expect(screen.getByText("read-only")).toHaveClass("chip", "r");
    expect(screen.getByText("canvas → product lines → areas → demand")).toBeInTheDocument();
    expect(screen.getByText(/Demand counts kept nodes for that area alone/)).toBeInTheDocument();
    expect(
      screen.getByText(/Orientation only\. Everything here is reachable from the flat tabs/),
    ).toBeInTheDocument();
  });

  it("reports cards that no area claims instead of hiding them", async () => {
    resolve({
      company_canvas: canvasNode({
        id: "canvas-1",
        name: "Company canvas",
        is_company: true,
        areas: [area({ id: "a1", name: "Landed cost", card_count: 4 })],
      }),
      unassigned_card_count: 37,
    });
    render(<MapTab scope={scope} />);

    await waitFor(() =>
      expect(screen.getByText(/37 cards are not classified to any area/)).toBeInTheDocument(),
    );
  });

  it("renders no write controls at all", async () => {
    resolve({
      company_canvas: canvasNode({
        id: "canvas-1",
        name: "Company canvas",
        is_company: true,
        areas: [
          area({
            id: "a1",
            name: "Duties & Taxes",
            children: [area({ id: "a2", name: "Landed cost", parent_id: "a1", card_count: 4 })],
          }),
        ],
      }),
      unassigned_card_count: 0,
    });
    render(<MapTab scope={scope} />);

    await waitFor(() => expect(screen.getByText("Landed cost")).toBeInTheDocument());
    // The only buttons are expand/collapse toggles; no inputs, no selects, no forms.
    for (const button of screen.getAllByRole("button")) {
      expect(button).toHaveAttribute("aria-expanded");
    }
    expect(screen.queryByRole("textbox")).not.toBeInTheDocument();
    expect(screen.queryByRole("combobox")).not.toBeInTheDocument();
    expect(document.querySelector("form")).toBeNull();
    expect(document.querySelector("[draggable='true']")).toBeNull();
  });

  it("collapses and expands a node, expanded by default", async () => {
    resolve({
      company_canvas: canvasNode({
        id: "canvas-1",
        name: "Company canvas",
        is_company: true,
        areas: [
          area({
            id: "a1",
            name: "Duties & Taxes",
            children: [area({ id: "a2", name: "Landed cost", parent_id: "a1", card_count: 4 })],
          }),
        ],
      }),
      unassigned_card_count: 0,
    });
    render(<MapTab scope={scope} />);

    await waitFor(() => expect(screen.getByText("Landed cost")).toBeInTheDocument());
    fireEvent.click(screen.getByLabelText("Collapse Duties & Taxes"));
    expect(screen.queryByText("Landed cost")).not.toBeInTheDocument();

    fireEvent.click(screen.getByLabelText("Expand Duties & Taxes"));
    expect(screen.getByText("Landed cost")).toBeInTheDocument();
  });

  it("attaches areas under the canvas that owns them", async () => {
    resolve({
      company_canvas: canvasNode({
        id: "canvas-1",
        name: "Company canvas",
        is_company: true,
        areas: [area({ id: "a1", name: "Company-level area", card_count: 1 })],
        product_lines: [
          canvasNode({
            id: "c2",
            name: "Localization",
            product_line: "Localization",
            inherits: ["A2"],
            areas: [area({ id: "a2", name: "Translation", card_count: 8 })],
          }),
        ],
      }),
      unassigned_card_count: 0,
    });
    render(<MapTab scope={scope} />);

    await waitFor(() => expect(screen.getByText("Translation")).toBeInTheDocument());
    // Translation sits inside the Localization branch, not beside the company areas.
    const localizationBranch = screen.getByText("Localization").closest("li");
    expect(localizationBranch).not.toBeNull();
    expect(within(localizationBranch as HTMLElement).getByText("Translation")).toBeInTheDocument();
    expect(
      within(localizationBranch as HTMLElement).queryByText("Company-level area"),
    ).not.toBeInTheDocument();
  });

  it("surfaces a load failure as an alert", async () => {
    vi.mocked(V3API.strategyMap.get).mockRejectedValue(new Error("Map unavailable"));
    render(<MapTab scope={scope} />);

    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent("Map unavailable"));
  });
});
