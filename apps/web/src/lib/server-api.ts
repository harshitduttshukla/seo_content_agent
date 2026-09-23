import { cookies } from "next/headers";
import { redirect, unstable_rethrow } from "next/navigation";

import type { ApiEnvelope, Organization } from "@/lib/api-types";
import { ACCESS_COOKIE } from "@/lib/oidc";

export async function serverApi<T>(path: string): Promise<T> {
  const cookieStore = await cookies();
  const accessToken = cookieStore.get(ACCESS_COOKIE)?.value;
  if (!accessToken) redirect("/login");
  const response = await fetch(`${process.env.API_INTERNAL_URL ?? "http://localhost:8000"}/api/v1${path}`, {
    headers: { Authorization: `Bearer ${accessToken}` },
    cache: "no-store",
  });
  if (response.status === 401) redirect("/login");
  const envelope = (await response.json()) as ApiEnvelope<T>;
  if (!response.ok || !envelope.data) {
    throw new Error(`${envelope.errors[0]?.message ?? "API request failed"} (${envelope.meta.request_id})`);
  }
  return envelope.data;
}

/**
 * The name of the project's own organization, read through the existing authorized
 * organization endpoint. Returns "" when it cannot be read, so callers fall back to
 * their generic label instead of rendering undefined or failing the page.
 */
export async function serverOrganizationName(organizationId: string): Promise<string> {
  try {
    const organization = await serverApi<Organization>(`/organizations/${organizationId}`);
    return organization.name?.trim() ?? "";
  } catch (error) {
    unstable_rethrow(error); // keep the 401 → /login redirect working
    return "";
  }
}
