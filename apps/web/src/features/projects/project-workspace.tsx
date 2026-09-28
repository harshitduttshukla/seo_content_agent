"use client";

import { ArrowRight } from "lucide-react";
import Link from "next/link";
import { FormEvent, useState } from "react";

import { v3 } from "@/components/v3/v3-top-bar";
import { ApiError, apiRequest, idempotencyKey } from "@/lib/client-api";
import type { Organization, Project } from "@/lib/api-types";

/** Status chips follow the V3 colour rule: teal is a system fact, grey is a resting label. */
function StatusChip({ status }: { status: string }) {
  return <span className={`chip ${status === "active" ? "t" : "r"} capitalize`}>{status}</span>;
}

export function ProjectWorkspace({ organization, initialItems }: { organization: Organization; initialItems: Project[] }) {
  const [items, setItems] = useState(initialItems);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [error, setError] = useState("");
  const [pending, setPending] = useState(false);

  async function createProject(event: FormEvent) {
    event.preventDefault();
    setPending(true);
    setError("");
    try {
      const created = await apiRequest<Project>("/projects", {
        method: "POST",
        headers: { "Idempotency-Key": idempotencyKey("project") },
        body: JSON.stringify({ organization_id: organization.id, name, description }),
      });
      setItems((current) => [created, ...current]);
      setName("");
      setDescription("");
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Project could not be created.");
    } finally {
      setPending(false);
    }
  }

  return (
    <div className="grid items-start gap-[16px] lg:grid-cols-[minmax(0,1fr)_320px]">
      <section aria-label="Projects" className="grid gap-[10px] sm:grid-cols-2">
        {items.map((project) => (
          <Link href={`/projects/${project.id}`} key={project.id} className={`${v3.cardLink} flex flex-col gap-[6px]`}>
            <div className="flex items-center justify-between gap-[10px]">
              <h2 className="m-0 font-serif text-[19px] font-medium text-[#12171A]">{project.name}</h2>
              <ArrowRight aria-hidden size={16} className="flex-none text-[#8A949A] transition-transform group-hover:translate-x-0.5 group-hover:text-[#15706A]" />
            </div>
            <p className="m-0 line-clamp-2 text-[12.6px] leading-[1.5] text-[#5C666C]">
              {project.description || "No description yet."}
            </p>
            <div className="mt-auto pt-[6px]">
              <StatusChip status={project.status} />
            </div>
          </Link>
        ))}
        {!items.length ? (
          <div className="rounded-[8px] border border-dashed border-[#D6DBD9] bg-[#FAFBFA] p-[22px] text-center sm:col-span-2">
            <p className="m-0 text-[13.3px] font-medium text-[#12171A]">No projects yet</p>
            <p className="m-[4px_0_0] text-[12.6px] text-[#5C666C]">Create one for each website or content program.</p>
          </div>
        ) : null}
      </section>

      <div className="grid gap-[10px]">
        <section aria-label="New project" className={`${v3.card} p-[16px_18px]`}>
          <h2 className="m-0 text-[13.3px] font-medium text-[#12171A]">New project</h2>
          <form className="mt-[12px] grid gap-[12px]" onSubmit={createProject}>
            <label className={v3.label}>
              Project name
              <input
                id="project-name"
                name="name"
                required
                value={name}
                onChange={(event) => setName(event.target.value)}
                placeholder="Editorial growth"
                className={v3.field}
              />
            </label>
            <label className={v3.label}>
              Description
              <textarea
                id="project-description"
                maxLength={2000}
                rows={3}
                value={description}
                onChange={(event) => setDescription(event.target.value)}
                placeholder="What this project covers"
                className={`${v3.field} resize-y`}
              />
            </label>
            {error ? <p role="alert" className="m-0 text-[12.6px] text-[#B9463A]">{error}</p> : null}
            <button type="submit" disabled={pending || name.trim().length < 2} className={v3.primary}>
              {pending ? "Creating…" : "Create project"}
            </button>
          </form>
        </section>
        <Link
          href={`/organizations/${organization.id}/settings`}
          className={`${v3.cardLink} flex items-center justify-between p-[12px_18px] text-[13.3px] text-[#12171A]`}
        >
          Organization settings
          <ArrowRight aria-hidden size={15} className="text-[#8A949A] group-hover:text-[#15706A]" />
        </Link>
      </div>
    </div>
  );
}
