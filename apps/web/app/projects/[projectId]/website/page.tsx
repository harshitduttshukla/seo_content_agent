import { ProjectShell } from "@/components/project-shell";
import { WebsiteWorkspace } from "@/features/websites/website-workspace";
import type { Project, Website } from "@/lib/api-types";
import { serverApi } from "@/lib/server-api";

export default async function ProjectWebsitePage({
  params,
}: {
  params: Promise<{ projectId: string }>;
}) {
  const { projectId } = await params;
  const [project, websites] = await Promise.all([
    serverApi<Project>(`/projects/${projectId}`),
    serverApi<{ items: Website[] }>(`/projects/${projectId}/websites`),
  ]);

  return (
    <ProjectShell active="Website" project={project}>
      <WebsiteWorkspace initialItems={websites.items} project={project} />
    </ProjectShell>
  );
}
