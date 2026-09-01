import { AlertCircle, LoaderCircle } from "lucide-react";

import { Card } from "@/components/card";

export function LoadingState({ label = "Loading workspace" }: { label?: string }) {
  return (
    <div className="flex min-h-48 items-center justify-center gap-3 text-sm text-[var(--muted)]">
      <LoaderCircle aria-hidden className="animate-spin" size={18} /> {label}
    </div>
  );
}

export function ErrorState({ message, requestId }: { message: string; requestId?: string }) {
  return (
    <Card className="flex gap-3 border-red-200 bg-red-50 p-4 text-sm text-red-900" role="alert">
      <AlertCircle aria-hidden className="mt-0.5 shrink-0" size={18} />
      <div>
        <p className="m-0 font-semibold">Something needs attention</p>
        <p className="mb-0 mt-1">{message}</p>
        {requestId ? <p className="mb-0 mt-2 font-mono text-xs">Request {requestId}</p> : null}
      </div>
    </Card>
  );
}
