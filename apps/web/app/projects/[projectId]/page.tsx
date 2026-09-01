import { BookOpen, Bot, KeyRound, SearchCheck, Target } from "lucide-react";
import Link from "next/link";

import { Card } from "@/components/card";
import { ProjectShell } from "@/components/project-shell";
import type { Project, Website } from "@/lib/api-types";
import { serverApi } from "@/lib/server-api";

export default async function ProjectDashboard({ params }: { params: Promise<{ projectId: string }> }) {
  const { projectId } = await params;
  const [project, websites] = await Promise.all([
    serverApi<Project>(`/projects/${projectId}`),
    serverApi<{ items: Website[] }>(`/projects/${projectId}/websites`),
  ]);
  const future = [
    ["Strategy", Target], ["Keywords", KeyRound], ["Content", BookOpen], ["SEO", SearchCheck], ["AI", Bot],
  ] as const;
  return (
    <ProjectShell active="Overview" project={project}>
      <p className="eyebrow">Project overview</p>
      <h1 className="page-title mt-3">{project.name}</h1>
      <p className="mt-4 max-w-3xl text-lg leading-7 text-[var(--muted)]">{project.description || "Add a clear project description in settings so every future workflow starts with the right context."}</p>
      <div className="mt-9 grid gap-4 lg:grid-cols-[1.2fr_0.8fr]">
        <Card className="p-6">
          <div className="flex items-center justify-between gap-4"><div><p className="eyebrow">Website</p><h2 className="mb-0 mt-2 text-xl font-bold">{websites.items[0]?.name ?? "No website connected"}</h2></div><span className="rounded-full bg-[var(--surface-soft)] px-3 py-1 text-xs font-bold capitalize">{websites.items[0]?.status ?? "Empty"}</span></div>
          <p className="mt-5 break-all text-sm text-[var(--muted)]">{websites.items[0]?.base_url ?? "Connect the canonical website that this project will organize."}</p>
          <Link className="mt-6 inline-flex text-sm font-bold text-[var(--accent)]" href={`/projects/${project.id}/website`}>{websites.items.length ? "Manage website" : "Add website"} →</Link>
        </Card>
        <Card className="p-6"><p className="eyebrow">Project status</p><p className="mt-3 text-2xl font-bold capitalize">{project.status}</p><p className="mb-0 mt-4 text-sm leading-6 text-[var(--muted)]">Default locale {project.default_locale}{project.default_country ? ` · ${project.default_country}` : ""}. No performance metrics are available in Phase 1.</p></Card>
      </div>
      <section className="mt-10"><div><p className="eyebrow">Platform modules</p><h2 className="mb-0 mt-2 text-2xl font-bold">Ready for what comes next</h2></div><div className="mt-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-5">{future.map(([label, Icon]) => <Card className="p-4" key={label}><Icon aria-hidden className="text-[#9aa3b3]" size={20} /><p className="mb-1 mt-5 font-bold">{label}</p><p className="m-0 text-xs text-[var(--muted)]">Coming in a later phase</p></Card>)}</div></section>
    </ProjectShell>
  );
}
