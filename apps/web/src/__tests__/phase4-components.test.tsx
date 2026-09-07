import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ContentMapView } from "@/features/content-map/content-map-view";
import { ContentDashboard } from "@/features/content/content-dashboard";
import { SEOGuideView } from "@/features/seo/seo-guide-view";
import { InternalLinkingDashboard } from "@/features/internal-linking/internal-linking-dashboard";
import { clientApi } from "@/lib/client-api";
import type {
  ContentArchitectureVersion,
  ContentMapGraph,
  ContentMapValidation,
  LinkOpportunity,
  PageRelationship,
  PlannedContentPage,
  SEOGuide,
} from "@/lib/api-types";

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push: vi.fn(),
    refresh: vi.fn(),
  }),
}));

vi.mock("@/lib/client-api", () => ({
  clientApi: vi.fn(),
}));

const mockGraph: ContentMapGraph = {
  nodes: [
    {
      id: "pillar-p1",
      type: "pillar",
      data: {
        entity_id: "p1",
        node_type: "PILLAR",
        title: "Cloud Infrastructure Security",
        label: "Cloud Infrastructure Security",
        subtitle: "Content Pillar",
        priority: 1,
        page_type: "PILLAR",
        primary_keyword: "cloud security",
        status: "ACTIVE",
        content_type: "PILLAR_PAGE",
        intent: "INFORMATIONAL",
        url: "/cloud-security",
        business_value: 90,
        inbound_links_count: 0,
        outbound_links_count: 0,
      },
    },
    {
      id: "page-pg1",
      type: "page",
      data: {
        entity_id: "pg1",
        node_type: "PAGE",
        title: "Kubernetes Threat Modeling Guide",
        label: "Kubernetes Threat Modeling Guide",
        subtitle: "Planned Page",
        priority: 1,
        url: "k8s-threat-modeling",
        primary_keyword: "k8s threat modeling",
        page_type: "PLANNED",
        content_type: "CLUSTER_PAGE",
        status: "PLANNED",
        intent: "INFORMATIONAL",
        business_value: 85,
        inbound_links_count: 2,
        outbound_links_count: 3,
      },
    },
  ],
  edges: [
    {
      id: "edge-1",
      source: "pillar-p1",
      target: "page-pg1",
      type: "hierarchy",
      label: "hierarchy",
    },
  ],
  graph_revision: 1,
  stats: {
    total_pillars: 1,
    total_topics: 2,
    total_clusters: 4,
    total_pages: 8,
    planned_pages: 5,
    existing_pages: 3,
    orphan_pages: 0,
    cannibalization_warnings: 0,
  },
};

const mockValidation: ContentMapValidation = {
  is_valid: true,
  issues: [],
  total_issues: 0,
};

const mockVersions: ContentArchitectureVersion[] = [
  {
    id: "ver-1",
    organization_id: "org-1",
    project_id: "proj-1",
    version: 1,
    snapshot_data: {} as unknown as Record<string, never>,
    change_summary: "Initial baseline architecture",
    created_by_id: "user-1",
    created_at: new Date().toISOString(),
  },
];

const mockPlannedPages: PlannedContentPage[] = [
  {
    id: "pg1",
    organization_id: "org-1",
    project_id: "proj-1",
    website_id: "site-1",
    title: "Kubernetes Threat Modeling Guide",
    slug: "k8s-threat-modeling",
    url: "/k8s-threat-modeling",
    page_type: "PLANNED",
    content_type: "CLUSTER_PAGE",
    status: "PLANNED",
    intent: "INFORMATIONAL",
    primary_keyword: "k8s threat modeling",
    priority: 1,
    business_value: 85.0,
    inbound_links_count: 2,
    outbound_links_count: 1,
    secondary_keywords: ["container security", "pod security"],
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
  },
];

