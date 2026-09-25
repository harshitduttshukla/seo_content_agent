import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { V3Shell } from "@/components/v3/v3-shell";
import { EditorSidebar } from "@/features/editor/editor-sidebar";
import { clientApi } from "@/lib/client-api";
import type { ContentDocument } from "@/lib/api-types";

vi.mock("next/navigation", () => ({
  usePathname: () => "/projects/proj-001/v3/content-hub",
  useRouter: () => ({ push: vi.fn(), refresh: vi.fn() }),
}));

vi.mock("@/lib/client-api", () => ({
  clientApi: vi.fn(),
  ApiError: class ApiError extends Error {},
}));

const doc = {
  id: "doc-001",
  organization_id: "org-001",
  project_id: "proj-001",
  page_id: "page-001",
  title: "Guide",
  slug: "guide",
  status: "DRAFT",
  current_version: 1,
  lock_version: 1,
  plain_text: "Guide",
  word_count: 1,
  content_blocks: [{ id: "block_001", type: "PARAGRAPH", text: "Guide" }],
  created_at: "2026-09-01T00:00:00Z",
  updated_at: "2026-09-01T00:00:00Z",
} as unknown as ContentDocument;

describe("legacy Production retirement", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(clientApi).mockResolvedValue({});
  });

  it("keeps V3 navigation and no longer links to the retired /content area", () => {
    render(
      <V3Shell projectId="proj-001">
        <div />
      </V3Shell>,
    );
    expect(screen.getByRole("link", { name: "Content Hub" })).toHaveAttribute(
      "href",
      "/projects/proj-001/v3/content-hub",
    );
    const hrefs = screen.getAllByRole("link").map((link) => link.getAttribute("href"));
    expect(hrefs).not.toContain("/projects/proj-001/content");
    expect(hrefs.some((href) => /\/content(\/|$)/.test(href ?? ""))).toBe(false);
  });

  it("editor has no SEO quality tab and never calls the removed quality-check route", async () => {
    render(
      <EditorSidebar
        document={doc}
        selectedBlockId={null}
        onApplyProposal={vi.fn()}
        onRejectProposal={vi.fn()}
        onSelectBlock={vi.fn()}
        onRestoreVersion={vi.fn()}
      />,
    );
    expect(screen.getByTestId("tab-chat")).toBeInTheDocument();
    expect(screen.queryByTestId("tab-seo")).not.toBeInTheDocument();
    await waitFor(() => expect(screen.getByTestId("editor-sidebar")).toBeInTheDocument());
    const called = vi.mocked(clientApi).mock.calls.map(([path]) => String(path));
    expect(called.some((path) => path.includes("quality-check"))).toBe(false);
  });
});
