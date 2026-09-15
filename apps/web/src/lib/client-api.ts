import type { ApiEnvelope } from "@/lib/api-types";

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly code: string,
    public readonly requestId: string,
    public readonly status: number,
    public readonly field?: string | null,
    public readonly details?: Record<string, unknown> | null,
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
    const reason =
      error?.details && typeof error.details.reason === "string" ? error.details.reason : null;
    const message =
      reason && error?.field
        ? `${error.message} (${error.field}: ${reason})`
        : reason
        ? `${error?.message ?? "Validation error"}: ${reason}`
        : error?.message ?? "The request could not be completed.";

    throw new ApiError(
      message,
      error?.code ?? "UNKNOWN_ERROR",
      envelope.meta.request_id,
      response.status,
      error?.field ?? null,
      error?.details ? (error.details as Record<string, unknown>) : null,
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
