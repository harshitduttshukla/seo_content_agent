import { cookies } from "next/headers";
import { NextRequest, NextResponse } from "next/server";

import { ACCESS_COOKIE } from "@/lib/oidc";

const RETURN_COOKIE = "gsc_return_project";
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

/** Google redirects here; the code and state go to the API, which verifies and stores the grant. */
export async function GET(request: NextRequest) {
  const appUrl = process.env.NEXT_PUBLIC_APP_URL || "http://localhost:3000";
  const cookieStore = await cookies();
  const returnProject = cookieStore.get(RETURN_COOKIE)?.value ?? "";
  const back = (project: string, key: string, value: string) => {
    const url = new URL(UUID.test(project) ? `/projects/${project}/v3/settings` : "/projects", appUrl);
    url.searchParams.set(key, value);
    const response = NextResponse.redirect(url);
    response.cookies.delete(RETURN_COOKIE);
    return response;
  };

  const params = request.nextUrl.searchParams;
  const googleError = params.get("error");
  if (googleError) return back(returnProject, "gsc_error", googleError === "access_denied" ? "GSC_ACCESS_DENIED" : "GSC_AUTH_FAILED");
  const code = params.get("code");
  const state = params.get("state");
  if (!code || !state) return back(returnProject, "gsc_error", "GSC_AUTH_FAILED");
  const accessToken = cookieStore.get(ACCESS_COOKIE)?.value;
  if (!accessToken) return NextResponse.redirect(new URL("/login", appUrl));

  const response = await fetch(`${process.env.API_INTERNAL_URL ?? "http://localhost:8000"}/api/v1/search-console/oauth/callback`, {
    method: "POST",
    headers: { Authorization: `Bearer ${accessToken}`, "Content-Type": "application/json" },
    body: JSON.stringify({ code, state }),
    cache: "no-store",
  });
  const envelope = (await response.json().catch(() => null)) as {
    data?: { project_id?: string } | null;
    errors?: { code?: string }[];
  } | null;
  if (!response.ok || !envelope?.data?.project_id) {
    return back(returnProject, "gsc_error", envelope?.errors?.[0]?.code ?? "GSC_AUTH_FAILED");
  }
  return back(envelope.data.project_id, "gsc", "connected");
}
