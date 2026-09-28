import type { components } from "@seo-content/shared-types";

export type User = components["schemas"]["UserDetail"];
export type Organization = components["schemas"]["OrganizationDetail"];
export type Project = components["schemas"]["ProjectDetail"];
export type Website = components["schemas"]["WebsiteDetail"];
export type ErrorItem = components["schemas"]["ErrorItem"];

export type CrawlJob = components["schemas"]["CrawlJobDetail"];
export type CrawlStatusSummary = components["schemas"]["CrawlStatusSummary"];
export type WebsiteVerification = components["schemas"]["WebsiteVerificationDetail"];
export type ContentPageSummary = components["schemas"]["ContentPageSummary"];
export type ContentPageDetail = components["schemas"]["ContentPageDetail"];
export type PageLink = components["schemas"]["PageLinkDetail"];

// Phase 3: Strategy, Keywords, Clusters, Architecture, Opportunities
export type SEOStrategy = components["schemas"]["StrategyResponse"];
export type SEOStrategyVersion = components["schemas"]["StrategyVersionResponse"];
export type StrategyData = components["schemas"]["StrategyDataSchema-Output"];
export type KeywordCluster = components["schemas"]["KeywordClusterDetail"];
export type KeywordClusterMember = components["schemas"]["KeywordClusterMemberDetail"];
export type ClusteringRun = components["schemas"]["ClusteringRunResponse"];
export type KeywordImport = components["schemas"]["KeywordImportResponse"];
export type KeywordPageMapping = components["schemas"]["KeywordPageMappingDetail"];
export type CannibalizationWarning = components["schemas"]["CannibalizationWarningDetail"];
export type ContentArchitectureGraph = components["schemas"]["ContentArchitectureGraphResponse"];

// Phase 4: Content Map, Planned Pages, SEO Guide, Internal Linking
export type ContentMapNode = components["schemas"]["ContentMapNodeDTO"];
export type ContentMapEdge = components["schemas"]["ContentMapEdgeDTO"];
export type ContentMapGraph = components["schemas"]["ContentMapGraphResponse"];
export type ValidationIssue = components["schemas"]["ValidationIssue"];
export type ContentMapValidation = components["schemas"]["ContentMapValidationResponse"];
export type ContentArchitectureVersion = components["schemas"]["ContentArchitectureVersionDetail"];
export type PageRelationship = components["schemas"]["PageRelationshipDetail"];
export type LinkOpportunity = components["schemas"]["LinkOpportunityDetail"];
export type InternalLinksSummary = components["schemas"]["InternalLinksSummary"];
export type OrphanPage = components["schemas"]["OrphanPageDetail"];

export type ApiEnvelope<T> = {
  data: T | null;
  meta: { request_id: string; next_cursor?: string | null; has_more?: boolean | null };
  errors: ErrorItem[];
};

// Phase 5: Block Editor

export type BlockType =
  | "DOCUMENT_TITLE"
  | "HEADING"
  | "PARAGRAPH"
  | "BULLET_LIST"
  | "NUMBERED_LIST"
  | "QUOTE"
  | "IMAGE"
  | "LINK"
  | "TABLE"
  | "FAQ";

export interface ContentBlock {
  id: string;
  type: BlockType;
  text: string;
  level?: number | null;
  items?: string[] | null;
  data?: Record<string, unknown>;
}

export interface ContentDocument {
  id: string;
  organization_id: string;
  project_id: string;
  website_id?: string | null;
  page_id: string;
  brief_id?: string | null;
  title: string;
  slug: string;
  status: string;
  current_version: number;
  lock_version: number;
  content_blocks: ContentBlock[];
  plain_text: string;
  word_count: number;
  created_by_id?: string | null;
  updated_by_id?: string | null;
  created_at: string;
  updated_at: string;
}

export interface ContentDocumentVersion {
  id: string;
  document_id: string;
  organization_id: string;
  project_id: string;
  version: number;
  content_blocks: ContentBlock[];
  plain_text: string;
  word_count: number;
  change_type: string;
  change_summary: string;
  created_by_id?: string | null;
  created_at: string;
}

