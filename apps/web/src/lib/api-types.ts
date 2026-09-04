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

export type ApiEnvelope<T> = {
  data: T | null;
  meta: { request_id: string; next_cursor?: string | null; has_more?: boolean | null };
  errors: ErrorItem[];
};
