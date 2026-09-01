"use client";

import { ArrowLeft, ArrowRight, CheckCircle2, FileText, Globe, Play, Plus, RefreshCw, Trash2, XCircle } from "lucide-react";
import Link from "next/link";
import { FormEvent, useState } from "react";

import { Button } from "@/components/button";
import { Card } from "@/components/card";
import { Input } from "@/components/input";
import { Modal } from "@/components/modal";
import { Table, TableCell, TableHead } from "@/components/table";
import { Toast } from "@/components/toast";
import { CrawlPanel } from "@/features/crawling/crawl-panel";
import { PageInventory } from "@/features/pages/page-inventory";
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
  const [selectedSite, setSelectedSite] = useState<Website | null>(
    initialItems.length > 0 ? initialItems[0] : null
  );
  const [activeTab, setActiveTab] = useState<"overview" | "crawl" | "pages">("crawl");

  // Create form state
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
      setSelectedSite(created);
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
      const remaining = items.filter((item) => item.id !== archiveTarget.id);
      setItems(remaining);
      if (selectedSite?.id === archiveTarget.id) {
        setSelectedSite(remaining.length > 0 ? remaining[0] : null);
      }
      setArchiveTarget(null);
      showToast("Website removed from active project.");
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Website could not be archived.");
    } finally {
      setArchivePending(false);
    }
  }

  return (
    <div className="grid gap-6">
      {/* Header & Website Selector */}
      <div className="flex flex-col justify-between gap-4 border-b border-[var(--border)] pb-5 sm:flex-row sm:items-center">
        <div>
          <p className="eyebrow">Website & Content Intelligence</p>
          <div className="mt-1 flex items-center gap-3">
            <h2 className="text-2xl font-bold text-[var(--ink)]">
              {selectedSite ? selectedSite.name : "Websites"}
            </h2>
            {selectedSite && (
              <span className="font-mono text-xs text-[var(--muted)]">
                ({selectedSite.normalized_host})
              </span>
            )}
          </div>
        </div>

        {items.length > 1 && (
          <div className="flex items-center gap-2">
            <label className="text-xs font-bold text-[var(--muted)]">Select Website:</label>
            <select
              className="rounded-lg border border-[var(--border)] bg-[var(--surface)] px-3 py-1.5 text-sm font-semibold text-[var(--ink)]"
              onChange={(e) => {
                const found = items.find((s) => s.id === e.target.value);
                if (found) setSelectedSite(found);
              }}
              value={selectedSite?.id}
            >
              {items.map((site) => (
                <option key={site.id} value={site.id}>
                  {site.name} ({site.normalized_host})
                </option>
              ))}
            </select>
          </div>
        )}
      </div>

      {selectedSite ? (
        <div className="grid gap-6">
          {/* Sub-Navigation Tabs */}
          <div className="flex border-b border-[var(--border)]">
            <button
              className={`flex items-center gap-2 border-b-2 px-4 py-2.5 text-sm font-bold transition ${
                activeTab === "crawl"
                  ? "border-[var(--ink)] text-[var(--ink)]"
                  : "border-transparent text-[var(--muted)] hover:text-[var(--ink)]"
              }`}
              onClick={() => setActiveTab("crawl")}
              type="button"
            >
              <RefreshCw size={16} />
              Crawl & Indexing
            </button>

            <button
              className={`flex items-center gap-2 border-b-2 px-4 py-2.5 text-sm font-bold transition ${
                activeTab === "pages"
                  ? "border-[var(--ink)] text-[var(--ink)]"
                  : "border-transparent text-[var(--muted)] hover:text-[var(--ink)]"
              }`}
              onClick={() => setActiveTab("pages")}
              type="button"
            >
              <FileText size={16} />
              Pages (Content Inventory)
            </button>

            <button
              className={`flex items-center gap-2 border-b-2 px-4 py-2.5 text-sm font-bold transition ${
                activeTab === "overview"
                  ? "border-[var(--ink)] text-[var(--ink)]"
                  : "border-transparent text-[var(--muted)] hover:text-[var(--ink)]"
              }`}
              onClick={() => setActiveTab("overview")}
              type="button"
            >
              <Globe size={16} />
              Domain Overview
            </button>
          </div>

          {/* Active Tab View */}
          {activeTab === "crawl" && (
            <CrawlPanel
              onWebsiteUpdated={(updated) => {
                setSelectedSite(updated);
                setItems((curr) => curr.map((s) => (s.id === updated.id ? updated : s)));
              }}
              website={selectedSite}
            />
          )}

          {activeTab === "pages" && <PageInventory website={selectedSite} />}

          {activeTab === "overview" && (
            <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_380px]">
              <Card className="grid gap-4 p-6">
                <h3 className="text-lg font-bold text-[var(--ink)]">Website Configuration</h3>
                <div className="grid grid-cols-2 gap-4 text-sm">
                  <div>
                    <span className="text-xs text-[var(--muted)]">Property Name</span>
                    <p className="m-0 font-semibold text-[var(--ink)]">{selectedSite.name}</p>
                  </div>
                  <div>
                    <span className="text-xs text-[var(--muted)]">Canonical Host</span>
                    <p className="m-0 font-mono text-xs font-semibold text-[var(--ink)]">
                      {selectedSite.normalized_host}
                    </p>
                  </div>
                  <div>
                    <span className="text-xs text-[var(--muted)]">Base URL</span>
                    <p className="m-0 font-mono text-xs text-[var(--ink)]">{selectedSite.base_url}</p>
                  </div>
                  <div>
                    <span className="text-xs text-[var(--muted)]">Locale & Region</span>
                    <p className="m-0 font-semibold text-[var(--ink)]">
                      {selectedSite.locale}
                      {selectedSite.country ? `-${selectedSite.country}` : ""}
                    </p>
                  </div>
                </div>

                <div className="mt-4 flex justify-end">
                  <Button
                    onClick={() => setArchiveTarget(selectedSite)}
                    size="sm"
                    variant="secondary"
                  >
                    <Trash2 className="mr-1.5 text-red-600" size={16} />
                    Archive Property
                  </Button>
                </div>
              </Card>

              <Card className="p-6">
                <h4 className="font-bold text-[var(--ink)]">Connect Another Website</h4>
                <form className="mt-3 grid gap-3" onSubmit={createWebsite}>
                  <Input
                    label="Website name"
                    onChange={(e) => setName(e.target.value)}
                    placeholder="e.g. Documentation"
                    required
                    value={name}
                  />
                  <Input
                    label="URL"
                    onChange={(e) => setUrl(e.target.value)}
                    placeholder="https://docs.example.com"
                    required
                    type="url"
                    value={url}
                  />
                  {error && <p className="text-xs text-red-600">{error}</p>}
                  <Button disabled={pending || !name.trim() || !url.trim()} size="sm" type="submit">
                    {pending ? "Adding..." : "Add Website"}
                  </Button>
                </form>
              </Card>
            </div>
          )}
        </div>
      ) : (
        <Card className="grid min-h-56 place-items-center border-dashed p-8 text-center">
          <div>
            <Globe aria-hidden className="mx-auto text-[var(--muted)]" size={32} />
            <p className="mb-1 mt-4 text-base font-semibold">No website connected</p>
            <p className="m-0 max-w-sm text-sm text-[var(--muted)]">
              Connect your primary website to begin organizing content architecture, keywords, and SEO guidance.
            </p>
            <div className="mx-auto mt-4 max-w-sm">
              <form className="grid gap-3" onSubmit={createWebsite}>
                <Input
                  label="Website name"
                  onChange={(e) => setName(e.target.value)}
                  placeholder="e.g. Main Website"
                  required
                  value={name}
                />
                <Input
                  label="Website URL"
                  onChange={(e) => setUrl(e.target.value)}
                  placeholder="https://example.com"
                  required
                  type="url"
                  value={url}
                />
                <Button disabled={pending || !name.trim() || !url.trim()} size="sm" type="submit">
                  {pending ? "Connecting…" : "Connect Website"}
                </Button>
              </form>
            </div>
          </div>
        </Card>
      )}

      {/* Archive Modal */}
      {archiveTarget && (
        <Modal
          onClose={() => setArchiveTarget(null)}
          title="Archive Website Property"
        >
          <div className="grid gap-4">
            <p className="m-0 text-sm text-[var(--muted)]">
              Are you sure you want to archive{" "}
              <strong className="text-[var(--ink)]">{archiveTarget.name}</strong> (
              {archiveTarget.normalized_host})?
            </p>
            <div className="flex justify-end gap-2">
              <Button onClick={() => setArchiveTarget(null)} variant="secondary">
                Cancel
              </Button>
              <Button
                disabled={archivePending}
                onClick={handleArchiveWebsite}
              >
                {archivePending ? "Archiving..." : "Confirm Archive"}
              </Button>
            </div>
          </div>
        </Modal>
      )}

      {toastMessage && <Toast message={toastMessage} />}
    </div>
  );
}
