import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { LandingPage } from "@/features/marketing/landing-page";

afterEach(cleanup);

describe("LandingPage", () => {
  it("presents the platform and routes signed-out users to login", () => {
    render(<LandingPage workspaceHref="/login" workspaceLabel="Sign in" />);

    expect(
      screen.getByRole("heading", { level: 1, name: /build content that works as a system/i }),
    ).toBeInTheDocument();
    expect(screen.getByRole("navigation", { name: /primary navigation/i })).toBeInTheDocument();
    expect(screen.getAllByRole("link", { name: /enter your workspace/i })[0]).toHaveAttribute(
      "href",
      "/login",
    );
    expect(screen.getByRole("heading", { name: /every content decision stays connected/i })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /ai that operates inside your rules/i })).toBeInTheDocument();
  });

  it("routes authenticated users to their workspace", () => {
    render(<LandingPage workspaceHref="/organizations" workspaceLabel="Open workspace" />);

    expect(screen.getAllByRole("link", { name: /open workspace/i })[0]).toHaveAttribute(
      "href",
      "/organizations",
    );
    expect(screen.getByRole("link", { name: /skip to content/i })).toHaveAttribute(
      "href",
      "#main-content",
    );
  });
});
