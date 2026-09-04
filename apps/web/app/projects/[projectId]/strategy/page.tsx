import { ProjectShell } from "@/components/project-shell";
import { StrategyManager } from "@/features/strategy/strategy-manager";
import type { Project, SEOStrategy, SEOStrategyVersion } from "@/lib/api-types";
import { serverApi } from "@/lib/server-api";

export default async function StrategyPage({
  params,
}: {
  params: Promise<{ projectId: string }>;
}) {
  const { projectId } = await params;
  const [project, strategy, versions] = await Promise.all([
    serverApi<Project>(`/projects/${projectId}`),
    serverApi<SEOStrategy>(`/projects/${projectId}/strategy`),
    serverApi<{ items: SEOStrategyVersion[] }>(`/projects/${projectId}/strategy/versions`).catch(() => ({
      items: [],
    })),
  ]);

  return (
    <ProjectShell active="Strategy" project={project}>
      <div className="mb-6">
        <p className="eyebrow">SEO Architecture & Intelligence</p>
        <h1 className="page-title mt-2">SEO Strategy & Positioning</h1>
        <p className="mt-2 text-base text-[var(--muted)] max-w-3xl">
          Define business positioning, target market, offerings, and SEO objectives. Every keyword and content
          recommendation links back to this authoritative strategy context.
        </p>
      </div>

      <StrategyManager
        projectId={project.id}
        initialStrategy={strategy}
        versions={versions.items}
      />
    </ProjectShell>
  );
}
