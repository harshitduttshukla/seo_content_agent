import { StrategyTabs } from "@/components/v3/strategy/strategy-tabs";
import type { Project } from "@/lib/api-types";
import { serverApi } from "@/lib/server-api";

export default async function CanvasPage({
  params,
}: {
  params: Promise<{ projectId: string }>;
}) {
  const { projectId } = await params;
  const project = await serverApi<Project>(`/projects/${projectId}`);
  return (
    <StrategyTabs organizationId={project.organization_id} projectId={project.id} defaultTab="canvas" />
  );
}
