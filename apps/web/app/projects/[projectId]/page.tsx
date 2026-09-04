import { GitBranch, KeyRound, Network, Settings, Target } from "lucide-react";
import Link from "next/link";

import { Card } from "@/components/card";
import { ProjectShell } from "@/components/project-shell";
import type { Project, Website } from "@/lib/api-types";
import { serverApi } from "@/lib/server-api";

export default async function ProjectDashboard({ params }: { params: Promise<{ projectId: string }> }) {
  const { projectId } = await params;
  const [project, websites] = await Promise.all([
    serverApi<Project>(`/projects/${projectId}`),
    serverApi<{ items: Website[] }>(`/projects/${projectId}/websites`).catch(() => ({ items: [] })),
  ]);

  const activeModules = [
    {
      label: "SEO Strategy",
      href: `/projects/${projectId}/strategy`,
      icon: Target,
      desc: "Business context, target market, product offerings, and immutable versions.",
    },
    {
      label: "Keyword Intelligence",
      href: `/projects/${projectId}/keywords`,
      icon: KeyRound,
      desc: "Keyword universe, deterministic intent, priority scoring, and clustering.",
    },
    {
      label: "Content Architecture",
      href: `/projects/${projectId}/architecture`,
      icon: GitBranch,
      desc: "Pillars, topics, live page mappings, and target opportunity recommendations.",
    },
    {
      label: "Website Crawler",
      href: `/projects/${projectId}/website`,
      icon: Network,
      desc: "Crawled live pages, headings, meta tags, and internal link graph.",
    },
  ];

  return (
    <ProjectShell active="Overview" project={project}>
      <p className="eyebrow">Project overview</p>
      <h1 className="page-title mt-3">{project.name}</h1>
      <p className="mt-4 max-w-3xl text-lg leading-7 text-[var(--muted)]">
        {project.description || "Manage SEO intelligence, keyword clusters, content architecture, and page mappings."}
      </p>

      <div className="mt-8 grid gap-4 lg:grid-cols-[1.2fr_0.8fr]">
        <Card className="p-6">
          <div className="flex items-center justify-between gap-4">
            <div>
              <p className="eyebrow">Website</p>
              <h2 className="mb-0 mt-2 text-xl font-bold">{websites.items[0]?.name ?? "No website connected"}</h2>
            </div>
            <span className="rounded-full bg-[var(--surface-soft)] px-3 py-1 text-xs font-bold capitalize">
              {websites.items[0]?.status ?? "Empty"}
            </span>
          </div>
          <p className="mt-4 break-all text-sm text-[var(--muted)]">
            {websites.items[0]?.base_url ?? "Connect the canonical website that this project will organize."}
          </p>
          <Link className="mt-5 inline-flex text-sm font-bold text-[var(--accent)]" href={`/projects/${project.id}/website`}>
            {websites.items.length ? "Manage website & crawl inventory" : "Add website"} →
          </Link>
        </Card>

        <Card className="p-6">
          <p className="eyebrow">Project status</p>
          <p className="mt-3 text-2xl font-bold capitalize">{project.status}</p>
          <p className="mb-0 mt-4 text-sm leading-6 text-[var(--muted)]">
            Default locale {project.default_locale}
            {project.default_country ? ` · ${project.default_country}` : ""}.
          </p>
          <Link className="mt-5 inline-flex text-sm font-semibold text-slate-600 hover:text-[var(--ink)]" href={`/projects/${project.id}/settings`}>
            Project settings →
          </Link>
        </Card>
      </div>

      <section className="mt-10">
        <div>
          <p className="eyebrow">SEO Intelligence Modules</p>
          <h2 className="mb-0 mt-2 text-2xl font-bold">Phase 3 Architecture Ready</h2>
        </div>
        <div className="mt-5 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {activeModules.map(({ label, href, icon: Icon, desc }) => (
            <Link key={label} href={href} className="group">
              <Card className="p-5 h-full flex flex-col justify-between hover:border-[var(--accent)] hover:shadow-md transition">
                <div>
                  <div className="flex items-center justify-between">
                    <Icon className="text-[var(--accent)]" size={22} />
                    <span className="text-[10px] font-bold uppercase tracking-wider text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded">
                      Active
                    </span>
                  </div>
                  <h3 className="mb-1 mt-4 font-bold text-base text-[var(--ink)] group-hover:text-[var(--accent)] transition">
                    {label}
                  </h3>
                  <p className="m-0 text-xs text-[var(--muted)] leading-relaxed">{desc}</p>
                </div>
                <span className="mt-4 inline-flex items-center text-xs font-bold text-[var(--accent)]">
                  Open module →
                </span>
              </Card>
            </Link>
          ))}
        </div>
      </section>
    </ProjectShell>
  );
}
