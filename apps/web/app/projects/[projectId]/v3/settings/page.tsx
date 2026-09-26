import { ProjectSettingsV3 } from "@/components/v3/settings/project-settings";
import type { Project } from "@/lib/api-types";
import { serverApi } from "@/lib/server-api";

export default async function SettingsPage({
  params,
  searchParams,
}: {
  params: Promise<{ projectId: string }>;
  searchParams: Promise<{ gsc?: string; gsc_error?: string }>;
}) {
  const [{ projectId }, query] = await Promise.all([params, searchParams]);
  const project = await serverApi<Project>(`/projects/${projectId}`);
  // Set by the Google OAuth callback route after the consent screen.
  const gscNotice =
    query.gsc === "connected" ? { ok: true, code: "connected" } : query.gsc_error ? { ok: false, code: query.gsc_error } : undefined;
  return <ProjectSettingsV3 project={project} gscNotice={gscNotice} />;
}
