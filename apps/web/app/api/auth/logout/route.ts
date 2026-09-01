import { NextResponse } from "next/server";

import { ACCESS_COOKIE, REFRESH_COOKIE, oidcConfig } from "@/lib/oidc";

export async function POST() {
  let redirectUrl = new URL("/login", process.env.NEXT_PUBLIC_APP_URL ?? "http://localhost:3000");
  try {
    const config = oidcConfig();
    if (config.endSessionEndpoint) {
      redirectUrl = new URL(config.endSessionEndpoint);
      redirectUrl.searchParams.set("post_logout_redirect_uri", `${config.appUrl}/login`);
      redirectUrl.searchParams.set("client_id", config.clientId);
    }
  } catch {
    // Local logout still clears the server-managed session.
  }
  const response = NextResponse.redirect(redirectUrl, 303);
  response.cookies.delete(ACCESS_COOKIE);
  response.cookies.delete(REFRESH_COOKIE);
  return response;
}
