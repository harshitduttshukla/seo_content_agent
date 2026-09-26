"use client";

import { useRouter } from "next/navigation";
import { type FormEvent, type ReactNode, useState } from "react";

import { GscIntegration } from "@/features/search-console/gsc-integration";
import type { Project } from "@/lib/api-types";
import { ApiError, apiRequest } from "@/lib/client-api";

const field =
  "w-full rounded-[5px] border border-[var(--line)] bg-white px-[8px] py-[5px] text-[13px] text-[#12171A] focus-visible:outline-2 focus-visible:outline-[var(--teal)] disabled:opacity-60";
const btnPrimary =
  "rounded-[5px] border border-[var(--teal)] bg-[var(--teal)] px-[12px] py-[5px] text-[12.5px] text-white focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--teal)] disabled:opacity-50";
const btn =
  "rounded-[5px] border border-[var(--line)] bg-white px-[12px] py-[5px] text-[12.5px] text-[#12171A] hover:bg-[#F0F2F1] disabled:opacity-50";
const btnDanger =
  "rounded-[5px] border border-[var(--coral)] bg-white px-[12px] py-[5px] text-[12.5px] text-[var(--coral)] hover:bg-[#FBEFEC] disabled:opacity-50";

function Section({ id, title, sub, children }: { id: string; title: string; sub: string; children: ReactNode }) {
  return (
    <section aria-labelledby={id} className="mb-[16px] rounded-[8px] border border-[var(--line)] bg-white">
      <header className="border-b border-[var(--line2)] px-[16px] py-[11px]">
        <h2 id={id} className="m-0 text-[14px] font-medium">{title}</h2>
        <p className="m-[2px_0_0] text-[12px] text-[var(--ink3)]">{sub}</p>
      </header>
      <div className="p-[16px]">{children}</div>
    </section>
  );
}

function Field({ label, htmlFor, hint, children }: { label: string; htmlFor: string; hint?: string; children: ReactNode }) {
  return (
    <div>
      <label htmlFor={htmlFor} className="mb-[4px] block text-[11.8px] text-[#5C666C]">{label}</label>
      {children}
      {hint ? <div className="mt-[3px] text-[11px] text-[var(--ink3)]">{hint}</div> : null}
    </div>
  );
}

function errorText(caught: unknown, fallback: string): string {
  return caught instanceof ApiError ? caught.message : fallback;
}