export interface AIProposal {
  id: string;
  document_id: string;
  chat_message_id?: string | null;
  status: "PROPOSED" | "APPROVED" | "REJECTED" | "APPLIED" | "FAILED";
  operation_type: string;
  target_block_ids: string[];
  old_content: unknown;
  proposed_content: unknown;
  diff_summary: Record<string, unknown>;
  reason: string;
  ai_provider: string;
  model: string;
  reviewed_at?: string | null;
  reviewed_by_id?: string | null;
  applied_at?: string | null;
  applied_version?: number | null;
  created_at: string;
}

export interface ChatMessage {
  id: string;
  session_id: string;
  document_id: string;
  role: "user" | "assistant" | "system";
  content: string;
  context_snapshot: Record<string, unknown>;
  token_usage: Record<string, unknown>;
  created_at: string;
  proposal?: AIProposal | null;
}

export interface ChatSession {
  id: string;
  organization_id: string;
  project_id: string;
  document_id: string;
  title: string;
  created_by_id?: string | null;
  created_at: string;
  messages?: ChatMessage[];
}

// Phase 6: AI Orchestrator & Tool/Action Layer
export type WorkflowStatus =
  | "PENDING"
  | "PLANNING"
  | "RUNNING"
  | "WAITING_FOR_APPROVAL"
  | "COMPLETED"
  | "FAILED"
  | "CANCELLED";

export type StepStatus =
  | "PENDING"
  | "RUNNING"
  | "WAITING_FOR_APPROVAL"
  | "COMPLETED"
  | "FAILED"
  | "SKIPPED";

export type RiskLevel =
  | "READ"
  | "SUGGEST"
  | "WRITE"
  | "DESTRUCTIVE"
  | "EXTERNAL_ACTION";

export type ToolAvailability = "AVAILABLE" | "UNAVAILABLE";

export interface ToolDescriptorDTO {
  name: string;
  description: string;
  input_schema: Record<string, unknown>;
  output_schema: Record<string, unknown>;
  authentication_requirements: string[];
  permissions: string[];
  cost: {
    estimated_usd_per_call: string;
    billing_unit: string;
  };
  rate_limits: {
    max_calls_per_workflow: number;
    max_concurrent_calls: number;
  };
  availability: ToolAvailability;
  version: string;
  risk_level: RiskLevel;
  required_permission: string;
  enabled: boolean;
}

export interface ToolExecutionRecordDTO {
  id: string;
  tool_name: string;
  status: string;
  risk_level: RiskLevel;
  requires_approval: boolean;
  started_at: string;
  completed_at?: string | null;
  duration_ms?: number | null;
  error_message?: string | null;
  output?: Record<string, unknown> | null;
}

export interface WorkflowStepDetail {
  id: string;
  workflow_id: string;
  step_index: number;
  tool_name: string;
  status: StepStatus;
  input: Record<string, unknown>;
  output?: Record<string, unknown> | null;
  error_message?: string | null;
  retry_count: number;
  started_at?: string | null;
  completed_at?: string | null;
}

export interface WorkflowDetail {
  id: string;
  organization_id: string;
  project_id: string;
  document_id?: string | null;
  brief_id?: string | null;
  created_by_id?: string | null;
  intent: string;
  status: WorkflowStatus;
  current_step: number;
  plan: Array<{
    step_index: number;
    tool_name: string;
    risk_level: RiskLevel;
    requires_approval: boolean;
    rationale: string;
    input_arguments: Record<string, unknown>;
  }>;
  result?: Record<string, unknown> | null;
  error_message?: string | null;
  token_usage?: Record<string, unknown> | null;
  created_at: string;
  updated_at: string;
  completed_at?: string | null;
  steps: WorkflowStepDetail[];
  executions: ToolExecutionRecordDTO[];
}

// Phase 7: V3 Foundation
export interface ClaimBase {
  id: string;
  row: string;
  text: string;
  evidence: string;
  approved: boolean;
  approved_by: string | null;
  version: number;
  superseded_by: string | null;
  clm_number: string;
  citation_count?: number;
}

