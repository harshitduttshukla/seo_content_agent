import { ChevronLeft, LogOut } from "lucide-react";
import Link from "next/link";

import { Brand } from "@/components/brand";

export function Header({ backHref, backLabel }: { backHref?: string; backLabel?: string }) {
  return (
    <header className="sticky top-0 z-50 flex h-20 items-center justify-between border-b border-[var(--border)] bg-[var(--canvas)] px-5 sm:px-8">
      <div className="flex items-center gap-5">
        <Brand />
        {backHref ? (
          <Link className="desktop-only inline-flex items-center gap-1 text-sm font-semibold text-[var(--muted)] hover:text-[var(--ink)]" href={backHref}>
            <ChevronLeft aria-hidden size={16} /> {backLabel}
          </Link>
        ) : null}
      </div>
      <form action="/api/auth/logout" method="post">
        <button className="inline-flex items-center gap-2 text-sm font-semibold text-[var(--muted)] hover:text-[var(--ink)]" type="submit">
          <LogOut aria-hidden size={16} /> <span className="desktop-only">Sign out</span>
        </button>
      </form>
    </header>
  );
}
