import { CardDetailView } from "@/components/v3/content-hub/card-detail";
import type { Project } from "@/lib/api-types";
import { serverApi } from "@/lib/server-api";

export default async function ContentCardPage({
  params,
}: {
  params: Promise<{ projectId: string; cardId: string }>;
}) {
  const { projectId, cardId } = await params;
  const project = await serverApi<Project>(`/projects/${projectId}`);
  return (
    <CardDetailView scope={{ organizationId: project.organization_id, projectId: project.id }} cardId={cardId} />
  );
}
