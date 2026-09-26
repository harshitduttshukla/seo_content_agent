import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { IterationLab } from "@/components/v3/iteration-lab/gsc-performance";
import { V3Shell } from "@/components/v3/v3-shell";
import { GscIntegration } from "@/features/search-console/gsc-integration";
import type { GscAnalytics, GscStatus } from "@/lib/api-types";
import { ApiError } from "@/lib/client-api";
import { GscAPI } from "@/lib/gsc-api";

vi.mock("next/navigation", () => ({
  usePathname: () => "/projects/p-1/v3/iteration-lab",
  useRouter: () => ({ push: vi.fn(), refresh: vi.fn() }),
}));

vi.mock("@/lib/gsc-api", () => ({
  GscAPI: {
    status: vi.fn(),
    connectUrl: (p: string) => `/api/integrations/google/start?project=${p}`,
    disconnect: vi.fn(),
    properties: vi.fn(),
    mapProperty: vi.fn(),
    sync: vi.fn(),
    analytics: vi.fn(),
  },
}));

const website = { website_id: "w-1", website_name: "Alpha", base_url: "https://alpha.test", property: null, last_sync: null };

function status(overrides: Partial<GscStatus> = {}): GscStatus {
  return {
    project_id: "p-1", configured: true, state: "connected", google_account_email: "owner@alpha.test",
    connected_at: "2026-09-26T10:00:00Z", last_error: null, can_manage: true, websites: [website],
    ...overrides,
  };
}

const mappedWebsite = {
  ...website,
  property: { site_url: "sc-domain:alpha.test", permission_level: "siteOwner", last_synced_at: "2026-09-26T11:00:00Z",
    last_sync_start: "2026-08-28", last_sync_end: "2026-09-24", stored_rows: 2 },
};

const analytics: GscAnalytics = {
  website_id: "w-1", site_url: "sc-domain:alpha.test", start_date: "2026-08-28", end_date: "2026-09-24",
  totals: { clicks: 4, impressions: 210, ctr: 4 / 210, position: 7.7, rows: 2, queries: 1, pages: 1 },
  rows: [
    { date: "2026-09-01", query: "landed cost", page: "https://alpha.test/landed-cost", clicks: 3, impressions: 120, ctr: 0.025, position: 7.4 },
    { date: "2026-09-02", query: "", page: "https://alpha.test/landed-cost", clicks: 1, impressions: 90, ctr: 1 / 90, position: 8.1 },
  ],
  next_offset: null,
};

