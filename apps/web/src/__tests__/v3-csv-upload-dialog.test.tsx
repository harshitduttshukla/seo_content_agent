import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { CsvUploadDialog, buildItems, columnMapping, initialChoices, readCsv } from "@/components/v3/strategy/csv-upload-dialog";
import { V3API } from "@/lib/v3-api";

vi.mock("@/lib/v3-api", () => ({
  V3API: { demand: { csvMapping: vi.fn(), importCsv: vi.fn() } },
}));

const scope = { organizationId: "org-1", projectId: "project-1" };
const TOOL_EXPORT = 'Keyword,Avg. monthly searches,Notes\nhow to fix a leaking tap,"2,400",x\nemergency plumber,5400,y\n';

describe("CSV mapping", () => {
  it("matches common tool headers and defaults type to keyword", () => {
    const { headers, rows } = readCsv(TOOL_EXPORT);
    const choices = initialChoices(headers, {});
    expect(choices.text).toBe("col:Keyword");
    expect(choices.volume).toBe("col:Avg. monthly searches");
    expect(choices.type).toBe("all:keyword");
    expect(choices.area).toBe("");
    const items = buildItems(headers, rows, choices);
    expect(items[0]).toMatchObject({ text: "how to fix a leaking tap", type: "keyword", volume: 2400, area: null });
    expect(columnMapping(choices)).toEqual({ text: "Keyword", volume: "Avg. monthly searches" });
  });

  it("prefers the saved mapping and applies one area to every row", () => {
    const { headers, rows } = readCsv("Term,Other\nleaking tap,a\n");
    const choices = { ...initialChoices(headers, { text: "Other" }), area: "all:area-1" };
    expect(choices.text).toBe("col:Other");
    expect(buildItems(headers, rows, { ...choices, text: "col:Term" })[0].area).toBe("area-1");
  });

  it("names the row that breaks a rule", () => {
    const { headers, rows } = readCsv("text,type\nok,keyword\nbad,video\n");
    expect(() => buildItems(headers, rows, initialChoices(headers, {}))).toThrow("Row 3: type must be keyword or prompt.");
  });
});

describe("CsvUploadDialog", () => {
  beforeEach(() => vi.clearAllMocks());

  it("imports with the chosen mapping and one area for all rows", async () => {
    vi.mocked(V3API.demand.csvMapping).mockResolvedValue({ column_mapping: {} });
    vi.mocked(V3API.demand.importCsv).mockResolvedValue({ created_count: 2, existing_count: 0, job_run_id: "j" });
    const onImported = vi.fn().mockResolvedValue(undefined);
    const areas = [{ id: "area-1", canvas_id: "c", parent_id: null, name: "Leak repairs", default_argument_id: null }];
    const { container } = render(
      <CsvUploadDialog scope={scope} isOpen onOpenChange={vi.fn()} onImported={onImported} areas={areas} />,
    );
    await waitFor(() => expect(V3API.demand.csvMapping).toHaveBeenCalled());

    const input = (container.ownerDocument.querySelector("input[type=file]") as HTMLInputElement);
    const file = new File([TOOL_EXPORT], "ahrefs.csv", { type: "text/csv" });
    Object.defineProperty(file, "text", { value: () => Promise.resolve(TOOL_EXPORT) }); // jsdom has no File.text
    fireEvent.change(input, { target: { files: [file] } });
    expect(await screen.findByText(/2 rows found/)).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Area"), { target: { value: "all:area-1" } });
    fireEvent.click(screen.getByRole("button", { name: "Import" }));

    await waitFor(() => expect(V3API.demand.importCsv).toHaveBeenCalled());
    const [, items, mapping] = vi.mocked(V3API.demand.importCsv).mock.calls[0];
    expect(items.map((item) => item.area)).toEqual(["area-1", "area-1"]);
    expect(mapping).toEqual({ text: "Keyword", volume: "Avg. monthly searches" });
    expect(onImported).toHaveBeenCalled();
  });
});
