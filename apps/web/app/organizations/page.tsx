import { LogOut } from "lucide-react";

import { Brand } from "@/components/brand";
import { OrganizationWorkspace } from "@/features/organizations/organization-workspace";
import type { Organization } from "@/lib/api-types";
import { serverApi } from "@/lib/server-api";

export default async function OrganizationsPage() {
  const result = await serverApi<{ items: Organization[] }>("/organizations");
  return (
    <main className="mx-auto min-h-screen max-w-7xl px-5 pb-16 sm:px-8">
      <header className="flex h-20 items-center justify-between border-b border-[var(--border)]">
        <Brand />
        <form action="/api/auth/logout" method="post">
          <button className="inline-flex items-center gap-2 text-sm font-semibold text-[var(--muted)] hover:text-[var(--ink)]" type="submit">
            <LogOut aria-hidden size={16} /> Sign out
          </button>
        </form>
      </header>
      <section className="py-12 sm:py-16">
        <p className="eyebrow">Workspace selection</p>
        <h1 className="page-title mt-3">Choose where the work belongs.</h1>
        <p className="mt-4 max-w-2xl text-lg leading-7 text-[var(--muted)]">Every organization is an isolated tenant. Select one to view its projects, or create a new workspace.</p>
      </section>
      <OrganizationWorkspace initialItems={result.items} />
    </main>
  );
}
