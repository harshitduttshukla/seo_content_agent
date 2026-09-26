import { cookies } from "next/headers";
import { NextRequest, NextResponse } from "next/server";

import { ACCESS_COOKIE, sessionCookieOptions } from "@/lib/oidc";

const RETURN_COOKIE = "gsc_return_project";
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

/** Starts Google consent for a project: the API issues the state-bound URL; the browser goes there. */
export async function GET(request: NextRequest) {
  const appUrl = process.env.NEXT_PUBLIC_APP_URL || "http://localhost:3000";
  const project = request.nextUrl.searchParams.get("project") ?? "";
  if (!UUID.test(project)) return NextResponse.redirect(new URL("/projects", appUrl));
  const settings = new URL(`/projects/${project}/v3/settings`, appUrl);
  const accessToken = (await cookies()).get(ACCESS_COOKIE)?.value;
  if (!accessToken) return NextResponse.redirect(new URL("/login", appUrl));

  const response = await fetch(
    `${process.env.API_INTERNAL_URL ?? "http://localhost:8000"}/api/v1/projects/${project}/search-console/connect`,
    { method: "POST", headers: { Authorization: `Bearer ${accessToken}` }, cache: "no-store" },
  );
  const envelope = (await response.json().catch(() => null)) as {
    data?: { authorization_url?: string } | null;
    errors?: { code?: string }[];
  } | null;
  const target = envelope?.data?.authorization_url;
  if (!response.ok || !target || !target.startsWith("https://accounts.google.com/")) {
    settings.searchParams.set("gsc_error", envelope?.errors?.[0]?.code ?? "GSC_CONNECT_FAILED");
    return NextResponse.redirect(settings);
  }
  const redirect = NextResponse.redirect(target);
  redirect.cookies.set(RETURN_COOKIE, project, { ...sessionCookieOptions, maxAge: 600 });
  return redirect;
}