/** V3 project settings: the same project APIs as before, in the V3 shell. */
export function ProjectSettingsV3({
  project: initial,
  gscNotice,
}: {
  project: Project;
  gscNotice?: { ok: boolean; code: string };
}) {
  const router = useRouter();
  const [project, setProject] = useState<Project>(initial);
  const [name, setName] = useState(initial.name);
  const [slug, setSlug] = useState(initial.slug);
  const [description, setDescription] = useState(initial.description || "");
  const [defaultLocale, setDefaultLocale] = useState(initial.default_locale || "en");
  const [defaultCountry, setDefaultCountry] = useState(initial.default_country || "");
  const [status, setStatus] = useState<"active" | "archived">(initial.status as "active" | "archived");
  const [saving, setSaving] = useState(false);
  const [notice, setNotice] = useState<{ ok: boolean; text: string } | null>(null);
  const [confirmArchive, setConfirmArchive] = useState(false);
  const [archiving, setArchiving] = useState(false);

  async function save(event: FormEvent) {
    event.preventDefault();
    setSaving(true);
    setNotice(null);
    try {
      const updated = await apiRequest<Project>(`/projects/${project.id}`, {
        method: "PUT",
        body: JSON.stringify({
          name: name.trim(),
          slug: slug.trim(),
          description: description.trim(),
          status,
          default_locale: defaultLocale.trim(),
          default_country: defaultCountry.trim() ? defaultCountry.trim().toUpperCase() : null,
          revision: project.revision,
        }),
      });
      setProject(updated);
      setName(updated.name);
      setSlug(updated.slug);
      setDescription(updated.description || "");
      setDefaultLocale(updated.default_locale);
      setDefaultCountry(updated.default_country || "");
      setStatus(updated.status as "active" | "archived");
      setNotice({ ok: true, text: "Project settings saved." });
      router.refresh();
    } catch (caught) {
      setNotice({ ok: false, text: errorText(caught, "Failed to update project settings.") });
    } finally {
      setSaving(false);
    }
  }

  async function archive() {
    setArchiving(true);
    setNotice(null);
    try {
      await apiRequest<Project>(`/projects/${project.id}`, { method: "DELETE" });
      router.push(`/projects?organization_id=${project.organization_id}`);
    } catch (caught) {
      setNotice({ ok: false, text: errorText(caught, "Failed to archive project.") });
      setConfirmArchive(false);
    } finally {
      setArchiving(false);
    }
  }

  return (
    <section className="animate-in fade-in duration-150">
      <div className="mb-[6px] text-[11.5px] text-[#8A949A]">Base · configured</div>
      <h1 className="m-0 font-serif text-[25px] font-medium tracking-tight text-[#12171A]">Settings</h1>
      <p className="m-[5px_0_18px] max-w-[74ch] text-[13.4px] text-[#5C666C]">
        Project configuration, integrations and archiving for {project.name}.
      </p>
      {notice ? (
        <p role={notice.ok ? "status" : "alert"} className={`mb-[12px] text-[12.8px] ${notice.ok ? "text-[var(--teal)]" : "text-[var(--coral)]"}`}>
          {notice.text}
        </p>
      ) : null}

      <Section id="settings-project" title="Project" sub="Name, identifiers and market defaults used across modules.">
        <form onSubmit={save} className="grid gap-[12px] md:grid-cols-2" aria-label="Project settings">
          <Field label="Project name" htmlFor="project-name">
            <input id="project-name" className={field} required maxLength={160} value={name} onChange={(e) => setName(e.target.value)} />
          </Field>
          <Field label="Slug" htmlFor="project-slug" hint="Lowercase letters, numbers and hyphens.">
            <input id="project-slug" className={field} required maxLength={120} value={slug} onChange={(e) => setSlug(e.target.value)} />
          </Field>
          <div className="md:col-span-2">
            <Field label="Description" htmlFor="project-description">
              <textarea id="project-description" rows={3} className={field} value={description} onChange={(e) => setDescription(e.target.value)} />
            </Field>
          </div>
          <Field label="Default locale" htmlFor="project-locale" hint="e.g. en or en-GB">
            <input id="project-locale" className={field} required maxLength={20} value={defaultLocale} onChange={(e) => setDefaultLocale(e.target.value)} />
          </Field>
          <Field label="Default country" htmlFor="project-country" hint="Two-letter code, e.g. US">
            <input id="project-country" className={field} maxLength={2} value={defaultCountry} onChange={(e) => setDefaultCountry(e.target.value)} />
          </Field>
          <Field label="Project status" htmlFor="project-status">
            <select id="project-status" className={field} value={status} onChange={(e) => setStatus(e.target.value as "active" | "archived")}>
              <option value="active">Active</option>
              <option value="archived">Archived</option>
            </select>
          </Field>
          <div className="flex items-end justify-end md:col-span-2">
            <button type="submit" className={btnPrimary} disabled={saving}>{saving ? "Saving…" : "Save changes"}</button>
          </div>
        </form>
      </Section>

      <Section id="settings-integrations" title="Integrations" sub="External data sources connected to this project.">
        <GscIntegration projectId={project.id} notice={gscNotice} />
      </Section>

      <Section id="settings-danger" title="Danger zone" sub="Archiving hides the project from standard navigation while preserving audit history, strategy records and the content graph.">
        {confirmArchive ? (
          <div role="group" aria-label="Confirm archive" className="rounded-[6px] border border-[var(--coral)] p-[10px] text-[12.8px]">
            <p className="m-[0_0_8px]">Archive {project.name}? It is hidden from standard navigation; its data is preserved.</p>
            <span className="flex gap-[6px]">
              <button type="button" className={btnDanger} disabled={archiving} onClick={archive}>{archiving ? "Archiving…" : "Archive project"}</button>
              <button type="button" className={btn} disabled={archiving} onClick={() => setConfirmArchive(false)}>Cancel</button>
            </span>
          </div>
        ) : (
          <button type="button" className={btnDanger} disabled={project.status === "archived"} onClick={() => setConfirmArchive(true)}>
            {project.status === "archived" ? "Project is archived" : "Archive project…"}
          </button>
        )}
      </Section>
    </section>
  );
}
