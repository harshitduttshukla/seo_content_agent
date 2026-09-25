import { Production } from "@/components/v3/production/production";
import type { Project } from "@/lib/api-types";
import { serverApi } from "@/lib/server-api";

export default async function ProductionPage({ params }: { params: Promise<{ projectId: string }> }) {
  const { projectId } = await params;
  const project = await serverApi<Project>(`/projects/${projectId}`);
  return <Production organizationId={project.organization_id} projectId={project.id} />;
}
