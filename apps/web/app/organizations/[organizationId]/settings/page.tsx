import { Header } from "@/components/header";
import {
  OrganizationMember,
  OrganizationSettings,
} from "@/features/organizations/organization-settings";
import type { Organization, User } from "@/lib/api-types";
import { serverApi } from "@/lib/server-api";

export default async function OrganizationSettingsPage({
  params,
}: {
  params: Promise<{ organizationId: string }>;
}) {
  const { organizationId } = await params;
  const [currentUser, organization, membersResponse] = await Promise.all([
    serverApi<User>("/users/me"),
    serverApi<Organization>(`/organizations/${organizationId}`),
    serverApi<{ items: OrganizationMember[] }>(`/organizations/${organizationId}/members`),
  ]);

  return (
    <div className="min-h-screen bg-[#f7f8fb]">
      <Header
        backHref={`/projects?organization_id=${organizationId}`}
        backLabel="Back to projects"
      />
      <main>
        <OrganizationSettings
          initialMembers={membersResponse.items}
          organization={organization}
        />
      </main>
    </div>
  );
}
