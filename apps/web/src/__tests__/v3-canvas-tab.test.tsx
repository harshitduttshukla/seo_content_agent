import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { CanvasTab } from "@/components/v3/strategy/canvas-tab";
import type { CanvasDetail, ClaimBase } from "@/lib/api-types";
import { V3API } from "@/lib/v3-api";

vi.mock("@/lib/v3-api", () => ({
  V3API: {
    areas: { list: vi.fn().mockResolvedValue([]), create: vi.fn() },
    canvas: {
      list: vi.fn(),
      get: vi.fn(),
      createCompany: vi.fn(),
      upsertAnchor: vi.fn(),
      createArgument: vi.fn(),
      createClaim: vi.fn(),
      approveClaim: vi.fn(),
      listContentCards: vi.fn(),
      addCitation: vi.fn(),
      checkClaimEdit: vi.fn(),
      getClaimDrilldown: vi.fn(),
      confirmClaimEdit: vi.fn(),
    },
  },
}));

const scope = { organizationId: "org-1", projectId: "project-1" };

const emptyCanvas: CanvasDetail = {
  id: "canvas-1",
  product_line: null,
  name: "Company canvas",
  anchors: [],
  problem_summary: "",
  differentiation_summary: "",
  version: 1,
  arguments: [],
  problem_summary_claim: null,
  differentiation_summary_claim: null,
  pitch_claim: null,
};

