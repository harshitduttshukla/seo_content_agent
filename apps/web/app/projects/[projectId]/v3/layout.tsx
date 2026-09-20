import { ReactNode, use } from "react";
import { V3Shell } from "@/components/v3/v3-shell";

export default function V3Layout({
  children,
  params,
}: {
  children: ReactNode;
  params: Promise<{ projectId: string }>;
}) {
  const { projectId } = use(params);
  return <V3Shell projectId={projectId}>{children}</V3Shell>;
}
