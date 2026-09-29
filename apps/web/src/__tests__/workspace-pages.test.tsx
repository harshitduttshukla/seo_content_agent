import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { OrganizationWorkspace } from "@/features/organizations/organization-workspace";
import { ProjectWorkspace } from "@/features/projects/project-workspace";
import type { Organization, Project } from "@/lib/api-types";
import { ApiError, apiRequest } from "@/lib/client-api";

vi.mock("@/lib/client-api", async (original) => ({
  ...(await original<typeof import("@/lib/client-api")>()),
  apiRequest: vi.fn(),
  idempotencyKey: () => "key-1",
}));

const org = { id: "org-1", name: "pajasa", slug: "pajasa" } as Organization;
const project = (id: string, name: string, status = "active") =>
  ({ id, name, description: "Apartment services", status, organization_id: "org-1" }) as unknown as Project;

describe("OrganizationWorkspace", () => {
  beforeEach(() => vi.clearAllMocks());

  it("links each organization to its projects and creates a new one", async () => {
    vi.mocked(apiRequest).mockResolvedValue({ id: "org-2", name: "Acme", slug: "acme" });
    render(<OrganizationWorkspace initialItems={[org]} />);

    expect(screen.getByRole("link", { name: /pajasa/ })).toHaveAttribute("href", "/projects?organization_id=org-1");
    const create = screen.getByRole("button", { name: "Create organization" });
    expect(create).toBeDisabled();
    fireEvent.change(screen.getByLabelText("Organization name"), { target: { value: "Acme" } });
    fireEvent.click(create);
    expect(await screen.findByRole("link", { name: /Acme/ })).toHaveAttribute("href", "/projects?organization_id=org-2");
  });

  it("shows the server's reason when creation fails", async () => {
    vi.mocked(apiRequest).mockRejectedValue(new ApiError("That name is taken.", "CONFLICT", "r", 409));
    render(<OrganizationWorkspace initialItems={[]} />);
    expect(screen.getByText("No organization yet")).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Organization name"), { target: { value: "pajasa" } });
    fireEvent.click(screen.getByRole("button", { name: "Create organization" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("That name is taken.");
  });
});

describe("ProjectWorkspace", () => {
  beforeEach(() => vi.clearAllMocks());

  it("shows each project with a status chip and creates a new one", async () => {
    vi.mocked(apiRequest).mockResolvedValue(project("p-2", "Blog"));
    render(<ProjectWorkspace organization={org} initialItems={[project("p-1", "pajasa_website")]} />);

    const card = screen.getByRole("link", { name: /pajasa_website/ });
    expect(card).toHaveAttribute("href", "/projects/p-1");
    expect(screen.getByText("active")).toHaveClass("chip", "t");
    expect(screen.getByRole("link", { name: /Organization settings/ })).toHaveAttribute("href", "/organizations/org-1/settings");

    fireEvent.change(screen.getByLabelText("Project name"), { target: { value: "Blog" } });
    fireEvent.change(screen.getByLabelText("Description"), { target: { value: "Articles" } });
    fireEvent.click(screen.getByRole("button", { name: "Create project" }));
    await waitFor(() =>
      expect(apiRequest).toHaveBeenCalledWith("/projects", expect.objectContaining({
        body: JSON.stringify({ organization_id: "org-1", name: "Blog", description: "Articles" }),
      })),
    );
    expect(await screen.findByRole("link", { name: /Blog/ })).toHaveAttribute("href", "/projects/p-2");
  });
});