export type CanvasAnchorType = "company" | "persona" | "use_case" | "alternative" | "category";

export interface CanvasAnchor {
  anchor_type: CanvasAnchorType | null;
  text: string;
  primary: boolean;
}

export interface CanvasAnchorInput {
  anchor_type: CanvasAnchorType;
  text: string;
  primary: boolean;
}

export interface CanvasArgumentInput {
  sub_problem: string;
  differentiation_pillar: string;
  capability: string;
  features: string[];
  benefit: string;
}

export interface CanvasClaimInput {
  row: string;
  text: string;
  evidence: string;
  argument_id?: string | null;
}

export interface ClaimEditConfirm {
  text: string;
  evidence: string;
}

export interface ClaimEditCheckResponse {
  citation_count: number;
  claim_text: string;
  claim_id: string;
}

export interface ClaimEditConfirmResponse {
  old_claim_id: string;
  new_claim_id: string;
  new_version: number;
  job_run_id: string;
}

export interface ContentCardStub {
  id: string;
  title: string;
  kind: string;
  state: string;
  url?: string | null;
}

export interface ClaimCitationInput {
  content_card_id?: string | null;
  title?: string;
  url?: string;
}

export interface CanvasListItem {
  id: string;
  product_line: string | null;
  name: string;
  argument_count: number;
}

export interface CanvasListResponse {
  company_canvas: CanvasListItem | null;
  product_lines: CanvasListItem[];
}

export interface CanvasArgument {
  id: string;
  order: number;
  sub_problem: string | null;
  differentiation_pillar: string | null;
  capability: string | null;
  features: string[];
  benefit: string | null;
  claims: ClaimBase[];
  inherited: boolean;
  override: boolean;
}

export interface CanvasDetail {
  id: string;
  product_line: string | null;
  name: string;
  anchors: CanvasAnchor[];
  problem_summary: string | null;
  differentiation_summary: string | null;
  version: number;
  arguments: CanvasArgument[];
  problem_summary_claim: ClaimBase | null;
  differentiation_summary_claim: ClaimBase | null;
  pitch_claim: ClaimBase | null;
}

export interface Area {
  id: string;
  canvas_id: string;
  parent_id: string | null;
  name: string;
  default_argument_id: string | null;
}

export interface AreaInput {
  name: string;
  parent_id?: string | null;
  default_argument_id?: string | null;
}

export interface ClaimDrilldown {
  argument_chain: ClaimBase[];
  demand_nodes: DemandNode[];
  content_cards: ContentCardStub[];
}

export interface DemandNode {
  id: string;
  text: string;
  type: "keyword" | "prompt";
  origin: string;
  volume: number | null;
  country: string | null;
  area_id: string | null;
  argument_id: string | null;
  funnel: string | null;
  intent: string | null;
  status: "pending" | "kept" | "discarded" | "pending_classify";
  score: number | null;
  confidence: number | null;
  discard_reason: string | null;
  citation_gap: number | null;
  platforms: string[];
  competitor_names: string[];
}

export interface DemandListResponse {
  items: DemandNode[];
  summary: {
    total_discarded: number;
    below_065_confidence: number;
    total_kept: number;
    gsc_striking_distance_count: number;
  };
  meta: { total_count: number; page: number; page_size: number };
}

export interface SiteImportResponse {
  job_run_id: string;
  status: string;
  created_count: number;
  existing_count: number;
}

export interface SiteImportStatusResponse extends SiteImportResponse {
  created_at: string;
  completed_at: string | null;
  unmapped_count: number;
}

export interface BulkUpdateResponse {
  updated_count: number;
  job_run_id: string;
}

export interface DemandImportItem {
  text: string;
  type: "keyword" | "prompt";
  volume?: number | null;
  country?: string | null;
  area?: string | null;
  funnel?: "tofu" | "mofu" | "bofu" | null;
  origin?: "upload" | "gsc_striking_distance" | "insight";
  competitor?: string | null;
  confidence?: number | null;
  score?: number | null;
  status?: "pending" | "kept" | "discarded" | "pending_classify";
}

