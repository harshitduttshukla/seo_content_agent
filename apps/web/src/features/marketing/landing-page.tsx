import {
  ArrowRight,
  BarChart3,
  Blocks,
  Bot,
  Check,
  CircleCheck,
  FileSearch,
  Fingerprint,
  GitBranch,
  Layers3,
  Link2,
  LockKeyhole,
  Orbit,
  ShieldCheck,
  Sparkles,
  Target,
} from "lucide-react";
import Link from "next/link";

import styles from "./landing-page.module.css";

type LandingPageProps = {
  workspaceHref: string;
  workspaceLabel: string;
};

const capabilities = [
  {
    icon: Target,
    label: "Strategy",
    title: "Turn business context into a usable content strategy.",
    description:
      "Capture positioning, audiences, goals, and constraints as structured, versioned decisions your entire workflow can use.",
    tone: "violet",
  },
  {
    icon: FileSearch,
    label: "Keyword intelligence",
    title: "Find demand patterns—not just keyword lists.",
    description:
      "Review intent, clusters, provenance, and conflicts together so every target has a clear strategic reason to exist.",
    tone: "blue",
  },
  {
    icon: GitBranch,
    label: "Content architecture",
    title: "Design the system before filling the calendar.",
    description:
      "Build the relationship between pillars, topics, clusters, and pages in visual and accessible views backed by the same source of truth.",
    tone: "mint",
  },
  {
    icon: ShieldCheck,
    label: "Governed AI",
    title: "Keep people in charge of every consequential change.",
    description:
      "AI works through typed, authorized tools and proposes reviewable patches. Publishing and rule changes always require fresh approval.",
    tone: "amber",
  },
];

const workflow = [
  {
    step: "01",
    title: "Model the business",
    description: "Give the system durable context: positioning, audiences, websites, goals, and guardrails.",
  },
  {
    step: "02",
    title: "Map the opportunity",
    description: "Turn research into reviewed intent, clusters, target assignments, and a coherent content architecture.",
  },
  {
    step: "03",
    title: "Create with evidence",
    description: "Build briefs and structured content against exact strategy, source, SEO, and linking rules.",
  },
  {
    step: "04",
    title: "Review, learn, improve",
    description: "Measure outcomes, review proposals, and promote only approved learning back into the system.",
  },
];

function ProductPreview() {
  return (
    <div className={styles.previewFrame} aria-label="Illustration of the content operating system workspace">
      <div className={styles.previewTopbar}>
        <div className="flex items-center gap-2">
          <span className={styles.previewMark}>
            <Orbit aria-hidden size={14} />
          </span>
          <span className="text-[11px] font-bold tracking-[-0.01em] text-white">Content Intelligence</span>
        </div>
        <div className="flex items-center gap-2" aria-hidden>
          <span className={styles.previewSearch}>Search workspace</span>
          <span className={styles.previewAvatar}>HS</span>
        </div>
      </div>

      <div className={styles.previewBody}>
        <aside className={styles.previewSidebar} aria-hidden>
          <div className={styles.sidebarPill} />
          {[Blocks, Target, FileSearch, GitBranch, BarChart3].map((Icon, index) => (
            <span className={index === 3 ? styles.sidebarIconActive : styles.sidebarIcon} key={index}>
              <Icon size={13} />
            </span>
          ))}
        </aside>

        <div className={styles.previewCanvas}>
          <div className="flex items-start justify-between gap-4">
            <div>
              <p className={styles.previewEyebrow}>Content architecture</p>
              <p className="mt-1 text-[15px] font-bold tracking-[-0.025em] text-[#171b24]">Organic growth map</p>
            </div>
            <span className={styles.previewStatus}>
              <CircleCheck aria-hidden size={10} /> Synced
            </span>
          </div>

          <div className={styles.mapArea} aria-hidden>
            <svg className={styles.mapLines} viewBox="0 0 540 280" preserveAspectRatio="none">
              <path d="M105 135 C170 135 163 62 230 62" />
              <path d="M105 135 C170 135 163 139 230 139" />
              <path d="M105 135 C170 135 163 216 230 216" />
              <path d="M320 62 C380 62 372 102 425 102" />
              <path d="M320 139 C380 139 372 102 425 102" />
              <path d="M320 139 C380 139 372 186 425 186" />
              <path d="M320 216 C380 216 372 186 425 186" />
            </svg>

            <div className={`${styles.mapNode} ${styles.mapNodeRoot}`}>
              <span className={styles.nodeIcon}><Layers3 size={12} /></span>
              <span><small>Pillar</small>Content operations</span>
            </div>
            <div className={`${styles.mapNode} ${styles.mapNodeOne}`}>
              <span className={styles.nodeDot} />
              <span><small>Topic</small>SEO strategy</span>
            </div>
            <div className={`${styles.mapNode} ${styles.mapNodeTwo}`}>
              <span className={styles.nodeDot} />
              <span><small>Topic</small>Content workflow</span>
            </div>
            <div className={`${styles.mapNode} ${styles.mapNodeThree}`}>
              <span className={styles.nodeDot} />
              <span><small>Topic</small>AI governance</span>
            </div>
            <div className={`${styles.mapNode} ${styles.mapNodeFour}`}>
              <span className={styles.pageNodeIcon}><FileSearch size={11} /></span>
              <span><small>Page</small>Strategy guide</span>
            </div>
            <div className={`${styles.mapNode} ${styles.mapNodeFive}`}>
              <span className={styles.pageNodeIcon}><FileSearch size={11} /></span>
              <span><small>Page</small>AI operations</span>
            </div>
          </div>

          <div className={styles.previewFooter}>
            <span><span className="bg-[#635bff]" /> Pillar</span>
            <span><span className="bg-[#23a982]" /> Topic</span>
            <span><span className="bg-[#4e87e9]" /> Page</span>
            <span className="ml-auto"><Link2 size={10} /> Relationship rules active</span>
          </div>
        </div>
      </div>
    </div>
  );
}