const mockGuide: SEOGuide = {
  id: "guide-1",
  organization_id: "org-1",
  project_id: "proj-1",
  page_id: "pg1",
  version: 1,
  status: "DRAFT",
  primary_keyword: "k8s threat modeling",
  secondary_keywords: ["container security", "pod security"],
  search_intent: "INFORMATIONAL",
  target_audience: "DevSecOps Engineers",
  recommended_title: "Kubernetes Threat Modeling: Complete Guide",
  meta_title: "Kubernetes Threat Modeling: Complete Guide & Best Practices",
  meta_description:
    "Learn step-by-step how to perform threat modeling on Kubernetes clusters with container breakout vectors.",
  recommended_url: "/k8s-threat-modeling",
  content_type: "GUIDE",
  word_count_target: 2500,
  required_topics: ["STRIDE", "RBAC", "Pod Security Standards"],
  key_entities: ["Kubernetes", "API Server", "Kubelet"],
  serp_notes: "Top results emphasize practical defense against container breakouts.",
  content_requirements: ["Include STRIDE threat matrix diagram"],
  outline: [
    { level: 1, title: "Kubernetes Threat Modeling Overview", required: true },
    { level: 2, title: "Attack Surfaces in K8s", required: true },
  ],
  seo_rules: {} as unknown as Record<string, never>,
  created_at: new Date().toISOString(),
  updated_at: new Date().toISOString(),
};

const mockOpportunities: LinkOpportunity[] = [
  {
    id: "opp-1",
    organization_id: "org-1",
    project_id: "proj-1",
    source_page_id: "pg1",
    source_page_title: "Kubernetes Threat Modeling Guide",
    source_page_url: "/k8s-threat-modeling",
    target_page_id: "pg2",
    target_page_title: "Container Runtime Security",
    target_page_url: "container-runtime-security",
    anchor_suggestion: "container security runtime",
    confidence: 0.94,
    priority: 1,
    reason: "Direct parent-to-supporting contextual link",
    status: "PROPOSED",
    created_at: new Date().toISOString(),
  },
];

const mockRelationships: PageRelationship[] = [
  {
    id: "rel-1",
    organization_id: "org-1",
    project_id: "proj-1",
    source_page_id: "pg1",
    source_page_title: "Kubernetes Threat Modeling Guide",
    source_page_url: "/k8s-threat-modeling",
    target_page_id: "pg2",
    target_page_title: "Container Runtime Security",
    target_page_url: "container-runtime-security",
    relationship_type: "PARENT_CHILD",
    anchor_text: "container runtime security",
    confidence: 1.0,
    priority: 1,
    reason: "Hierarchical parent-child link",
    status: "ACTIVE",
    created_at: new Date().toISOString(),
  },
];