describe("Google Search Console settings", () => {
  beforeEach(() => vi.clearAllMocks());

  it("explains a server without GSC configuration and offers no actions", async () => {
    vi.mocked(GscAPI.status).mockResolvedValue(status({ configured: false, state: "not_connected" }));
    render(<GscIntegration projectId="p-1" />);
    expect(await screen.findByText(/Not configured on the server/)).toBeInTheDocument();
    expect(screen.getByTestId("gsc-state")).toHaveTextContent("Not configured");
    expect(screen.queryByRole("link", { name: /Connect Google/ })).not.toBeInTheDocument();
  });

  it("starts the Google connection through the server route and shows OAuth errors", async () => {
    vi.mocked(GscAPI.status).mockResolvedValue(status({ state: "not_connected", google_account_email: null, connected_at: null }));
    render(<GscIntegration projectId="p-1" notice={{ ok: false, code: "GSC_ACCESS_DENIED" }} />);
    expect(await screen.findByTestId("gsc-state")).toHaveTextContent("Not connected");
    expect(screen.getByRole("link", { name: "Connect Google" })).toHaveAttribute(
      "href",
      "/api/integrations/google/start?project=p-1",
    );
    expect(screen.getByRole("alert")).toHaveTextContent("Google access was not granted.");
  });

  it("asks to reconnect when access was revoked", async () => {
    vi.mocked(GscAPI.status).mockResolvedValue(status({ state: "reauth_required", last_error: "Google access was revoked or expired. Reconnect Google." }));
    render(<GscIntegration projectId="p-1" />);
    expect(await screen.findByTestId("gsc-state")).toHaveTextContent("Reconnect needed");
    expect(screen.getByRole("link", { name: "Reconnect Google" })).toBeInTheDocument();
    expect(screen.getByText(/Reconnect Google\.$/)).toBeInTheDocument();
  });

  it("loads real properties, maps one to a website and syncs it", async () => {
    vi.mocked(GscAPI.status).mockResolvedValueOnce(status()).mockResolvedValue(status({ websites: [mappedWebsite] }));
    vi.mocked(GscAPI.properties).mockResolvedValue({ items: [{ site_url: "sc-domain:alpha.test", permission_level: "siteOwner", mapped_website_ids: [] }] });
    vi.mocked(GscAPI.mapProperty).mockResolvedValue(mappedWebsite.property);
    vi.mocked(GscAPI.sync).mockResolvedValue({
      job_run_id: "j", status: "completed", started_at: null, completed_at: null, start_date: "2026-08-28", end_date: "2026-09-24",
      rows_fetched: 3, rows_stored: 2, rows_rejected: 1, truncated: false, error: null,
    });
    render(<GscIntegration projectId="p-1" />);
    fireEvent.click(await screen.findByRole("button", { name: "Load Search Console properties" }));
    const select = await screen.findByLabelText("Property for Alpha");
    fireEvent.change(select, { target: { value: "sc-domain:alpha.test" } });
    fireEvent.click(screen.getByRole("button", { name: "Save" }));
    await waitFor(() => expect(GscAPI.mapProperty).toHaveBeenCalledWith("w-1", "sc-domain:alpha.test"));
    let finish!: (value: Awaited<ReturnType<typeof GscAPI.sync>>) => void;
    const done = {
      job_run_id: "j", status: "completed", started_at: null, completed_at: null, start_date: "2026-08-28", end_date: "2026-09-24",
      rows_fetched: 3, rows_stored: 2, rows_rejected: 1, truncated: false, error: null,
    };
    vi.mocked(GscAPI.sync).mockReturnValue(new Promise((resolve) => (finish = resolve)));
    fireEvent.click(await screen.findByRole("button", { name: "Sync last 28 days" }));
    await waitFor(() => expect(GscAPI.sync).toHaveBeenCalledWith("w-1"));
    expect(await screen.findByTestId("sync-state")).toHaveTextContent("Syncing…");
    vi.mocked(GscAPI.status).mockResolvedValue(status({ websites: [{ ...mappedWebsite, last_sync: { ...done, completed_at: "2026-09-26T11:00:00Z" } }] }));
    finish(done);
    expect(await screen.findByText("Synced Alpha: 2 rows for 2026-08-28 → 2026-09-24, 1 rejected.")).toBeInTheDocument();
    await waitFor(() => expect(screen.getByTestId("sync-state")).toHaveTextContent("Sync successful"));
  });

  it("gives viewers the status without connect, map or sync controls", async () => {
    vi.mocked(GscAPI.status).mockResolvedValue(status({ can_manage: false, websites: [mappedWebsite] }));
    render(<GscIntegration projectId="p-1" />);
    expect(await screen.findByText("Only project managers can connect, map or sync.")).toBeInTheDocument();
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });

  it("shows a failed sync and server errors in words", async () => {
    const failed = { job_run_id: "j", status: "failed", started_at: null, completed_at: "2026-09-26T11:00:00Z",
      start_date: "2026-08-28", end_date: "2026-09-24", rows_fetched: 0, rows_stored: 0, rows_rejected: 0, truncated: false,
      error: "GSC_RATE_LIMITED: Search Console rate limit reached. Try again later." };
    vi.mocked(GscAPI.status).mockResolvedValue(status({ websites: [{ ...mappedWebsite, last_sync: failed }] }));
    vi.mocked(GscAPI.sync).mockRejectedValue(new ApiError("Search Console rate limit reached. Try again later.", "GSC_RATE_LIMITED", "r", 429));
    render(<GscIntegration projectId="p-1" />);
    fireEvent.click(await screen.findByRole("button", { name: "Sync last 28 days" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Search Console rate limit reached. Try again later.");
    expect(screen.getByText("Sync failed")).toBeInTheDocument();
  });

  it("points to the existing website flow instead of creating websites", async () => {
    vi.mocked(GscAPI.status).mockResolvedValue(status({ websites: [] }));
    render(<GscIntegration projectId="p-1" />);
    expect(await screen.findByText(/This project has no websites yet/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Technical SEO › Websites" })).toHaveAttribute("href", "/projects/p-1/website");
  });
});

describe("Iteration Lab · GSC Performance", () => {
  beforeEach(() => vi.clearAllMocks());

  it("shows an empty state instead of numbers when nothing is mapped", async () => {
    vi.mocked(GscAPI.status).mockResolvedValue(status({ state: "not_connected" }));
    render(<IterationLab projectId="p-1" />);
    expect(await screen.findByText(/No Search Console data yet/)).toBeInTheDocument();
    expect(screen.queryByLabelText("Totals")).not.toBeInTheDocument();
    expect(GscAPI.analytics).not.toHaveBeenCalled();
  });

  it("renders stored totals and rows exactly as the API returns them", async () => {
    vi.mocked(GscAPI.status).mockResolvedValue(status({ websites: [mappedWebsite] }));
    vi.mocked(GscAPI.analytics).mockResolvedValue(analytics);
    render(<IterationLab projectId="p-1" />);
    const totals = await screen.findByLabelText("Totals");
    expect(within(totals).getByText("4")).toBeInTheDocument();
    expect(within(totals).getByText("210")).toBeInTheDocument();
    expect(within(totals).getByText("1.90%")).toBeInTheDocument();
    expect(within(totals).getByText("7.7")).toBeInTheDocument();
    const rows = within(screen.getByRole("table", { name: "Search Console rows" })).getAllByRole("row").slice(1);
    expect(rows[0]).toHaveTextContent("2026-09-01landed costhttps://alpha.test/landed-cost31202.50%7.4");
    expect(rows[1]).toHaveTextContent("(empty)");
    expect(GscAPI.analytics).toHaveBeenCalledWith("w-1", { sort: "clicks", limit: 50 });
    fireEvent.change(screen.getByLabelText("Sort by"), { target: { value: "position" } });
    await waitFor(() => expect(GscAPI.analytics).toHaveBeenCalledWith("w-1", { sort: "position", limit: 50 }));
  });

  it("links the V3 Iteration Lab from the shell", () => {
    render(
      <V3Shell projectId="p-1">
        <div />
      </V3Shell>,
    );
    expect(screen.getByRole("link", { name: "Iteration Lab" })).toHaveAttribute("href", "/projects/p-1/v3/iteration-lab");
  });
});
