import { redirect } from "next/navigation";

export default async function ProjectEntryPage({
  params,
}: {
  params: Promise<{ projectId: string }>;
}) {
  const { projectId } = await params;
  redirect(`/projects/${projectId}/v3/canvas`);
}