export interface DemandImportResponse {
  created_count: number;
  existing_count: number;
  job_run_id: string;
}

export interface BrandKitInput {
  spelling: string;
  banned_words: string[];
  style: string;
  vocabulary: string;
  tone_profile: string;
  profile_provisional: boolean;
}

export interface BrandKit extends BrandKitInput {
  id: string;
  revision: number;
  updated_at: string;
}

export interface VoiceSnippetInput {
  source_type: string;
  source_name: string;
  captured_on: string;
  content: string;
  area_id?: string | null;
}

export interface VoiceSnippet extends VoiceSnippetInput {
  id: string;
  created_at: string;
}

export interface SocialProofInput {
  label: string;
  proof_type: string;
  area_ids: string[];
  markets: string[];
  approved: boolean;
}

export interface SocialProof extends SocialProofInput {
  id: string;
  created_at: string;
}

export interface BrandKitDetail {
  brand_kit: BrandKit | null;
  voice_snippets: VoiceSnippet[];
  social_proofs: SocialProof[];
}

// ── V3 strategy map (handoff §4.4) ───────────────────────────────────

export interface MapAreaNode {
  id: string;
  name: string;
  parent_id: string | null;
  default_argument_id: string | null;
  default_argument_pillar: string | null;
  demand_count: number;
  card_count: number;
  card_states: Record<string, number>;
  descendant_card_states: Record<string, number>;
  is_unmapped: boolean;
  content_gap: boolean;
  children: MapAreaNode[];
}

export interface MapCanvasNode {
  id: string;
  name: string;
  product_line: string | null;
  is_company: boolean;
  argument_count: number;
  cell_count: number;
  inherits: string[];
  override_count: number;
  adds: string[];
  areas: MapAreaNode[];
  product_lines: MapCanvasNode[];
}

export interface StrategyMap {
  company_canvas: MapCanvasNode | null;
  unassigned_card_count: number;
}

// ── V3 demand Plan (handoff §4.5) ────────────────────────────────────

export interface PlanKindCounts {
  pillar: number;
  cluster: number;
  compare: number;
  refresh: number;
  secondary_demands: number;
}

export interface PlanCardPreview {
  kind: "pillar" | "cluster" | "compare" | "refresh";
  primary_node_id: string;
  primary_text: string;
  primary_type: "keyword" | "prompt";
  score: number | null;
  volume: number | null;
  word_budget: number;
  secondary_demands: { node_id: string; text: string }[];
}

export interface PlanGroupPreview {
  area_id: string;
  area_name: string;
  market_country: string | null;
  counts: PlanKindCounts;
  cards: PlanCardPreview[];
}

export interface PlanPreview {
  selected_count: number;
  eligible_count: number;
  skipped_count: number;
  totals: PlanKindCounts;
  groups: PlanGroupPreview[];
  skipped: { node_id: string; text: string | null; reason: string }[];
  deferred: string[];
}

export interface PlanResult extends PlanPreview {
  created_count: number;
  created_card_ids: string[];
  job_run_id: string;
}

// ── V3 Content Hub "Lock plan" (handoff §5.1) ────────────────────────

export interface PlanLockState {
  project_id: string;
  /** Set once by the server's clock; repeat locks return the original. */
  plan_locked_at: string;
  locked_now: boolean;
}


// ── V3 Content Hub plan board (handoff §5.1) ─────────────────────────
// Mirrors app/domains/content_cards/schemas.py (ContentHubBoard and friends).

export type BoardColumnKey = "backlog" | "planned" | "outline" | "draft" | "review" | "approved" | "live";

export interface BoardRef {
  id: string;
  name: string;
}

export interface BoardDemandRef {
  id: string;
  text: string;
  volume: number | null;
  citation_gap: number | null;
  platform_count: number;
}

