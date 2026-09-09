import { NextRequest } from "next/server";
import { afterEach, describe, expect, it, vi } from "vitest";

import { GET } from "../../app/api/auth/login/route";
import { isLocalAuthEnabled, isLocalAuthUser } from "@/lib/local-auth";

afterEach(() => vi.unstubAllEnvs());

describe("local authentication policy", () => {
  it("is enabled only by an explicit flag in the local environment", () => {
    expect(isLocalAuthEnabled({ APP_ENV: "local", ALLOW_LOCAL_AUTH: "true" })).toBe(true);
    expect(isLocalAuthEnabled({ APP_ENV: "local", ALLOW_LOCAL_AUTH: "false" })).toBe(false);
    expect(isLocalAuthEnabled({ APP_ENV: "production", ALLOW_LOCAL_AUTH: "true" })).toBe(false);
  });

  it("allows only the two development identities shown on the login page", () => {
    expect(isLocalAuthUser("admin")).toBe(true);
    expect(isLocalAuthUser("seo_lead")).toBe(true);
    expect(isLocalAuthUser("unknown")).toBe(false);
    expect(isLocalAuthUser(null)).toBe(false);
  });

  it("creates a local session only when the local gate is enabled", async () => {
    vi.stubEnv("APP_ENV", "local");
    vi.stubEnv("ALLOW_LOCAL_AUTH", "true");
    vi.stubEnv("NEXT_PUBLIC_APP_URL", "http://localhost:3000");

    const response = await GET(
      new NextRequest("http://localhost:3000/api/auth/login?dev_user=admin"),
    );

    expect(response.headers.get("location")).toBe("http://localhost:3000/organizations");
    expect(response.headers.get("set-cookie")).toContain("cio_access_token=dev-admin");
  });

  it("refuses a development login URL outside the local gate", async () => {
    vi.stubEnv("APP_ENV", "production");
    vi.stubEnv("ALLOW_LOCAL_AUTH", "true");
    vi.stubEnv("NEXT_PUBLIC_APP_URL", "http://localhost:3000");

    const response = await GET(
      new NextRequest("http://localhost:3000/api/auth/login?dev_user=admin"),
    );

    expect(response.headers.get("location")).toBe(
      "http://localhost:3000/login?error=local_auth_disabled",
    );
    expect(response.headers.get("set-cookie")).toBeNull();
  });
});
