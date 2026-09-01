import { redirect } from "next/navigation";

import { Header } from "@/components/header";
import { ProjectWorkspace } from "@/features/projects/project-workspace";
import type { Organization, Project } from "@/lib/api-types";
import { serverApi } from "@/lib/server-api";

export default async function ProjectsPage({ searchParams }: { searchParams: Promise<{ organization_id?: string }> }) {
  const { organization_id: organizationId } = await searchParams;
  if (!organizationId) redirect("/organizations");
  const [organization, projectList] = await Promise.all([
    serverApi<Organization>(`/organizations/${organizationId}`),
    serverApi<{ items: Project[] }>(`/projects?organization_id=${encodeURIComponent(organizationId)}`),
  ]);
  return (
    <main className="min-h-screen">
      <Header backHref="/organizations" backLabel="All organizations" />
      <div className="mx-auto max-w-7xl px-5 py-10 sm:px-8 sm:py-14">
        <p className="eyebrow">{organization.name}</p>
        <h1 className="page-title mt-3">Projects</h1>
        <p className="mt-4 max-w-2xl text-lg text-[var(--muted)]">Each project is a private operating surface for one content program and its websites.</p>
        <div className="mt-10"><ProjectWorkspace initialItems={projectList.items} organization={organization} /></div>
      </div>
    </main>
  );
}
