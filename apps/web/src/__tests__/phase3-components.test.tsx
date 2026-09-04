import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { StrategyManager } from "@/features/strategy/strategy-manager";
import { KeywordsDashboard } from "@/features/keywords/keywords-dashboard";
import { ArchitectureDashboard } from "@/features/content/architecture-dashboard";
import type {
  CannibalizationWarning,
  ContentArchitectureGraph,
  ContentOpportunity,
  ContentPillar,
  Keyword,
  KeywordCluster,
  KeywordPageMapping,
  SEOStrategy,
  Topic,
} from "@/lib/api-types";

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push: vi.fn(),
    refresh: vi.fn(),
  }),
}));

const mockStrategy: SEOStrategy = {
  id: "strat-1",
  organization_id: "org-1",
  project_id: "proj-1",
  current_version: 1,
  status: "active",
  strategy_data: {
    business_context: {
      business_name: "Acme SEO",
      description: "AI-powered Content OS",
      industry: "B2B SaaS",
    },
    products: [
      {
        name: "Content Engine",
        description: "Deterministic keyword clustering",
        category: "Software",
        priority: 1,
        url: null,
      },
    ],
  },
  change_summary: "Initial setup",
  created_at: new Date().toISOString(),
  updated_at: new Date().toISOString(),
};

const mockKeywords: Keyword[] = [
  {
    id: "kw-1",
    organization_id: "org-1",
    project_id: "proj-1",
    website_id: "site-1",
    keyword: "b2b content intelligence",
    normalized_keyword: "b2b content intelligence",
    search_volume: 2400,
    keyword_difficulty: 35,
    cpc: 8.5,
    intent: "COMMERCIAL",
    intent_confidence: 0.9,
    funnel_stage: "MOFU",
    business_value_score: 85,
    priority_score: 80,
    source: "CSV",
    status: "active",
    provider_metadata: {},
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
  },
];

const mockClusters: KeywordCluster[] = [
  {
    id: "cluster-1",
    organization_id: "org-1",
    project_id: "proj-1",
    topic_id: null,
    clustering_run_id: "run-1",
    cluster_name: "Content Intelligence",
    primary_keyword_id: "kw-1",
    primary_keyword: "b2b content intelligence",
    intent: "COMMERCIAL",
    cluster_score: 82,
    status: "proposed",
    rationale: "Clustered around primary term",
    member_count: 1,
    members: [],
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
  },
];

const mockWarnings: CannibalizationWarning[] = [
  {
    keyword_id: "kw-1",
    keyword: "b2b content intelligence",
    intent: "COMMERCIAL",
    competing_pages: [],
    severity: "HIGH",
    reason: "2 pages have competing titles",
  },
];

const mockPillars: ContentPillar[] = [
  {
    id: "pillar-1",
    organization_id: "org-1",
    project_id: "proj-1",
    name: "Content Strategy",
    slug: "content-strategy",
    description: "Pillar overview",
    business_goal: "Drive organic leads",
    priority: 1,
    status: "proposed",
    topic_count: 1,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
  },
];

const mockTopics: Topic[] = [
  {
    id: "topic-1",
    organization_id: "org-1",
    project_id: "proj-1",
    pillar_id: "pillar-1",
    name: "Clustering Algorithms",
    slug: "clustering-algorithms",
    description: "Topic details",
    priority: 1,
    status: "proposed",
    cluster_count: 1,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
  },
];

const mockOpportunities: ContentOpportunity[] = [
  {
    id: "opp-1",
    organization_id: "org-1",
    project_id: "proj-1",
    website_id: "site-1",
    cluster_id: "cluster-1",
    cluster_name: "Content Intelligence",
    keyword_id: "kw-1",
    keyword: "b2b content intelligence",
    action: "NEW_PAGE",
    priority: 85,
    business_value_score: 85,
    existing_page_id: null,
    existing_page_url: null,
    reason: "No suitable target page on site",
    confidence: 0.9,
    status: "proposed",
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
  },
];

const mockMappings: KeywordPageMapping[] = [
  {
    id: "map-1",
    organization_id: "org-1",
    project_id: "proj-1",
    website_id: "site-1",
    keyword_id: "kw-1",
    keyword: "b2b content intelligence",
    search_volume: 2400,
    intent: "COMMERCIAL",
    page_id: null,
    page_url: null,
    page_title: null,
    mapping_type: "NEW_PAGE_REQUIRED",
    confidence: 1.0,
    source: "DETERMINISTIC",
    status: "proposed",
    rationale: "No target page",
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
  },
];

const mockGraph: ContentArchitectureGraph = {
  nodes: [
    {
      id: "pillar-1",
      type: "pillar",
      data: {
        label: "Content Strategy",
        subtitle: "Pillar",
        status: "proposed",
        metrics: {},
        details: {},
      },
    },
  ],
  edges: [],
};

describe("Phase 3 Strategy, Keywords & Content Architecture Components", () => {
  it("renders StrategyManager with versioning and products", () => {
    render(
      <StrategyManager
        projectId="proj-1"
        initialStrategy={mockStrategy}
        versions={[]}
      />
    );
    expect(screen.getByText("Version 1")).toBeInTheDocument();
    expect(screen.getByText("1. Business Context & Positioning")).toBeInTheDocument();
    expect(screen.getByDisplayValue("Content Engine")).toBeInTheDocument();
  });

  it("renders KeywordsDashboard with keyword table and cannibalization warning banner", () => {
    render(
      <KeywordsDashboard
        projectId="proj-1"
        initialKeywords={mockKeywords}
        initialClusters={mockClusters}
        initialWarnings={mockWarnings}
      />
    );
    expect(screen.getByText(/Keyword Cannibalization Detected/i)).toBeInTheDocument();
    expect(screen.getByText("b2b content intelligence")).toBeInTheDocument();
  });

  it("renders ArchitectureDashboard with content pillars and opportunities", () => {
    render(
      <ArchitectureDashboard
        projectId="proj-1"
        websiteId="site-1"
        initialPillars={mockPillars}
        initialTopics={mockTopics}
        initialOpportunities={mockOpportunities}
        initialMappings={mockMappings}
        initialGraph={mockGraph}
      />
    );
    expect(screen.getByText("Content Strategy")).toBeInTheDocument();
    expect(screen.getByText("Clustering Algorithms")).toBeInTheDocument();
  });
});
