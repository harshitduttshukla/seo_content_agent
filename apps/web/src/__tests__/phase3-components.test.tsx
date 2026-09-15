import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
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
import { clientApi } from "@/lib/client-api";

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push: vi.fn(),
    refresh: vi.fn(),
  }),
}));

vi.mock("@/lib/client-api", () => ({
  clientApi: vi.fn(),
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
  beforeEach(() => {
    vi.clearAllMocks();
  });

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

  it("saves a new strategy version and updates state immediately", async () => {
    const updatedStrategy: SEOStrategy = {
      ...mockStrategy,
      current_version: 2,
      updated_at: new Date().toISOString(),
    };
    const updatedVersions = [
      {
        id: "ver-2",
        strategy_id: "strat-1",
        organization_id: "org-1",
        project_id: "proj-1",
        version: 2,
        change_summary: "Added enterprise competitors and SEO objectives",
        strategy_data: mockStrategy.strategy_data,
        created_at: new Date().toISOString(),
      },
      {
        id: "ver-1",
        strategy_id: "strat-1",
        organization_id: "org-1",
        project_id: "proj-1",
        version: 1,
        change_summary: "Initial setup",
        strategy_data: mockStrategy.strategy_data,
        created_at: new Date().toISOString(),
      },
    ];

    vi.mocked(clientApi).mockImplementation(async (path: string) => {
      if (path === "/projects/proj-1/strategy") {
        return updatedStrategy as any;
      }
      if (path === "/projects/proj-1/strategy/versions") {
        return { items: updatedVersions } as any;
      }
      return {} as any;
    });

    render(
      <StrategyManager
        projectId="proj-1"
        initialStrategy={mockStrategy}
        versions={[updatedVersions[1]]}
      />
    );

    // Initial version is 1
    expect(screen.getByText("Version 1")).toBeInTheDocument();
    expect(screen.getByText(/Version History \(1\)/)).toBeInTheDocument();

    // Fill in Version Change Summary
    const summaryInput = screen.getByPlaceholderText(
      /Explain what was changed in this version/i
    );
    fireEvent.change(summaryInput, {
      target: { value: "Added enterprise competitors and SEO objectives" },
    });

    // Click "Save New Version"
    const saveButton = screen.getByRole("button", { name: /Save New Version/i });
    fireEvent.click(saveButton);

    // Verify PUT request payload was sent with explicit mapping
    await waitFor(() => {
      expect(clientApi).toHaveBeenCalledWith(
        "/projects/proj-1/strategy",
        expect.objectContaining({
          method: "PUT",
          body: expect.stringContaining("Added enterprise competitors and SEO objectives"),
        })
      );
    });

    // Verify UI updated to reflect Version 2 and Version History (2)
    await waitFor(() => {
      expect(screen.getByText("Version 2")).toBeInTheDocument();
      expect(screen.getByText(/Version History \(2\)/)).toBeInTheDocument();
      expect(screen.getByText(/Strategy successfully updated and immutable version recorded/i)).toBeInTheDocument();
    });

    // Verify change summary was cleared
    expect((summaryInput as HTMLInputElement).value).toBe("");
  });

  it("prevents duplicate submissions on rapid multiple clicks", async () => {
    let resolveSave: ((val: any) => void) | null = null;
    const savePromise = new Promise((resolve) => {
      resolveSave = resolve;
    });

    vi.mocked(clientApi).mockImplementation(async (path: string) => {
      if (path === "/projects/proj-1/strategy") {
        await savePromise;
        return { ...mockStrategy, current_version: 2 } as any;
      }
      return { items: [] } as any;
    });

    render(
      <StrategyManager
        projectId="proj-1"
        initialStrategy={mockStrategy}
        versions={[{
          id: "ver-1",
          strategy_id: "strat-1",
          organization_id: "org-1",
          project_id: "proj-1",
          version: 1,
          change_summary: "Initial",
          strategy_data: mockStrategy.strategy_data,
          created_at: new Date().toISOString(),
        }]}
      />
    );

    const saveButton = screen.getByRole("button", { name: /Save New Version/i });

    // Rapid clicks
    fireEvent.click(saveButton);
    fireEvent.click(saveButton);
    fireEvent.click(saveButton);

    // Only 1 PUT request should be initiated
    const putCalls = vi.mocked(clientApi).mock.calls.filter(
      (c) => c[0] === "/projects/proj-1/strategy"
    );
    expect(putCalls.length).toBe(1);

    // Button should be disabled during saving
    expect(saveButton).toBeDisabled();

    // Resolve the promise
    resolveSave!({ ...mockStrategy, current_version: 2 });
    await waitFor(() => {
      expect(screen.getByText("Version 2")).toBeInTheDocument();
    });
  });

  it("displays error message and preserves form values on save failure", async () => {
    vi.mocked(clientApi).mockRejectedValueOnce(new Error("Database connection timed out"));

    render(
      <StrategyManager
        projectId="proj-1"
        initialStrategy={mockStrategy}
        versions={[{
          id: "ver-1",
          strategy_id: "strat-1",
          organization_id: "org-1",
          project_id: "proj-1",
          version: 1,
          change_summary: "Initial",
          strategy_data: mockStrategy.strategy_data,
          created_at: new Date().toISOString(),
        }]}
      />
    );

    const summaryInput = screen.getByPlaceholderText(
      /Explain what was changed in this version/i
    );
    fireEvent.change(summaryInput, {
      target: { value: "My unsaved edits" },
    });

    const saveButton = screen.getByRole("button", { name: /Save New Version/i });
    fireEvent.click(saveButton);

    await waitFor(() => {
      expect(screen.getByText("Database connection timed out")).toBeInTheDocument();
    });

    // Form value remains intact
    expect((summaryInput as HTMLInputElement).value).toBe("My unsaved edits");
    // Button is re-enabled for retry
    expect(saveButton).not.toBeDisabled();
    // Version is NOT updated
    expect(screen.getByText("Version 1")).toBeInTheDocument();
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

  it("edits a keyword from its table row", async () => {
    vi.mocked(clientApi).mockResolvedValue(mockKeywords[0]);
    render(
      <KeywordsDashboard
        projectId="proj-1"
        initialKeywords={mockKeywords}
        initialClusters={mockClusters}
        initialWarnings={[]}
      />,
    );

    fireEvent.click(
      screen.getByRole("button", { name: "Edit keyword b2b content intelligence" }),
    );
    const dialog = screen.getByRole("dialog", { name: "Edit keyword" });
    fireEvent.change(within(dialog).getByLabelText("Keyword"), {
      target: { value: "enterprise content intelligence" },
    });
    fireEvent.change(within(dialog).getByLabelText("Search Volume"), {
      target: { value: "3600" },
    });
    fireEvent.click(within(dialog).getByRole("button", { name: "Save changes" }));

    await waitFor(() =>
      expect(clientApi).toHaveBeenCalledWith("/projects/proj-1/keywords/kw-1", {
        method: "PUT",
        body: JSON.stringify({
          keyword: "enterprise content intelligence",
          search_volume: 3600,
          keyword_difficulty: 35,
          cpc: 8.5,
          intent: "COMMERCIAL",
          funnel_stage: "MOFU",
          status: "active",
        }),
      }),
    );
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    expect(
      screen.getByText('Keyword "enterprise content intelligence" updated successfully.'),
    ).toBeInTheDocument();
  });

  it("confirms before deleting a keyword", async () => {
    vi.mocked(clientApi).mockResolvedValue({
      keyword_id: "kw-1",
      keyword: "b2b content intelligence",
      message: "Keyword deleted with its dependent assignments and mappings.",
    });
    render(
      <KeywordsDashboard
        projectId="proj-1"
        initialKeywords={mockKeywords}
        initialClusters={mockClusters}
        initialWarnings={[]}
      />,
    );

    fireEvent.click(
      screen.getByRole("button", { name: "Delete keyword b2b content intelligence" }),
    );
    const dialog = screen.getByRole("dialog", { name: "Delete keyword?" });
    expect(within(dialog).getByText(/cluster memberships/i)).toBeInTheDocument();
    fireEvent.click(within(dialog).getByRole("button", { name: "Delete keyword" }));

    await waitFor(() =>
      expect(clientApi).toHaveBeenCalledWith("/projects/proj-1/keywords/kw-1", {
        method: "DELETE",
      }),
    );
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    expect(
      screen.getByText('Keyword "b2b content intelligence" deleted successfully.'),
    ).toBeInTheDocument();
  });

  it("confirms and deletes an individual keyword cluster", async () => {
    vi.mocked(clientApi).mockResolvedValue({
      cluster_id: "cluster-1",
      cluster_name: "Content Intelligence",
      message: "Cluster deleted. Its underlying keywords were retained.",
    });
    render(
      <KeywordsDashboard
        projectId="proj-1"
        initialKeywords={mockKeywords}
        initialClusters={mockClusters}
        initialWarnings={[]}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Clusters (1)" }));
    fireEvent.click(
      screen.getByRole("button", { name: "Delete cluster Content Intelligence" }),
    );

    const dialog = screen.getByRole("dialog", { name: "Delete cluster?" });
    expect(within(dialog).getByText("cluster-1")).toBeInTheDocument();
    expect(within(dialog).getByText(/underlying keywords are kept/i)).toBeInTheDocument();

    fireEvent.click(within(dialog).getByRole("button", { name: "Delete cluster" }));

    await waitFor(() =>
      expect(clientApi).toHaveBeenCalledWith("/projects/proj-1/clusters/cluster-1", {
        method: "DELETE",
      }),
    );
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    expect(
      screen.getByText('Cluster "Content Intelligence" deleted. Its keywords were kept.'),
    ).toBeInTheDocument();
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
