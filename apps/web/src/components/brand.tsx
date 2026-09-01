import { Orbit } from "lucide-react";
import Link from "next/link";

export function Brand() {
  return (
    <Link className="inline-flex items-center gap-2.5 font-bold tracking-[-0.02em]" href="/organizations">
      <span className="grid size-9 place-items-center rounded-[11px] bg-[var(--ink)] text-white">
        <Orbit aria-hidden size={19} />
      </span>
      <span>Content Intelligence OS</span>
    </Link>
  );
}
