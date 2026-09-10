import { afterEach, describe, expect, it, vi } from "vitest";

import { apiRequest, idempotencyKey } from "@/lib/client-api";

afterEach(() => vi.unstubAllGlobals());

describe("Client API helper", () => {
  it("generates random idempotency key with prefix", () => {
    const key1 = idempotencyKey("org");
    const key2 = idempotencyKey("org");
    expect(key1).toMatch(/^org-[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i);
    expect(key2).toMatch(/^org-[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i);
    expect(key1).not.toEqual(key2);
  });

  it("generates an idempotency key when randomUUID is unavailable over HTTP", () => {
    const source = Uint8Array.from([
      0x00, 0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07,
      0x08, 0x09, 0x0a, 0x0b, 0x0c, 0x0d, 0x0e, 0x0f,
    ]);
    vi.stubGlobal("crypto", {
      getRandomValues: (target: Uint8Array) => {
        target.set(source);
        return target;
      },
    });

    expect(idempotencyKey("organization")).toBe(
      "organization-00010203-0405-4607-8809-0a0b0c0d0e0f",
    );
  });

  it("handles successful envelope responses", async () => {
    const mockData = { id: "123", name: "Test Org" };
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        data: mockData,
        meta: { request_id: "req_test" },
        errors: [],
      }),
    });

    const result = await apiRequest<{ id: string; name: string }>("/organizations");
    expect(result).toEqual(mockData);
    expect(global.fetch).toHaveBeenCalledWith(
      "/api/backend/organizations",
      expect.objectContaining({
        headers: expect.objectContaining({
          "Content-Type": "application/json",
        }),
      })
    );
  });

  it("throws ApiError when response contains errors", async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 409,
      json: async () => ({
        data: null,
        meta: { request_id: "req_err" },
        errors: [
          {
            code: "ORGANIZATION_SLUG_CONFLICT",
            message: "An active organization already uses this slug.",
          },
        ],
      }),
    });

    const request = apiRequest("/organizations");
    await expect(request).rejects.toMatchObject({
      name: "Error",
      message: "An active organization already uses this slug.",
      code: "ORGANIZATION_SLUG_CONFLICT",
      requestId: "req_err",
      status: 409,
    });
  });
});
