import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { CardDetailView } from "@/components/v3/content-hub/card-detail";
import { PlanBoard } from "@/components/v3/content-hub/plan-board";
import type { BoardCard, CardDetail, OutlineV3 } from "@/lib/api-types";
import { ApiError } from "@/lib/client-api";
import { V3API } from "@/lib/v3-api";

vi.mock("@/lib/v3-api", () => ({
  V3API: {
    contentHub: {
      board: vi.fn(),
      card: vi.fn(),
      buildBundle: vi.fn(),
      generateOutline: vi.fn(),
      saveOutline: vi.fn(),
      moveCard: vi.fn(),
      reorderPlanned: vi.fn(),
    },
    planLock: { lock: vi.fn() },
  },
}));

const scope = { organizationId: "org-1", projectId: "project-1" };

const face: BoardCard = {
  id: "card-1",
  title: "Landed cost calculation",
  kind: "pillar",
  state: "bundled",
  column: "planned",
  origin: "plan",
  area: { id: "area-1", name: "Landed cost" },
  argument: { id: "arg-1", name: "Item-level landed cost" },
  owner: { id: "user-1", name: "Anirudh" },
  market: "en-GB",
  due: "2026-10-01",
  priority: 1,
  primary_demand: null,
  primary_prompt: null,
  secondary_demand_count: 1,
  score: null,
  has_qa_report: false,
  url: null,
  cms_id: null,
  published_at: null,
  stale_claim_count: 0,
  planned_at: null,
  is_new_after_plan_lock: false,
  revision: 3,
  updated_at: "2026-09-25T00:00:00Z",
};

const outline: OutlineV3 = {
  schema_version: "v3.outline.v1",
  primary_mode: "keyword",
  title: "Landed cost calculation",
  prompt_target_id: null,
  direct_answer: null,
  sections: [
    {
      section_id: "s1", order: 1, heading: "What landed cost includes", purpose: "", claim_ids: ["clm-1"],
      target_demand_id: "dem-1", planned_internal_links: [], citable_statement: null, notes: "", needs_claim: [],
    },
    {
      section_id: "s2", order: 2, heading: "Choosing a calculator", purpose: "", claim_ids: [],
      target_demand_id: null, planned_internal_links: [], citable_statement: null, notes: "", needs_claim: [],
    },
  ],
};

function detail(overrides: Partial<CardDetail> = {}): CardDetail {
  return {
    card: face,
    outline: null,
    outline_unreadable: false,
    bundle: { bundle_ref: "run-1", content_hash: "abcdef0123456789", built_at: "2026-09-25T08:00:00Z", is_current: true },
    context: {
      card: { id: "card-1", title: face.title, kind: "pillar", origin: "plan", market: "en-GB", word_budget: 2000, url: null, primary_mode: "keyword" },
      rules: { brand: { tone: "plain", voice: null, style: "no superlatives", words_to_avoid: ["cheap"], formatting_rules: [] }, claim_policy: "cite" },
      claims: [{ id: "clm-1", text: "Duty per HS code at item level", evidence: "", row: "pillar", argument_id: "arg-1", version: 2 }],
      demand: [
        { id: "dem-1", role: "primary", type: "keyword", text: "landed cost calculator", volume: 2310, intent: null, citation_gap: null, platforms: [] },
        { id: "dem-2", role: "secondary", type: "keyword", text: "how to calculate landed cost", volume: 480, intent: null, citation_gap: null, platforms: [] },
      ],
      tone: { tone: "plain", voice_snippets: [], social_proof: ["Rodier"] },
      siblings: [{ id: "card-2", title: "Duties and taxes for DTC brands", kind: "pillar", state: "approved", url: null }],
      references: {
        existing_pages: { pages: [{ page_id: "page-1", url: "https://site.test/duties", title: "Duties guide", relationship: "related" }] },
        website: { crawled_pages: [{ page_id: "page-1", url: "https://site.test/duties", title: "Duties guide", headings: ["Duty"], content_snippet: "x", word_count: 900 }] },
        internal_linking: { opportunities: [] },
      },
      pitch: { argument_id: "arg-1", differentiation_pillar: "Item-level landed cost", sub_problem: "", capability: "", benefit: "", problem_summary: "", differentiation_summary: "" },
      sources: [],
      budget: { max_tokens: 6000, used_tokens: 900, truncated_sections: [] },
    },
    claim_options: [
      { id: "clm-1", text: "Duty per HS code at item level", evidence: "", row: "pillar", argument_id: "arg-1", argument_name: "Item-level", version: 2, approved: true },
      { id: "clm-2", text: "No post-delivery invoice", evidence: "", row: "pillar", argument_id: "arg-1", argument_name: "Item-level", version: 1, approved: true },
    ],
    checks: [
      { key: "bundle_exists", label: "Bundle exists", status: "pass", detail: "" },
      { key: "bundle_current", label: "Bundle is current", status: "pass", detail: "" },
      { key: "outline_exists", label: "Outline exists", status: "fail", detail: "" },
    ],
    actions: { can_build_bundle: true, can_generate_outline: true, can_save_outline: true },
    ...overrides,
  };
}

