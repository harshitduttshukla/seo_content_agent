import { permanentRedirect } from "next/navigation";

/** Project settings moved to the V3 shell; old bookmarks (and their query) keep working. */
export default async function ProjectSettingsPage({
  params,
  searchParams,
}: {
  params: Promise<{ projectId: string }>;
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const [{ projectId }, query] = await Promise.all([params, searchParams]);
  const kept = new URLSearchParams();
  for (const key of ["gsc", "gsc_error"]) {
    const value = query[key];
    if (typeof value === "string") kept.set(key, value);
  }
  const suffix = kept.size ? `?${kept.toString()}` : "";
  permanentRedirect(`/projects/${encodeURIComponent(projectId)}/v3/settings${suffix}`);
}
