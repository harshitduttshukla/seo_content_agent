import { V3PageHeading, V3TopBar } from "@/components/v3/v3-top-bar";
import { OrganizationWorkspace } from "@/features/organizations/organization-workspace";
import type { Organization } from "@/lib/api-types";
import { serverApi } from "@/lib/server-api";

export default async function OrganizationsPage() {
  const result = await serverApi<{ items: Organization[] }>("/organizations");
  return (
    <div className="min-h-screen bg-[#ECEEED] text-[14px] text-[#12171A] antialiased">
      <V3TopBar />
      <main className="mx-auto max-w-[1120px] px-[20px] pb-[70px] pt-[32px] sm:px-[28px]">
        <V3PageHeading
          eyebrow="Workspace"
          title="Choose an organization"
          lead="Each organization is kept separate. Open one to see its projects, or create a new one."
        />
        <OrganizationWorkspace initialItems={result.items} />
      </main>
    </div>
  );
}
