import { cookies } from "next/headers";
import { NextRequest, NextResponse } from "next/server";

import {
  ACCESS_COOKIE,
  REFRESH_COOKIE,
  oidcConfig,
  sessionCookieOptions,
} from "@/lib/oidc";

const ALLOWED_METHODS = new Set(["GET", "POST", "PUT", "PATCH", "DELETE"]);

async function refreshAccessToken(): Promise<string | null> {
  const cookieStore = await cookies();
  const refreshToken = cookieStore.get(REFRESH_COOKIE)?.value;
  if (!refreshToken) return null;
  const config = oidcConfig();
  const body = new URLSearchParams({
    grant_type: "refresh_token",
    client_id: config.clientId,
    refresh_token: refreshToken,
  });
  if (config.clientSecret) body.set("client_secret", config.clientSecret);
  const response = await fetch(config.tokenEndpoint, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body,
    cache: "no-store",
  });
  if (!response.ok) return null;
  const tokens = (await response.json()) as {
    access_token?: string;
    refresh_token?: string;
    expires_in?: number;
  };
  if (!tokens.access_token) return null;
  cookieStore.set(ACCESS_COOKIE, tokens.access_token, {
    ...sessionCookieOptions,
    maxAge: tokens.expires_in ?? 3600,
  });
  if (tokens.refresh_token) {
    cookieStore.set(REFRESH_COOKIE, tokens.refresh_token, {
      ...sessionCookieOptions,
      maxAge: 60 * 60 * 24 * 30,
    });
  }
  return tokens.access_token;
}

async function proxy(
  request: NextRequest,
  path: string[],
  accessToken: string,
  requestBody: ArrayBuffer | undefined,
) {
  const safePath = path.map((part) => encodeURIComponent(part)).join("/");
  const url = new URL(`${process.env.API_INTERNAL_URL ?? "http://localhost:8000"}/api/v1/${safePath}`);
  request.nextUrl.searchParams.forEach((value, key) => url.searchParams.append(key, value));
  const headers = new Headers({ Authorization: `Bearer ${accessToken}` });
  for (const name of ["content-type", "idempotency-key", "x-request-id"]) {
    const value = request.headers.get(name);
    if (value) headers.set(name, value);
  }
  return fetch(url, {
    method: request.method,
    headers,
    body: requestBody,
    cache: "no-store",
  });
}

async function handler(request: NextRequest, context: { params: Promise<{ path: string[] }> }) {
  if (!ALLOWED_METHODS.has(request.method)) {
    return NextResponse.json({ error: "Method not allowed" }, { status: 405 });
  }
  const cookieStore = await cookies();
  let accessToken = cookieStore.get(ACCESS_COOKIE)?.value;
  if (!accessToken) return NextResponse.json({ error: "Authentication required" }, { status: 401 });
  const { path } = await context.params;
  const requestBody = request.method === "GET" ? undefined : await request.arrayBuffer();
  let response = await proxy(request, path, accessToken, requestBody);
  if (response.status === 401) {
    accessToken = await refreshAccessToken() ?? undefined;
    if (accessToken) response = await proxy(request, path, accessToken, requestBody);
  }
  return new NextResponse(response.body, {
    status: response.status,
    headers: {
      "Content-Type": response.headers.get("content-type") ?? "application/json",
      "X-Request-ID": response.headers.get("x-request-id") ?? "unknown",
    },
  });
}

export const GET = handler;
export const POST = handler;
export const PUT = handler;
export const PATCH = handler;
export const DELETE = handler;