export interface BoardCard {
  id: string;
  title: string;
  kind: string;
  /** Stored §5.2 state, e.g. qa_passed; `column` is where the board shows it. */
  state: string;
  column: BoardColumnKey;
  origin: string;
  area: BoardRef | null;
  argument: BoardRef | null;
  owner: BoardRef | null;
  market: string | null;
  due: string | null;
  priority: number;
  primary_demand: BoardDemandRef | null;
  primary_prompt: BoardDemandRef | null;
  secondary_demand_count: number;
  score: number | null;
  has_qa_report: boolean;
  url: string | null;
  cms_id: string | null;
  published_at: string | null;
  stale_claim_count: number;
  planned_at: string | null;
  /** Server-derived "new" chip: planned_at strictly after plan_locked_at. */
  is_new_after_plan_lock: boolean;
  revision: number;
  updated_at: string;
}

export interface BoardColumnView {
  key: BoardColumnKey;
  label: string;
  tone: "rest" | "system" | "human";
  count: number;
  cards: BoardCard[];
}

export interface BoardFilterOptions {
  areas: BoardRef[];
  kinds: string[];
  owners: BoardRef[];
  arguments: BoardRef[];
  markets: string[];
}

export interface ContentHubBoard {
  project_id: string;
  plan_locked_at: string | null;
  total_count: number;
  columns: BoardColumnView[];
  filter_options: BoardFilterOptions;
}

export interface BoardFilters {
  area_id?: string;
  kind?: string;
  owner_id?: string;
  argument_id?: string;
  market?: string;
}

// ── V3 card detail, context bundle and outline (handoff §6.1–6.2) ────
// Mirrors app/domains/ai/context.py (CardContextBundle), content_cards/outline.py
// (OutlineV3) and content_cards/workflow_schemas.py.

export interface PlannedInternalLink {
  page_id: string;
  url: string;
  anchor_text: string;
}

export interface OutlineSection {
  section_id: string;
  order: number;
  heading: string;
  purpose: string;
  claim_ids: string[];
  target_demand_id: string | null;
  planned_internal_links: PlannedInternalLink[];
  citable_statement: string | null;
  notes: string;
  needs_claim: string[];
}

export interface OutlineV3 {
  schema_version: "v3.outline.v1";
  primary_mode: "keyword" | "prompt";
  title: string;
  prompt_target_id: string | null;
  direct_answer: string | null;
  sections: OutlineSection[];
}

export interface BundleDemand {
  id: string;
  role: "primary" | "prompt" | "secondary";
  type: string;
  text: string;
  volume: number | null;
  intent: string | null;
  citation_gap: number | null;
  platforms: string[];
}

export interface BundleClaim {
  id: string;
  text: string;
  evidence: string;
  row: string;
  argument_id: string | null;
  version: number;
}

export interface BundleSource {
  section: string;
  source_type: string;
  source_id: string;
  version: number | null;
}

export interface CardContextBundle {
  card: {
    id: string;
    title: string;
    kind: string;
    origin: string;
    market: string | null;
    word_budget: number | null;
    url: string | null;
    primary_mode: "keyword" | "prompt";
  };
  rules: {
    brand: {
      tone: string | null;
      voice: string | null;
      style: string | null;
      words_to_avoid: string[];
      formatting_rules: string[];
    };
    claim_policy: string;
  };
  claims: BundleClaim[];
  demand: BundleDemand[];
  tone: { tone: string | null; voice_snippets: string[]; social_proof: string[] };
  siblings: { id: string; title: string; kind: string; state: string; url: string | null }[];
  references: {
    existing_pages: { pages: { page_id: string | null; url: string; title: string | null; relationship: string }[] };
    website: {
      crawled_pages: {
        page_id: string | null;
        url: string;
        title: string | null;
        headings: string[];
        content_snippet: string | null;
        word_count: number;
      }[];
    };
    internal_linking: { opportunities: Record<string, string>[] };
  };
  pitch: {
    argument_id: string | null;
    differentiation_pillar: string;
    sub_problem: string;
    capability: string;
    benefit: string;
    problem_summary: string;
    differentiation_summary: string;
  };
  sources: BundleSource[];
  budget: { max_tokens: number; used_tokens: number; truncated_sections: string[] };
}

export interface BundleStatus {
  bundle_ref: string;
  content_hash: string;
  built_at: string;
  is_current: boolean;
}

