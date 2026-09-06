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
