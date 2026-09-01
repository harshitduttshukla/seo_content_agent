import { cookies } from "next/headers";
import { NextRequest, NextResponse } from "next/server";

import {
  ACCESS_COOKIE,
  REFRESH_COOKIE,
  STATE_COOKIE,
  VERIFIER_COOKIE,
  oidcConfig,
  sessionCookieOptions,
} from "@/lib/oidc";

type TokenResponse = { access_token?: string; refresh_token?: string; expires_in?: number };

export async function GET(request: NextRequest) {
  const config = oidcConfig();
  const cookieStore = await cookies();
  const state = request.nextUrl.searchParams.get("state");
  const code = request.nextUrl.searchParams.get("code");
  const expectedState = cookieStore.get(STATE_COOKIE)?.value;
  const verifier = cookieStore.get(VERIFIER_COOKIE)?.value;
  if (!code || !state || !expectedState || state !== expectedState || !verifier) {
    return NextResponse.redirect(new URL("/login?error=invalid_callback", config.appUrl));
  }

  const body = new URLSearchParams({
    grant_type: "authorization_code",
    client_id: config.clientId,
    redirect_uri: `${config.appUrl}/api/auth/callback`,
    code,
    code_verifier: verifier,
  });
  if (config.clientSecret) body.set("client_secret", config.clientSecret);
  const tokenResult = await fetch(config.tokenEndpoint, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body,
    cache: "no-store",
  });
  if (!tokenResult.ok) {
    return NextResponse.redirect(new URL("/login?error=token_exchange", config.appUrl));
  }
  const tokens = (await tokenResult.json()) as TokenResponse;
  if (!tokens.access_token) {
    return NextResponse.redirect(new URL("/login?error=missing_token", config.appUrl));
  }

  const response = NextResponse.redirect(new URL("/organizations", config.appUrl));
  response.cookies.set(ACCESS_COOKIE, tokens.access_token, {
    ...sessionCookieOptions,
    maxAge: tokens.expires_in ?? 3600,
  });
  if (tokens.refresh_token) {
    response.cookies.set(REFRESH_COOKIE, tokens.refresh_token, {
      ...sessionCookieOptions,
      maxAge: 60 * 60 * 24 * 30,
    });
  }
  response.cookies.delete(STATE_COOKIE);
  response.cookies.delete(VERIFIER_COOKIE);
  return response;
}