async function renderDetail(data: CardDetail) {
  vi.mocked(V3API.contentHub.card).mockResolvedValue(data);
  render(<CardDetailView scope={scope} cardId="card-1" />);
  await screen.findByRole("heading", { name: face.title });
}

const section = (n: number) => screen.getByRole("region", { name: `Section ${n}` });

describe("V3 card detail", () => {
  beforeEach(() => vi.clearAllMocks());

  it("shows a loading state while the card loads", () => {
    vi.mocked(V3API.contentHub.card).mockReturnValue(new Promise(() => {}));
    render(<CardDetailView scope={scope} cardId="card-1" />);
    expect(screen.getByLabelText("Loading the card")).toBeInTheDocument();
  });

  it("renders the header, context, document and checks from real data", async () => {
    await renderDetail(detail());
    expect(V3API.contentHub.card).toHaveBeenCalledWith(scope, "card-1");
    expect(screen.getByRole("link", { name: "← Back to Content Hub" })).toHaveAttribute("href", "/projects/project-1/v3/content-hub");
    expect(screen.getByTestId("card-state")).toHaveTextContent("bundled");
    for (const text of ["Item-level landed cost", "landed cost calculator · 2310", "owner Anirudh", "due 2026-10-01"]) {
      expect(screen.getAllByText(text).length).toBeGreaterThan(0);
    }
    const context = screen.getByRole("region", { name: "Context" });
    expect(within(context).getByText("Duty per HS code at item level")).toBeInTheDocument();
    expect(within(context).getByText(/secondary · how to calculate landed cost/)).toBeInTheDocument();
    expect(within(context).getByText("Tone · plain")).toBeInTheDocument();
    expect(within(context).getByText("Avoid · cheap")).toBeInTheDocument();
    expect(within(context).getByText("Proof · Rodier")).toBeInTheDocument();
    expect(within(context).getByText("Duties guide · 900 words")).toBeInTheDocument();
    expect(within(context).getByText("No data configured")).toBeInTheDocument(); // linking
    expect(within(context).getByText("stored bundle")).toBeInTheDocument();
    const checks = screen.getByRole("list", { name: "Checks" });
    expect(within(checks).getAllByRole("listitem").map((li) => li.getAttribute("data-status"))).toEqual(["pass", "pass", "fail"]);
  });

  it("shows the Draft tab as not yet available", async () => {
    await renderDetail(detail());
    fireEvent.click(screen.getByRole("tab", { name: "Draft" }));
    expect(await screen.findByText("Draft generation will be available in the next production phase.")).toBeInTheDocument();
  });

  it("builds the bundle with the card revision and reloads", async () => {
    await renderDetail(detail({ bundle: null, actions: { can_build_bundle: true, can_generate_outline: false, can_save_outline: false } }));
    expect(screen.getByRole("button", { name: "Generate outline" })).toBeDisabled();
    vi.mocked(V3API.contentHub.buildBundle).mockResolvedValue({ card: face, bundle: detail().bundle!, reused: false });

    fireEvent.click(screen.getByRole("button", { name: "Build bundle" }));

    await waitFor(() => expect(V3API.contentHub.buildBundle).toHaveBeenCalledWith(scope, "card-1", 3));
    expect(await screen.findByText("Bundle built.")).toBeInTheDocument();
    expect(V3API.contentHub.card).toHaveBeenCalledTimes(2);
  });

  it("renders saved outline sections and edits, reorders, adds and removes them", async () => {
    await renderDetail(detail({ outline }));
    expect(screen.getByLabelText("Section 1 heading")).toHaveValue("What landed cost includes");
    expect(screen.getByRole("button", { name: "Save outline" })).toBeDisabled(); // nothing changed yet

    fireEvent.change(screen.getByLabelText("Section 1 heading"), { target: { value: "What it includes" } });
    fireEvent.click(screen.getByRole("button", { name: "Move Section 1 down" }));
    expect(screen.getByLabelText("Section 2 heading")).toHaveValue("What it includes");
    expect(screen.getByLabelText("Section 1 heading")).toHaveValue("Choosing a calculator");

    fireEvent.click(screen.getByRole("button", { name: "+ Add section" }));
    expect(screen.getByRole("region", { name: "Section 3" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Remove Section 3" }));
    expect(screen.queryByRole("region", { name: "Section 3" })).not.toBeInTheDocument();
  });

  it("attaches and removes claims, sets demand and links, and saves with the revision", async () => {
    await renderDetail(detail({ outline }));
    vi.mocked(V3API.contentHub.saveOutline).mockResolvedValue({ card: { ...face, state: "outlined", revision: 4 }, outline });

    const second = section(2);
    fireEvent.change(within(second).getByLabelText("Attach claim to Section 2"), { target: { value: "clm-2" } });
    expect(within(second).getByText("No post-delivery invoice")).toBeInTheDocument();
    fireEvent.change(within(second).getByLabelText("Section 2 target demand"), { target: { value: "dem-2" } });
    fireEvent.change(within(second).getByLabelText("Add internal link to Section 2"), { target: { value: "page-1" } });
    fireEvent.change(within(second).getByLabelText("Section 2 citable statement"), { target: { value: "Duty is per item." } });
    fireEvent.change(within(second).getByLabelText("Section 2 notes"), { target: { value: "Link the guide." } });
    fireEvent.click(within(section(1)).getByRole("button", { name: /Remove claim Duty per HS code/ }));

    fireEvent.click(screen.getByRole("button", { name: "Save outline" }));

    await waitFor(() => expect(V3API.contentHub.saveOutline).toHaveBeenCalled());
    const [, cardId, saved, revision] = vi.mocked(V3API.contentHub.saveOutline).mock.calls[0];
    expect([cardId, revision]).toEqual(["card-1", 3]);
    expect(saved.sections[0].claim_ids).toEqual([]);
    expect(saved.sections[1]).toMatchObject({
      order: 2,
      claim_ids: ["clm-2"],
      target_demand_id: "dem-2",
      planned_internal_links: [{ page_id: "page-1", url: "https://site.test/duties", anchor_text: "" }],
      citable_statement: "Duty is per item.",
      notes: "Link the guide.",
    });
    expect(await screen.findByText("Outline saved.")).toBeInTheDocument();
  });

  it("puts a generated proposal in the editor without saving it", async () => {
    await renderDetail(detail());
    vi.mocked(V3API.contentHub.generateOutline).mockResolvedValue({
      outline, job_run_id: "job-1", prompt_version: "v3.outline.v1", provider: "gemini", model: "gemini-flash", attempts: 1, bundle_ref: "run-1",
    });

    fireEvent.click(screen.getByRole("button", { name: "Generate outline" }));

    expect(await screen.findByLabelText("Section 1 heading")).toHaveValue("What landed cost includes");
    expect(screen.getByText(/Proposal from gemini-flash \(v3.outline.v1\)/)).toBeInTheDocument();
    expect(V3API.contentHub.saveOutline).not.toHaveBeenCalled();
    expect(screen.getByRole("button", { name: "Save outline" })).toBeEnabled();
  });

  it("shows why a generated outline was rejected", async () => {
    await renderDetail(detail());
    vi.mocked(V3API.contentHub.generateOutline).mockRejectedValue(
      new ApiError("The generated outline was rejected and not saved.", "OUTLINE_INVALID", "req", 422, null, {
        issues: [{ code: "UNKNOWN_CLAIM", message: "claim is not an approved, current claim", section_id: "s1" }],
      }),
    );
    fireEvent.click(screen.getByRole("button", { name: "Generate outline" }));
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("The generated outline was rejected and not saved.");
    expect(alert).toHaveTextContent("s1: claim is not an approved, current claim");
  });

  it("reports a revision conflict and offers a reload", async () => {
    await renderDetail(detail({ outline }));
    vi.mocked(V3API.contentHub.saveOutline).mockRejectedValue(
      new ApiError("The card changed", "VERSION_CONFLICT", "req", 409, null, { current_revision: 5 }),
    );
    fireEvent.change(screen.getByLabelText("Section 1 heading"), { target: { value: "Edited" } });
    fireEvent.click(screen.getByRole("button", { name: "Save outline" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Your version is out of date. Reload before saving.");
    fireEvent.click(screen.getByRole("button", { name: "Reload" }));
    await waitFor(() => expect(V3API.contentHub.card).toHaveBeenCalledTimes(2));
  });

  it("supports prompt-primary fields with a word count", async () => {
    const base = detail();
    const promptDetail = detail({
      context: {
        ...base.context,
        card: { ...base.context.card, primary_mode: "prompt" },
        demand: [{ id: "p-1", role: "prompt", type: "prompt", text: "who pays eu duties", volume: null, intent: null, citation_gap: 1, platforms: ["chatgpt"] }],
      },
    });
    await renderDetail(promptDetail);
    fireEvent.click(screen.getByRole("button", { name: "Start a blank outline" }));
    expect(screen.getByLabelText("Prompt target")).toHaveValue("p-1");
    fireEvent.change(screen.getByLabelText("Direct answer"), { target: { value: "word ".repeat(61) } });
    expect(screen.getByText("61 / 60 words").className).toContain("coral");
    expect(screen.getByLabelText("Section 1 citable statement")).toHaveAttribute("placeholder", "Citable statement (required)");
  });

  it("explains a missing card and a failed load", async () => {
    vi.mocked(V3API.contentHub.card).mockRejectedValueOnce(new ApiError("nope", "RESOURCE_NOT_FOUND", "r", 404));
    const { unmount } = render(<CardDetailView scope={scope} cardId="missing" />);
    expect(await screen.findByRole("alert")).toHaveTextContent("This card was not found in this project.");
    unmount();
    vi.mocked(V3API.contentHub.card).mockRejectedValueOnce(new ApiError("Boom", "INTERNAL", "r", 500));
    render(<CardDetailView scope={scope} cardId="card-1" />);
    expect(await screen.findByRole("alert")).toHaveTextContent("Boom");
  });

  it("links board cards to their detail page", async () => {
    vi.mocked(V3API.contentHub.board).mockResolvedValue({
      project_id: "project-1", plan_locked_at: null, total_count: 1,
      columns: [{ key: "planned", label: "Planned", tone: "rest", count: 1, cards: [face] }],
      filter_options: { areas: [], kinds: [], owners: [], arguments: [], markets: [] },
    });
    render(<PlanBoard scope={scope} />);
    expect(await screen.findByRole("link", { name: face.title })).toHaveAttribute("href", "/projects/project-1/v3/content-hub/card-1");
  });
});
