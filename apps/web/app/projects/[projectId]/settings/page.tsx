import { ProjectShell } from "@/components/project-shell";
import { ProjectSettings } from "@/features/projects/project-settings";
import type { Project } from "@/lib/api-types";
import { serverApi } from "@/lib/server-api";

export default async function ProjectSettingsPage({
  params,
}: {
  params: Promise<{ projectId: string }>;
}) {
  const { projectId } = await params;
  const project = await serverApi<Project>(`/projects/${projectId}`);

  return (
    <ProjectShell active="Settings" project={project}>
      <ProjectSettings project={project} />
    </ProjectShell>
  );
}
