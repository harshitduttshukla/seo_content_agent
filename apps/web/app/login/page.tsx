import { ArrowRight, CheckCircle2, LockKeyhole, UserCheck } from "lucide-react";

import { Brand } from "@/components/brand";
import { Card } from "@/components/card";
import { isLocalAuthEnabled } from "@/lib/local-auth";

export default async function LoginPage({
  searchParams,
}: {
  searchParams: Promise<{ error?: string }>;
}) {
  const { error } = await searchParams;
  const localAuthEnabled = isLocalAuthEnabled();

  return (
    <main className="grid min-h-screen grid-cols-1 lg:grid-cols-[1.15fr_0.85fr]">
      <section className="flex min-h-[48vh] flex-col justify-between bg-[#151a27] p-7 text-white sm:p-12 lg:p-16">
        <Brand />
        <div className="max-w-2xl py-14">
          <p className="eyebrow !text-[#8f87ff]">Governed content operations</p>
          <h1 className="mt-5 font-serif text-5xl leading-[0.98] tracking-[-0.04em] sm:text-7xl">
            Turn context into a content system.
          </h1>
          <p className="mt-7 max-w-xl text-lg leading-8 text-[#abb4c7]">
            One secure workspace for strategy, websites, content intelligence, and the AI workflows that follow.
          </p>
        </div>
        <div className="flex flex-wrap gap-x-8 gap-y-3 text-sm text-[#cbd2df]">
          {["Tenant isolated", "Human governed", "API first"].map((item) => (
            <span className="inline-flex items-center gap-2" key={item}>
              <CheckCircle2 aria-hidden className="text-[#49d5a6]" size={16} /> {item}
            </span>
          ))}
        </div>
      </section>
      <section className="flex items-center justify-center p-6 sm:p-12">
        <Card className="w-full max-w-md p-7 shadow-[var(--shadow)] sm:p-9">
          <span className="grid size-11 place-items-center rounded-xl bg-[var(--accent-soft)] text-[var(--accent)]">
            <LockKeyhole aria-hidden size={20} />
          </span>
          <h2 className="mt-6 text-2xl font-bold tracking-[-0.03em]">Welcome to your workspace</h2>
          <p className="mt-2 leading-6 text-[var(--muted)]">
            Sign in through your organization’s identity provider. Credentials never pass through this application.
          </p>
          {error ? (
            <p className="mt-5 rounded-lg bg-red-50 p-3 text-sm text-red-800" role="alert">
              Sign-in could not be completed. Please try again or contact your administrator.
            </p>
          ) : null}
          <a
            className="mt-7 inline-flex min-h-12 w-full items-center justify-center gap-2 rounded-[10px] bg-[var(--accent)] px-5 font-semibold text-white transition hover:bg-[var(--accent-strong)]"
            href="/api/auth/login"
          >
            Continue with SSO <ArrowRight aria-hidden size={18} />
          </a>

          {localAuthEnabled ? (
            <div className="mt-6 border-t border-[var(--border)] pt-5">
              <p className="mb-3 text-xs font-bold uppercase tracking-wider text-[var(--muted)]">
                Local Development Logins
              </p>
              <div className="grid gap-2">
                <a
                  className="flex items-center justify-between rounded-lg border border-[var(--border)] bg-[var(--surface-soft)] p-3 text-xs font-semibold text-[var(--ink)] hover:border-[var(--accent)]"
                  href="/api/auth/login?dev_user=admin"
                >
                  <span className="flex items-center gap-2">
                    <UserCheck aria-hidden size={14} className="text-[var(--accent)]" /> Admin User
                  </span>
                  <span className="text-[var(--muted)]">admin@example.com →</span>
                </a>
                <a
                  className="flex items-center justify-between rounded-lg border border-[var(--border)] bg-[var(--surface-soft)] p-3 text-xs font-semibold text-[var(--ink)] hover:border-[var(--accent)]"
                  href="/api/auth/login?dev_user=seo_lead"
                >
                  <span className="flex items-center gap-2">
                    <UserCheck aria-hidden size={14} className="text-[var(--accent)]" /> SEO Manager
                  </span>
                  <span className="text-[var(--muted)]">seo_lead@example.com →</span>
                </a>
              </div>
            </div>
          ) : null}

          <p className="mb-0 mt-5 text-center text-xs leading-5 text-[var(--muted)]">
            Access is controlled by your organization and project permissions.
          </p>
        </Card>
      </section>
    </main>
  );
}
