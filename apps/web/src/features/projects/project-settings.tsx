"use client";

import { AlertTriangle, ArrowRight, Save, Trash2 } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";

import { Button } from "@/components/button";
import { Card } from "@/components/card";
import { Dropdown } from "@/components/dropdown";
import { Input } from "@/components/input";
import { Modal } from "@/components/modal";
import { Toast } from "@/components/toast";
import { ApiError, apiRequest } from "@/lib/client-api";
import type { Project } from "@/lib/api-types";

export function ProjectSettings({ project: initialProject }: { project: Project }) {
  const router = useRouter();
  const [project, setProject] = useState<Project>(initialProject);
  const [name, setName] = useState(initialProject.name);
  const [slug, setSlug] = useState(initialProject.slug);
  const [description, setDescription] = useState(initialProject.description || "");
  const [defaultLocale, setDefaultLocale] = useState(initialProject.default_locale || "en");
  const [defaultCountry, setDefaultCountry] = useState(initialProject.default_country || "");
  const [status, setStatus] = useState<"active" | "archived">(
    initialProject.status as "active" | "archived"
  );

  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  const [toastMessage, setToastMessage] = useState<string | null>(null);

  // Archive modal
  const [showArchiveModal, setShowArchiveModal] = useState(false);
  const [archivePending, setArchivePending] = useState(false);

  function showToast(message: string) {
    setToastMessage(message);
    setTimeout(() => setToastMessage(null), 3500);
  }

  async function handleUpdate(event: FormEvent) {
    event.preventDefault();
    setPending(true);
    setError("");
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
      showToast("Project settings saved successfully.");
      router.refresh();
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Failed to update project settings.");
    } finally {
      setPending(false);
    }
  }

  async function handleArchive() {
    setArchivePending(true);
    try {
      await apiRequest<Project>(`/projects/${project.id}`, {
        method: "DELETE",
      });
      showToast("Project archived successfully.");
      router.push(`/projects?organization_id=${project.organization_id}`);
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Failed to archive project.");
      setShowArchiveModal(false);
    } finally {
      setArchivePending(false);
    }
  }

  return (
    <div className="grid max-w-4xl gap-8">
      <div>
        <p className="eyebrow">Project configuration</p>
        <h1 className="mb-0 mt-1 text-2xl font-bold">Project Settings</h1>
        <p className="mt-1 text-sm text-[var(--muted)]">
          Manage general workspace settings, default locale targeting, and lifecycle status.
        </p>
      </div>

      <Card className="p-6">
        <form className="grid gap-5" onSubmit={handleUpdate}>
          <div className="grid gap-4 sm:grid-cols-2">
            <Input
              label="Project name"
              name="name"
              onChange={(e) => setName(e.target.value)}
              required
              value={name}
            />
            <Input
              label="URL slug"
              name="slug"
              onChange={(e) => setSlug(e.target.value)}
              required
              value={slug}
            />
          </div>

          <label className="grid gap-2 text-sm font-semibold">
            Description
            <textarea
              className="min-h-24 rounded-[10px] border border-[var(--border)] bg-white p-3 text-sm font-normal"
              maxLength={2000}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="What strategic purpose or content domain this workspace serves"
              value={description}
            />
          </label>

          <div className="grid gap-4 sm:grid-cols-3">
            <Input
              label="Default Locale"
              maxLength={20}
              name="default_locale"
              onChange={(e) => setDefaultLocale(e.target.value)}
              required
              value={defaultLocale}
            />
            <Input
              label="Default Country (ISO-2)"
              maxLength={2}
              name="default_country"
              onChange={(e) => setDefaultCountry(e.target.value.toUpperCase())}
              placeholder="US"
              value={defaultCountry}
            />
            <Dropdown
              label="Project Status"
              name="status"
              onChange={(e) => setStatus(e.target.value as "active" | "archived")}
              value={status}
            >
              <option value="active">Active</option>
              <option value="archived">Archived</option>
            </Dropdown>
          </div>

          <div className="rounded-lg bg-[var(--surface-soft)] p-3 text-xs text-[var(--muted)]">
            <span>Current schema revision: {project.revision}</span>
            <span className="ml-4">
              Created: {new Date(project.created_at).toLocaleDateString()}
            </span>
          </div>

          {error ? (
            <p className="m-0 text-xs font-semibold text-[var(--danger)]" role="alert">
              {error}
            </p>
          ) : null}

          <div className="flex items-center justify-between pt-2">
            <Link
              className="inline-flex items-center gap-1 text-xs font-semibold text-[var(--muted)] hover:text-[var(--ink)]"
              href={`/projects/${project.id}`}
            >
              <ArrowRight aria-hidden className="rotate-180" size={14} /> Back to dashboard
            </Link>
            <Button
              className="flex items-center gap-2"
              disabled={pending || name.trim().length < 2 || slug.trim().length < 2}
              type="submit"
            >
              <Save aria-hidden size={16} /> {pending ? "Saving…" : "Save changes"}
            </Button>
          </div>
        </form>
      </Card>

      {/* Danger Zone */}
      <Card className="border-red-200 bg-red-50/40 p-6">
        <div className="flex items-start justify-between gap-4">
          <div>
            <div className="flex items-center gap-2 text-red-900">
              <AlertTriangle aria-hidden size={18} />
              <h2 className="m-0 text-base font-bold">Archive Project</h2>
            </div>
            <p className="mb-0 mt-1 max-w-xl text-xs text-red-700">
              Archiving this project hides it from standard navigation while preserving all audit histories, strategy records, and content graph structures.
            </p>
          </div>
          <Button
            className="shrink-0"
            disabled={project.status === "archived"}
            onClick={() => setShowArchiveModal(true)}
            tone="danger"
            type="button"
          >
            <Trash2 aria-hidden size={15} /> Archive project
          </Button>
        </div>
      </Card>

      {/* Archive Modal */}
      <Modal
        onClose={() => setShowArchiveModal(false)}
        open={showArchiveModal}
        title="Archive Project"
      >
        <div className="grid gap-4">
          <p className="m-0 text-sm text-[var(--muted)]">
            Are you sure you want to archive <strong className="text-[var(--ink)]">{project.name}</strong>?
            This operation requires tenant authorization.
          </p>
          <div className="flex justify-end gap-3 pt-2">
            <Button
              disabled={archivePending}
              onClick={() => setShowArchiveModal(false)}
              tone="secondary"
            >
              Cancel
            </Button>
            <Button
              disabled={archivePending}
              onClick={handleArchive}
              tone="danger"
            >
              {archivePending ? "Archiving…" : "Confirm Archive"}
            </Button>
          </div>
        </div>
      </Modal>

      {toastMessage ? <Toast message={toastMessage} tone="success" /> : null}
    </div>
  );
}
