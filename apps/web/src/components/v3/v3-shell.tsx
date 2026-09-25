"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

export function V3Shell({ projectId, children }: { projectId: string; children: React.ReactNode }) {
  const pathname = usePathname();

  const navItems = [
    { name: "Strategy", path: `/projects/${projectId}/v3/canvas` },
    { name: "Content Hub", path: `/projects/${projectId}/v3/content-hub` },
    { name: "Iteration Lab", path: `/projects/${projectId}/content-harness` },
    { name: "Technical SEO", path: `/projects/${projectId}/website` },
  ];

  return (
    <div className="flex min-h-screen bg-[#ECEEED] text-[#12171A] font-sans antialiased text-[14px]">
      <aside className="w-[238px] flex-none bg-[#FAFBFA] border-r border-[#D6DBD9] sticky top-0 h-screen overflow-y-auto">
        <div className="px-[17px] pt-[17px] pb-[13px] border-b border-[#E7EAE9]">
          <div className="flex items-center gap-[8px]">
            <span className="w-[9px] h-[9px] rounded-full bg-[#15706A]"></span>
            <h2 className="font-serif font-medium text-[17px] m-0">Strategy Graph</h2>
          </div>
        </div>

        <nav className="p-[10px_9px_30px]">
          <div className="mt-[13px]">
            <span className="block px-[8px] pb-[5px] text-[11px] text-[#8A949A]">Modules</span>
            {navItems.map((item) => (
              <Link
                key={item.path}
                href={item.path}
                className={`flex items-center gap-[9px] w-full text-left p-[7px_8px] rounded-[5px] text-[13.3px] mb-1 hover:bg-[#F0F2F1] hover:text-[#12171A] ${pathname.startsWith(item.path)
                  ? "bg-[#E5EAE8] text-[#12171A] font-medium"
                  : "text-[#5C666C]"
                  }`}
              >
                {item.name}
              </Link>
            ))}
          </div>
        </nav>
      </aside>

      <main className="flex-1 min-w-0 p-[24px_28px_70px] max-w-[1280px]">
        {children}
      </main>
    </div>
  );
}
