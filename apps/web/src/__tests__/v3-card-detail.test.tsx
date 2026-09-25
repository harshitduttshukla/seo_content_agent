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
      approveG1: vi.fn(),
      sendBackG1: vi.fn(),
      generateDraft: vi.fn(),
      runQA: vi.fn(),
      repairDraft: vi.fn(),
      regenerateSection: vi.fn(),
      approveG2: vi.fn(),
      sendBackG2: vi.fn(),
      dismissWarning: vi.fn(),
      moveCard: vi.fn(),
      reorderPlanned: vi.fn(),
    },
    planLock: { lock: vi.fn() },
  },
}));

const scope = { organizationId: "org-1", projectId: "project-1" };
const NO_PRODUCTION = {
  can_run_qa: false,
  can_repair: false,
  can_regenerate_section: false,
  can_review_g2: false,
  can_dismiss_warnings: false,
};

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
    actions: { can_build_bundle: true, can_generate_outline: true, can_save_outline: true, can_review_g1: false, can_generate_draft: false, ...NO_PRODUCTION },
    review: { status: "not_ready", ready: false, can_review: true, reviewers_restricted: false, last_decision: null, history: [] },
    draft: null,
    draft_unreadable: false,
    last_draft_run: null,
    generation: null,
    qa: null,
    g2: null,
    ...overrides,
  };
}

