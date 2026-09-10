import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { Button } from "@/components/button";
import { Card } from "@/components/card";
import { Dropdown } from "@/components/dropdown";
import { Header } from "@/components/header";
import { Input } from "@/components/input";
import { Sidebar } from "@/components/sidebar";
import { ErrorState, LoadingState } from "@/components/states";
import { Table, TableCell, TableHead } from "@/components/table";
import { Toast } from "@/components/toast";

describe("Core UI Components", () => {
  it("renders Button with primary tone and handles click", () => {
    const handleClick = vi.fn();
    render(<Button onClick={handleClick}>Click Me</Button>);
    const button = screen.getByRole("button", { name: /click me/i });
    expect(button).toBeInTheDocument();
    fireEvent.click(button);
    expect(handleClick).toHaveBeenCalledTimes(1);
  });

  it("renders Button with danger tone", () => {
    render(<Button tone="danger">Delete</Button>);
    const button = screen.getByRole("button", { name: /delete/i });
    expect(button).toHaveClass("bg-[var(--danger)]");
  });

  it("renders Input with label and value", () => {
    const handleChange = vi.fn();
    render(
      <Input
        label="Project Name"
        name="name"
        onChange={handleChange}
        placeholder="Enter name"
        value="Test Project"
      />
    );
    expect(screen.getByText("Project Name")).toBeInTheDocument();
    const input = screen.getByPlaceholderText("Enter name");
    expect(input).toHaveValue("Test Project");
    fireEvent.change(input, { target: { value: "Updated" } });
    expect(handleChange).toHaveBeenCalled();
  });

  it("renders Dropdown with options", () => {
    const handleChange = vi.fn();
    render(
      <Dropdown label="Select Status" onChange={handleChange} value="active">
        <option value="active">Active</option>
        <option value="archived">Archived</option>
      </Dropdown>
    );
    expect(screen.getByText("Select Status")).toBeInTheDocument();
    const select = screen.getByRole("combobox");
    expect(select).toHaveValue("active");
  });

  it("renders Card container", () => {
    render(<Card>Card content</Card>);
    expect(screen.getByText("Card content")).toBeInTheDocument();
  });

  it("renders Table with headers and cells", () => {
    render(
      <Table>
        <thead>
          <tr>
            <TableHead>Header 1</TableHead>
          </tr>
        </thead>
        <tbody>
          <tr>
            <TableCell>Row 1 Cell</TableCell>
          </tr>
        </tbody>
      </Table>
    );
    expect(screen.getByText("Header 1")).toBeInTheDocument();
    expect(screen.getByText("Row 1 Cell")).toBeInTheDocument();
  });

  it("renders Toast notification", () => {
    render(<Toast message="Operation succeeded" tone="success" />);
    expect(screen.getByRole("status")).toHaveTextContent("Operation succeeded");
  });

  it("renders LoadingState and ErrorState", () => {
    const { rerender } = render(<LoadingState label="Loading data…" />);
    expect(screen.getByText("Loading data…")).toBeInTheDocument();

    rerender(<ErrorState message="Server error occurred" requestId="req_12345" />);
    expect(screen.getByRole("alert")).toHaveTextContent("Server error occurred");
    expect(screen.getByText(/req_12345/)).toBeInTheDocument();
  });

  it("renders Header with back link", () => {
    render(<Header backHref="/projects" backLabel="Back to Projects" />);
    expect(screen.getByText("Back to Projects")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /sign out/i })).toBeInTheDocument();
    expect(screen.getByRole("banner")).toHaveClass("sticky", "top-0", "z-50");
  });

  it("keeps project navigation fixed below the header", () => {
    render(<Sidebar active="Content" projectId="project-001" />);
    expect(screen.getByTestId("project-sidebar")).toHaveClass(
      "sticky",
      "top-20",
      "h-[calc(100vh-5rem)]",
      "overflow-y-auto"
    );
  });
});
