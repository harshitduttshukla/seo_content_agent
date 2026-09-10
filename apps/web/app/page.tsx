import type { Metadata } from "next";
import { cookies } from "next/headers";

import { LandingPage } from "@/features/marketing/landing-page";
import { ACCESS_COOKIE } from "@/lib/oidc";

export const metadata: Metadata = {
  title: "Content Intelligence OS | Governed SEO operations",
  description:
    "Connect strategy, keyword intelligence, content architecture, SEO rules, and governed AI workflows in one secure operating system.",
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
