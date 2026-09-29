import {
  Network,
  Sparkles,
} from "lucide-react";
import Link from "next/link";
import type { ComponentType } from "react";

type NavigationItem = {
  label: string;
  href: string;
  icon: ComponentType<{ size?: number; "aria-hidden"?: boolean }>;
};

export function Sidebar({ projectId, active }: { projectId: string; active: string }) {
  const items: NavigationItem[] = [
    { label: "Website", href: `/projects/${projectId}/website`, icon: Network },
    { label: "Content Harness", href: `/projects/${projectId}/content-harness`, icon: Sparkles }
  ];
  return (
    <aside
      className="sticky top-20 h-[calc(100vh-5rem)] self-start overflow-y-auto border-r border-[var(--border)] bg-[#f0f2f7] p-3 sm:p-5"
      data-testid="project-sidebar"
    >
      <nav aria-label="Project navigation" className="grid gap-1">
        {items.map((item) => {
          const Icon = item.icon;
          const current = item.label === active;
          return (
            <Link
              className={`flex items-center gap-3 rounded-[10px] px-3 py-2.5 text-sm font-semibold transition ${current ? "bg-white text-[var(--accent)] shadow-sm" : "text-[var(--muted)] hover:bg-white/70 hover:text-[var(--ink)]"
                }`}
              href={item.href}
              key={item.label}
            >
              <Icon aria-hidden size={17} /> <span className="desktop-only">{item.label}</span>
            </Link>
          );
        })}
      </nav>
    </aside>
  );
}