describe("Phase 4 Frontend Components", () => {
  beforeEach(() => {
    vi.mocked(clientApi).mockReset();
  });

  it("renders ContentMapView with metrics and node hierarchy", () => {
    render(
      <ContentMapView
        projectId="proj-1"
        initialGraph={mockGraph}
        initialValidation={mockValidation}
        initialVersions={mockVersions}
      />
    );

    // Verify stats cards
    expect(screen.getAllByText("Pillars").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Cloud Infrastructure Security").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Kubernetes Threat Modeling Guide").length).toBeGreaterThan(0);

    fireEvent.click(screen.getByText("Kubernetes Threat Modeling Guide"));
    expect(screen.getByRole("link", { name: "Open Brief & Editor" })).toHaveAttribute(
      "href",
      "/projects/proj-1/content/pg1"
    );
  });

  it("creates a planned page from the Content Map modal", async () => {
    vi.mocked(clientApi)
      .mockResolvedValueOnce(mockPlannedPages[0])
      .mockResolvedValueOnce(mockGraph)
      .mockResolvedValueOnce(mockValidation);

    render(
      <ContentMapView
        projectId="proj-1"
        initialGraph={mockGraph}
        initialValidation={mockValidation}
        initialVersions={mockVersions}
      />
    );

    fireEvent.click(screen.getByRole("button", { name: "Create Planned Page" }));
    fireEvent.change(screen.getByPlaceholderText("e.g. Technical SEO Audit Guide"), {
      target: { value: "SEO Audit Guide" },
    });
    fireEvent.change(screen.getByPlaceholderText("e.g. technical-seo-audit"), {
      target: { value: "seo-audit-guide" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Save Planned Page" }));

    await waitFor(() => {
      expect(clientApi).toHaveBeenCalledWith(
        "/projects/proj-1/content-pages",
        expect.objectContaining({ method: "POST" })
      );
      expect(screen.queryByText("Create Planned Content Page")).not.toBeInTheDocument();
      expect(screen.getByText("Planned page successfully created.")).toBeInTheDocument();
    });
  });

  it("shows a planned-page save error inside the open modal", async () => {
    vi.mocked(clientApi).mockRejectedValueOnce(new Error("The page could not be saved."));

    render(
      <ContentMapView
        projectId="proj-1"
        initialGraph={mockGraph}
        initialValidation={mockValidation}
        initialVersions={mockVersions}
      />
    );

    fireEvent.click(screen.getByRole("button", { name: "Create Planned Page" }));
    fireEvent.change(screen.getByPlaceholderText("e.g. Technical SEO Audit Guide"), {
      target: { value: "SEO Audit Guide" },
    });
    fireEvent.change(screen.getByPlaceholderText("e.g. technical-seo-audit"), {
      target: { value: "seo-audit-guide" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Save Planned Page" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("The page could not be saved.");
    expect(screen.getByText("Create Planned Content Page")).toBeInTheDocument();
  });

  it("renders ContentDashboard with planned pages inventory", () => {
    render(
      <ContentDashboard
        projectId="proj-1"
        initialPages={mockPlannedPages}
        initialPillars={[]}
        initialTopics={[]}
        initialOpportunities={[]}
        availableKeywords={[]}
        initialCrawledPages={[]}
      />
    );

    expect(screen.getAllByText("Kubernetes Threat Modeling Guide").length).toBeGreaterThan(0);
    expect(screen.getAllByText("k8s threat modeling").length).toBeGreaterThan(0);
    expect(screen.getAllByText(/planned/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText("SEO Guide").length).toBeGreaterThan(0);
    expect(screen.getByRole("link", { name: "Brief & Editor" })).toHaveAttribute(
      "href",
      "/projects/proj-1/content/pg1"
    );
  });

  it("renders SEOGuideView with SERP preview and outline sections", () => {
    render(
      <SEOGuideView
        projectId="proj-1"
        page={mockPlannedPages[0]}
        initialGuide={mockGuide}
        initialVersions={[]}
        assignedKeywords={[]}
      />
    );

    // Google SERP preview
    expect(screen.getAllByText("Kubernetes Threat Modeling: Complete Guide & Best Practices").length).toBeGreaterThan(0);
    expect(screen.getAllByText(/Learn step-by-step how to perform threat modeling/).length).toBeGreaterThan(0);

    // Outline items (inputs)
    expect(screen.getByDisplayValue("Kubernetes Threat Modeling Overview")).toBeDefined();
    expect(screen.getByDisplayValue("Attack Surfaces in K8s")).toBeDefined();
  });

  it("renders InternalLinkingDashboard with opportunities and relationships", () => {
    render(
      <InternalLinkingDashboard
        projectId="proj-1"
        initialOpportunities={mockOpportunities}
        initialRelationships={mockRelationships}
        initialOrphans={[]}
        availablePages={mockPlannedPages}
      />
    );

    expect(screen.getAllByText("Kubernetes Threat Modeling Guide").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Container Runtime Security").length).toBeGreaterThan(0);
    expect(screen.getAllByText("container security runtime").length).toBeGreaterThan(0);
    expect(screen.getByText(/Score:\s*94\/100/)).toBeDefined();
  });
});
