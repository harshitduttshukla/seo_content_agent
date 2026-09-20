import {
  FileText,
  GitBranch,
  KeyRound,
  Link2,
  Network,
  Settings,
  Target,
  Layers,
} from "lucide-react";
import Link from "next/link";

import { Card } from "@/components/card";
import { ProjectShell } from "@/components/project-shell";
import type { Project, Website } from "@/lib/api-types";
import { serverApi } from "@/lib/server-api";

export default async function ProjectDashboard({
  params,
}: {
  params: Promise<{ projectId: string }>;
}) {
  const { projectId } = await params;
  const [project, websites] = await Promise.all([
    serverApi<Project>(`/projects/${projectId}`),
    serverApi<{ items: Website[] }>(`/projects/${projectId}/websites`).catch(() => ({ items: [] })),
  ]);

  const activeModules = [
    {
      label: "Visual Content Map",
      href: `/projects/${projectId}/content-map`,
      icon: Layers,
      tag: "Phase 4",
      desc: "Interactive visual content graph projecting Pillars, Topics, Clusters, and Pages with validation.",
    },
    {
      label: "Planned Content Pages",
      href: `/projects/${projectId}/content`,
      icon: FileText,
      tag: "Phase 4",
      desc: "Planned content inventory, keyword assignments, live page optimization, and opportunity conversion.",
    },
    {
      label: "Internal Linking",
      href: `/projects/${projectId}/internal-linking`,
      icon: Link2,
      tag: "Phase 4",
      desc: "Governed link opportunities pipeline, parent-child relationships, and orphan pages detection.",
    },
    {
      label: "SEO Strategy",
      href: `/projects/${projectId}/strategy`,
      icon: Target,
      tag: "Phase 3",
      desc: "Business context, target market, product offerings, and immutable versions.",
    },
    {
      label: "Keyword Intelligence",
      href: `/projects/${projectId}/keywords`,
      icon: KeyRound,
      tag: "Phase 3",
      desc: "Keyword universe, deterministic intent, priority scoring, and clustering.",
    },
    {
      label: "Content Architecture",
      href: `/projects/${projectId}/architecture`,
      icon: GitBranch,
      tag: "Phase 3",
      desc: "Pillars, topics, live page mappings, and target opportunity recommendations.",
    },
    {
      label: "Website Crawler",
      href: `/projects/${projectId}/website`,
      icon: Network,
      tag: "Phase 2",
      desc: "Crawled live pages, headings, meta tags, and internal link graph.",
    },
  ];

  return (
    <ProjectShell active="Overview" project={project}>
      <p className="eyebrow">Project overview</p>
      <h1 className="page-title mt-3">{project.name}</h1>
      <p className="mt-4 max-w-3xl text-lg leading-7 text-[var(--muted)]">
        {project.description ||
          "Manage SEO intelligence, keyword clusters, content architecture, visual content maps, and internal linking."}
      </p>

      <div className="mt-8 grid gap-4 lg:grid-cols-[1.2fr_0.8fr]">
        <Card className="p-6">
          <div className="flex items-center justify-between gap-4">
            <div>
              <p className="eyebrow">Website</p>
              <h2 className="mb-0 mt-2 text-xl font-bold">
                {websites.items[0]?.name ?? "No website connected"}
              </h2>
            </div>
            <span className="rounded-full bg-[var(--surface-soft)] px-3 py-1 text-xs font-bold capitalize">
              {websites.items[0]?.status ?? "Empty"}
            </span>
          </div>
          <p className="mt-4 break-all text-sm text-[var(--muted)]">
            {websites.items[0]?.base_url ?? "Connect the canonical website that this project will organize."}
          </p>
          <Link
            className="mt-5 inline-flex text-sm font-bold text-[var(--accent)]"
            href={`/projects/${project.id}/website`}
          >
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
          <Link
            className="mt-5 inline-flex text-sm font-semibold text-slate-600 hover:text-[var(--ink)]"
            href={`/projects/${project.id}/settings`}
          >
            Project settings →
          </Link>
        </Card>
      </div>

      <section className="mt-10">
        <div>
          <p className="eyebrow">SEO Intelligence & Content OS</p>
          <h2 className="mb-0 mt-2 text-2xl font-bold">Content Operating System Modules</h2>
        </div>
        <div className="mt-5 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <Link href={`/projects/${projectId}/v3/canvas`} className="group sm:col-span-2 lg:col-span-3">
            <Card className="p-5 flex flex-col hover:border-[var(--accent)] hover:shadow-md transition bg-gradient-to-r from-indigo-50 to-blue-50 border-indigo-200">
              <div className="flex items-center justify-between">
                <Target className="text-indigo-600" size={22} />
                <span className="text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded text-indigo-700 bg-indigo-100 border border-indigo-300">
                  V3 Preview
                </span>
              </div>
              <h3 className="mb-1 mt-4 font-bold text-base text-indigo-900 group-hover:text-indigo-700 transition">
                V3 Strategy & Workspace (Preview)
              </h3>
              <p className="m-0 text-sm text-indigo-800/80 leading-relaxed max-w-3xl">
                The next-generation Content OS. Includes the new Strategy Canvas, Demand graph, and Site Import pipeline. Completely isolated from the legacy application.
              </p>
              <span className="mt-4 inline-flex items-center text-xs font-bold text-indigo-700">
                Enter V3 Preview →
              </span>
            </Card>
          </Link>
          {activeModules.map(({ label, href, icon: Icon, desc, tag }) => (
            <Link key={label} href={href} className="group">
              <Card className="p-5 h-full flex flex-col justify-between hover:border-[var(--accent)] hover:shadow-md transition">
                <div>
                  <div className="flex items-center justify-between">
                    <Icon className="text-[var(--accent)]" size={22} />
                    <span
                      className={`text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded ${
                        tag === "Phase 4"
                          ? "text-purple-700 bg-purple-50 border border-purple-200"
                          : "text-emerald-700 bg-emerald-50"
                      }`}
                    >
                      {tag}
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
