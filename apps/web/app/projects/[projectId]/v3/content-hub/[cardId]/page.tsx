import { CardDetailView } from "@/components/v3/content-hub/card-detail";
import type { Project } from "@/lib/api-types";
import { serverApi } from "@/lib/server-api";

export default async function ContentCardPage({
  params,
  searchParams,
}: {
  params: Promise<{ projectId: string; cardId: string }>;
  searchParams: Promise<{ from?: string }>;
}) {
  const [{ projectId, cardId }, { from }] = await Promise.all([params, searchParams]);
  const project = await serverApi<Project>(`/projects/${projectId}`);
  return (
    <CardDetailView
      scope={{ organizationId: project.organization_id, projectId: project.id }}
      cardId={cardId}
      backTo={from === "production" ? "production" : "content-hub"}
    />
  );
}
