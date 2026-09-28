import { ArrowRight } from "lucide-react";
import Link from "next/link";

type LandingPageProps = {
  workspaceHref: string;
  workspaceLabel: string;
};

const primaryCta =
  "inline-flex items-center gap-[8px] rounded-[5px] border border-[#15706A] bg-[#15706A] px-[16px] py-[9px] text-[14px] font-medium text-white! hover:bg-[#115C57] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#15706A]";
const secondaryCta =
  "inline-flex items-center rounded-[5px] border border-[#D6DBD9] bg-white px-[16px] py-[9px] text-[14px] text-[#12171A] hover:border-[#15706A] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#15706A]";

const modules = [
  {
    name: "Strategy",
    title: "Decide what the brand may say.",
    body: "Write your positioning as claims on one canvas and approve them. Keyword and prompt demand is grouped into areas under it.",
  },
  {
    name: "Content Hub",
    title: "Plan pages from real demand.",
    body: "Kept demand becomes content cards on one board. Lock the plan, and every later addition stays visible.",
  },
  {
    name: "Production",
    title: "Draft against approved claims only.",
    body: "Each card gets a context bundle, an outline, a draft and a QA run. Two human gates decide what moves on.",
  },
  {
    name: "Iteration Lab",
    title: "See how pages perform.",
    body: "Google Search Console data is read into the same workspace, next to the pages it measures.",
  },
];

// The Content Hub's own columns: grey rests, teal means the system is working, coral means a person decides.
const columns: Array<{ name: string; tone: "rest" | "sys" | "human"; cards: string[] }> = [
  { name: "Planned", tone: "rest", cards: ["eu vat rates 2026"] },
  { name: "Outline", tone: "sys", cards: ["hs code lookup"] },
  { name: "Draft", tone: "sys", cards: ["ddp vs dap"] },
  { name: "Review", tone: "human", cards: ["who pays eu duties"] },
  { name: "Approved", tone: "rest", cards: ["landed cost guide"] },
];

const toneHead = {
  rest: "bg-[#F0F2F1] text-[#5C666C]",
  sys: "bg-[#E1EFED] text-[#15706A]",
  human: "bg-[#FBEBE8] text-[#B9463A]",
};

const steps = [
  { name: "Context bundle", note: "Approved claims, brand rules, demand and linkable pages", gate: false },
  { name: "Outline", note: "AI proposes; a writer can edit or start blank", gate: false },
  { name: "G1 · outline review", note: "A person approves the plan of the page", gate: true },
  { name: "Draft", note: "Written from the approved outline, claims cited inline", gate: false },
  { name: "QA and repair", note: "Claims, links, banned words and length checked", gate: false },
  { name: "G2 · draft review", note: "A person approves the finished text", gate: true },
];

