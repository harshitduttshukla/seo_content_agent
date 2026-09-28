import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { AreasPanel } from "@/components/v3/strategy/areas-panel";
import type { Area } from "@/lib/api-types";
import { V3API } from "@/lib/v3-api";

vi.mock("@/lib/v3-api", () => ({
  V3API: { areas: { list: vi.fn(), create: vi.fn() } },
}));

const scope = { organizationId: "org-1", projectId: "project-1" };
const area = (id: string, name: string, parent_id: string | null = null): Area => ({
  id,
  canvas_id: "canvas-1",
  parent_id,
  name,
  default_argument_id: null,
});

describe("AreasPanel", () => {
  beforeEach(() => vi.clearAllMocks());

  it("says there are no areas and creates a top-level one", async () => {
    vi.mocked(V3API.areas.list).mockResolvedValue([]);
    vi.mocked(V3API.areas.create).mockResolvedValue(area("a1", "Leak repairs"));
    render(<AreasPanel scope={scope} canvasId="canvas-1" canvasArguments={[]} />);

    expect(await screen.findByText(/No areas yet/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Add area" })).toBeDisabled();
    fireEvent.change(screen.getByLabelText("Area name"), { target: { value: " Leak repairs " } });
    fireEvent.click(screen.getByRole("button", { name: "Add area" }));

    await waitFor(() =>
      expect(V3API.areas.create).toHaveBeenCalledWith(scope, "canvas-1", {
        name: "Leak repairs",
        parent_id: null,
        default_argument_id: null,
      }),
    );
    expect(await screen.findByText("Leak repairs", { selector: "li" })).toBeInTheDocument();
  });

  it("lists sub-areas under their parent and offers them as parents", async () => {
    vi.mocked(V3API.areas.list).mockResolvedValue([area("c1", "Tap leaks", "r1"), area("r1", "Leak repairs")]);
    render(<AreasPanel scope={scope} canvasId="canvas-1" canvasArguments={[]} />);

    const items = await screen.findAllByRole("listitem");
    expect(items.map((item) => item.textContent)).toEqual(["Leak repairs", "└ Tap leaks"]);
    fireEvent.change(screen.getByLabelText("Parent area"), { target: { value: "r1" } });
    fireEvent.change(screen.getByLabelText("Area name"), { target: { value: "Pipe leaks" } });
    vi.mocked(V3API.areas.create).mockResolvedValue(area("c2", "Pipe leaks", "r1"));
    fireEvent.click(screen.getByRole("button", { name: "Add area" }));
    await waitFor(() =>
      expect(V3API.areas.create).toHaveBeenCalledWith(scope, "canvas-1", {
        name: "Pipe leaks",
        parent_id: "r1",
        default_argument_id: null,
      }),
    );
  });

  it("shows the server's error, such as a duplicate name", async () => {
    vi.mocked(V3API.areas.list).mockResolvedValue([]);
    vi.mocked(V3API.areas.create).mockRejectedValue(new Error("An area named 'Leak repairs' already exists."));
    render(<AreasPanel scope={scope} canvasId="canvas-1" canvasArguments={[]} />);
    fireEvent.change(await screen.findByLabelText("Area name"), { target: { value: "Leak repairs" } });
    fireEvent.click(screen.getByRole("button", { name: "Add area" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("already exists");
  });
});
