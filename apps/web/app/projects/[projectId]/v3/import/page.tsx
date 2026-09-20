import { SiteImportTab } from "@/components/v3/workspace/site-import-tab";
import type { Project } from "@/lib/api-types";
import { serverApi } from "@/lib/server-api";

export default async function SiteImportPage({
  params,
}: {
  params: Promise<{ projectId: string }>;
}) {
  const { projectId } = await params;
  const project = await serverApi<Project>(`/projects/${projectId}`);
  return (
    <section className="animate-in fade-in duration-150">
      <div className="mb-[18px] flex flex-wrap items-start gap-[16px]">
        <div className="min-w-[280px] flex-1">
          <div className="mb-[6px] text-[11.5px] text-[#8A949A]">Workspace · config</div>
          <h1 className="m-0 font-serif text-[25px] font-medium tracking-tight text-[#12171A]">Site Import</h1>
          <p className="m-[5px_0_0] max-w-[74ch] text-[13.4px] text-[#5C666C]">
            Import canonical URLs into tenant-scoped Content Cards and inspect each governed run.
          </p>
        </div>
      </div>
      <SiteImportTab scope={{ organizationId: project.organization_id, projectId: project.id }} />
    </section>
  );
}
