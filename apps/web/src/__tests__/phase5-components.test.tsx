import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ContentBriefView } from "@/features/briefs/content-brief-view";
import { ContentEditor } from "@/features/editor/content-editor";
import { EditorSidebar } from "@/features/editor/editor-sidebar";
import { ContentPageWorkspace } from "@/features/content/content-page-workspace";
import { clientApi } from "@/lib/client-api";
import type {
  ContentBrief,
  ContentDocument,
  PlannedContentPage,
  AIProposal,
  SEOQualityReport,
} from "@/lib/api-types";

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push: vi.fn(),
    refresh: vi.fn(),
  }),
}));

vi.mock("@/lib/client-api", () => ({
  clientApi: vi.fn(),
  ApiError: class ApiError extends Error {},
}));

const mockBrief: ContentBrief = {
  id: "brief-001",
  organization_id: "org-001",
  project_id: "proj-001",
  page_id: "page-001",
  version: 1,
  status: "DRAFT",
  primary_keyword: "zero trust architecture",
  secondary_keywords: ["microsegmentation", "least privilege"],
  search_intent: "INFORMATIONAL",
  target_audience: "Enterprise Security Leaders",
  business_goal: "Position platform as authority",
  content_type: "PILLAR_PAGE",
  recommended_title: "Zero Trust Architecture Guide",
  recommended_url: "/zero-trust-architecture",
  meta_title: "Zero Trust Architecture Guide - Best Practices",
  meta_description: "Explore zero trust network principles and implementation.",
  target_word_count: 2000,
  required_topics: ["Perimeter vs Identity", "Microsegmentation Policies"],
  key_entities: ["NIST", "IAM"],
  questions_to_answer: ["What is Zero Trust?"],
  internal_link_targets: [
    { title: "Identity Governance", url: "/identity-governance" },
  ],
  external_source_requirements: [],
  content_requirements: [],
  brand_requirements: { tone: "authoritative" },
  created_at: new Date().toISOString(),
  updated_at: new Date().toISOString(),
};

const mockDoc: ContentDocument = {
  id: "doc-001",
  organization_id: "org-001",
  project_id: "proj-001",
  page_id: "page-001",
  title: "Zero Trust Architecture Guide",
  slug: "zero-trust-architecture",
  status: "DRAFT",
  current_version: 1,
  lock_version: 1,
  plain_text: "Zero Trust Architecture Guide\nNever trust, always verify.",
  word_count: 50,
  content_blocks: [
    {
      id: "block_001",
      type: "DOCUMENT_TITLE",
      text: "Zero Trust Architecture Guide",
      level: 1,
    },
    {
      id: "block_002",
      type: "PARAGRAPH",
      text: "Never trust, always verify.",
    },
    {
      id: "block_003",
      type: "HEADING",
      text: "Core Principles",
      level: 2,
    },
  ],
  created_at: new Date().toISOString(),
  updated_at: new Date().toISOString(),
};

const mockPlannedPage: PlannedContentPage = {
  id: "page-001",
  organization_id: "org-001",
  project_id: "proj-001",
  title: "Zero Trust Architecture Guide",
  slug: "zero-trust-architecture",
  url: "/zero-trust-architecture",
  page_type: "PLANNED",
  content_type: "PILLAR_PAGE",
  status: "PLANNED",
  intent: "INFORMATIONAL",
  primary_keyword: "zero trust architecture",
  business_value: 90,
  priority: 1,
  inbound_links_count: 2,
  outbound_links_count: 3,
  created_at: new Date().toISOString(),
  updated_at: new Date().toISOString(),
};