async function renderDetail(data: CardDetail) {
  vi.mocked(V3API.contentHub.card).mockResolvedValue(data);
  render(<CardDetailView scope={scope} cardId="card-1" />);
  await screen.findByRole("heading", { name: face.title, level: 1 });
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

  it("explains that drafting starts after G1", async () => {
    await renderDetail(detail());
    fireEvent.click(screen.getByRole("tab", { name: "Draft" }));
    expect(await screen.findByText("Drafting starts after the outline passes G1.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Generate draft/ })).not.toBeInTheDocument();
  });

  it("builds the bundle with the card revision and reloads", async () => {
    await renderDetail(detail({ bundle: null, actions: { can_build_bundle: true, can_generate_outline: false, can_save_outline: false, can_review_g1: false, can_generate_draft: false, ...NO_PRODUCTION } }));
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

// ── Phase 3: G1 review and draft ─────────────────────────────────────

const outlinedFace = { ...face, state: "outlined" as const, column: "outline" as const, revision: 5 };
const passingChecks = detail().checks.map((c) => ({ ...c, status: "pass" as const }));

function g1Detail(overrides: Partial<CardDetail> = {}): CardDetail {
  return detail({
    card: outlinedFace,
    outline,
    checks: passingChecks,
    actions: { can_build_bundle: true, can_generate_outline: true, can_save_outline: true, can_review_g1: true, can_generate_draft: false, ...NO_PRODUCTION },
    review: { status: "awaiting_review", ready: true, can_review: true, reviewers_restricted: false, last_decision: null, history: [] },
    ...overrides,
  });
}

const sentBack = {
  id: "gate-1", gate: "G1" as const, action: "send_back" as const, reviewer_id: "user-9", reviewer_name: "Priya",
  decided_at: "2026-09-25T09:00:00Z", card_revision: 4, reason: "claim" as const, feedback: "Section one needs the duty claim.",
};

const storedDraft = {
  version: 2,
  draft: {
    schema_version: "v3.draft.v1" as const, primary_mode: "keyword" as const, title: "Landed cost calculation",
    prompt_target_id: null, direct_answer: null,
    sections: [{
      section_id: "s1", order: 1, heading: "What landed cost includes", target_demand_id: "dem-1",
      body: "Duty is charged per item [CLM:11111111-2222-3333-4444-555555555555]. See [the guide](https://site.test/duties).\n\n[NEEDS-CLAIM: refund reduction figure]",
      claim_ids: ["11111111-2222-3333-4444-555555555555"], needs_claim: ["refund reduction figure"],
      internal_links: [{ page_id: "page-1", url: "https://site.test/duties", anchor_text: "" }],
    }],
  },
  unresolved: [{ section_id: "s1", text: "refund reduction figure" }],
  job_run_id: "job-9", prompt_version: "v3.draft.v1", provider: "gemini", model: "gemini-flash", bundle_ref: "run-1",
  bundle_hash: "abc", source_revision: 6, generated_at: "2026-09-25T10:00:00Z", generated_by: "user-1",
};

const draftingFace = { ...face, state: "drafting" as const, column: "draft" as const, revision: 7 };

function draftingDetail(overrides: Partial<CardDetail> = {}): CardDetail {
  return g1Detail({
    card: draftingFace,
    actions: { can_build_bundle: true, can_generate_outline: false, can_save_outline: false, can_review_g1: false, can_generate_draft: true, ...NO_PRODUCTION },
    review: {
      status: "approved", ready: true, can_review: true, reviewers_restricted: false,
      last_decision: { ...sentBack, id: "gate-2", action: "approve", reason: null, feedback: null, card_revision: 5 },
      history: [],
    },
    ...overrides,
  });
}

describe("V3 G1 review and draft", () => {
  beforeEach(() => vi.clearAllMocks());

  it("shows the G1 review state and approves only after confirmation, with the revision", async () => {
    await renderDetail(g1Detail());
    expect(screen.getAllByTestId("g1-status")[0]).toHaveTextContent("G1 review");
    vi.mocked(V3API.contentHub.approveG1).mockResolvedValue({ card: draftingFace, decision: sentBack });

    fireEvent.click(screen.getByRole("button", { name: "Approve" }));
    expect(V3API.contentHub.approveG1).not.toHaveBeenCalled();
    const confirm = screen.getByRole("group", { name: "Confirm G1 approval" });
    fireEvent.click(within(confirm).getByRole("button", { name: "Confirm approval" }));

    await waitFor(() => expect(V3API.contentHub.approveG1).toHaveBeenCalledWith(scope, "card-1", 5));
    expect(await screen.findByText("Outline approved at G1. Drafting can start.")).toBeInTheDocument();
    expect(V3API.contentHub.card).toHaveBeenCalledTimes(2);
  });

  it("requires feedback to send back and sends the typed reason", async () => {
    await renderDetail(g1Detail());
    vi.mocked(V3API.contentHub.sendBackG1).mockResolvedValue({ card: outlinedFace, decision: sentBack });
    fireEvent.click(screen.getByRole("button", { name: "Send back" }));
    const form = screen.getByRole("form", { name: "Send back to outline" });
    const submit = within(form).getByRole("button", { name: "Send back to outline" });
    expect(submit).toBeDisabled();
    fireEvent.change(within(form).getByLabelText("This is about"), { target: { value: "claim" } });
    fireEvent.change(within(form).getByLabelText("Reason · required"), { target: { value: "  Needs the duty claim.  " } });
    fireEvent.click(submit);
    await waitFor(() =>
      expect(V3API.contentHub.sendBackG1).toHaveBeenCalledWith(scope, "card-1", 5, "claim", "Needs the duty claim."),
    );
    expect(await screen.findByText("Outline sent back with feedback.")).toBeInTheDocument();
  });

  it("shows sent-back feedback on the outline and keeps it editable", async () => {
    await renderDetail(g1Detail({
      review: { status: "sent_back", ready: true, can_review: true, reviewers_restricted: false, last_decision: sentBack, history: [sentBack] },
    }));
    expect(screen.getAllByTestId("g1-status")[0]).toHaveTextContent("Sent back");
    const banner = screen.getByTestId("sent-back-banner");
    expect(banner).toHaveTextContent("Section one needs the duty claim.");
    expect(banner).toHaveTextContent("G1 sent back by Priya");
    expect(screen.getByLabelText("Section 1 heading")).toBeEnabled();
  });

  it("keeps Approve disabled while a check fails and explains why", async () => {
    await renderDetail(g1Detail({
      checks: [{ key: "bundle_current", label: "Bundle is current", status: "fail", detail: "Sources changed; rebuild." }],
      actions: { can_build_bundle: true, can_generate_outline: false, can_save_outline: true, can_review_g1: false, can_generate_draft: false, ...NO_PRODUCTION },
      review: { status: "not_ready", ready: false, can_review: true, reviewers_restricted: false, last_decision: null, history: [] },
    }));
    expect(screen.getByRole("button", { name: "Approve" })).toBeDisabled();
    expect(screen.getByText("Approve enables when every check above passes.")).toBeInTheDocument();
  });

  it("shows no gate controls to users who cannot review", async () => {
    await renderDetail(g1Detail({
      review: { status: "awaiting_review", ready: true, can_review: false, reviewers_restricted: true, last_decision: null, history: [] },
      actions: { can_build_bundle: true, can_generate_outline: true, can_save_outline: true, can_review_g1: false, can_generate_draft: false, ...NO_PRODUCTION },
    }));
    expect(screen.queryByRole("button", { name: "Approve" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Send back" })).not.toBeInTheDocument();
    expect(screen.getByText("Only the named G1 reviewers for this project can decide.")).toBeInTheDocument();
  });

  it("reports a G1 revision conflict and a failing-check refusal", async () => {
    await renderDetail(g1Detail());
    vi.mocked(V3API.contentHub.approveG1).mockRejectedValueOnce(
      new ApiError("stale", "VERSION_CONFLICT", "r", 409, null, { current_revision: 6 }),
    );
    fireEvent.click(screen.getByRole("button", { name: "Approve" }));
    fireEvent.click(screen.getByRole("button", { name: "Confirm approval" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Your version is out of date. Reload before saving.");

    vi.mocked(V3API.contentHub.approveG1).mockRejectedValueOnce(
      new ApiError("The outline cannot pass G1 until every check passes.", "G1_CHECKS_FAILED", "r", 409, null, {
        checks: [{ key: "claims_resolve", label: "Claim IDs resolve", status: "fail", detail: "s1 claim is not current" }],
      }),
    );
    fireEvent.click(screen.getByRole("button", { name: "Confirm approval" }));
    const alert = await screen.findByText(/cannot pass G1/);
    expect(alert.closest("[role=alert]")).toHaveTextContent("Claim IDs resolve: s1 claim is not current");
  });

  it("opens drafting cards on the Draft tab, locks the outline and generates with the revision", async () => {
    await renderDetail(draftingDetail());
    expect(screen.queryByText("Drafting starts after the outline passes G1.")).not.toBeInTheDocument();
    expect(screen.getByText("No draft yet.")).toBeInTheDocument();
    expect(screen.getAllByTestId("g1-status")[0]).toHaveTextContent("G1 approved");
    for (const name of ["Generate outline", "Save outline"]) {
      expect(screen.queryByRole("button", { name })).not.toBeInTheDocument();
    }
    let resolve!: (value: Awaited<ReturnType<typeof V3API.contentHub.generateDraft>>) => void;
    vi.mocked(V3API.contentHub.generateDraft).mockReturnValue(new Promise((r) => (resolve = r)));

    fireEvent.click(screen.getByRole("button", { name: "Generate draft" }));
    expect(await screen.findByText(/Generating the draft from the stored bundle/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Generating draft…" })).toBeDisabled();
    expect(V3API.contentHub.generateDraft).toHaveBeenCalledWith(scope, "card-1", 7, undefined);
    resolve({ card: { ...draftingFace, revision: 8 }, draft: storedDraft });
    expect(await screen.findByText(/Draft v2 stored from gemini-flash/)).toBeInTheDocument();

    fireEvent.click(screen.getByRole("tab", { name: "Outline" }));
    expect(await screen.findByText(/Approved at G1 on/)).toBeInTheDocument();
    expect(screen.getByLabelText("Section 1 heading")).toBeDisabled();
  });

  it("renders the draft with claim markers, links and unresolved claim needs", async () => {
    await renderDetail(draftingDetail({
      draft: storedDraft,
      claim_options: [{ id: "11111111-2222-3333-4444-555555555555", text: "Duty per HS code", evidence: "", row: "pillar", argument_id: null, argument_name: null, version: 3, approved: true }],
    }));
    const article = screen.getByRole("article", { name: "Draft" });
    expect(within(article).getByRole("heading", { name: "What landed cost includes" })).toBeInTheDocument();
    const marker = within(article).getByTestId("claim-marker");
    expect(marker).toHaveTextContent("[CLM-11111111]");
    expect(marker).toHaveAttribute("title", "Duty per HS code · v3 approved");
    expect(within(article).getByRole("link", { name: "the guide" })).toHaveAttribute("href", "https://site.test/duties");
    expect(within(article).getByTestId("needs-claim-marker")).toHaveTextContent("[NEEDS-CLAIM: refund reduction figure]");
    expect(within(article).getByTestId("unresolved")).toHaveTextContent("s1: refund reduction figure");
    expect(screen.getByRole("button", { name: "Regenerate draft" })).toBeEnabled();
  });

  it("shows a generation failure and keeps the previous draft", async () => {
    await renderDetail(draftingDetail({
      draft: storedDraft,
      last_draft_run: {
        job_run_id: "job-10", status: "failed", prompt_version: "v3.draft.v1", provider: "gemini", model: "gemini-flash",
        attempts: 2, error: "CLAIM_NOT_IN_OUTLINE", issues: [], created_at: "2026-09-25T11:00:00Z", stored: false,
      },
    }));
    expect(screen.getByRole("status")).toHaveTextContent("was not stored: CLAIM_NOT_IN_OUTLINE. The previous draft is unchanged.");
    expect(screen.getByRole("article", { name: "Draft" })).toBeInTheDocument();

    vi.mocked(V3API.contentHub.generateDraft).mockRejectedValue(
      new ApiError("The generated draft was rejected and not saved.", "DRAFT_INVALID", "r", 422, null, {
        issues: [{ code: "INVENTED_URL", message: "links only to stored project pages", section_id: "s1" }],
      }),
    );
    fireEvent.click(screen.getByRole("button", { name: "Regenerate draft" }));
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("The generated draft was rejected and not saved.");
    expect(alert).toHaveTextContent("s1: links only to stored project pages");
    await waitFor(() => expect(V3API.contentHub.card).toHaveBeenCalledTimes(2)); // failed run reloaded
  });

  it("blocks drafting on a stale bundle and shows no QA, G2 or publish controls", async () => {
    await renderDetail(draftingDetail({
      actions: { can_build_bundle: true, can_generate_outline: false, can_save_outline: false, can_review_g1: false, can_generate_draft: false, ...NO_PRODUCTION },
    }));
    expect(screen.getByRole("button", { name: "Generate draft" })).toBeDisabled();
    expect(screen.getByText("The bundle is out of date. Rebuild it before drafting.")).toBeInTheDocument();
    for (const name of [/publish/i, /^qa/i, /G2/, /export/i]) {
      expect(screen.queryByRole("button", { name })).not.toBeInTheDocument();
    }
  });
});

describe("V3 generation model select", () => {
  beforeEach(() => vi.clearAllMocks());
  const generation = {
    default_model: "claude-sonnet-5",
    options: [
      { provider: "anthropic", model: "claude-sonnet-5" },
      { provider: "anthropic", model: "claude-opus-5-5" },
      { provider: "gemini", model: "gemini-flash-latest" },
      { provider: "gemini", model: "gemini-3.5-flash" },
    ],
  };

  it("groups Gemini and Claude models and sends the chosen one for outline generation", async () => {
    await renderDetail(detail({ generation }));
    const select = screen.getByRole("combobox", { name: "Generation model" });
    expect(select).toHaveValue("claude-sonnet-5");
    const groups = [...select.querySelectorAll("optgroup")].map((g) => [g.label, [...g.querySelectorAll("option")].map((o) => o.value)]);
    expect(groups).toEqual([
      ["Anthropic Claude", ["claude-sonnet-5", "claude-opus-5-5"]],
      ["Google Gemini", ["gemini-flash-latest", "gemini-3.5-flash"]],
    ]);
    vi.mocked(V3API.contentHub.generateOutline).mockResolvedValue({
      outline, job_run_id: "j", prompt_version: "v3.outline.v1", provider: "gemini", model: "gemini-3.5-flash", attempts: 1, bundle_ref: "run-1",
    });
    fireEvent.change(select, { target: { value: "gemini-3.5-flash" } });
    fireEvent.click(screen.getByRole("button", { name: "Generate outline" }));
    await waitFor(() => expect(V3API.contentHub.generateOutline).toHaveBeenCalledWith(scope, "card-1", "gemini-3.5-flash"));
  });

  it("passes the selected model to draft generation", async () => {
    await renderDetail(draftingDetail({ generation }));
    vi.mocked(V3API.contentHub.generateDraft).mockReturnValue(new Promise(() => {}));
    fireEvent.change(screen.getByRole("combobox", { name: "Generation model" }), { target: { value: "gemini-flash-latest" } });
    fireEvent.click(screen.getByRole("button", { name: "Generate draft" }));
    expect(V3API.contentHub.generateDraft).toHaveBeenCalledWith(scope, "card-1", 7, "gemini-flash-latest");
  });

  it("shows no select when only one model is available", async () => {
    await renderDetail(detail({ generation: { default_model: "claude-sonnet-5", options: [generation.options[0]] } }));
    expect(screen.queryByRole("combobox", { name: "Generation model" })).not.toBeInTheDocument();
  });
});

// ── Phase 4: QA, repair, section regeneration and G2 ─────────────────

const reportBase = {
  schema_version: "v3.qa.v1" as const, run_at: "2026-09-25T12:00:00Z", job_run_id: "qa-1", card_revision: 7,
  draft_version: 2, bundle_ref: "run-1", bundle_hash: "abc", model_layer: "ran" as const, model_note: "",
  provider: "anthropic", model: "claude-sonnet-5", dismissals: [], affected_claim_ids: [], affected_urls: [],
};
const errorFinding = {
  id: "f-err", code: "MISSING_CLAIM_MARKER", severity: "error" as const, layer: "deterministic" as const,
  message: "the section does not cite a claim the outline attached to it", section_id: "s1",
  claim_id: "11111111-2222-3333-4444-555555555555", url: null, evidence: null,
  suggested_repair: "Cite the claim.", blocking: true,
};
const warningFinding = {
  id: "f-warn", code: "TONE", severity: "warning" as const, layer: "model" as const, message: "Tone is flat",
  section_id: "s1", claim_id: null, url: null, evidence: "Duty is charged per item", suggested_repair: "", blocking: false,
};
const failedReport = { ...reportBase, status: "failed" as const, findings: [errorFinding, warningFinding],
  error_count: 1, warning_count: 1, affected_sections: ["s1"] };
const passedReport = { ...reportBase, status: "passed" as const, findings: [warningFinding],
  error_count: 0, warning_count: 1, affected_sections: ["s1"] };
const g2Base = {
  status: "not_ready" as const, ready: false, blockers: ["QA has not passed."], can_review: true,
  reviewers_restricted: false, warnings_require_dismissal: true, pending_warning_ids: [], last_decision: null, history: [],
};

function productionDetail(state: "drafting" | "qa_failed" | "qa_passed", overrides: Partial<CardDetail> = {}): CardDetail {
  const base = draftingDetail({ draft: { ...storedDraft, version: 2 } });
  return {
    ...base,
    card: { ...draftingFace, state, column: state === "qa_passed" ? ("review" as const) : ("draft" as const) },
    actions: { ...base.actions, can_generate_draft: state === "drafting", ...NO_PRODUCTION },
    qa: { report: null, stale: false },
    g2: g2Base,
    ...overrides,
  };
}

describe("V3 production QA and G2", () => {
  beforeEach(() => vi.clearAllMocks());

  it("runs QA with the card revision and shows the running state", async () => {
    await renderDetail(productionDetail("drafting", { actions: { ...productionDetail("drafting").actions, can_run_qa: true } }));
    expect(screen.getAllByTestId("qa-status")[0]).toHaveTextContent("QA not run");
    let resolve!: (v: Awaited<ReturnType<typeof V3API.contentHub.runQA>>) => void;
    vi.mocked(V3API.contentHub.runQA).mockReturnValue(new Promise((r) => (resolve = r)));
    fireEvent.click(screen.getByRole("button", { name: "Run QA" }));
    expect(await screen.findByRole("button", { name: "Running QA…" })).toBeDisabled();
    expect(V3API.contentHub.runQA).toHaveBeenCalledWith(scope, "card-1", 7, undefined);
    resolve({ card: draftingFace, report: passedReport });
    expect(await screen.findByText("QA passed with 1 warning(s).")).toBeInTheDocument();
  });

  it("shows failed findings on the checks pane and the draft, and repairs", async () => {
    await renderDetail(productionDetail("qa_failed", {
      qa: { report: failedReport, stale: false },
      actions: { ...productionDetail("qa_failed").actions, can_run_qa: true, can_repair: true, can_regenerate_section: true },
    }));
    expect(screen.getAllByTestId("qa-status")[0]).toHaveTextContent("QA failed");
    const errors = screen.getByRole("list", { name: "QA errors" });
    expect(within(errors).getByText("the section does not cite a claim the outline attached to it")).toBeInTheDocument();
    expect(within(errors).getByText(/section s1 · CLM-11111111/)).toBeInTheDocument();
    expect(within(errors).queryByRole("button", { name: "Dismiss" })).not.toBeInTheDocument(); // errors cannot be dismissed
    expect(screen.getAllByTestId("section-finding").map((c) => c.textContent)).toEqual(["✕ missing claim marker", "! tone"]);
    vi.mocked(V3API.contentHub.repairDraft).mockResolvedValue({ card: draftingFace, draft: { ...storedDraft, version: 3 } });
    fireEvent.click(screen.getByRole("button", { name: "Repair 1 error(s)" }));
    await waitFor(() => expect(V3API.contentHub.repairDraft).toHaveBeenCalledWith(scope, "card-1", 7, undefined));
    expect(await screen.findByText("Draft v3 repaired. Run QA again.")).toBeInTheDocument();
  });

  it("dismisses a warning with a reason and keeps G2 blocked until ready", async () => {
    await renderDetail(productionDetail("qa_passed", {
      qa: { report: passedReport, stale: false },
      g2: { ...g2Base, status: "awaiting_review", blockers: ["Dismiss or fix every warning first."], pending_warning_ids: ["f-warn"] },
      actions: { ...productionDetail("qa_passed").actions, can_dismiss_warnings: true, can_regenerate_section: true },
    }));
    expect(screen.getByRole("list", { name: "G2 blockers" })).toHaveTextContent("Dismiss or fix every warning first.");
    expect(screen.getByRole("button", { name: "Approve draft" })).toBeDisabled();
    vi.mocked(V3API.contentHub.dismissWarning).mockResolvedValue({ card: draftingFace, report: passedReport });
    fireEvent.click(within(screen.getByRole("list", { name: "QA warnings" })).getByRole("button", { name: "Dismiss" }));
    const submit = screen.getByRole("button", { name: "Dismiss warning" });
    expect(submit).toBeDisabled();
    fireEvent.change(screen.getByLabelText("Reason for dismissing"), { target: { value: "Plain tone is intended." } });
    fireEvent.click(submit);
    await waitFor(() =>
      expect(V3API.contentHub.dismissWarning).toHaveBeenCalledWith(scope, "card-1", 7, "f-warn", "Plain tone is intended."),
    );
  });

  it("shows dismissed warnings with who dismissed them", async () => {
    const dismissed = { ...passedReport, dismissals: [{ finding_id: "f-warn", reviewer_id: "u", reviewer_name: "Priya",
      dismissed_at: "2026-09-25T13:00:00Z", reason: "Intended", card_revision: 7 }] };
    await renderDetail(productionDetail("qa_passed", { qa: { report: dismissed, stale: false }, g2: { ...g2Base, status: "awaiting_review", blockers: [] } }));
    expect(screen.getByTestId("dismissed")).toHaveTextContent("Dismissed by Priya");
  });

  it("approves at G2 after confirmation and sends back with required feedback", async () => {
    const ready = productionDetail("qa_passed", {
      qa: { report: { ...passedReport, findings: [], warning_count: 0 }, stale: false },
      g2: { ...g2Base, status: "awaiting_review", ready: true, blockers: [] },
      actions: { ...productionDetail("qa_passed").actions, can_review_g2: true },
    });
    await renderDetail(ready);
    expect(screen.getAllByTestId("g2-status")[0]).toHaveTextContent("G2 review");
    vi.mocked(V3API.contentHub.approveG2).mockResolvedValue({ card: { ...draftingFace, state: "approved" }, decision: sentBack });
    fireEvent.click(screen.getByRole("button", { name: "Approve draft" }));
    expect(V3API.contentHub.approveG2).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "Confirm G2 approval" }));
    await waitFor(() => expect(V3API.contentHub.approveG2).toHaveBeenCalledWith(scope, "card-1", 7));
    expect(await screen.findByText("Draft approved at G2.")).toBeInTheDocument();

    vi.mocked(V3API.contentHub.sendBackG2).mockResolvedValue({ card: draftingFace, decision: sentBack });
    fireEvent.click(screen.getByRole("button", { name: "Send back to drafting" }));
    const form = screen.getByRole("form", { name: "Send back to drafting" });
    expect(within(form).getByRole("button", { name: "Send back" })).toBeDisabled();
    fireEvent.change(within(form).getByLabelText("This is about"), { target: { value: "qa_rule" } });
    fireEvent.change(within(form).getByLabelText("Reason · required"), { target: { value: "Section two is off-topic." } });
    fireEvent.click(within(form).getByRole("button", { name: "Send back" }));
    await waitFor(() =>
      expect(V3API.contentHub.sendBackG2).toHaveBeenCalledWith(scope, "card-1", 7, "qa_rule", "Section two is off-topic."),
    );
  });

  it("regenerates one section from feedback", async () => {
    await renderDetail(productionDetail("drafting", {
      actions: { ...productionDetail("drafting").actions, can_regenerate_section: true },
    }));
    vi.mocked(V3API.contentHub.regenerateSection).mockResolvedValue({ card: draftingFace, draft: { ...storedDraft, version: 3 } });
    fireEvent.click(screen.getByRole("button", { name: "Regenerate section" }));
    fireEvent.change(screen.getByLabelText("Feedback for What landed cost includes"), { target: { value: "Lead with duty." } });
    fireEvent.click(screen.getByRole("button", { name: "Regenerate this section" }));
    await waitFor(() =>
      expect(V3API.contentHub.regenerateSection).toHaveBeenCalledWith(scope, "card-1", "s1", 7, "Lead with duty.", undefined),
    );
    expect(await screen.findByText("Section regenerated (draft v3). Run QA again.")).toBeInTheDocument();
  });

  it("reports provider errors and revision conflicts, reloading after a failed run", async () => {
    await renderDetail(productionDetail("drafting", { actions: { ...productionDetail("drafting").actions, can_run_qa: true } }));
    vi.mocked(V3API.contentHub.runQA).mockRejectedValueOnce(
      new ApiError("The AI provider failed during QA. Try again.", "AI_PROVIDER_ERROR", "r", 502),
    );
    fireEvent.click(screen.getByRole("button", { name: "Run QA" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("The AI provider failed during QA. Try again.");
    await waitFor(() => expect(V3API.contentHub.card).toHaveBeenCalledTimes(2));

    vi.mocked(V3API.contentHub.runQA).mockRejectedValueOnce(new ApiError("stale", "VERSION_CONFLICT", "r", 409));
    fireEvent.click(screen.getByRole("button", { name: "Run QA" }));
    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent("Your version is out of date. Reload before saving."));
  });

  it("keeps showing the passed QA result on an approved card", async () => {
    await renderDetail(productionDetail("qa_passed", {
      card: { ...draftingFace, state: "approved", column: "approved" },
      qa: { report: passedReport, stale: true },
      g2: { ...g2Base, status: "approved", blockers: [] },
    }));
    expect(screen.getAllByTestId("qa-status")[0]).toHaveTextContent("QA passed");
    expect(screen.getAllByTestId("g2-status")[0]).toHaveTextContent("Approved");
    expect(screen.getByText("Approved. Publishing arrives in a later phase.")).toBeInTheDocument();
  });

  it("flags a stale QA report and shows no publishing controls", async () => {
    await renderDetail(productionDetail("qa_passed", {
      qa: { report: passedReport, stale: true },
      g2: { ...g2Base, status: "awaiting_review", blockers: ["The QA report is stale; run QA again."] },
    }));
    expect(screen.getAllByTestId("qa-status")[0]).toHaveTextContent("QA stale");
    expect(screen.getByText("The draft changed after this QA run; run QA again before G2.")).toBeInTheDocument();
    expect(screen.queryAllByTestId("section-finding")).toHaveLength(0); // stale findings are not annotated
    for (const name of [/publish/i, /export/i, /go live/i]) {
      expect(screen.queryByRole("button", { name })).not.toBeInTheDocument();
    }
  });
});
