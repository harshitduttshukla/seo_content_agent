import { IterationLab } from "@/components/v3/iteration-lab/gsc-performance";
import type { Project } from "@/lib/api-types";
import { serverApi } from "@/lib/server-api";

export default async function IterationLabPage({ params }: { params: Promise<{ projectId: string }> }) {
  const { projectId } = await params;
  const project = await serverApi<Project>(`/projects/${projectId}`);
  return <IterationLab projectId={project.id} />;
}
