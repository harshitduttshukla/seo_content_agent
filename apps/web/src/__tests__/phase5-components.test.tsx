import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ContentEditor } from "@/features/editor/content-editor";
import { EditorSidebar } from "@/features/editor/editor-sidebar";
import { clientApi } from "@/lib/client-api";
import type {
  ContentDocument,
  AIProposal,
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

describe("Phase 5: Chat-Native AI Content Editor", () => {
  beforeEach(() => {
    vi.clearAllMocks();
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

    await waitFor(() => {
      expect(screen.getByText("Applied to Document")).toBeInTheDocument();
    });
  });

  it("renders human-readable diff text when proposal contains structured operations and text object", async () => {
    const structuredProposal: AIProposal = {
      id: "prop-003",
      document_id: mockDoc.id,
      status: "PROPOSED",
      operation_type: "replace_block",
      target_block_ids: ["block_001"],
      old_content: { text: "Original technical SEO description." },
      proposed_content: {
        text: "Optimized: Technical SEO ensures search engines discover, crawl, and index your content.",
        operations: [
          {
            operation: "replace_block",
            block_id: "block_001",
            new_content:
              "Optimized: Technical SEO ensures search engines discover, crawl, and index your content.",
          },
        ],
      },
      diff_summary: {},
      reason: "Polished phrasing according to active brand guidelines and SEO rules.",
      ai_provider: "mock",
      model: "mock-v1",
      created_at: new Date().toISOString(),
    };

    vi.mocked(clientApi).mockImplementation((url: string) => {
      if (url.includes("/chat")) {
        return Promise.resolve({
          id: "msg-003",
          session_id: "sess-001",
          document_id: mockDoc.id,
          role: "assistant",
          content: "I have proposed an edit to block 1.",
          proposal: structuredProposal,
          created_at: new Date().toISOString(),
        });
      }
      return Promise.resolve({});
    });

    render(
      <EditorSidebar
        document={mockDoc}
        selectedBlockId="block_001"
        onApplyProposal={vi.fn()}
        onRejectProposal={vi.fn()}
        onSelectBlock={vi.fn()}
        onRestoreVersion={vi.fn()}
      />
    );

    const input = screen.getByTestId("chat-input");
    fireEvent.change(input, { target: { value: "Optimize block" } });
    fireEvent.click(screen.getByTestId("send-chat-btn"));

    await waitFor(() => {
      expect(screen.getByTestId("proposal-card")).toBeInTheDocument();
      expect(screen.getByText("Original technical SEO description.")).toBeInTheDocument();
      expect(
        screen.getByText(
          "Optimized: Technical SEO ensures search engines discover, crawl, and index your content."
        )
      ).toBeInTheDocument();
      expect(screen.queryByText(/\{"operations":/)).not.toBeInTheDocument();
    });
  });

  it("renders only the message from a legacy JSON chat envelope", async () => {
    const readableMessage = "This page uses SEO naturally across its headings and paragraphs.";
    vi.mocked(clientApi).mockImplementation((url: string) => {
      if (url.includes("/chat")) {
        return Promise.resolve({
          id: "msg-json-envelope",
          session_id: "sess-001",
          document_id: mockDoc.id,
          role: "assistant",
          content: JSON.stringify({
            message: readableMessage,
            operations: [],
            reason: "Answered the user's question.",
            diff_summary: null,
          }),
          created_at: new Date().toISOString(),
        });
      }
      return Promise.resolve({});
    });

    render(
      <EditorSidebar
        document={mockDoc}
        selectedBlockId={null}
        onApplyProposal={vi.fn()}
        onRejectProposal={vi.fn()}
        onSelectBlock={vi.fn()}
        onRestoreVersion={vi.fn()}
      />
    );

    fireEvent.change(screen.getByTestId("chat-input"), {
      target: { value: "What SEO is added to this page?" },
    });
    fireEvent.click(screen.getByTestId("send-chat-btn"));

    await waitFor(() => {
      expect(screen.getByText(readableMessage)).toBeInTheDocument();
    });
    expect(screen.queryByText(/\"operations\":\[\]/)).not.toBeInTheDocument();
  });

  it("hides an incomplete legacy assistant JSON envelope", async () => {
    vi.mocked(clientApi).mockImplementation((url: string, options?: RequestInit) => {
      if (url.includes("/chat") && !options?.method) {
        return Promise.resolve({
          id: "session-incomplete",
          organization_id: "org-001",
          project_id: "proj-001",
          document_id: mockDoc.id,
          title: "Document Assistant",
          created_at: new Date().toISOString(),
          messages: [
            {
              id: "incomplete-assistant",
              session_id: "session-incomplete",
              document_id: mockDoc.id,
              role: "ASSISTANT",
              content: '{"message":"Completed the article","operations":[',
              context_snapshot: {},
              token_usage: {},
              created_at: new Date().toISOString(),
            },
          ],
        });
      }
      return Promise.resolve({});
    });

    render(
      <EditorSidebar
        document={mockDoc}
        selectedBlockId={null}
        onApplyProposal={vi.fn()}
        onRejectProposal={vi.fn()}
        onSelectBlock={vi.fn()}
        onRestoreVersion={vi.fn()}
      />
    );

    await waitFor(() => {
      expect(
        screen.getByText(
          "This earlier AI response was incomplete, so no document changes were created."
        )
      ).toBeInTheDocument();
    });
    expect(screen.queryByText(/\"operations\"/)).not.toBeInTheDocument();
  });

  it("copies assistant messages and lets users edit and resend their prompts", async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: { writeText },
    });

    vi.mocked(clientApi).mockImplementation((url: string) => {
      if (url.includes("/chat")) {
        return Promise.resolve({
          id: "assistant-actions",
          session_id: "sess-001",
          document_id: mockDoc.id,
          role: "assistant",
          content: "I updated your content proposal.",
          created_at: new Date().toISOString(),
        });
      }
      return Promise.resolve({});
    });

    render(
      <EditorSidebar
        document={mockDoc}
        selectedBlockId={null}
        onApplyProposal={vi.fn()}
        onRejectProposal={vi.fn()}
        onSelectBlock={vi.fn()}
        onRestoreVersion={vi.fn()}
      />
    );

    fireEvent.change(screen.getByTestId("chat-input"), {
      target: { value: "Write this page" },
    });
    fireEvent.click(screen.getByTestId("send-chat-btn"));

    await waitFor(() => {
      expect(screen.getByText("I updated your content proposal.")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId("copy-message-assistant-actions"));
    await waitFor(() => {
      expect(writeText).toHaveBeenCalledWith("I updated your content proposal.");
    });

    fireEvent.click(screen.getByTestId("edit-message-temp_1"));
    const editInput = screen.getByTestId("edit-message-input-temp_1");
    fireEvent.change(editInput, { target: { value: "Complete the entire page" } });
    fireEvent.click(screen.getByTestId("save-edit-message-temp_1"));

    await waitFor(() => {
      expect(screen.getByText("Complete the entire page")).toBeInTheDocument();
      expect(screen.queryByText("Write this page")).not.toBeInTheDocument();
      expect(clientApi).toHaveBeenLastCalledWith(
        `/content-documents/${mockDoc.id}/chat`,
        expect.objectContaining({
          method: "POST",
          body: JSON.stringify({
            message: "Complete the entire page",
          }),
        })
      );
    });
  });

  it("restores persisted chat history when the editor reloads", async () => {
    vi.mocked(clientApi).mockImplementation((url: string, options?: RequestInit) => {
      if (url.includes("/chat") && !options?.method) {
        return Promise.resolve({
          id: "session-history",
          organization_id: "org-001",
          project_id: "proj-001",
          document_id: mockDoc.id,
          title: "Document Assistant",
          created_at: new Date().toISOString(),
          messages: [
            {
              id: "persisted-user",
              session_id: "session-history",
              document_id: mockDoc.id,
              role: "USER",
              content: "Incorporate keywords",
              context_snapshot: {},
              token_usage: {},
              created_at: new Date().toISOString(),
            },
            {
              id: "persisted-assistant",
              session_id: "session-history",
              document_id: mockDoc.id,
              role: "ASSISTANT",
              content: "I prepared a keyword proposal.",
              context_snapshot: {},
              token_usage: {},
              created_at: new Date().toISOString(),
            },
          ],
        });
      }
      return Promise.resolve({});
    });

    render(
      <EditorSidebar
        document={mockDoc}
        selectedBlockId={null}
        onApplyProposal={vi.fn()}
        onRejectProposal={vi.fn()}
        onSelectBlock={vi.fn()}
        onRestoreVersion={vi.fn()}
      />
    );

    await waitFor(() => {
      expect(screen.getByText("Incorporate keywords")).toBeInTheDocument();
      expect(screen.getByText("I prepared a keyword proposal.")).toBeInTheDocument();
      expect(screen.getByTestId("edit-message-persisted-user")).toBeInTheDocument();
    });
  });
});
