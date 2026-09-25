import { ContentHub } from "@/components/v3/content-hub/content-hub";
import type { Project } from "@/lib/api-types";
import { serverApi } from "@/lib/server-api";

export default async function ContentHubPage({ params }: { params: Promise<{ projectId: string }> }) {
  const { projectId } = await params;
  const project = await serverApi<Project>(`/projects/${projectId}`);
  return <ContentHub organizationId={project.organization_id} projectId={project.id} />;
}