export interface ClaimOption {
  id: string;
  text: string;
  evidence: string;
  row: string;
  argument_id: string | null;
  argument_name: string | null;
  version: number;
  approved: boolean;
}

export interface CardCheck {
  key: string;
  label: string;
  status: "pass" | "fail" | "not_applicable";
  detail: string;
}

export interface CardDetail {
  card: BoardCard;
  outline: OutlineV3 | null;
  outline_unreadable: boolean;
  bundle: BundleStatus | null;
  context: CardContextBundle;
  claim_options: ClaimOption[];
  checks: CardCheck[];
  actions: CardActions;
  review: G1Review;
  draft: StoredDraft | null;
  draft_unreadable: boolean;
  last_draft_run: DraftRunStatus | null;
  /** Models offered across every provider with a key; the default is first. */
  generation: GenerationOptions | null;
  qa: QAState | null;
  g2: G2Review | null;
}

// ── V3 Production QA, repair and G2 (handoff §5.2, §6.4) ──────────────
// Mirrors content_cards/qa.py and workflow_schemas.py.

export type QASeverity = "error" | "warning" | "info";

export interface QAFinding {
  id: string;
  code: string;
  severity: QASeverity;
  layer: "deterministic" | "model";
  message: string;
  section_id: string | null;
  claim_id: string | null;
  url: string | null;
  evidence: string | null;
  suggested_repair: string;
  blocking: boolean;
}

export interface WarningDismissal {
  finding_id: string;
  reviewer_id: string;
  reviewer_name: string | null;
  dismissed_at: string;
  reason: string;
  card_revision: number;
}

export interface QAReport {
  schema_version: "v3.qa.v1";
  status: "passed" | "failed";
  run_at: string;
  job_run_id: string;
  card_revision: number;
  draft_version: number;
  bundle_ref: string;
  bundle_hash: string;
  findings: QAFinding[];
  model_layer: "ran" | "skipped";
  model_note: string;
  provider: string | null;
  model: string | null;
  dismissals: WarningDismissal[];
  error_count: number;
  warning_count: number;
  affected_sections: string[];
  affected_claim_ids: string[];
  affected_urls: string[];
}

export interface QAState {
  report: QAReport | null;
  stale: boolean;
}

export type G2Status = "not_ready" | "awaiting_review" | "sent_back" | "approved";

export interface G2Review {
  status: G2Status;
  ready: boolean;
  blockers: string[];
  can_review: boolean;
  reviewers_restricted: boolean;
  warnings_require_dismissal: boolean;
  pending_warning_ids: string[];
  last_decision: GateDecision | null;
  history: GateDecision[];
}

export interface QARunResponse {
  card: BoardCard;
  report: QAReport;
}

export interface DraftRevisionResponse {
  card: BoardCard;
  draft: StoredDraft;
}

export interface WarningDismissResponse {
  card: BoardCard;
  report: QAReport;
}

export interface GenerationOptions {
  default_model: string | null;
  options: { provider: "gemini" | "anthropic" | string; model: string }[];
}

export interface CardActions {
  can_build_bundle: boolean;
  can_generate_outline: boolean;
  can_save_outline: boolean;
  can_review_g1: boolean;
  can_generate_draft: boolean;
  can_run_qa: boolean;
  can_repair: boolean;
  can_regenerate_section: boolean;
  can_review_g2: boolean;
  can_dismiss_warnings: boolean;
}

// ── V3 G1 review and draft (handoff §5.2-5.3, §6.3) ──────────────────
// Mirrors content_cards/workflow_schemas.py and content_cards/draft.py.

export type G1Reason = "writer" | "claim" | "tone_rule" | "plan";
export type G2Reason = G1Reason | "qa_rule";
export type G1Status = "not_ready" | "awaiting_review" | "sent_back" | "approved";

export interface GateDecision {
  id: string;
  gate: "G1" | "G2";
  action: "approve" | "send_back";
  reviewer_id: string | null;
  reviewer_name: string | null;
  decided_at: string;
  card_revision: number;
  reason: G2Reason | null;
  feedback: string | null;
}

