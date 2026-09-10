import { ProjectShell } from "@/components/project-shell";
import { KeywordsDashboard } from "@/features/keywords/keywords-dashboard";
import type {
  CannibalizationWarning,
  Keyword,
  KeywordCluster,
  Project,
  Website,
} from "@/lib/api-types";
import { serverApi } from "@/lib/server-api";

export default async function KeywordsPage({
  params,
}: {
  params: Promise<{ projectId: string }>;
}) {
  const { projectId } = await params;
  const [project, websites, keywordsRes, clustersRes] = await Promise.all([
    serverApi<Project>(`/projects/${projectId}`),
    serverApi<{ items: Website[] }>(`/projects/${projectId}/websites`).catch(() => ({ items: [] })),
    serverApi<{ items: Keyword[] }>(`/projects/${projectId}/keywords`).catch(() => ({ items: [] })),
    serverApi<{ items: KeywordCluster[] }>(`/projects/${projectId}/clusters`).catch(() => ({ items: [] })),
  ]);

  const websiteId = websites.items[0]?.id;
  let warnings: CannibalizationWarning[] = [];
  if (websiteId) {
    try {
      const warningsRes = await serverApi<{ items: CannibalizationWarning[] }>(
        `/projects/${projectId}/cannibalization-warnings?website_id=${websiteId}`
      );
      warnings = warningsRes.items;
    } catch {
      warnings = [];
    }
  }

  return (
    <ProjectShell active="Keywords" project={project}>
      <div className="mb-6">
        <p className="eyebrow">Keyword Intelligence & Clusters</p>
        <h1 className="page-title mt-2">Keyword Universe & Clusters</h1>
        <p className="mt-2 text-base text-[var(--muted)] max-w-3xl">
          Manage normalized search queries, deterministic intent classification, business value scores, and semantic
          keyword clusters.
        </p>
      </div>

      <KeywordsDashboard
        projectId={project.id}
        initialKeywords={keywordsRes.items}
        initialClusters={clustersRes.items}
        initialWarnings={warnings}
      />
    </ProjectShell>
  );
}
