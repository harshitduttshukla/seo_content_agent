const LOCAL_AUTH_USERS = ["admin", "seo_lead"] as const;

export type LocalAuthUser = (typeof LOCAL_AUTH_USERS)[number];

interface LocalAuthEnvironment {
  APP_ENV?: string;
  ALLOW_LOCAL_AUTH?: string;
}

export function isLocalAuthEnabled(env?: LocalAuthEnvironment): boolean {
  const runtimeEnv = env ?? {
    APP_ENV: process.env.APP_ENV,
    ALLOW_LOCAL_AUTH: process.env.ALLOW_LOCAL_AUTH,
  };
  return runtimeEnv.APP_ENV === "local" && runtimeEnv.ALLOW_LOCAL_AUTH === "true";
}

export function isLocalAuthUser(value: string | null): value is LocalAuthUser {
  return value !== null && LOCAL_AUTH_USERS.some((user) => user === value);
}
