import crypto from "node:crypto";

export const ACCESS_COOKIE = "cio_access_token";
export const REFRESH_COOKIE = "cio_refresh_token";
export const STATE_COOKIE = "cio_oauth_state";
export const VERIFIER_COOKIE = "cio_pkce_verifier";

export function oidcConfig() {
  const required = {
    clientId: process.env.OIDC_CLIENT_ID,
    authorizationEndpoint: process.env.OIDC_AUTHORIZATION_ENDPOINT,
    tokenEndpoint: process.env.OIDC_TOKEN_ENDPOINT,
    appUrl: process.env.NEXT_PUBLIC_APP_URL,
  };
  const missing = Object.entries(required)
    .filter(([, value]) => !value)
    .map(([key]) => key);
  if (missing.length) throw new Error(`Missing OIDC configuration: ${missing.join(", ")}`);
  return {
    ...required,
    clientId: required.clientId!,
    authorizationEndpoint: required.authorizationEndpoint!,
    tokenEndpoint: required.tokenEndpoint!,
    appUrl: required.appUrl!,
    clientSecret: process.env.OIDC_CLIENT_SECRET,
    endSessionEndpoint: process.env.OIDC_END_SESSION_ENDPOINT,
  };
}

export function randomBase64Url(bytes = 32) {
  return crypto.randomBytes(bytes).toString("base64url");
}

export function pkceChallenge(verifier: string) {
  return crypto.createHash("sha256").update(verifier).digest("base64url");
}

interface SessionCookieEnvironment {
  APP_ENV?: string;
  NEXT_PUBLIC_APP_URL?: string;
}

export function isSecureCookieEnabled(env?: SessionCookieEnvironment): boolean {
  const runtimeEnv = env ?? {
    APP_ENV: process.env.APP_ENV,
    NEXT_PUBLIC_APP_URL: process.env.NEXT_PUBLIC_APP_URL,
  };
  return (
    runtimeEnv.APP_ENV === "production" ||
    runtimeEnv.NEXT_PUBLIC_APP_URL?.startsWith("https://") === true
  );
}

export const sessionCookieOptions = {
  httpOnly: true,
  sameSite: "lax" as const,
  secure: isSecureCookieEnabled(),
  path: "/",
};