export function LandingPage({ workspaceHref, workspaceLabel }: LandingPageProps) {
  return (
    <div className={styles.landing}>
      <a className={styles.skipLink} href="#main-content">Skip to content</a>

      <header className={styles.header}>
        <div className={styles.container}>
          <nav className="flex h-[76px] items-center justify-between gap-5" aria-label="Primary navigation">
            <Link className={styles.brandLink} href="/">
              <span className={styles.brandMark}><Orbit aria-hidden size={19} /></span>
              <span>Content Intelligence</span>
            </Link>

            <div className="hidden items-center gap-8 text-sm font-medium text-[#aeb8c8] md:flex">
              <a className={styles.navLink} href="#platform">Platform</a>
              <a className={styles.navLink} href="#workflow">Workflow</a>
              <a className={styles.navLink} href="#governance">Governance</a>
            </div>

            <Link className={styles.headerCta} href={workspaceHref}>
              {workspaceLabel} <ArrowRight aria-hidden size={15} />
            </Link>
          </nav>
        </div>
      </header>

      <main id="main-content">
      <section className={styles.hero}>
        <div className={`${styles.container} grid items-center gap-16 pb-20 pt-20 lg:grid-cols-[0.9fr_1.1fr] lg:pb-28 lg:pt-24`}>
          <div className="relative z-10 max-w-2xl">
            <div className={styles.heroEyebrow}>
              <Sparkles aria-hidden size={14} /> The operating system for organic growth
            </div>
            <h1 className={styles.heroTitle}>
              Build content that works as a <span>system.</span>
            </h1>
            <p className={styles.heroCopy}>
              Connect business strategy to keyword intelligence, content architecture, SEO rules, and governed AI workflows—without losing the decisions in between.
            </p>
            <div className="mt-9 flex flex-col gap-3 sm:flex-row">
              <Link className={styles.primaryCta} href={workspaceHref}>
                {workspaceLabel === "Sign in" ? "Enter your workspace" : workspaceLabel}
                <ArrowRight aria-hidden size={18} />
              </Link>
              <a className={styles.secondaryCta} href="#platform">Explore the platform</a>
            </div>
            <ul className="mt-9 flex flex-wrap gap-x-6 gap-y-3 text-sm text-[#aeb8c8]" aria-label="Platform principles">
              {["Structured by design", "Human approved", "Tenant isolated"].map((item) => (
                <li className="inline-flex items-center gap-2" key={item}>
                  <span className={styles.checkIcon}><Check aria-hidden size={11} /></span>{item}
                </li>
              ))}
            </ul>
          </div>

          <div className={styles.previewWrap}>
            <div className={styles.previewGlow} aria-hidden />
            <ProductPreview />
            <div className={styles.floatingCard} aria-hidden>
              <span className={styles.floatingIcon}><ShieldCheck size={15} /></span>
              <span><small>Governance check</small>All actions authorized</span>
              <CircleCheck className="ml-auto text-[#57d4aa]" size={17} />
            </div>
          </div>
        </div>

        <div className={`${styles.container} ${styles.disciplineRow}`} aria-label="Connected disciplines">
          <span>Strategy</span><i /><span>Discovery</span><i /><span>Architecture</span><i />
          <span>Creation</span><i /><span>Governance</span><i /><span>Learning</span>
        </div>
      </section>

      <section className={styles.platformSection} id="platform">
        <div className={styles.container}>
          <div className="max-w-3xl">
            <p className={styles.sectionEyebrow}>One connected workspace</p>
            <h2 className={styles.sectionTitle}>Every content decision stays connected.</h2>
            <p className={styles.sectionCopy}>
              Replace scattered docs, keyword exports, and disconnected AI prompts with a structured operating model your team can inspect, govern, and improve.
            </p>
          </div>

          <div className="mt-14 grid gap-5 md:grid-cols-2">
            {capabilities.map(({ icon: Icon, label, title, description, tone }) => (
              <article className={styles.capabilityCard} key={label}>
                <div className={`${styles.capabilityIcon} ${styles[tone]}`}><Icon aria-hidden size={21} /></div>
                <p className={styles.cardLabel}>{label}</p>
                <h3>{title}</h3>
                <p>{description}</p>
                <span className={styles.cardRule} aria-hidden />
              </article>
            ))}
          </div>
        </div>
      </section>

      <section className={styles.workflowSection} id="workflow">
        <div className={`${styles.container} grid gap-14 lg:grid-cols-[0.72fr_1.28fr]`}>
          <div className="lg:sticky lg:top-28 lg:self-start">
            <p className={styles.sectionEyebrow}>A durable workflow</p>
            <h2 className={styles.sectionTitle}>From first principle to measurable page.</h2>
            <p className={styles.sectionCopy}>
              Each step produces structured, versioned context for the next—so your content program gets smarter without becoming less accountable.
            </p>
          </div>

          <ol className={styles.workflowList}>
            {workflow.map((item, index) => (
              <li className={styles.workflowItem} key={item.step}>
                <span className={styles.workflowNumber}>{item.step}</span>
                <div>
                  <h3>{item.title}</h3>
                  <p>{item.description}</p>
                </div>
                <span className={styles.workflowGlyph} aria-hidden>
                  {[Target, GitBranch, Layers3, BarChart3].map((Icon, iconIndex) =>
                    iconIndex === index ? <Icon key={iconIndex} size={20} /> : null,
                  )}
                </span>
              </li>
            ))}
          </ol>
        </div>
      </section>

      <section className={styles.governanceSection} id="governance">
        <div className={`${styles.container} grid items-center gap-14 lg:grid-cols-2`}>
          <div className={styles.governanceVisual}>
            <div className={styles.governanceOrbit} aria-hidden>
              <span className={styles.orbitOne}><Fingerprint size={18} /></span>
              <span className={styles.orbitTwo}><LockKeyhole size={18} /></span>
              <span className={styles.orbitThree}><Bot size={18} /></span>
              <span className={styles.orbitCore}><ShieldCheck size={30} /></span>
            </div>
            <div className={styles.auditCard}>
              <div className="flex items-center justify-between gap-4">
                <span className="text-xs font-bold text-white">Proposal review</span>
                <span className={styles.reviewStatus}>Approval required</span>
              </div>
              <div className="mt-5 grid gap-3">
                {["Exact source context attached", "Permission policy evaluated", "Original and patch preserved"].map((item) => (
                  <div className="flex items-center gap-2 text-[11px] text-[#bac3d1]" key={item}>
                    <CircleCheck aria-hidden className="text-[#57d4aa]" size={13} /> {item}
                  </div>
                ))}
              </div>
            </div>
          </div>

          <div className="max-w-xl">
            <p className={`${styles.sectionEyebrow} !text-[#8f87ff]`}>Governed at the foundation</p>
            <h2 className={`${styles.sectionTitle} !text-white`}>AI that operates inside your rules.</h2>
            <p className={`${styles.sectionCopy} !text-[#aeb8c8]`}>
              Content Intelligence OS treats AI output as a proposal, not a command. Every tool call is typed, scoped, authorized, and auditable before it can affect your work.
            </p>
            <ul className="mt-8 grid gap-4 text-sm text-[#dbe1eb]">
              {[
                "No unrestricted database access",
                "Source-attributed, token-budgeted context",
                "Explicit approval for high-impact actions",
                "Tenant and project scope on every protected operation",
              ].map((item) => (
                <li className="flex items-center gap-3" key={item}>
                  <span className={styles.darkCheck}><Check aria-hidden size={12} /></span>{item}
                </li>
              ))}
            </ul>
          </div>
        </div>
      </section>

      <section className={styles.finalSection}>
        <div className={`${styles.container} ${styles.finalCard}`}>
          <div className="relative z-10 max-w-3xl">
            <p className={styles.sectionEyebrow}>Build with clarity</p>
            <h2 className={styles.finalTitle}>Your content program deserves a source of truth.</h2>
            <p className={styles.finalCopy}>
              Bring strategy, architecture, rules, and human-governed AI into one operational system.
            </p>
            <Link className={styles.primaryCta} href={workspaceHref}>
              {workspaceLabel === "Sign in" ? "Enter your workspace" : workspaceLabel}
              <ArrowRight aria-hidden size={18} />
            </Link>
          </div>
          <Orbit className={styles.finalOrbit} aria-hidden />
        </div>
      </section>
      </main>

      <footer className={styles.footer}>
        <div className={`${styles.container} flex flex-col gap-7 py-10 sm:flex-row sm:items-center sm:justify-between`}>
          <Link className="inline-flex items-center gap-2.5 font-bold tracking-[-0.02em] text-[#1a202b]" href="/">
            <span className={styles.footerMark}><Orbit aria-hidden size={16} /></span>
            Content Intelligence OS
          </Link>
          <p className="text-sm text-[#6d7583]">Structured strategy. Governed intelligence. Better content.</p>
          <div className="flex gap-5 text-sm font-medium text-[#555e6c]">
            <a href="#platform">Platform</a>
            <a href="#workflow">Workflow</a>
            <Link href={workspaceHref}>{workspaceLabel}</Link>
          </div>
        </div>
      </footer>
    </div>
  );
}
