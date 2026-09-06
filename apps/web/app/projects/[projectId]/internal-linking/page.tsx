import { ProjectShell } from "@/components/project-shell";
import { InternalLinkingDashboard } from "@/features/internal-linking/internal-linking-dashboard";
import type {
  LinkOpportunity,
  OrphanPage,
  PageRelationship,
  PlannedContentPageList,
  Project,
} from "@/lib/api-types";
import { serverApi } from "@/lib/server-api";

export default async function InternalLinkingPage({
  params,
}: {
  params: Promise<{ projectId: string }>;
}) {
  const { projectId } = await params;

  const [project, oppsRes, relsRes, orphansRes, pagesRes] = await Promise.all([
    serverApi<Project>(`/projects/${projectId}`),
    serverApi<{ items: LinkOpportunity[] }>(`/projects/${projectId}/link-opportunities`).catch(
      () => ({ items: [] })
    ),
    serverApi<{ items: PageRelationship[] }>(`/projects/${projectId}/page-relationships`).catch(
      () => ({ items: [] })
    ),
    serverApi<{ items: OrphanPage[] }>(`/projects/${projectId}/orphan-pages`).catch(() => ({
      items: [],
    })),
    serverApi<PlannedContentPageList>(`/projects/${projectId}/content-pages`).catch(() => ({
      items: [],
      total: 0,
    })),
  ]);

  return (
    <ProjectShell active="Internal Linking" project={project}>
      <div className="mb-6">
        <p className="eyebrow">Internal Linking & Information Architecture</p>
        <h1 className="page-title mt-2">Internal Linking Architecture & Opportunities</h1>
        <p className="mt-2 text-base text-[var(--muted)] max-w-3xl">
          Govern page relationships, approve algorithmic internal linking proposals,
          remedy orphan pages, and eliminate topic cannibalization across your domain.
        </p>
      </div>

      <InternalLinkingDashboard
        projectId={project.id}
        initialOpportunities={oppsRes.items}
        initialRelationships={relsRes.items}
        initialOrphans={orphansRes.items}
        availablePages={pagesRes.items}
      />
    </ProjectShell>
  );
}
