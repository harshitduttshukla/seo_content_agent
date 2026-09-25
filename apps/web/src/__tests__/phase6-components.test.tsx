import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { WorkflowActivity } from "@/features/editor/workflow-activity";
import { EditorSidebar } from "@/features/editor/editor-sidebar";
import { clientApi } from "@/lib/client-api";
import type {
  ContentDocument,
  WorkflowDetail,
} from "@/lib/api-types";

vi.mock("@/lib/client-api", () => ({
  clientApi: vi.fn(),
  ApiError: class ApiError extends Error {},
}));

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
  ],
  created_at: new Date().toISOString(),
  updated_at: new Date().toISOString(),
};

const mockRunningWorkflow: WorkflowDetail = {
  id: "wf-100",
  organization_id: "org-001",
  project_id: "proj-001",
  document_id: "doc-001",
  intent: "MULTI_STEP_CONTENT_TASK",
  status: "WAITING_FOR_APPROVAL",
  current_step: 3,
  plan: [
    {
      step_index: 0,
      tool_name: "read_document",
      risk_level: "READ",
      requires_approval: false,
      rationale: "Read current blocks",
      input_arguments: { document_id: "doc-001" },
    },
    {
      step_index: 1,
      tool_name: "analyze_content_quality",
      risk_level: "READ",
      requires_approval: false,
      rationale: "Evaluate SEO quality",
      input_arguments: { document_id: "doc-001" },
    },
    {
      step_index: 2,
      tool_name: "generate_link_suggestions",
      risk_level: "SUGGEST",
      requires_approval: false,
      rationale: "Discover internal linking targets",
      input_arguments: { document_id: "doc-001" },
    },
    {
      step_index: 3,
      tool_name: "propose_edit",
      risk_level: "WRITE",
      requires_approval: true,
      rationale: "Propose updated block with links",
      input_arguments: { document_id: "doc-001" },
    },
  ],
  steps: [
    {
      id: "step-0",
      workflow_id: "wf-100",
      step_index: 0,
      tool_name: "read_document",
      status: "COMPLETED",
      input: { document_id: "doc-001" },
      output: { blocks_count: 2 },
      retry_count: 0,
      completed_at: new Date().toISOString(),
    },
    {
      id: "step-1",
      workflow_id: "wf-100",
      step_index: 1,
      tool_name: "analyze_content_quality",
      status: "COMPLETED",
      input: { document_id: "doc-001" },
      output: { score: 85 },
      retry_count: 0,
      completed_at: new Date().toISOString(),
    },
    {
      id: "step-2",
      workflow_id: "wf-100",
      step_index: 2,
      tool_name: "generate_link_suggestions",
      status: "COMPLETED",
      input: { document_id: "doc-001" },
      output: { count: 3 },
      retry_count: 0,
      completed_at: new Date().toISOString(),
    },
    {
      id: "step-3",
      workflow_id: "wf-100",
      step_index: 3,
      tool_name: "propose_edit",
      status: "WAITING_FOR_APPROVAL",
      input: { document_id: "doc-001" },
      output: { proposal_id: "prop-999" },
      retry_count: 0,
    },
  ],
  executions: [
    {
      id: "exec-0",
      tool_name: "read_document",
      status: "SUCCESS",
      risk_level: "READ",
      requires_approval: false,
      started_at: new Date().toISOString(),
      duration_ms: 24,
    },
    {
      id: "exec-1",
      tool_name: "analyze_content_quality",
      status: "SUCCESS",
      risk_level: "READ",
      requires_approval: false,
      started_at: new Date().toISOString(),
      duration_ms: 68,
    },
  ],
  created_at: new Date().toISOString(),
  updated_at: new Date().toISOString(),
};

describe("Phase 6 — WorkflowActivity Component", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders empty state when no workflow is provided", () => {
    render(<WorkflowActivity workflow={null} />);
    expect(screen.getByText("No Active Workflow")).toBeInTheDocument();
  });

  it("renders loading state when orchestrating and workflow is null", () => {
    render(<WorkflowActivity workflow={null} isLoading={true} />);
    expect(screen.getByText("Orchestrating agent workflow...")).toBeInTheDocument();
  });

  it("renders workflow status, progress, and steps with risk levels", () => {
    render(<WorkflowActivity workflow={mockRunningWorkflow} />);

    expect(screen.getByTestId("workflow-status-badge")).toHaveTextContent("WAITING FOR APPROVAL");
    expect(screen.getByText("Progress: 3 of 4 steps")).toBeInTheDocument();

    // Tools rendered
    expect(screen.getByText("read_document")).toBeInTheDocument();
    expect(screen.getByText("analyze_content_quality")).toBeInTheDocument();
    expect(screen.getByText("generate_link_suggestions")).toBeInTheDocument();
    expect(screen.getByText("propose_edit")).toBeInTheDocument();

    // Risk level badges
    expect(screen.getAllByText("READ").length).toBeGreaterThanOrEqual(2);
    expect(screen.getByText("SUGGEST")).toBeInTheDocument();
    expect(screen.getByText("WRITE")).toBeInTheDocument();

    // Durations
    expect(screen.getByText("24ms")).toBeInTheDocument();
    expect(screen.getByText("68ms")).toBeInTheDocument();
  });

  it("renders approval gate with Approve & Apply and Reject buttons", async () => {
    const onApprove = vi.fn().mockResolvedValue(undefined);
    const onReject = vi.fn().mockResolvedValue(undefined);

    render(
      <WorkflowActivity
        workflow={mockRunningWorkflow}
        onApproveStep={onApprove}
        onRejectStep={onReject}
      />
    );

    expect(screen.getByText("Human Approval Required for Write Action")).toBeInTheDocument();
    expect(screen.getByText("Proposal: prop-999")).toBeInTheDocument();

    const approveBtn = screen.getByTestId("approve-step-btn");
    const rejectBtn = screen.getByTestId("reject-step-btn");

    expect(approveBtn).toBeInTheDocument();
    expect(rejectBtn).toBeInTheDocument();

    fireEvent.click(approveBtn);
    await waitFor(() => {
      expect(onApprove).toHaveBeenCalledWith("step-3");
    });

    fireEvent.click(rejectBtn);
    await waitFor(() => {
      expect(onReject).toHaveBeenCalledWith("step-3");
    });
  });

  it("renders retry button when workflow failed", async () => {
    const failedWorkflow: WorkflowDetail = {
      ...mockRunningWorkflow,
      status: "FAILED",
      steps: [
        {
          ...mockRunningWorkflow.steps[0],
          status: "FAILED",
          error_message: "Tool timeout exceeded",
        },
      ],
    };
    const onRetry = vi.fn().mockResolvedValue(undefined);

    render(<WorkflowActivity workflow={failedWorkflow} onRetryStep={onRetry} />);

    expect(screen.getByTestId("workflow-status-badge")).toHaveTextContent("FAILED");
    expect(screen.getByText("Tool timeout exceeded")).toBeInTheDocument();

    const retryBtn = screen.getByTestId("workflow-retry-btn");
    fireEvent.click(retryBtn);

    await waitFor(() => {
      expect(onRetry).toHaveBeenCalled();
    });
  });
});

