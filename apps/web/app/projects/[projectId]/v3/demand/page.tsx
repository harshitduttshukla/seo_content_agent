import { StrategyTabs } from "@/components/v3/strategy/strategy-tabs";
import type { Project } from "@/lib/api-types";
import { serverApi, serverOrganizationName } from "@/lib/server-api";

export default async function DemandPage({
  params,
  searchParams,
}: {
  params: Promise<{ projectId: string }>;
  /** `?area=&status=` arrive from the Map tab: land here with both filters applied (§4). */
  searchParams: Promise<{ area?: string; status?: string }>;
}) {
  const { projectId } = await params;
  const { area, status } = await searchParams;
  const project = await serverApi<Project>(`/projects/${projectId}`);
  const organizationName = await serverOrganizationName(project.organization_id);
  return (
    <StrategyTabs
      organizationId={project.organization_id}
      organizationName={organizationName}
      projectId={project.id}
      defaultTab="demand"
      initialAreaId={area ?? ""}
      initialStatus={status ?? "all"}
    />
  );
}
