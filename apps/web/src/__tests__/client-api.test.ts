import { describe, expect, it, vi } from "vitest";

import { ApiError, apiRequest, idempotencyKey } from "@/lib/client-api";

describe("Client API helper", () => {
  it("generates random idempotency key with prefix", () => {
    const key1 = idempotencyKey("org");
    const key2 = idempotencyKey("org");
    expect(key1).toMatch(/^org-[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i);
    expect(key2).toMatch(/^org-[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i);
    expect(key1).not.toEqual(key2);
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

    await expect(apiRequest("/organizations")).rejects.toThrow(ApiError);
    await expect(apiRequest("/organizations")).rejects.toThrow(
      "An active organization already uses this slug."
    );
  });
});
