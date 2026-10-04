import { V3ContentHarnessView } from "@/features/content-harness/v3-content-harness-view";
import type { Project } from "@/lib/api-types";
import { serverApi } from "@/lib/server-api";

export default async function V3ContentHarnessPage({
  params,
}: {
  params: Promise<{ projectId: string }>;
}) {
  const { projectId } = await params;
  const project = await serverApi<Project>(`/projects/${projectId}`);

  return <V3ContentHarnessView organizationId={project.organization_id} projectId={project.id} />;
}
