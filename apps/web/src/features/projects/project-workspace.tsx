"use client";

import { ArrowRight, FolderKanban, Plus, Settings } from "lucide-react";
import Link from "next/link";
import { FormEvent, useState } from "react";

import { Button } from "@/components/button";
import { Card } from "@/components/card";
import { Input } from "@/components/input";
import { ApiError, apiRequest, idempotencyKey } from "@/lib/client-api";
import type { Organization, Project } from "@/lib/api-types";

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
    <div className="grid gap-8 lg:grid-cols-[minmax(0,1fr)_350px]">
      <div className="grid content-start gap-4 sm:grid-cols-2">
        {items.map((project) => (
          <Link href={`/projects/${project.id}`} key={project.id}>
            <Card className="group h-full p-5 transition hover:-translate-y-0.5 hover:border-[#b8b2ff] hover:shadow-md">
              <div className="flex items-start justify-between">
                <span className="grid size-11 place-items-center rounded-xl bg-[var(--accent-soft)] text-[var(--accent)]"><FolderKanban aria-hidden size={20} /></span>
                <ArrowRight aria-hidden className="text-[var(--muted)] transition group-hover:translate-x-1" size={18} />
              </div>
              <h2 className="mb-1 mt-7 text-lg font-bold">{project.name}</h2>
              <p className="line-clamp-2 min-h-10 text-sm leading-5 text-[var(--muted)]">{project.description || "No project description yet."}</p>
              <span className="mt-5 inline-flex rounded-full bg-emerald-50 px-2.5 py-1 text-xs font-bold capitalize text-emerald-700">{project.status}</span>
            </Card>
          </Link>
        ))}
        {!items.length ? <Card className="grid min-h-52 place-items-center border-dashed p-6 text-center sm:col-span-2"><div><FolderKanban aria-hidden className="mx-auto text-[var(--muted)]" /><p className="mb-1 mt-4 font-semibold">No projects yet</p><p className="m-0 text-sm text-[var(--muted)]">Create a project to connect a website and prepare the content workspace.</p></div></Card> : null}
      </div>
      <div className="grid content-start gap-4">
        <Card className="p-6 shadow-[var(--shadow)]">
          <span className="inline-flex items-center gap-2 text-sm font-bold"><Plus aria-hidden size={16} /> New project</span>
          <form className="mt-5 grid gap-4" onSubmit={createProject}>
            <Input label="Project name" name="name" onChange={(event) => setName(event.target.value)} placeholder="Editorial growth" required value={name} />
            <label className="grid gap-2 text-sm font-semibold">Description<textarea className="min-h-24 rounded-[10px] border border-[var(--border)] bg-white p-3 font-normal" maxLength={2000} onChange={(event) => setDescription(event.target.value)} placeholder="What this workspace will organize" value={description} /></label>
            {error ? <p className="m-0 text-sm text-[var(--danger)]" role="alert">{error}</p> : null}
            <Button disabled={pending || name.trim().length < 2} type="submit">{pending ? "Creating…" : "Create project"}</Button>
          </form>
        </Card>
        <Link href={`/organizations/${organization.id}/settings`}><Card className="flex items-center gap-3 p-4 text-sm font-semibold hover:border-[#b8b2ff]"><Settings aria-hidden className="text-[var(--accent)]" size={18} /> Organization settings <ArrowRight aria-hidden className="ml-auto" size={16} /></Card></Link>
      </div>
    </div>
  );
}
