import { ProjectShell } from "@/components/project-shell";
import { ArchitectureDashboard } from "@/features/content/architecture-dashboard";
import type {
  ContentArchitectureGraph,
  ContentOpportunity,
  ContentPillar,
  KeywordPageMapping,
  Project,
  Topic,
  Website,
} from "@/lib/api-types";
import { serverApi } from "@/lib/server-api";

export default async function ArchitecturePage({
  params,
}: {
  params: Promise<{ projectId: string }>;
}) {
  const { projectId } = await params;
  const [
    project,
    websites,
    pillarsRes,
    topicsRes,
    oppsRes,
    mappingsRes,
    graphRes,
  ] = await Promise.all([
    serverApi<Project>(`/projects/${projectId}`),
    serverApi<{ items: Website[] }>(`/projects/${projectId}/websites`).catch(() => ({ items: [] })),
    serverApi<{ items: ContentPillar[] }>(`/projects/${projectId}/content-pillars`).catch(() => ({ items: [] })),
    serverApi<{ items: Topic[] }>(`/projects/${projectId}/topics`).catch(() => ({ items: [] })),
    serverApi<{ items: ContentOpportunity[] }>(`/projects/${projectId}/content-opportunities`).catch(() => ({
      items: [],
    })),
    serverApi<{ items: KeywordPageMapping[] }>(`/projects/${projectId}/keyword-mappings`).catch(() => ({
      items: [],
    })),
    serverApi<ContentArchitectureGraph>(`/projects/${projectId}/content-architecture/graph`).catch(() => ({
      nodes: [],
      edges: [],
    })),
  ]);

  const websiteId = websites.items[0]?.id;

  return (
    <ProjectShell active="Content Map" project={project}>
      <div className="mb-6">
        <p className="eyebrow">Content Architecture & Target Mappings</p>
        <h1 className="page-title mt-2">Content Pillars & Opportunities</h1>
        <p className="mt-2 text-base text-[var(--muted)] max-w-3xl">
          Hierarchical structure connecting business strategy to topic pillars, keyword clusters, crawled live pages,
          and target page recommendations.
        </p>
      </div>

      <ArchitectureDashboard
        projectId={project.id}
        websiteId={websiteId}
        initialPillars={pillarsRes.items}
        initialTopics={topicsRes.items}
        initialOpportunities={oppsRes.items}
        initialMappings={mappingsRes.items}
        initialGraph={graphRes}
      />
    </ProjectShell>
  );
}
