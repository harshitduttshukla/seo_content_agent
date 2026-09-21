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
export type Keyword = components["schemas"]["KeywordDetail"];
export type KeywordCluster = components["schemas"]["KeywordClusterDetail"];
export type KeywordClusterMember = components["schemas"]["KeywordClusterMemberDetail"];
export type ClusteringRun = components["schemas"]["ClusteringRunResponse"];
export type KeywordImport = components["schemas"]["KeywordImportResponse"];
export type ContentPillar = components["schemas"]["ContentPillarDetail"];
export type Topic = components["schemas"]["TopicDetail"];
export type KeywordPageMapping = components["schemas"]["KeywordPageMappingDetail"];
export type CannibalizationWarning = components["schemas"]["CannibalizationWarningDetail"];
export type ContentOpportunity = components["schemas"]["ContentOpportunityDetail"];
export type ContentArchitectureGraph = components["schemas"]["ContentArchitectureGraphResponse"];

// Phase 4: Content Map, Planned Pages, SEO Guide, Internal Linking
export type PlannedContentPage = components["schemas"]["PlannedContentPageDetail"];
export type PlannedContentPageList = components["schemas"]["PlannedContentPageList"];
export type PageKeyword = components["schemas"]["PageKeywordDetail"];
export type ContentMapNode = components["schemas"]["ContentMapNodeDTO"];
export type ContentMapEdge = components["schemas"]["ContentMapEdgeDTO"];
export type ContentMapGraph = components["schemas"]["ContentMapGraphResponse"];
export type ValidationIssue = components["schemas"]["ValidationIssue"];
export type ContentMapValidation = components["schemas"]["ContentMapValidationResponse"];
export type ContentArchitectureVersion = components["schemas"]["ContentArchitectureVersionDetail"];
export type SEOGuide = components["schemas"]["SEOGuideDetail"];
export type SEOGuideOutlineSection = components["schemas"]["SEOGuideOutlineSection"];
export type SEOGuideVersion = components["schemas"]["SEOGuideVersionDetail"];
export type PageRelationship = components["schemas"]["PageRelationshipDetail"];
export type LinkOpportunity = components["schemas"]["LinkOpportunityDetail"];
export type InternalLinksSummary = components["schemas"]["InternalLinksSummary"];
export type OrphanPage = components["schemas"]["OrphanPageDetail"];

export type ApiEnvelope<T> = {
  data: T | null;
  meta: { request_id: string; next_cursor?: string | null; has_more?: boolean | null };
  errors: ErrorItem[];
};

// Phase 5: Content Brief & Block Editor
export type BriefStatus = "DRAFT" | "PROPOSED" | "REVIEW" | "APPROVED" | "ARCHIVED";

export interface InternalLinkTarget {
  target_page_id?: string | null;
  title: string;
  url: string;
}

export interface ContentBrief {
  id: string;
  organization_id: string;
  project_id: string;
  website_id?: string | null;
  page_id: string;
  seo_guide_id?: string | null;
  version: number;
  status: BriefStatus;
  primary_keyword: string;
  secondary_keywords: string[];
  search_intent: string;
  target_audience: string;
  business_goal: string;
  content_type: string;
  recommended_title: string;
  recommended_url: string;
  meta_title: string;
  meta_description: string;
  target_word_count: number;
  required_topics: string[];
  key_entities: string[];
  questions_to_answer: string[];
  internal_link_targets: InternalLinkTarget[];
  external_source_requirements: string[];
  content_requirements: string[];
  brand_requirements: Record<string, unknown>;
  created_by_id?: string | null;
  updated_by_id?: string | null;
  created_at: string;
  updated_at: string;
}

export interface ContentBriefVersion {
  id: string;
  brief_id: string;
  organization_id: string;
  project_id: string;
  version: number;
  snapshot_data: Record<string, unknown>;
  change_summary: string;
  created_by_id?: string | null;
  created_at: string;
}

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

export interface QualityCheckItem {
  name: string;
  status: "PASS" | "WARNING" | "FAIL";
  message: string;
  recommendation: string;
}

export interface SEOQualityReport {
  document_id: string;
  title: string;
  word_count: number;
  target_word_count: number;
  score_percentage: number;
  checks: QualityCheckItem[];
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
  funnel?: "tofu" | "mofu" | "bofu" | null;
  origin?: "upload" | "gsc_striking_distance" | "insight";
  competitor?: string | null;
  confidence?: number | null;
}

export interface DemandImportResponse {
  created_count: number;
  existing_count: number;
  job_run_id: string;
}
