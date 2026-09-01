"use client";

import { ArrowRight, Globe, Plus, Trash2 } from "lucide-react";
import Link from "next/link";
import { FormEvent, useState } from "react";

import { Button } from "@/components/button";
import { Card } from "@/components/card";
import { Input } from "@/components/input";
import { Modal } from "@/components/modal";
import { Table, TableCell, TableHead } from "@/components/table";
import { Toast } from "@/components/toast";
import { ApiError, apiRequest, idempotencyKey } from "@/lib/client-api";
import type { Project, Website } from "@/lib/api-types";

export function WebsiteWorkspace({
  project,
  initialItems,
}: {
  project: Project;
  initialItems: Website[];
}) {
  const [items, setItems] = useState<Website[]>(initialItems);
  const [name, setName] = useState("");
  const [url, setUrl] = useState("");
  const [locale, setLocale] = useState(project.default_locale || "en");
  const [country, setCountry] = useState(project.default_country || "");
  const [error, setError] = useState("");
  const [pending, setPending] = useState(false);
  const [toastMessage, setToastMessage] = useState<string | null>(null);

  // Archive modal state
  const [archiveTarget, setArchiveTarget] = useState<Website | null>(null);
  const [archivePending, setArchivePending] = useState(false);

  function showToast(message: string) {
    setToastMessage(message);
    setTimeout(() => setToastMessage(null), 3500);
  }

  async function createWebsite(event: FormEvent) {
    event.preventDefault();
    setPending(true);
    setError("");
    try {
      const created = await apiRequest<Website>(`/projects/${project.id}/websites`, {
        method: "POST",
        headers: { "Idempotency-Key": idempotencyKey("website") },
        body: JSON.stringify({
          name: name.trim(),
          url: url.trim(),
          locale: locale.trim() || "en",
          country: country.trim() ? country.trim().toUpperCase() : null,
        }),
      });
      setItems((current) => [created, ...current]);
      setName("");
      setUrl("");
      showToast("Website connected successfully.");
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Website could not be created.");
    } finally {
      setPending(false);
    }
  }

  async function handleArchiveWebsite() {
    if (!archiveTarget) return;
    setArchivePending(true);
    try {
      await apiRequest<Website>(`/websites/${archiveTarget.id}`, {
        method: "DELETE",
      });
      setItems((current) => current.filter((item) => item.id !== archiveTarget.id));
      setArchiveTarget(null);
      showToast("Website removed from active project.");
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Website could not be archived.");
    } finally {
      setArchivePending(false);
    }
  }

  return (
    <div className="grid gap-8 lg:grid-cols-[minmax(0,1fr)_380px]">
      <section className="grid content-start gap-6">
        <div>
          <p className="eyebrow">Connected properties</p>
          <h2 className="mb-0 mt-1 text-2xl font-bold">Websites</h2>
          <p className="mt-1 text-sm text-[var(--muted)]">
            Websites connected to this project serve as the canonical domain for future crawl, content mapping, and SEO audits.
          </p>
        </div>

        {items.length > 0 ? (
          <Card className="overflow-hidden p-0">
            <Table>
              <thead>
                <tr>
                  <TableHead>Website name</TableHead>
                  <TableHead>Host & URL</TableHead>
                  <TableHead>Locale</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </tr>
              </thead>
              <tbody>
                {items.map((site) => (
                  <tr className="transition hover:bg-[var(--surface-soft)]" key={site.id}>
                    <TableCell className="font-semibold">{site.name}</TableCell>
                    <TableCell>
                      <span className="font-mono text-xs text-[var(--ink)]">{site.normalized_host}</span>
                      <p className="m-0 text-xs text-[var(--muted)]">{site.base_url}</p>
                    </TableCell>
                    <TableCell>
                      <span className="rounded bg-[var(--surface-soft)] px-2 py-0.5 text-xs font-medium">
                        {site.locale}
                        {site.country ? `-${site.country}` : ""}
                      </span>
                    </TableCell>
                    <TableCell>
                      <span
                        className={`inline-flex rounded-full px-2.5 py-0.5 text-xs font-bold capitalize ${
                          site.status === "active"
                            ? "bg-emerald-50 text-emerald-700"
                            : "bg-amber-50 text-amber-700"
                        }`}
                      >
                        {site.status}
                      </span>
                    </TableCell>
                    <TableCell className="text-right">
                      <button
                        aria-label={`Remove ${site.name}`}
                        className="rounded-lg p-1.5 text-[var(--muted)] transition hover:bg-red-50 hover:text-red-600"
                        onClick={() => setArchiveTarget(site)}
                        type="button"
                      >
                        <Trash2 aria-hidden size={16} />
                      </button>
                    </TableCell>
                  </tr>
                ))}
              </tbody>
            </Table>
          </Card>
        ) : (
          <Card className="grid min-h-56 place-items-center border-dashed p-8 text-center">
            <div>
              <Globe aria-hidden className="mx-auto text-[var(--muted)]" size={32} />
              <p className="mb-1 mt-4 text-base font-semibold">No website connected</p>
              <p className="m-0 max-w-sm text-sm text-[var(--muted)]">
                Connect your primary website to begin organizing content architecture, keywords, and SEO guidance.
              </p>
            </div>
          </Card>
        )}
      </section>

      <aside className="grid content-start gap-4">
        <Card className="p-6 shadow-[var(--shadow)]">
          <span className="inline-flex items-center gap-2 text-sm font-bold">
            <Plus aria-hidden size={16} /> Connect website
          </span>
          <p className="mb-5 mt-2 text-xs leading-5 text-[var(--muted)]">
            Specify the base domain and default locale for this website property.
          </p>

          <form className="grid gap-4" onSubmit={createWebsite}>
            <Input
              label="Website name"
              name="name"
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. Marketing Blog"
              required
              value={name}
            />
            <Input
              label="Website URL"
              name="url"
              onChange={(e) => setUrl(e.target.value)}
              placeholder="https://example.com"
              required
              type="url"
              value={url}
            />
            <div className="grid grid-cols-2 gap-3">
              <Input
                label="Locale"
                maxLength={20}
                name="locale"
                onChange={(e) => setLocale(e.target.value)}
                placeholder="en"
                required
                value={locale}
              />
              <Input
                label="Country (ISO-2)"
                maxLength={2}
                name="country"
                onChange={(e) => setCountry(e.target.value.toUpperCase())}
                placeholder="US"
                value={country}
              />
            </div>

            {error ? (
              <p className="m-0 text-xs font-semibold text-[var(--danger)]" role="alert">
                {error}
              </p>
            ) : null}

            <Button disabled={pending || name.trim().length < 2 || !url.trim()} type="submit">
              {pending ? "Connecting…" : "Add website"}
            </Button>
          </form>
        </Card>

        <Card className="p-5">
          <p className="mb-2 text-xs font-bold uppercase tracking-wider text-[var(--muted)]">
            Domain Verification & Crawling
          </p>
          <p className="m-0 text-xs leading-relaxed text-[var(--muted)]">
            Automated crawl indexing, sitemap ingestion, and DNS ownership verification will be activated in Phase 2.
          </p>
          <Link
            className="mt-3 inline-flex items-center gap-1.5 text-xs font-bold text-[var(--accent)]"
            href={`/projects/${project.id}`}
          >
            Back to project overview <ArrowRight aria-hidden size={14} />
          </Link>
        </Card>
      </aside>

      {/* Confirmation modal for archiving */}
      <Modal
        onClose={() => setArchiveTarget(null)}
        open={Boolean(archiveTarget)}
        title="Remove website"
      >
        <div className="grid gap-4">
          <p className="m-0 text-sm text-[var(--muted)]">
            Are you sure you want to archive{" "}
            <strong className="text-[var(--ink)]">{archiveTarget?.name}</strong> (
            {archiveTarget?.normalized_host})?
          </p>
          <div className="flex justify-end gap-3 pt-2">
            <Button
              disabled={archivePending}
              onClick={() => setArchiveTarget(null)}
              tone="secondary"
            >
              Cancel
            </Button>
            <Button
              disabled={archivePending}
              onClick={handleArchiveWebsite}
              tone="danger"
            >
              {archivePending ? "Removing…" : "Remove website"}
            </Button>
          </div>
        </div>
      </Modal>

      {toastMessage ? <Toast message={toastMessage} tone="success" /> : null}
    </div>
  );
}
