"use client";

import { ExternalLink, FileText, Image as ImageIcon, Link as LinkIcon, Search } from "lucide-react";
import { useEffect, useState } from "react";

import { Button } from "@/components/button";
import { Card } from "@/components/card";
import { Input } from "@/components/input";
import { Modal } from "@/components/modal";
import { Table, TableCell, TableHead } from "@/components/table";
import { apiRequest } from "@/lib/client-api";
import type {
  ContentPageDetail,
  ContentPageSummary,
  Website,
} from "@/lib/api-types";

export function PageInventory({ website }: { website: Website }) {
  const [pages, setPages] = useState<ContentPageSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [selectedStatus, setSelectedStatus] = useState<string | null>(null);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [hasMore, setHasMore] = useState(false);

  // Detail modal
  const [selectedPage, setSelectedPage] = useState<ContentPageDetail | null>(null);
  const [loadingDetail, setLoadingDetail] = useState(false);

  async function loadPages(cursor?: string | null, isAppend = false) {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (search.trim()) params.set("search", search.trim());
      if (selectedStatus) params.set("status", selectedStatus);
      if (cursor) params.set("cursor", cursor);
      params.set("limit", "25");

      const query = params.toString() ? `?${params.toString()}` : "";
      const res = await apiRequest<{ items: ContentPageSummary[] }>(
        `/websites/${website.id}/pages${query}`
      );
      setPages((curr) => (isAppend ? [...curr, ...(res.items || [])] : res.items || []));
    } catch {
      // Handled
    } finally {
      setLoading(false);
    }
  }

  async function openPageDetail(pageId: string) {
    setLoadingDetail(true);
    try {
      const detail = await apiRequest<ContentPageDetail>(
        `/websites/${website.id}/pages/${pageId}`
      );
      setSelectedPage(detail);
    } catch {
      // Handled
    } finally {
      setLoadingDetail(false);
    }
  }

  useEffect(() => {
    loadPages();
  }, [website.id, selectedStatus]);

  function handleSearchSubmit(e: React.FormEvent) {
    e.preventDefault();
    loadPages();
  }

  const statuses = [
    { label: "All", value: null },
    { label: "Indexed", value: "indexed" },
    { label: "Duplicate", value: "duplicate" },
    { label: "Failed", value: "failed" },
    { label: "Redirect", value: "redirect" },
  ];

  return (
    <div className="grid gap-6">
      {/* Search & Filter Header */}
      <Card className="flex flex-col justify-between gap-4 p-4 sm:flex-row sm:items-center">
        <form className="flex items-center gap-2 sm:w-80" onSubmit={handleSearchSubmit}>
          <div className="relative w-full">
            <Search className="absolute left-3 top-2.5 text-[var(--muted)]" size={16} />
            <Input
              className="pl-9 text-sm"
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search by URL or title..."
              value={search}
            />
          </div>
          <Button size="sm" type="submit" variant="secondary">
            Search
          </Button>
        </form>

        <div className="flex flex-wrap items-center gap-1.5">
          {statuses.map((item) => (
            <button
              className={`rounded-lg px-3 py-1 text-xs font-semibold transition ${
                selectedStatus === item.value
                  ? "bg-[var(--ink)] text-[var(--surface)]"
                  : "bg-[var(--surface-soft)] text-[var(--muted)] hover:text-[var(--ink)]"
              }`}
              key={item.label}
              onClick={() => setSelectedStatus(item.value)}
              type="button"
            >
              {item.label}
            </button>
          ))}
        </div>
      </Card>

      {/* Pages Table */}
      <Card className="overflow-hidden p-0">
        {pages.length > 0 ? (
          <Table>
            <thead>
              <tr>
                <TableHead>Page Title & URL</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>HTTP</TableHead>
                <TableHead>Words</TableHead>
                <TableHead>Last Crawled</TableHead>
              </tr>
            </thead>
            <tbody>
              {pages.map((p) => (
                <tr
                  className="cursor-pointer transition hover:bg-[var(--surface-soft)]"
                  key={p.id}
                  onClick={() => openPageDetail(p.id)}
                >
                  <TableCell className="max-w-md">
                    <p className="m-0 truncate font-semibold text-[var(--ink)]">
                      {p.title || "(No Title Extracted)"}
                    </p>
                    <p className="m-0 truncate font-mono text-xs text-[var(--muted)]">{p.url}</p>
                  </TableCell>
                  <TableCell>
                    <span
                      className={`inline-flex rounded-full px-2.5 py-0.5 text-xs font-bold capitalize ${
                        p.content_status === "indexed"
                          ? "bg-emerald-50 text-emerald-700"
                          : p.content_status === "duplicate"
                          ? "bg-amber-50 text-amber-700"
                          : "bg-red-50 text-red-700"
                      }`}
                    >
                      {p.content_status}
                    </span>
                  </TableCell>
                  <TableCell>
                    <span className="font-mono text-xs font-medium text-[var(--ink)]">
                      {p.http_status || "—"}
                    </span>
                  </TableCell>
                  <TableCell className="font-medium">{p.word_count}</TableCell>
                  <TableCell className="text-xs text-[var(--muted)]">
                    {p.last_crawled_at ? new Date(p.last_crawled_at).toLocaleDateString() : "—"}
                  </TableCell>
                </tr>
              ))}
            </tbody>
          </Table>
        ) : (
          <div className="grid min-h-52 place-items-center p-8 text-center text-sm text-[var(--muted)]">
            <div>
              <FileText className="mx-auto mb-2 text-[var(--muted)]" size={32} />
              <p className="font-semibold text-[var(--ink)]">No indexed pages found</p>
              <p className="m-0 max-w-sm text-xs text-[var(--muted)]">
                Launch a crawl on this website to index pages, headings, and internal link structure.
              </p>
            </div>
          </div>
        )}
      </Card>

      {/* Page Detail Inspection Modal */}
      {selectedPage && (
        <Modal
          onClose={() => setSelectedPage(null)}
          open={Boolean(selectedPage)}
          title="Structured Page Inspection"
        >
          <div className="grid max-h-[75vh] gap-5 overflow-y-auto pr-1 text-sm">
            {/* Header properties */}
            <div className="rounded-xl bg-[var(--surface-soft)] p-4">
              <h3 className="text-base font-bold text-[var(--ink)]">{selectedPage.title}</h3>
              <a
                className="mt-1 flex items-center gap-1 font-mono text-xs text-blue-600 hover:underline"
                href={selectedPage.url}
                rel="noreferrer"
                target="_blank"
              >
                {selectedPage.url}
                <ExternalLink size={12} />
              </a>

              {selectedPage.meta_description && (
                <p className="mt-3 text-xs leading-relaxed text-[var(--muted)]">
                  <strong className="text-[var(--ink)]">Meta Description:</strong>{" "}
                  {selectedPage.meta_description}
                </p>
              )}

              <div className="mt-3 flex flex-wrap gap-4 text-xs font-medium text-[var(--muted)]">
                <div>
                  HTTP: <span className="font-mono text-[var(--ink)]">{selectedPage.http_status}</span>
                </div>
                <div>
                  Language: <span className="text-[var(--ink)]">{selectedPage.language}</span>
                </div>
                <div>
                  Word Count: <span className="text-[var(--ink)]">{selectedPage.word_count}</span>
                </div>
                {selectedPage.canonical_url && (
                  <div className="truncate">
                    Canonical: <span className="font-mono text-[var(--ink)]">{selectedPage.canonical_url}</span>
                  </div>
                )}
              </div>
            </div>

            {/* Headings Structure */}
            <div>
              <h4 className="mb-2 font-bold text-[var(--ink)]">Headings Hierarchy (H1–H6)</h4>
              {selectedPage.headings && selectedPage.headings.length > 0 ? (
                <div className="grid gap-1.5 rounded-lg border border-[var(--border)] p-3">
                  {selectedPage.headings.map((h, i) => (
                    <div
                      className="flex items-center gap-2 text-xs"
                      key={i}
                      style={{ paddingLeft: `${(Number(h.level) - 1) * 12}px` }}
                    >
                      <span className="rounded bg-blue-50 px-1.5 py-0.5 font-mono text-[10px] font-bold text-blue-700">
                        H{String(h.level)}
                      </span>
                      <span className="text-[var(--ink)]">{String(h.text)}</span>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-xs text-[var(--muted)]">No headings detected on this page.</p>
              )}
            </div>

            {/* Extracted Images */}
            <div>
              <div className="mb-2 flex items-center gap-2">
                <ImageIcon size={16} className="text-[var(--muted)]" />
                <h4 className="font-bold text-[var(--ink)]">
                  Extracted Images ({selectedPage.images?.length || 0})
                </h4>
              </div>
              {selectedPage.images && selectedPage.images.length > 0 ? (
                <div className="grid gap-2 rounded-lg border border-[var(--border)] p-3 text-xs">
                  {selectedPage.images.map((img, i) => (
                    <div className="flex items-center justify-between gap-2 border-b border-[var(--border)] pb-1.5 last:border-0" key={i}>
                      <span className="truncate font-mono text-[var(--ink)]">{String(img.src)}</span>
                      {img.alt ? (
                        <span className="rounded bg-emerald-50 px-2 py-0.5 text-[10px] font-bold text-emerald-700">
                          Alt: {String(img.alt)}
                        </span>
                      ) : (
                        <span className="rounded bg-red-50 px-2 py-0.5 text-[10px] font-bold text-red-600">
                          Missing Alt
                        </span>
                      )}
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-xs text-[var(--muted)]">No images extracted.</p>
              )}
            </div>

            <div className="flex justify-end">
              <Button onClick={() => setSelectedPage(null)} variant="secondary">
                Close
              </Button>
            </div>
          </div>
        </Modal>
      )}
    </div>
  );
}