function BoardPreview() {
  return (
    <div
      aria-label="Example Content Hub board"
      role="img"
      className="overflow-hidden rounded-[8px] border border-[#D6DBD9] bg-[#FAFBFA]"
    >
      <div className="flex items-center gap-[8px] border-b border-[#E7EAE9] px-[14px] py-[10px]">
        <span aria-hidden className="h-[8px] w-[8px] rounded-full bg-[#15706A]" />
        <span className="font-serif text-[14px]">Content Hub</span>
        <span className="ml-auto rounded-full border border-[#DDE2E0] bg-[#F0F2F1] px-[8px] py-[1px] text-[11px] text-[#6F787D]">
          plan locked
        </span>
      </div>
      <div className="grid grid-cols-5 gap-[6px] p-[10px]">
        {columns.map((column) => (
          <div key={column.name} className="min-w-0 rounded-[6px] border border-[#D6DBD9] bg-[#F5F7F6]">
            <div className={`truncate rounded-t-[6px] border-b border-[#D6DBD9] px-[7px] py-[5px] text-[11px] font-medium ${toneHead[column.tone]}`}>
              {column.name}
            </div>
            <div className="grid gap-[5px] p-[5px]">
              {column.cards.map((card) => (
                <div key={card} className="rounded-[4px] border border-[#D6DBD9] bg-white px-[6px] py-[5px] text-[10.5px] leading-[1.3] text-[#12171A]">
                  {card}
                  <div className="mt-[3px] text-[9.5px] text-[#8A949A]">pillar</div>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

export function LandingPage({ workspaceHref, workspaceLabel }: LandingPageProps) {
  const ctaLabel = workspaceLabel === "Sign in" ? "Enter your workspace" : workspaceLabel;
  return (
    <div className="min-h-screen bg-[#ECEEED] text-[15px] text-[#12171A] antialiased">
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:absolute focus:left-[16px] focus:top-[12px] focus:z-50 focus:rounded-[5px] focus:bg-white focus:px-[12px] focus:py-[6px]"
      >
        Skip to content
      </a>

      <header className="border-b border-[#D6DBD9] bg-[#FAFBFA]">
        <nav aria-label="Primary navigation" className="mx-auto flex h-[58px] max-w-[1120px] items-center gap-[24px] px-[20px] sm:px-[28px]">
          <Link href="/" className="flex items-center gap-[8px]">
            <span aria-hidden className="h-[9px] w-[9px] rounded-full bg-[#15706A]" />
            <span className="font-serif text-[17px] font-medium">Strategy Graph</span>
          </Link>
          <div className="hidden items-center gap-[20px] text-[13.5px] text-[#5C666C] md:flex">
            <a href="#modules" className="hover:text-[#12171A]">Modules</a>
            <a href="#workflow" className="hover:text-[#12171A]">Workflow</a>
            <a href="#claims" className="hover:text-[#12171A]">Claims</a>
          </div>
          <Link href={workspaceHref} className="ml-auto inline-flex items-center gap-[6px] text-[13.5px] font-medium text-[#15706A]! hover:text-[#115C57]!">
            {workspaceLabel} <ArrowRight aria-hidden size={15} />
          </Link>
        </nav>
      </header>

      <main id="main-content">
        <section className="mx-auto grid max-w-[1120px] items-center gap-[40px] px-[20px] pb-[56px] pt-[56px] sm:px-[28px] lg:grid-cols-[0.95fr_1.05fr]">
          <div className="grid gap-[16px]">
            <span className="text-[11.5px] font-medium uppercase tracking-[0.08em] text-[#15706A]">SEO and AI-search content</span>
            <h1 className="m-0 font-serif text-[clamp(32px,5vw,46px)] font-medium leading-[1.08] tracking-tight [text-wrap:balance]">
              Every sentence traces to a claim you approved.
            </h1>
            <p className="m-0 max-w-[54ch] text-[16px] leading-[1.6] text-[#5C666C]">
              Plan pages from real search demand, draft them only from positioning your team signed off, and let people decide at two review gates.
            </p>
            <div className="mt-[6px] flex flex-wrap gap-[10px]">
              <Link href={workspaceHref} className={primaryCta}>
                {ctaLabel} <ArrowRight aria-hidden size={16} />
              </Link>
              <a href="#workflow" className={secondaryCta}>See how an article is made</a>
            </div>
          </div>
          <BoardPreview />
        </section>

        <section id="modules" className="border-t border-[#D6DBD9] bg-[#F5F7F6]">
          <div className="mx-auto max-w-[1120px] px-[20px] py-[56px] sm:px-[28px]">
            <h2 className="m-0 max-w-[26ch] font-serif text-[28px] font-medium leading-tight [text-wrap:balance]">
              One card travels from strategy to a live page.
            </h2>
            <p className="m-[10px_0_28px] max-w-[62ch] text-[15px] leading-[1.6] text-[#5C666C]">
              A content card is planned in Strategy, scheduled in the Content Hub, written in Production and measured in the Iteration Lab.
            </p>
            <div className="grid gap-[10px] sm:grid-cols-2 lg:grid-cols-4">
              {modules.map((module) => (
                <article key={module.name} className="grid content-start gap-[6px] rounded-[8px] border border-[#D6DBD9] bg-white p-[16px_18px]">
                  <span className="text-[11.5px] font-medium uppercase tracking-[0.08em] text-[#15706A]">{module.name}</span>
                  <h3 className="m-0 font-serif text-[18px] font-medium leading-snug">{module.title}</h3>
                  <p className="m-0 text-[13.5px] leading-[1.55] text-[#5C666C]">{module.body}</p>
                </article>
              ))}
            </div>
          </div>
        </section>

        <section id="workflow" className="border-t border-[#D6DBD9]">
          <div className="mx-auto grid max-w-[1120px] gap-[32px] px-[20px] py-[56px] sm:px-[28px] lg:grid-cols-[0.8fr_1.2fr]">
            <div>
              <h2 className="m-0 font-serif text-[28px] font-medium leading-tight [text-wrap:balance]">How an article is made</h2>
              <p className="m-[10px_0_0] max-w-[44ch] text-[15px] leading-[1.6] text-[#5C666C]">
                The AI does the drafting and checking. People approve the outline and the final text, and every decision is recorded.
              </p>
            </div>
            <ol className="m-0 grid list-none gap-[8px] p-0">
              {steps.map((step, index) => (
                <li
                  key={step.name}
                  className={`grid grid-cols-[34px_1fr] items-baseline gap-[10px] rounded-[8px] border bg-white p-[12px_16px] ${step.gate ? "border-[#F0D2CC]" : "border-[#E7EAE9]"}`}
                >
                  <span className={`font-mono text-[13px] tabular-nums ${step.gate ? "text-[#B9463A]" : "text-[#15706A]"}`}>
                    {String(index + 1).padStart(2, "0")}
                  </span>
                  <div>
                    <h3 className="m-0 text-[14.5px] font-medium">{step.name}</h3>
                    <p className="m-[2px_0_0] text-[13.5px] text-[#5C666C]">{step.note}</p>
                  </div>
                </li>
              ))}
            </ol>
          </div>
        </section>

        <section id="claims" className="border-t border-[#D6DBD9] bg-[#F5F7F6]">
          <div className="mx-auto grid max-w-[1120px] items-center gap-[32px] px-[20px] py-[56px] sm:px-[28px] lg:grid-cols-2">
            <div>
              <h2 className="m-0 font-serif text-[28px] font-medium leading-tight [text-wrap:balance]">
                The AI cites claims. It never invents them.
              </h2>
              <p className="m-[10px_0_0] max-w-[50ch] text-[15px] leading-[1.6] text-[#5C666C]">
                When a draft needs a fact about your company that nobody approved, it leaves a marker instead of making one up. QA will not pass until a person resolves it.
              </p>
            </div>
            <figure className="m-0 rounded-[8px] border border-[#D6DBD9] bg-white p-[18px_20px]">
              <p className="m-0 text-[14.5px] leading-[1.75]">
                We file IOSS returns for every EU order{" "}
                <span className="rounded-[4px] border border-[#C4DEDA] bg-[#E1EFED] px-[5px] font-mono text-[12px] text-[#15706A]">CLM-012</span>
                , so buyers never pay duty on delivery.{" "}
                <span className="rounded-[4px] border border-[#F0D2CC] bg-[#FBEBE8] px-[5px] font-mono text-[12px] text-[#B9463A]">NEEDS-CLAIM: same-day customs clearance</span>
              </p>
              <figcaption className="mt-[12px] border-t border-[#E7EAE9] pt-[10px] text-[12.5px] text-[#8A949A]">
                Teal: backed by approved claim 12, version 2. Coral: blocks QA until someone approves or removes it.
              </figcaption>
            </figure>
          </div>
        </section>

        <section className="border-t border-[#D6DBD9]">
          <div className="mx-auto flex max-w-[1120px] flex-wrap items-center justify-between gap-[16px] px-[20px] py-[48px] sm:px-[28px]">
            <h2 className="m-0 max-w-[30ch] font-serif text-[26px] font-medium leading-tight [text-wrap:balance]">
              Start from your positioning, not a blank prompt.
            </h2>
            <Link href={workspaceHref} className={primaryCta}>
              {ctaLabel} <ArrowRight aria-hidden size={16} />
            </Link>
          </div>
        </section>
      </main>

      <footer className="border-t border-[#D6DBD9] bg-[#FAFBFA]">
        <div className="mx-auto flex max-w-[1120px] flex-wrap items-center gap-x-[24px] gap-y-[10px] px-[20px] py-[22px] text-[13px] text-[#5C666C] sm:px-[28px]">
          <span className="flex items-center gap-[8px] text-[#12171A]">
            <span aria-hidden className="h-[8px] w-[8px] rounded-full bg-[#15706A]" />
            <span className="font-serif text-[15px]">Strategy Graph</span>
          </span>
          <span>Approved claims in. Reviewed pages out.</span>
          <span className="ml-auto flex gap-[16px]">
            <a href="#modules" className="hover:text-[#12171A]">Modules</a>
            <a href="#workflow" className="hover:text-[#12171A]">Workflow</a>
            <Link href={workspaceHref} className="hover:text-[#12171A]">{workspaceLabel}</Link>
          </span>
        </div>
      </footer>
    </div>
  );
}