export interface G1Review {
  status: G1Status;
  ready: boolean;
  can_review: boolean;
  reviewers_restricted: boolean;
  last_decision: GateDecision | null;
  history: GateDecision[];
}

export interface G1DecisionResponse {
  card: BoardCard;
  decision: GateDecision;
}

export interface DraftSection {
  section_id: string;
  order: number;
  heading: string;
  target_demand_id: string | null;
  /** Markdown-ish text with inline [CLM:<uuid>] and [NEEDS-CLAIM: …] markers. */
  body: string;
  claim_ids: string[];
  needs_claim: string[];
  internal_links: { page_id: string; url: string; anchor_text: string }[];
}

export interface DraftV3 {
  schema_version: "v3.draft.v1";
  primary_mode: "keyword" | "prompt";
  title: string;
  prompt_target_id: string | null;
  direct_answer: string | null;
  sections: DraftSection[];
}

export interface StoredDraft {
  version: number;
  draft: DraftV3;
  unresolved: { section_id: string; text: string }[];
  job_run_id: string;
  prompt_version: string;
  provider: string;
  model: string;
  bundle_ref: string;
  bundle_hash: string;
  source_revision: number;
  generated_at: string;
  generated_by: string;
  generation_type?: "generate" | "repair" | "section_regeneration";
  previous_version?: number | null;
  trigger?: Record<string, unknown>;
}

export interface DraftRunStatus {
  job_run_id: string;
  status: string;
  prompt_version: string;
  provider: string;
  model: string;
  attempts: number;
  error: string | null;
  issues: { code: string; message: string; section_id: string | null; ref: string | null }[];
  created_at: string;
  stored: boolean;
}

export interface DraftGenerateResponse {
  card: BoardCard;
  draft: StoredDraft;
}

export interface BundleBuildResponse {
  card: BoardCard;
  bundle: BundleStatus;
  reused: boolean;
}

export interface OutlineProposal {
  outline: OutlineV3;
  job_run_id: string;
  prompt_version: string;
  provider: string;
  model: string;
  attempts: number;
  bundle_ref: string;
}

export interface OutlineSaveResponse {
  card: BoardCard;
  outline: OutlineV3;
}

// ── Google Search Console (Phase 6A, read-only) ──────────────────────
// Mirrors app/domains/search_console/schemas.py. No schema carries a credential.

export type GscConnectionState = "not_connected" | "pending" | "connected" | "reauth_required" | "disconnected";

export interface GscMappedProperty {
  site_url: string;
  permission_level: string;
  last_synced_at: string | null;
  last_sync_start: string | null;
  last_sync_end: string | null;
  stored_rows: number;
}

export interface GscSyncRun {
  job_run_id: string;
  status: string;
  started_at: string | null;
  completed_at: string | null;
  start_date: string | null;
  end_date: string | null;
  rows_fetched: number;
  rows_stored: number;
  rows_rejected: number;
  truncated: boolean;
  error: string | null;
}

export interface GscWebsite {
  website_id: string;
  website_name: string;
  base_url: string;
  property: GscMappedProperty | null;
  last_sync: GscSyncRun | null;
}

export interface GscStatus {
  project_id: string;
  configured: boolean;
  state: GscConnectionState;
  google_account_email: string | null;
  connected_at: string | null;
  last_error: string | null;
  can_manage: boolean;
  websites: GscWebsite[];
}

export interface GscAvailableProperty {
  site_url: string;
  permission_level: string;
  mapped_website_ids: string[];
}

export interface GscAnalyticsRow {
  date: string;
  query: string;
  page: string;
  clicks: number;
  impressions: number;
  ctr: number;
  position: number;
}

export interface GscAnalytics {
  website_id: string;
  site_url: string;
  start_date: string;
  end_date: string;
  totals: {
    clicks: number;
    impressions: number;
    ctr: number;
    position: number | null;
    rows: number;
    queries: number;
    pages: number;
  };
  rows: GscAnalyticsRow[];
  next_offset: number | null;
}
