import { notFound } from "next/navigation";
import { ProjectShell } from "@/components/project-shell";
import { ErrorState } from "@/components/states";
import { SEOGuideView } from "@/features/seo/seo-guide-view";
import type {
  PageKeyword,
  PlannedContentPage,
  Project,
  SEOGuide,
  SEOGuideVersion,
} from "@/lib/api-types";
import { serverApi } from "@/lib/server-api";

export default async function SEOGuidePage({
  params,
}: {
  params: Promise<{ projectId: string; pageId: string }>;
}) {
  const { projectId, pageId } = await params;

  const [project, plannedPage] = await Promise.all([
    serverApi<Project>(`/projects/${projectId}`),
    serverApi<PlannedContentPage>(`/content-pages/${pageId}`).catch(() => null),
  ]);

  if (!plannedPage) {
    notFound();
  }

  const guideResult = await serverApi<SEOGuide>(`/content-pages/${pageId}/seo-guide`)
    .then((guide) => ({ guide, error: null }))
    .catch((error: unknown) => ({
      guide: null,
      error: error instanceof Error ? error.message : "The SEO guide could not be initialized.",
    }));

  if (!guideResult.guide) {
    return (
      <ProjectShell active="Content" project={project}>
        <ErrorState
          message={`The SEO guide could not be initialized. Refresh the page to try again. ${guideResult.error}`}
        />
      </ProjectShell>
    );
  }

  const guide = guideResult.guide;
  const [versionsRes, keywordsRes] = await Promise.all([
    serverApi<{ items: SEOGuideVersion[] }>(
      `/content-pages/${pageId}/seo-guide/versions`
    ).catch(() => ({ items: [] })),
    serverApi<{ items: PageKeyword[] }>(`/content-pages/${pageId}/keywords`)
      .then((r) => r.items || [])
      .catch(() => []),
  ]);

  return (
    <ProjectShell active="Content" project={project}>
      <SEOGuideView
        projectId={project.id}
        page={plannedPage}
        initialGuide={guide}
        initialVersions={versionsRes.items || []}
        assignedKeywords={keywordsRes}
      />
    </ProjectShell>
  );
}
