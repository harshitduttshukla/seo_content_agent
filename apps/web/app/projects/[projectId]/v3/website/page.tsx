import { WebsiteWorkspace } from "@/features/websites/website-workspace";
import type { Project, Website } from "@/lib/api-types";
import { serverApi } from "@/lib/server-api";

export default async function V3WebsitePage({ params }: { params: Promise<{ projectId: string }> }) {
  const { projectId } = await params;
  const [project, websites] = await Promise.all([
    serverApi<Project>(`/projects/${projectId}`),
    serverApi<{ items: Website[] }>(`/projects/${projectId}/websites`),
  ]);

  return <WebsiteWorkspace apiPrefix="/v3" initialItems={websites.items} project={project} />;
}
