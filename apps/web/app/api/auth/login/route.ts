import { NextRequest, NextResponse } from "next/server";

import {
  ACCESS_COOKIE,
  STATE_COOKIE,
  VERIFIER_COOKIE,
  oidcConfig,
  pkceChallenge,
  randomBase64Url,
  sessionCookieOptions,
} from "@/lib/oidc";
import { isLocalAuthEnabled, isLocalAuthUser } from "@/lib/local-auth";

export async function GET(request: NextRequest) {
  const searchParams = request.nextUrl.searchParams;
  const devUser = searchParams.get("dev_user");
  const appUrl = process.env.NEXT_PUBLIC_APP_URL || "http://localhost:3000";

  if (devUser) {
    if (!isLocalAuthEnabled() || !isLocalAuthUser(devUser)) {
      return NextResponse.redirect(new URL("/login?error=local_auth_disabled", appUrl));
    }
    const response = NextResponse.redirect(new URL("/organizations", appUrl));
    response.cookies.set(ACCESS_COOKIE, `dev-${devUser}`, {
      ...sessionCookieOptions,
      maxAge: 60 * 60 * 24 * 7,
    });
    return response;
  }

  try {
    const config = oidcConfig();
    const state = randomBase64Url();
    const verifier = randomBase64Url(48);
    const url = new URL(config.authorizationEndpoint);
    url.search = new URLSearchParams({
      client_id: config.clientId,
      redirect_uri: `${config.appUrl}/api/auth/callback`,
      response_type: "code",
      scope: "openid profile email offline_access",
      state,
      code_challenge: pkceChallenge(verifier),
      code_challenge_method: "S256",
    }).toString();
    const response = NextResponse.redirect(url);
    response.cookies.set(STATE_COOKIE, state, { ...sessionCookieOptions, maxAge: 600 });
    response.cookies.set(VERIFIER_COOKIE, verifier, { ...sessionCookieOptions, maxAge: 600 });
    return response;
  } catch {
    return NextResponse.redirect(new URL("/login?error=configuration", appUrl));
  }
}