describe("V3 Canvas", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(V3API.canvas.list).mockResolvedValue({
      company_canvas: null,
      product_lines: [],
    });
  });

  it("creates the first company canvas and shows its empty grid", async () => {
    vi.mocked(V3API.canvas.createCompany).mockResolvedValue(emptyCanvas);

    render(<CanvasTab scope={scope} />);

    const createButton = await screen.findByRole("button", {
      name: "Create company canvas",
    });
    fireEvent.click(createButton);

    await waitFor(() => {
      expect(V3API.canvas.createCompany).toHaveBeenCalledWith(scope);
    });
    expect(await screen.findByText("No arguments yet")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /add anchor/i })).toBeInTheDocument();
    expect(screen.getByText("Company canvas")).toBeInTheDocument();
    expect(screen.queryByText("No canvas yet")).not.toBeInTheDocument();
  });

  it("submits anchor, argument, and blank-cell authoring requests", async () => {
    const canvasWithArgument: CanvasDetail = {
      ...emptyCanvas,
      arguments: [
        {
          id: "argument-1",
          order: 0,
          sub_problem: "",
          differentiation_pillar: "",
          capability: "",
          features: [],
          benefit: "",
          claims: [],
          inherited: false,
          override: false,
        },
      ],
    };
    vi.mocked(V3API.canvas.list).mockResolvedValue({
      company_canvas: { id: "canvas-1", product_line: null, name: "Company canvas", argument_count: 0 },
      product_lines: [],
    });
    vi.mocked(V3API.canvas.get).mockResolvedValue(emptyCanvas);
    vi.mocked(V3API.canvas.upsertAnchor).mockResolvedValue(emptyCanvas);
    vi.mocked(V3API.canvas.createArgument).mockResolvedValue(canvasWithArgument);
    vi.mocked(V3API.canvas.createClaim).mockResolvedValue(canvasWithArgument);

    render(<CanvasTab scope={scope} />);
    await screen.findByText("No arguments yet");

    fireEvent.click(screen.getByRole("button", { name: /add anchor/i }));
    fireEvent.change(screen.getByLabelText("Text"), { target: { value: "Acme" } });
    fireEvent.click(screen.getByRole("button", { name: "Save anchor" }));
    await waitFor(() => {
      expect(V3API.canvas.upsertAnchor).toHaveBeenCalledWith(scope, "canvas-1", {
        anchor_type: "company",
        text: "Acme",
        primary: false,
      });
    });

    fireEvent.click(screen.getByRole("button", { name: "+ column" }));
    fireEvent.change(screen.getByLabelText("Sub-problem"), { target: { value: "Slow onboarding" } });
    fireEvent.click(screen.getByRole("button", { name: "Add column" }));
    await waitFor(() => {
      expect(V3API.canvas.createArgument).toHaveBeenCalledWith(scope, "canvas-1", {
        sub_problem: "Slow onboarding",
        differentiation_pillar: "",
        capability: "",
        features: [],
        benefit: "",
      });
    });

    // Row 1 is differentiation pillar in the argument column
    fireEvent.click(screen.getAllByRole("button", { name: "—" })[1]);
    fireEvent.change(screen.getByLabelText("Claim text"), { target: { value: "Automate handoffs" } });
    fireEvent.click(screen.getByRole("button", { name: "Create claim" }));
    await waitFor(() => {
      expect(V3API.canvas.createClaim).toHaveBeenCalledWith(scope, "canvas-1", {
        row: "pillar",
        text: "Automate handoffs",
        evidence: "",
        argument_id: "argument-1",
      });
    });
  });

  it("renders elevator pitch empty state and allows manual entry", async () => {
    vi.mocked(V3API.canvas.list).mockResolvedValue({
      company_canvas: { id: "canvas-1", product_line: null, name: "Company canvas", argument_count: 0 },
      product_lines: [],
    });
    vi.mocked(V3API.canvas.get).mockResolvedValue(emptyCanvas);
    vi.mocked(V3API.canvas.createClaim).mockResolvedValue({
      ...emptyCanvas,
      pitch_claim: {
        id: "claim-pitch",
        clm_number: "CLM-000",
        row: "pitch",
        text: "Acme makes cross-border easy.",
        evidence: "Customer survey",
        approved: false,
        approved_by: null,
        version: 1,
        superseded_by: null,
        citation_count: 0,
      },
    });

    render(<CanvasTab scope={scope} />);
    await screen.findByText("No elevator pitch defined yet.");

    fireEvent.click(screen.getByRole("button", { name: "Write pitch" }));
    expect(screen.getByText("Add Elevator pitch")).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Claim text"), {
      target: { value: "Acme makes cross-border easy." },
    });
    fireEvent.change(screen.getByLabelText("Evidence (optional)"), {
      target: { value: "Customer survey" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Create claim" }));

    await waitFor(() => {
      expect(V3API.canvas.createClaim).toHaveBeenCalledWith(scope, "canvas-1", {
        row: "pitch",
        text: "Acme makes cross-border easy.",
        evidence: "Customer survey",
        argument_id: null,
      });
    });
  });

  it("renders populated pitch claim, evidence, and allows approval", async () => {
    const pitchClaim: ClaimBase = {
      id: "claim-pitch-1",
      clm_number: "CLM-000",
      row: "pitch",
      text: "Glopal is a cross-border ecommerce platform.",
      evidence: "14 discovery calls",
      approved: false,
      approved_by: null,
      version: 1,
      superseded_by: null,
      citation_count: 3,
    };
    const canvasWithPitch: CanvasDetail = {
      ...emptyCanvas,
      pitch_claim: pitchClaim,
    };

    vi.mocked(V3API.canvas.list).mockResolvedValue({
      company_canvas: { id: "canvas-1", product_line: null, name: "Company canvas", argument_count: 0 },
      product_lines: [],
    });
    vi.mocked(V3API.canvas.get).mockResolvedValue(canvasWithPitch);
    vi.mocked(V3API.canvas.approveClaim).mockResolvedValue({
      ...pitchClaim,
      approved: true,
    });

    render(<CanvasTab scope={scope} />);
    await screen.findByText("Glopal is a cross-border ecommerce platform.");

    expect(screen.getByText("CLM-000 · v1")).toBeInTheDocument();
    expect(screen.getByText("evidence: 14 discovery calls")).toBeInTheDocument();
    expect(screen.getByText("cited by 3 live pages")).toBeInTheDocument();
    expect(screen.getByText("unapproved")).toBeInTheDocument();

    const approveButton = screen.getByRole("button", { name: "Approve" });
    fireEvent.click(approveButton);

    await waitFor(() => {
      expect(V3API.canvas.approveClaim).toHaveBeenCalledWith(scope, "claim-pitch-1");
    });
  });

  it("creates a test card, lists it in the drilldown, and refreshes the pitch citation count", async () => {
    const pitchClaim: ClaimBase = {
      id: "claim-pitch-1",
      clm_number: "CLM-000",
      row: "pitch",
      text: "Glopal is a cross-border ecommerce platform.",
      evidence: "14 discovery calls",
      approved: true,
      approved_by: "user-1",
      version: 1,
      superseded_by: null,
      citation_count: 0,
    };
    const canvasWithPitch: CanvasDetail = {
      ...emptyCanvas,
      pitch_claim: pitchClaim,
    };
    const createdCard = {
      id: "card-1",
      title: "Test citation card",
      kind: "cluster",
      state: "live",
      url: "https://example.com/test-card",
    };

    vi.mocked(V3API.canvas.list).mockResolvedValue({
      company_canvas: { id: "canvas-1", product_line: null, name: "Company canvas", argument_count: 0 },
      product_lines: [],
    });
    vi.mocked(V3API.canvas.get)
      .mockResolvedValueOnce(canvasWithPitch)
      .mockResolvedValueOnce({
        ...canvasWithPitch,
        pitch_claim: { ...pitchClaim, citation_count: 1 },
      });
    vi.mocked(V3API.canvas.checkClaimEdit)
      .mockResolvedValueOnce({
        citation_count: 0,
        claim_text: pitchClaim.text,
        claim_id: pitchClaim.id,
      })
      .mockResolvedValueOnce({
        citation_count: 1,
        claim_text: pitchClaim.text,
        claim_id: pitchClaim.id,
      });
    vi.mocked(V3API.canvas.getClaimDrilldown).mockResolvedValue({
      argument_chain: [],
      demand_nodes: [],
      content_cards: [],
    });
    vi.mocked(V3API.canvas.listContentCards)
      .mockResolvedValueOnce([])
      .mockResolvedValueOnce([createdCard]);
    vi.mocked(V3API.canvas.addCitation).mockResolvedValue({
      argument_chain: [],
      demand_nodes: [],
      content_cards: [createdCard],
    });

    render(<CanvasTab scope={scope} />);
    await screen.findByText("cited by 0 live pages");

    fireEvent.click(screen.getByRole("button", { name: "Edit cell" }));
    fireEvent.click(await screen.findByRole("button", { name: "View argument chain and linked work" }));
    fireEvent.change(await screen.findByRole("textbox", { name: "Create test card" }), {
      target: { value: "Test citation card" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Create test card" }));

    expect(await screen.findByText("Test citation card")).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getByText("cited by 1 live pages")).toBeInTheDocument();
    });
    expect(V3API.canvas.addCitation).toHaveBeenCalledWith(scope, "claim-pitch-1", {
      title: "Test citation card",
    });
    expect(V3API.canvas.confirmClaimEdit).not.toHaveBeenCalled();
  });

  it("loads the full linked-work drilldown for an Argument claim when opened", async () => {
    const argumentClaims: ClaimBase[] = [
      ["sub_problem", "Slow campaign planning"],
      ["pillar", "Differentiated research"],
      ["capability", "Automated clustering"],
      ["feature", "Live search signals"],
      ["benefit", "Faster content decisions"],
    ].map(([row, text], index) => ({
      id: `argument-claim-${index}`,
      clm_number: `CLM-ARG-${index}`,
      row,
      text,
      evidence: "",
      approved: true,
      approved_by: "user-1",
      version: 1,
      superseded_by: null,
      citation_count: 0,
    }));
    const canvasWithArgument: CanvasDetail = {
      ...emptyCanvas,
      arguments: [{
        id: "argument-1",
        order: 0,
        sub_problem: argumentClaims[0].text,
        differentiation_pillar: argumentClaims[1].text,
        capability: argumentClaims[2].text,
        features: [argumentClaims[3].text],
        benefit: argumentClaims[4].text,
        claims: argumentClaims,
        inherited: false,
        override: false,
      }],
    };
    vi.mocked(V3API.canvas.list).mockResolvedValue({
      company_canvas: { id: "canvas-1", product_line: null, name: "Company canvas", argument_count: 1 },
      product_lines: [],
    });
    vi.mocked(V3API.canvas.get).mockResolvedValue(canvasWithArgument);
    vi.mocked(V3API.canvas.checkClaimEdit).mockResolvedValue({
      citation_count: 0,
      claim_text: argumentClaims[1].text,
      claim_id: argumentClaims[1].id,
    });
    vi.mocked(V3API.canvas.listContentCards).mockResolvedValue([]);
    vi.mocked(V3API.canvas.getClaimDrilldown).mockResolvedValue({
      argument_chain: argumentClaims,
      demand_nodes: [],
      content_cards: [],
    });

    render(<CanvasTab scope={scope} />);
    fireEvent.click(await screen.findByText("Differentiated research"));
    fireEvent.click(await screen.findByRole("button", { name: "View argument chain and linked work" }));

    expect(await screen.findByText("Slow campaign planning")).toBeInTheDocument();
    expect(screen.getAllByText("Faster content decisions")).toHaveLength(2);
    expect(screen.getByText("0 linked nodes")).toBeInTheDocument();
    expect(screen.getByText("No content cards cite this claim yet.")).toBeInTheDocument();
    expect(V3API.canvas.getClaimDrilldown).toHaveBeenCalledWith(scope, "argument-claim-1");
  });

  it("renders all anchor types inline with primary badge", async () => {
    const canvasWithAnchors: CanvasDetail = {
      ...emptyCanvas,
      anchors: [
        { anchor_type: "company", text: "Glopal", primary: true },
        { anchor_type: "persona", text: "Head of Ecommerce", primary: true },
        { anchor_type: "use_case", text: "Selling to 20+ markets", primary: true },
        { anchor_type: "alternative", text: "Global-e · Weglot", primary: false },
        { anchor_type: "category", text: "Cross-border platform", primary: false },
      ],
    };

    vi.mocked(V3API.canvas.list).mockResolvedValue({
      company_canvas: { id: "canvas-1", product_line: null, name: "Company canvas", argument_count: 0 },
      product_lines: [],
    });
    vi.mocked(V3API.canvas.get).mockResolvedValue(canvasWithAnchors);

    render(<CanvasTab scope={scope} />);
    await screen.findByText("Glopal");

    expect(screen.getByText("Head of Ecommerce")).toBeInTheDocument();
    expect(screen.getByText("Selling to 20+ markets")).toBeInTheDocument();
    expect(screen.getByText("Global-e · Weglot")).toBeInTheDocument();
    expect(screen.getByText("Cross-border platform")).toBeInTheDocument();

    // 3 primary badges
    const primaryBadges = screen.getAllByText("primary");
    expect(primaryBadges).toHaveLength(3);

    expect(screen.getByText("Each primary anchor passes the stands-on-its-own rule")).toBeInTheDocument();
  });
});

describe("V3 Canvas company label", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(V3API.canvas.list).mockResolvedValue({
      company_canvas: { id: "canvas-1", product_line: null, name: "Company canvas", argument_count: 0 },
      product_lines: [
        { id: "canvas-2", product_line: "Localization", name: "Localization", argument_count: 0 },
      ],
    });
    vi.mocked(V3API.canvas.get).mockResolvedValue(emptyCanvas);
  });

  it("names the company row after the project's organization, and switches with it", async () => {
    const { rerender } = render(<CanvasTab scope={scope} organizationName="Organization A" />);
    expect(await screen.findByText("Organization A — company canvas")).toBeInTheDocument();

    rerender(<CanvasTab scope={scope} organizationName="Organization B" />);
    expect(await screen.findByText("Organization B — company canvas")).toBeInTheDocument();
    expect(screen.queryByText(/Organization A/)).not.toBeInTheDocument();
  });

  it("falls back to 'Company canvas' when the name is unavailable", async () => {
    render(<CanvasTab scope={scope} organizationName="" />);
    expect(await screen.findByText("Company canvas")).toBeInTheDocument();
    expect(screen.queryByText(/undefined|null|\[object Object\]/)).not.toBeInTheDocument();
  });
});
