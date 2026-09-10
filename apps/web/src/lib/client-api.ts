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

export function idempotencyKey(prefix: string) {
  return `${prefix}-${crypto.randomUUID()}`;
}
