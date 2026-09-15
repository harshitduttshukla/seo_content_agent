import { ProjectShell } from "@/components/project-shell";
import { ContentHarnessView } from "@/features/content-harness/content-harness-view";
import type { Project } from "@/lib/api-types";
import { serverApi } from "@/lib/server-api";

export default async function ContentHarnessPage({
  params,
}: {
  params: Promise<{ projectId: string }>;
}) {
  const { projectId } = await params;

  const [project, goldenCasesRes, runsRes] = await Promise.all([
    serverApi<Project>(`/projects/${projectId}`),
    serverApi<any[]>(`/content-harness/golden-cases`).catch(() => []),
    serverApi<any[]>(`/content-harness/runs?project_id=${projectId}&limit=20`).catch(() => []),
  ]);

  return (
    <ProjectShell active="Content Harness" project={project}>
      <ContentHarnessView
        goldenCases={goldenCasesRes || []}
        initialRuns={runsRes || []}
        projectId={projectId}
      />
    </ProjectShell>
  );
}
