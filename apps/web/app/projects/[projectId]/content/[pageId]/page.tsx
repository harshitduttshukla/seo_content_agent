import { ProjectShell } from "@/components/project-shell";
import { ContentPageWorkspace } from "@/features/content/content-page-workspace";
import type {
  ContentBrief,
  ContentDocument,
  PlannedContentPage,
  Project,
} from "@/lib/api-types";
import { serverApi } from "@/lib/server-api";

export default async function ContentEditorPage({
  params,
}: {
  params: Promise<{ projectId: string; pageId: string }>;
}) {
  const { projectId, pageId } = await params;

  const [project, page, brief, document] = await Promise.all([
    serverApi<Project>(`/projects/${projectId}`),
    serverApi<PlannedContentPage>(`/content-pages/${pageId}`),
    serverApi<ContentBrief>(`/content-pages/${pageId}/brief`),
    serverApi<ContentDocument>(`/content-pages/${pageId}/document`),
  ]);

  return (
    <ProjectShell active="Content" project={project}>
      <ContentPageWorkspace
        projectId={project.id}
        page={page}
        initialBrief={brief}
        initialDocument={document}
      />
    </ProjectShell>
  );
}
