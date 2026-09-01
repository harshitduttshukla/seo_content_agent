import { CheckCircle2, XCircle } from "lucide-react";

export function Toast({ message, tone = "success" }: { message: string; tone?: "success" | "error" }) {
  return (
    <div className="fixed bottom-5 right-5 z-50 flex max-w-sm items-center gap-3 rounded-xl border border-[var(--border)] bg-white px-4 py-3 text-sm font-semibold shadow-[var(--shadow)]" role="status">
      {tone === "success" ? <CheckCircle2 aria-hidden className="text-[var(--mint)]" size={18} /> : <XCircle aria-hidden className="text-[var(--danger)]" size={18} />}
      {message}
    </div>
  );
}
