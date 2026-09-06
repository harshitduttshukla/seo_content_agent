import { ProjectShell } from "@/components/project-shell";
import { ContentMapView } from "@/features/content-map/content-map-view";
import type {
  ContentArchitectureVersion,
  ContentMapGraph,
  ContentMapValidation,
  Project,
} from "@/lib/api-types";
import { serverApi } from "@/lib/server-api";

export default async function ContentMapPage({
  params,
}: {
  params: Promise<{ projectId: string }>;
}) {
  const { projectId } = await params;
  const [project, graphRes, validationRes, versionsRes] = await Promise.all([
    serverApi<Project>(`/projects/${projectId}`),
    serverApi<ContentMapGraph>(`/projects/${projectId}/content-map`).catch(() => ({
      nodes: [],
      edges: [],
      graph_revision: 1,
      stats: {
        cannibalization_warnings: 0,
        existing_pages: 0,
        orphan_pages: 0,
        planned_pages: 0,
        total_clusters: 0,
        total_pages: 0,
        total_pillars: 0,
        total_topics: 0,
      },
    })),
    serverApi<ContentMapValidation>(`/projects/${projectId}/content-map/validation`).catch(() => ({
      is_valid: true,
      issues: [],
      total_issues: 0,
    })),
    serverApi<{ items: ContentArchitectureVersion[] }>(`/projects/${projectId}/content-map/versions`)
      .then((r) => r.items || [])
      .catch(() => []),
  ]);

  return (
    <ProjectShell active="Content Map" project={project}>
      <div className="mb-6">
        <p className="eyebrow">Content Architecture Graph</p>
        <h1 className="page-title mt-2">Visual Content Map</h1>
        <p className="mt-2 text-base text-[var(--muted)] max-w-3xl">
          Visual projection of your structured content architecture: Content Pillars, Topics, Keyword Clusters,
          and Planned/Live Pages with deterministic relationship validation.
        </p>
      </div>

      <ContentMapView
        projectId={project.id}
        initialGraph={graphRes}
        initialValidation={validationRes}
        initialVersions={versionsRes}
      />
    </ProjectShell>
  );
}