describe("Phase 6 — EditorSidebar Agent Tab Integration", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    (clientApi as any).mockResolvedValue({});
  });

  it("switches to Agent tab and renders quick recipes and input box", async () => {
    render(
      <EditorSidebar
        document={mockDoc}
        onApplyProposal={vi.fn()}
        onRejectProposal={vi.fn()}
        onSelectBlock={vi.fn()}
        onRestoreVersion={vi.fn()}
      />
    );

    const agentTabBtn = screen.getByTestId("tab-workflows");
    expect(agentTabBtn).toBeInTheDocument();

    fireEvent.click(agentTabBtn);

    expect(screen.getByTestId("workflows-tab-content")).toBeInTheDocument();
    expect(screen.getByText("Agent Actions")).toBeInTheDocument();
    expect(screen.getByText("Optimize Document")).toBeInTheDocument();
    expect(screen.getByText("Audit & Fix SEO")).toBeInTheDocument();
    expect(screen.getByTestId("workflow-input")).toBeInTheDocument();
    expect(screen.getByTestId("workflow-submit-btn")).toBeInTheDocument();
  });

  it("executes workflow via quick recipe button", async () => {
    (clientApi as any).mockImplementation((endpoint: string, options?: any) => {
      if (endpoint === "/orchestrator/workflows") {
        return Promise.resolve(mockRunningWorkflow);
      }
      return Promise.resolve({});
    });

    render(
      <EditorSidebar
        document={mockDoc}
        onApplyProposal={vi.fn()}
        onRejectProposal={vi.fn()}
        onSelectBlock={vi.fn()}
        onRestoreVersion={vi.fn()}
      />
    );

    fireEvent.click(screen.getByTestId("tab-workflows"));

    const recipeBtn = screen.getByTestId("recipe-btn-0");
    fireEvent.click(recipeBtn);

    await waitFor(() => {
      expect(clientApi).toHaveBeenCalledWith(
        "/orchestrator/workflows",
        expect.objectContaining({
          method: "POST",
          body: expect.stringContaining("Perform a comprehensive content and SEO optimization"),
        })
      );
    });

    // Workflow activity is rendered
    expect(await screen.findByTestId("workflow-activity")).toBeInTheDocument();
    expect(screen.getByTestId("approve-step-btn")).toBeInTheDocument();
  });

  it("approves step via workflow without duplicate proposal apply", async () => {
    const onApplyMock = vi.fn();
    (clientApi as any).mockImplementation((endpoint: string) => {
      if (endpoint === "/orchestrator/workflows") {
        return Promise.resolve(mockRunningWorkflow);
      }
      if (endpoint.includes("/steps/step-3/approve")) {
        return Promise.resolve({
          ...mockRunningWorkflow,
          status: "COMPLETED",
          steps: mockRunningWorkflow.steps.map((s) => ({
            ...s,
            status: "COMPLETED",
          })),
        });
      }
      return Promise.resolve({});
    });

    render(
      <EditorSidebar
        document={mockDoc}
        onApplyProposal={onApplyMock}
        onRejectProposal={vi.fn()}
        onSelectBlock={vi.fn()}
        onRestoreVersion={vi.fn()}
      />
    );

    fireEvent.click(screen.getByTestId("tab-workflows"));

    // Trigger workflow
    fireEvent.click(screen.getByTestId("recipe-btn-0"));

    const approveBtn = await screen.findByTestId("approve-step-btn");
    fireEvent.click(approveBtn);

    await waitFor(() => {
      expect(clientApi).toHaveBeenCalledWith(
        "/orchestrator/workflows/wf-100/steps/step-3/approve",
        { method: "POST" }
      );
      // Verify double apply is eliminated: onApplyProposal is not called
      expect(onApplyMock).not.toHaveBeenCalled();
    });
  });
});
