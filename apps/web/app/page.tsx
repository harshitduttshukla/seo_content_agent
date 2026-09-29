import type { Metadata } from "next";
import { cookies } from "next/headers";

import { LandingPage } from "@/features/marketing/landing-page";
import { ACCESS_COOKIE } from "@/lib/oidc";

export const metadata: Metadata = {
  title: "Strategy Graph | Claim-grounded SEO content",
  description:
    "Plan pages from search demand, draft them only from approved positioning claims, and approve every article at two human review gates.",
  alternates: { canonical: "/" },
};

export default async function HomePage() {
  const cookieStore = await cookies();
  const hasSession = cookieStore.has(ACCESS_COOKIE);

  return (
    <LandingPage
      workspaceHref={hasSession ? "/organizations" : "/login"}
      workspaceLabel={hasSession ? "Open workspace" : "Sign in"}
    />
  );
}
