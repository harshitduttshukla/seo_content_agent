import { redirect } from "next/navigation";

import { V3PageHeading, V3TopBar } from "@/components/v3/v3-top-bar";
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
    <div className="min-h-screen bg-[#ECEEED] text-[14px] text-[#12171A] antialiased">
      <V3TopBar backHref="/organizations" backLabel="All organizations" />
      <main className="mx-auto max-w-[1120px] px-[20px] pb-[70px] pt-[32px] sm:px-[28px]">
        <V3PageHeading
          eyebrow={organization.name}
          title="Projects"
          lead="A project holds one website's strategy, content plan and articles."
        />
        <ProjectWorkspace initialItems={projectList.items} organization={organization} />
      </main>
    </div>
  );
}
