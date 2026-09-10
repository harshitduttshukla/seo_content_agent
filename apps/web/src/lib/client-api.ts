import type { ApiEnvelope } from "@/lib/api-types";

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly code: string,
    public readonly requestId: string,
    public readonly status: number,
  ) {
    super(message);
  }
}

export async function apiRequest<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`/api/backend${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
  });
  const envelope = (await response.json()) as ApiEnvelope<T>;
  if (!response.ok || !envelope.data) {
    const error = envelope.errors[0];
    throw new ApiError(
      error?.message ?? "The request could not be completed.",
      error?.code ?? "UNKNOWN_ERROR",
      envelope.meta.request_id,
      response.status,
    );
  }
  return envelope.data;
}

export const clientApi = apiRequest;

function randomUuidFromValues(cryptoApi: Crypto): string {
  const bytes = cryptoApi.getRandomValues(new Uint8Array(16));
  bytes[6] = (bytes[6] & 0x0f) | 0x40;
  bytes[8] = (bytes[8] & 0x3f) | 0x80;
  const hex = Array.from(bytes, (byte) => byte.toString(16).padStart(2, "0")).join("");

  return [
    hex.slice(0, 8),
    hex.slice(8, 12),
    hex.slice(12, 16),
    hex.slice(16, 20),
    hex.slice(20),
  ].join("-");
}

export function idempotencyKey(prefix: string) {
  const cryptoApi = globalThis.crypto;
  const randomId =
    typeof cryptoApi.randomUUID === "function"
      ? cryptoApi.randomUUID()
      : randomUuidFromValues(cryptoApi);
  return `${prefix}-${randomId}`;
}
