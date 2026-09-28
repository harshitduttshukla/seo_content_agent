import { ChevronLeft, LogOut } from "lucide-react";
import Link from "next/link";

/** The V3 header for pages outside a project: the Strategy Graph mark, an optional way back, sign out. */
export function V3TopBar({ backHref, backLabel }: { backHref?: string; backLabel?: string }) {
  return (
    <header className="sticky top-0 z-40 border-b border-[#D6DBD9] bg-[#FAFBFA]">
      <div className="mx-auto flex h-[56px] max-w-[1120px] items-center gap-[18px] px-[20px] sm:px-[28px]">
        <Link href="/organizations" className="flex items-center gap-[8px] text-[#12171A]">
          <span aria-hidden className="h-[9px] w-[9px] rounded-full bg-[#15706A]" />
          <span className="font-serif text-[17px] font-medium">Strategy Graph</span>
        </Link>
        {backHref ? (
          <Link
            href={backHref}
            className="hidden items-center gap-[3px] text-[13px] text-[#5C666C] hover:text-[#12171A] sm:inline-flex"
          >
            <ChevronLeft aria-hidden size={15} /> {backLabel}
          </Link>
        ) : null}
        <form action="/api/auth/logout" method="post" className="ml-auto">
          <button
            type="submit"
            className="inline-flex items-center gap-[6px] rounded-[5px] px-[8px] py-[5px] text-[13px] text-[#5C666C] hover:bg-[#F0F2F1] hover:text-[#12171A] focus-visible:outline-2 focus-visible:outline-[#15706A]"
          >
            <LogOut aria-hidden size={15} /> <span className="hidden sm:inline">Sign out</span>
          </button>
        </form>
      </div>
    </header>
  );
}

/** Shared V3 form and card classes for the workspace pages. */
export const v3 = {
  card: "rounded-[8px] border border-[#D6DBD9] bg-white",
  cardLink:
    "group block rounded-[8px] border border-[#D6DBD9] bg-white p-[16px_18px] transition-colors hover:border-[#15706A] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#15706A]",
  label: "grid gap-[5px] text-[12.6px] font-medium text-[#12171A]",
  field:
    "w-full rounded-[5px] border border-[#D6DBD9] bg-white px-[10px] py-[7px] text-[13.3px] font-normal text-[#12171A] placeholder:text-[#8A949A] focus-visible:outline-2 focus-visible:outline-[#15706A]",
  primary:
    "rounded-[5px] border border-[#15706A] bg-[#15706A] px-[12px] py-[7px] text-[13px] font-medium text-white hover:bg-[#115C57] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#15706A] disabled:cursor-not-allowed disabled:opacity-50",
};

export function V3PageHeading({ eyebrow, title, lead }: { eyebrow: string; title: string; lead: string }) {
  return (
    <div className="mb-[22px] grid gap-[6px]">
      <span className="text-[11.5px] font-medium uppercase tracking-[0.08em] text-[#15706A]">{eyebrow}</span>
      <h1 className="m-0 font-serif text-[30px] font-medium leading-tight tracking-tight text-[#12171A] [text-wrap:balance]">
        {title}
      </h1>
      <p className="m-0 max-w-[62ch] text-[14px] leading-[1.55] text-[#5C666C]">{lead}</p>
    </div>
  );
}
