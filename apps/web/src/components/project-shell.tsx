import type { Project } from "@/lib/api-types";

import { Header } from "@/components/header";
import { Sidebar } from "@/components/sidebar";

export function ProjectShell({ project, active, children }: { project: Project; active: string; children: React.ReactNode }) {
  return (
    <main className="min-h-screen">
      <Header backHref={`/projects?organization_id=${project.organization_id}`} backLabel="All projects" />
      <div className="grid min-h-[calc(100vh-5rem)] grid-cols-[4.25rem_minmax(0,1fr)] sm:grid-cols-[15.5rem_minmax(0,1fr)]">
        <Sidebar active={active} projectId={project.id} />
        <section className="min-w-0 p-5 sm:p-8 lg:p-10">{children}</section>
      </div>
    </main>
  );
}
