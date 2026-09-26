import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import OldSettingsPage from "../../app/projects/[projectId]/settings/page";
import { ProjectSettingsV3 } from "@/components/v3/settings/project-settings";
import { V3Shell } from "@/components/v3/v3-shell";
import type { Project } from "@/lib/api-types";
import { ApiError, apiRequest } from "@/lib/client-api";
import { GscAPI } from "@/lib/gsc-api";

const push = vi.fn();
const refresh = vi.fn();
const permanentRedirect = vi.fn();
vi.mock("next/navigation", () => ({
  usePathname: () => "/projects/p-1/v3/settings",
  useRouter: () => ({ push, refresh }),
  permanentRedirect: (url: string) => permanentRedirect(url),
}));

vi.mock("@/lib/client-api", () => ({
  apiRequest: vi.fn(),
  ApiError: class ApiError extends Error {
    constructor(message: string, public code = "", public requestId = "", public status = 0) {
      super(message);
    }
  },
}));

vi.mock("@/lib/gsc-api", () => ({
  GscAPI: { status: vi.fn(), connectUrl: (p: string) => `/api/integrations/google/start?project=${p}` },
}));

const project = {
  id: "p-1", organization_id: "o-1", name: "obdsmart", slug: "obdsmart", description: "Diagnostics",
  status: "active", default_locale: "en", default_country: "US", revision: 4,
} as unknown as Project;

describe("V3 project settings", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(GscAPI.status).mockResolvedValue({
      project_id: "p-1", configured: true, state: "not_connected", google_account_email: null, connected_at: null,
      last_error: null, can_manage: true, websites: [],
    });
  });

  it("shows the project, integrations and danger zone sections with existing values", async () => {
    render(<ProjectSettingsV3 project={project} />);
    expect(screen.getByRole("heading", { level: 1, name: "Settings" })).toBeInTheDocument();
    for (const name of ["Project", "Integrations", "Danger zone"]) {
      expect(screen.getByRole("heading", { level: 2, name })).toBeInTheDocument();
    }
    expect(screen.getByLabelText("Project name")).toHaveValue("obdsmart");
    expect(screen.getByLabelText("Description")).toHaveValue("Diagnostics");
    expect(screen.getByLabelText("Default locale")).toHaveValue("en");
    expect(screen.getByLabelText("Default country")).toHaveValue("US");
    expect(screen.getByLabelText("Project status")).toHaveValue("active");
    const integrations = screen.getByRole("region", { name: "Integrations" });
    expect(await within(integrations).findByTestId("gsc-state")).toHaveTextContent("Not connected");
    expect(GscAPI.status).toHaveBeenCalledWith("p-1");
  });

  it("saves through the existing project API with the revision", async () => {
    vi.mocked(apiRequest).mockResolvedValue({ ...project, name: "OBD Smart", default_country: "IN", revision: 5 });
    render(<ProjectSettingsV3 project={project} />);
    fireEvent.change(screen.getByLabelText("Project name"), { target: { value: " OBD Smart " } });
    fireEvent.change(screen.getByLabelText("Default country"), { target: { value: "in" } });
    fireEvent.click(screen.getByRole("button", { name: "Save changes" }));
    await waitFor(() => expect(apiRequest).toHaveBeenCalled());
    const [path, init] = vi.mocked(apiRequest).mock.calls[0];
    expect(path).toBe("/projects/p-1");
    expect(init?.method).toBe("PUT");
    expect(JSON.parse(String(init?.body))).toEqual({
      name: "OBD Smart", slug: "obdsmart", description: "Diagnostics", status: "active",
      default_locale: "en", default_country: "IN", revision: 4,
    });
    expect(await screen.findByRole("status")).toHaveTextContent("Project settings saved.");
    expect(refresh).toHaveBeenCalled();
  });

  it("reports a failed save", async () => {
    vi.mocked(apiRequest).mockRejectedValue(new ApiError("The project changed. Reload.", "VERSION_CONFLICT", "r", 409));
    render(<ProjectSettingsV3 project={project} />);
    fireEvent.click(screen.getByRole("button", { name: "Save changes" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("The project changed. Reload.");
  });

  it("archives only after confirmation, through the existing API", async () => {
    vi.mocked(apiRequest).mockResolvedValue({ ...project, status: "archived" });
    render(<ProjectSettingsV3 project={project} />);
    fireEvent.click(screen.getByRole("button", { name: "Archive project…" }));
    expect(apiRequest).not.toHaveBeenCalled();
    fireEvent.click(within(screen.getByRole("group", { name: "Confirm archive" })).getByRole("button", { name: "Archive project" }));
    await waitFor(() => expect(apiRequest).toHaveBeenCalledWith("/projects/p-1", { method: "DELETE" }));
    expect(push).toHaveBeenCalledWith("/projects?organization_id=o-1");
  });

  it("cannot archive an archived project again", () => {
    render(<ProjectSettingsV3 project={{ ...project, status: "archived" } as Project} />);
    expect(screen.getByRole("button", { name: "Project is archived" })).toBeDisabled();
  });

  it("shows the Google OAuth result passed back by the callback", async () => {
    render(<ProjectSettingsV3 project={project} gscNotice={{ ok: false, code: "GSC_OAUTH_STATE_EXPIRED" }} />);
    expect(await screen.findByRole("alert")).toHaveTextContent("The Google sign-in took too long. Start again.");
  });
});

describe("Settings navigation and the old URL", () => {
  beforeEach(() => vi.clearAllMocks());

  it("lists Settings under Base, apart from the modules", () => {
    render(
      <V3Shell projectId="p-1">
        <div />
      </V3Shell>,
    );
    const link = screen.getByRole("link", { name: "Settings" });
    expect(link).toHaveAttribute("href", "/projects/p-1/v3/settings");
    expect(link).toHaveAttribute("aria-current", "page");
    expect(screen.getByText("Base")).toBeInTheDocument();
    for (const name of ["Strategy", "Content Hub", "Production", "Iteration Lab", "Technical SEO"]) {
      expect(screen.getByRole("link", { name })).toBeInTheDocument();
    }
  });

  it("permanently redirects the old settings URL and keeps the OAuth result", async () => {
    await OldSettingsPage({
      params: Promise.resolve({ projectId: "p-1" }),
      searchParams: Promise.resolve({ gsc: "connected", other: "x" }),
    });
    expect(permanentRedirect).toHaveBeenCalledWith("/projects/p-1/v3/settings?gsc=connected");
    await OldSettingsPage({ params: Promise.resolve({ projectId: "p-1" }), searchParams: Promise.resolve({}) });
    expect(permanentRedirect).toHaveBeenLastCalledWith("/projects/p-1/v3/settings");
  });
});
