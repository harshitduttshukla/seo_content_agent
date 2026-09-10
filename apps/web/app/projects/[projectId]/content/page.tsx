import { ProjectShell } from "@/components/project-shell";
import { ContentDashboard } from "@/features/content/content-dashboard";
import type {
  ContentOpportunity,
  ContentPageSummary,
  ContentPillar,
  Keyword,
  PlannedContentPageList,
  Project,
  Topic,
  Website,
} from "@/lib/api-types";
import { serverApi } from "@/lib/server-api";

export default async function ContentPlanningPage({
  params,
}: {
  params: Promise<{ projectId: string }>;
}) {
  const { projectId } = await params;

  const [
    project,
    websitesRes,
    plannedPagesRes,
    pillarsRes,
    topicsRes,
    opportunitiesRes,
    keywordsRes,
  ] = await Promise.all([
    serverApi<Project>(`/projects/${projectId}`),
    serverApi<{ items: Website[] }>(`/projects/${projectId}/websites`).catch(() => ({ items: [] })),
    serverApi<PlannedContentPageList>(`/projects/${projectId}/content-pages`).catch(() => ({
      items: [],
      total: 0,
    })),
    serverApi<{ items: ContentPillar[] }>(`/projects/${projectId}/content-pillars`).catch(() => ({
      items: [],
    })),
    serverApi<{ items: Topic[] }>(`/projects/${projectId}/topics`).catch(() => ({ items: [] })),
    serverApi<{ items: ContentOpportunity[] }>(`/projects/${projectId}/content-opportunities`).catch(
      () => ({ items: [] })
    ),
    serverApi<{ items: Keyword[] }>(`/projects/${projectId}/keywords`).catch(() => ({ items: [] })),
  ]);

  const websiteId = websitesRes.items[0]?.id;
  let crawledPages: ContentPageSummary[] = [];
  if (websiteId) {
    try {
      const crawledRes = await serverApi<{ items: ContentPageSummary[] }>(
        `/websites/${websiteId}/pages?limit=100`
      );
      crawledPages = crawledRes.items || [];
    } catch {
      crawledPages = [];
    }
  }

  return (
    <ProjectShell active="Content" project={project}>
      <div className="mb-6">
        <p className="eyebrow">Content Production & Planning</p>
        <h1 className="page-title mt-2">Planned Content Pages & Inventory</h1>
        <p className="mt-2 text-base text-[var(--muted)] max-w-3xl">
          Track planned articles, map target keywords to pages, optimize live crawled URLs,
          and convert high-intent keyword opportunities into published content.
        </p>
      </div>

      <ContentDashboard
        projectId={project.id}
        websiteId={websiteId}
        initialPages={plannedPagesRes.items}
        initialPillars={pillarsRes.items}
        initialTopics={topicsRes.items}
        initialOpportunities={opportunitiesRes.items}
        initialCrawledPages={crawledPages}
        availableKeywords={keywordsRes.items}
      />
    </ProjectShell>
  );
}