describe("Phase 5: Content Brief & Chat-Native AI Content Editor", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders ContentBriefView with parameters, topics, and approval flow", async () => {
    vi.mocked(clientApi).mockResolvedValueOnce({
      ...mockBrief,
      status: "APPROVED",
      version: 2,
    });

    const onApproveMock = vi.fn();

    render(
      <ContentBriefView
        brief={mockBrief}
        onApprove={onApproveMock}
      />
    );

    expect(screen.getByTestId("content-brief-view")).toBeInTheDocument();
    expect(
      screen.getAllByText("Zero Trust Architecture Guide").length
    ).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("zero trust architecture")).toBeInTheDocument();
    expect(screen.getByText("Perimeter vs Identity")).toBeInTheDocument();
    expect(screen.getByTestId("brief-status-badge")).toHaveTextContent("DRAFT");

    // Click Approve Brief
    const approveBtn = screen.getByTestId("approve-brief-btn");
    fireEvent.click(approveBtn);

    await waitFor(() => {
      expect(clientApi).toHaveBeenCalledWith(
        `/content-briefs/${mockBrief.id}/approve`,
        expect.objectContaining({ method: "POST" })
      );
      expect(onApproveMock).toHaveBeenCalled();
    });
  });

  it("renders ContentEditor with blocks, stable IDs, and selection callbacks", () => {
    const onSelectBlockMock = vi.fn();

    render(
      <ContentEditor
        document={mockDoc}
        selectedBlockId="block_002"
        onSelectBlock={onSelectBlockMock}
      />
    );

    expect(screen.getByTestId("content-editor")).toBeInTheDocument();
    expect(screen.getByTestId("block-block_001")).toBeInTheDocument();
    expect(screen.getByTestId("block-block_002")).toBeInTheDocument();
    expect(screen.getByTestId("save-status-saved")).toBeInTheDocument();

    // Click block to select
    fireEvent.click(screen.getByTestId("block-block_003"));
    expect(onSelectBlockMock).toHaveBeenCalledWith("block_003");
  });

  it("renders inline diff overlay in ContentEditor when an active AI proposal targets a block", () => {
    const activeProposal: AIProposal = {
      id: "prop-001",
      document_id: mockDoc.id,
      status: "PROPOSED",
      operation_type: "replace_block",
      target_block_ids: ["block_002"],
      old_content: "Never trust, always verify.",
      proposed_content: "Zero trust mandates continuous identity verification.",
      diff_summary: { type: "replace" },
      reason: "Make intro more authoritative",
      ai_provider: "mock",
      model: "mock-gpt4",
      created_at: new Date().toISOString(),
    };

    const onApplyMock = vi.fn();
    const onRejectMock = vi.fn();

    render(
      <ContentEditor
        document={mockDoc}
        activeProposal={activeProposal}
        onApplyProposal={onApplyMock}
        onRejectProposal={onRejectMock}
      />
    );

    expect(screen.getByTestId("proposal-diff-overlay")).toBeInTheDocument();
    expect(screen.getByText("Make intro more authoritative")).toBeInTheDocument();

    // Apply button
    const applyBtn = screen.getByTestId("inline-apply-btn");
    fireEvent.click(applyBtn);
    expect(onApplyMock).toHaveBeenCalledWith("prop-001");

    // Dismiss/Reject button
    const rejectBtn = screen.getByTestId("inline-reject-btn");
    fireEvent.click(rejectBtn);
    expect(onRejectMock).toHaveBeenCalledWith("prop-001");
  });

  it("renders EditorSidebar and allows submitting AI chat prompts", async () => {
    const mockProposal: AIProposal = {
      id: "prop-002",
      document_id: mockDoc.id,
      status: "PROPOSED",
      operation_type: "replace_block",
      target_block_ids: ["block_002"],
      old_content: "Never trust",
      proposed_content: "Zero trust continuous authentication",
      diff_summary: {},
      reason: "Keyword optimization",
      ai_provider: "mock",
      model: "mock-gpt4",
      created_at: new Date().toISOString(),
    };

    vi.mocked(clientApi).mockImplementation((url: string) => {
      if (url.includes("/quality-check")) {
        const report: SEOQualityReport = {
          document_id: mockDoc.id,
          title: mockDoc.title,
          word_count: 500,
          target_word_count: 2000,
          score_percentage: 85,
          checks: [
            {
              name: "H1 Heading Presence",
              status: "PASS",
              message: "H1 heading present",
              recommendation: "",
            },
          ],
        };
        return Promise.resolve(report);
      }
      if (url.includes("/chat")) {
        return Promise.resolve({
          id: "msg-002",
          session_id: "sess-001",
          document_id: mockDoc.id,
          role: "assistant",
          content: "I have proposed an edit to block 2.",
          proposal: mockProposal,
          created_at: new Date().toISOString(),
        });
      }
      return Promise.resolve({});
    });

    const onApplyProposal = vi.fn();
    const onRejectProposal = vi.fn();

    render(
      <EditorSidebar
        document={mockDoc}
        selectedBlockId="block_002"
        onApplyProposal={onApplyProposal}
        onRejectProposal={onRejectProposal}
        onSelectBlock={vi.fn()}
        onRestoreVersion={vi.fn()}
      />
    );

    expect(screen.getByTestId("editor-sidebar")).toBeInTheDocument();
    expect(screen.getByTestId("tab-chat")).toBeInTheDocument();

    // Type in chat input and send
    const input = screen.getByTestId("chat-input");
    fireEvent.change(input, { target: { value: "Please enhance this block" } });

    const sendBtn = screen.getByTestId("send-chat-btn");
    fireEvent.click(sendBtn);

    await waitFor(() => {
      expect(clientApi).toHaveBeenCalledWith(
        `/content-documents/${mockDoc.id}/chat`,
        expect.objectContaining({ method: "POST" })
      );
      expect(screen.getByTestId("proposal-card")).toBeInTheDocument();
    });

    // Apply proposal from sidebar card
    const applyBtn = screen.getByTestId("apply-proposal-btn");
    fireEvent.click(applyBtn);
    expect(onApplyProposal).toHaveBeenCalledWith("prop-002");
  });

  it("renders ContentPageWorkspace and toggles between Brief and Editor tabs", () => {
    render(
      <ContentPageWorkspace
        projectId="proj-001"
        page={mockPlannedPage}
        initialBrief={mockBrief}
        initialDocument={mockDoc}
      />
    );

    expect(screen.getByTestId("content-page-workspace")).toBeInTheDocument();
    expect(screen.getByTestId("content-editor")).toBeInTheDocument();

    // Switch to Brief View
    const briefTabBtn = screen.getByTestId("tab-brief-view");
    fireEvent.click(briefTabBtn);
    expect(screen.getByTestId("content-brief-view")).toBeInTheDocument();

    // Switch back to Editor View
    const editorTabBtn = screen.getByTestId("tab-editor-view");
    fireEvent.click(editorTabBtn);
    expect(screen.getByTestId("content-editor")).toBeInTheDocument();
  });
});
