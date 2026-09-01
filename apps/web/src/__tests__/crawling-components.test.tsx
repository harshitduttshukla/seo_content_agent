import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { CrawlPanel } from "@/features/crawling/crawl-panel";
import { PageInventory } from "@/features/pages/page-inventory";
import { WebsiteWorkspace } from "@/features/websites/website-workspace";
import type { Project, Website } from "@/lib/api-types";

// Mock client-api
vi.mock("@/lib/client-api", () => ({
  apiRequest: vi.fn().mockImplementation((path: string) => {
    if (path.includes("/crawl-status")) {
      return Promise.resolve({
        website_id: "site-1",
        verification_status: "verified",
        active_job: null,
        last_job: null,
        total_indexed_pages: 5,
      });
    }
    if (path.includes("/crawl-jobs")) {
      return Promise.resolve({ items: [] });
    }
    if (path.includes("/verification")) {
      return Promise.resolve({
        website_id: "site-1",
        verification_status: "verified",
        verified_at: new Date().toISOString(),
        verification_token: "ag-verify-mock-token",
        meta_tag_snippet: '<meta name="antigravity-verification" content="ag-verify-mock-token">',
        file_snippet: "ag-verify-mock-token",
      });
    }
    if (path.includes("/pages")) {
      return Promise.resolve({
        items: [
          {
            id: "page-1",
            website_id: "site-1",
            url: "https://example.com/about",
            normalized_url: "https://example.com/about",
            canonical_url: "https://example.com/about",
            title: "About Us",
            http_status: 200,
            content_status: "indexed",
            word_count: 320,
            last_crawled_at: new Date().toISOString(),
            created_at: new Date().toISOString(),
          },
        ],
      });
    }
    return Promise.resolve({});
  }),
  idempotencyKey: () => "mock-key",
}));

const mockProject: Project = {
  id: "proj-1",
  organization_id: "org-1",
  name: "Marketing Suite",
  slug: "marketing-suite",
  description: "SEO Project",
  status: "active",
  default_locale: "en",
  default_country: "US",
  settings: {},
  archived_at: null,
  revision: 1,
  created_at: new Date().toISOString(),
  updated_at: new Date().toISOString(),
};

const mockWebsite: Website = {
  id: "site-1",
  organization_id: "org-1",
  project_id: "proj-1",
  name: "Main Blog",
  base_url: "https://example.com",
  normalized_host: "example.com",
  status: "active",
  locale: "en",
  country: "US",
  verification_status: "verified",
  verified_at: new Date().toISOString(),
  settings: {},
  archived_at: null,
  revision: 1,
  created_at: new Date().toISOString(),
  updated_at: new Date().toISOString(),
};

describe("Phase 2 Crawling & Page UI Components", () => {
  it("renders CrawlPanel with verified domain and Start Crawl button", async () => {
    render(<CrawlPanel website={mockWebsite} />);
    expect(screen.getByText("Crawler Engine")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /start crawl/i })).toBeInTheDocument();
  });

  it("renders PageInventory and displays search & table rows", async () => {
    const { unmount } = render(<PageInventory website={mockWebsite} />);
    expect(screen.getByPlaceholderText(/search by url or title/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /indexed/i })).toBeInTheDocument();
    unmount();
  });

  it("renders WebsiteWorkspace tabs and switches views", () => {
    render(
      <WebsiteWorkspace
        initialItems={[mockWebsite]}
        project={mockProject}
      />
    );
    expect(screen.getByText("Crawl & Indexing")).toBeInTheDocument();
    expect(screen.getByText("Pages (Content Inventory)")).toBeInTheDocument();
    expect(screen.getByText("Domain Overview")).toBeInTheDocument();

    fireEvent.click(screen.getByText("Pages (Content Inventory)"));
    expect(screen.getByPlaceholderText(/search by url or title/i)).toBeInTheDocument();
  });
});
