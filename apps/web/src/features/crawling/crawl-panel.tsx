"use client";

import { CheckCircle2, Copy, Play, RefreshCw, StopCircle, XCircle } from "lucide-react";
import { useEffect, useState } from "react";

import { Button } from "@/components/button";
import { Card } from "@/components/card";
import { Input } from "@/components/input";
import { Modal } from "@/components/modal";
import { Table, TableCell, TableHead } from "@/components/table";
import { apiRequest } from "@/lib/client-api";
import type {
  CrawlJob,
  CrawlStatusSummary,
  Website,
  WebsiteVerification,
} from "@/lib/api-types";

export function CrawlPanel({
  website,
  onWebsiteUpdated,
}: {
  website: Website;
  onWebsiteUpdated?: (updated: Website) => void;
}) {
  const [summary, setSummary] = useState<CrawlStatusSummary | null>(null);
  const [jobs, setJobs] = useState<CrawlJob[]>([]);
  const [verificationInfo, setVerificationInfo] = useState<WebsiteVerification | null>(null);
  const [isVerifyModalOpen, setIsVerifyModalOpen] = useState(false);
  const [isCrawlModalOpen, setIsCrawlModalOpen] = useState(false);

  // Verification state
  const [verifyMethod, setVerifyMethod] = useState("http_meta");
  const [verifying, setVerifying] = useState(false);
  const [verifyError, setVerifyError] = useState("");
  const [copied, setCopied] = useState(false);

  // Crawl configuration state
  const [maxPages, setMaxPages] = useState(100);
  const [maxDepth, setMaxDepth] = useState(4);
  const [respectRobots, setRespectRobots] = useState(true);
  const [includeSubdomains, setIncludeSubdomains] = useState(false);
  const [crawlStarting, setCrawlStarting] = useState(false);
  const [crawlError, setCrawlError] = useState("");

  // Polling for live crawl status
  async function fetchCrawlStatus() {
    try {
      const res = await apiRequest<CrawlStatusSummary>(`/websites/${website.id}/crawl-status`);
      setSummary(res);
    } catch {
      // Ignored in background polling
    }
  }

  async function fetchJobs() {
    try {
      const res = await apiRequest<{ items: CrawlJob[] }>(`/websites/${website.id}/crawl-jobs?limit=10`);
      setJobs(res.items || []);
    } catch {
      // Ignored
    }
  }

  async function fetchVerificationInfo() {
    try {
      const res = await apiRequest<WebsiteVerification>(`/websites/${website.id}/verification`);
      setVerificationInfo(res);
    } catch {
      // Ignored
    }
  }

  useEffect(() => {
    fetchCrawlStatus();
    fetchJobs();
    fetchVerificationInfo();

    const interval = setInterval(() => {
      fetchCrawlStatus();
      fetchJobs();
    }, 4000);

    return () => clearInterval(interval);
  }, [website.id]);

  async function handleVerify() {
    setVerifying(true);
    setVerifyError("");
    try {
      const res = await apiRequest<WebsiteVerification>(`/websites/${website.id}/verify`, {
        method: "POST",
        body: JSON.stringify({ method: verifyMethod }),
      });
      setVerificationInfo(res);
      if (res.verification_status === "verified") {
        setIsVerifyModalOpen(false);
        fetchCrawlStatus();
        if (onWebsiteUpdated) {
          onWebsiteUpdated({ ...website, verification_status: "verified" });
        }
      } else {
        setVerifyError("Verification tag was not found on your website. Please check placement.");
      }
    } catch (caught: unknown) {
      setVerifyError(caught instanceof Error ? caught.message : "Verification request failed.");
    } finally {
      setVerifying(false);
    }
  }

  async function handleDevBypassVerify() {
    setVerifying(true);
    setVerifyError("");
    try {
      const res = await apiRequest<WebsiteVerification>(`/websites/${website.id}/verify`, {
        method: "POST",
        body: JSON.stringify({ method: "dev_bypass" }),
      });
      setVerificationInfo(res);
      if (res.verification_status === "verified") {
        setIsVerifyModalOpen(false);
        fetchCrawlStatus();
        if (onWebsiteUpdated) {
          onWebsiteUpdated({ ...website, verification_status: "verified" });
        }
      }
    } catch (caught: unknown) {
      setVerifyError(caught instanceof Error ? caught.message : "Verification failed.");
    } finally {
      setVerifying(false);
    }
  }

  async function handleStartCrawl() {
    setCrawlStarting(true);
    setCrawlError("");
    try {
      await apiRequest<CrawlJob>(`/websites/${website.id}/crawl`, {
        method: "POST",
        body: JSON.stringify({
          configuration: {
            max_pages: maxPages,
            max_depth: maxDepth,
            respect_robots: respectRobots,
            include_subdomains: includeSubdomains,
          },
        }),
      });
      setIsCrawlModalOpen(false);
      fetchCrawlStatus();
      fetchJobs();
    } catch (caught: unknown) {
      setCrawlError(caught instanceof Error ? caught.message : "Could not start crawl.");
    } finally {
      setCrawlStarting(false);
    }
  }

  const [cancellingJobId, setCancellingJobId] = useState<string | null>(null);

  async function handleCancelCrawl(jobId: string) {
    setCancellingJobId(jobId);
    try {
      await apiRequest<CrawlJob>(`/crawl-jobs/${jobId}/cancel`, {
        method: "POST",
      });
      await fetchCrawlStatus();
      await fetchJobs();
    } catch {
      // Handled
    } finally {
      setCancellingJobId(null);
    }
  }

  const activeJob = summary?.active_job;
  const isVerified = (verificationInfo?.verification_status || website.verification_status) === "verified";

  return (
    <div className="grid gap-6">
      {/* Verification Banner */}
      <Card className="flex flex-col justify-between gap-4 p-5 sm:flex-row sm:items-center">
        <div className="flex items-center gap-3">
          {isVerified ? (
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-emerald-50 text-emerald-600">
              <CheckCircle2 size={22} />
            </div>
          ) : (
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-amber-50 text-amber-600">
              <XCircle size={22} />
            </div>
          )}
          <div>
            <div className="flex items-center gap-2">
              <h4 className="font-semibold text-[var(--ink)]">Domain Verification</h4>
              <span
                className={`rounded-full px-2.5 py-0.5 text-xs font-bold capitalize ${
                  isVerified ? "bg-emerald-50 text-emerald-700" : "bg-amber-50 text-amber-700"
                }`}
              >
                {isVerified ? "Verified" : "Unverified"}
              </span>
            </div>
            <p className="m-0 text-xs text-[var(--muted)]">
              {isVerified
                ? "Your ownership is verified. The crawler is authorized to discover and index pages."
                : "Verify website domain ownership before initiating automated crawl jobs."}
            </p>
          </div>
        </div>

        <div>
          {!isVerified && (
            <Button onClick={() => setIsVerifyModalOpen(true)} size="sm">
              Verify Website
            </Button>
          )}
        </div>
      </Card>

      {/* Crawl Control & Active Progress */}
      <Card className="grid gap-5 p-6">
        <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-center">
          <div>
            <h3 className="text-lg font-bold text-[var(--ink)]">Crawler Engine</h3>
            <p className="m-0 text-sm text-[var(--muted)]">
              Discover site architecture, parse robots.txt and sitemaps, and extract structured page content.
            </p>
          </div>

          <div className="flex items-center gap-2">
            {activeJob ? (
              <Button
                disabled={Boolean(cancellingJobId)}
                onClick={() => handleCancelCrawl(activeJob.id)}
                size="sm"
                variant="secondary"
              >
                <StopCircle className="mr-1.5 text-red-600" size={16} />
                {cancellingJobId === activeJob.id ? "Cancelling..." : "Cancel Crawl"}
              </Button>
            ) : (
              <Button
                disabled={!isVerified}
                onClick={() => setIsCrawlModalOpen(true)}
                size="sm"
              >
                <Play className="mr-1.5" size={16} />
                Start Crawl
              </Button>
            )}
          </div>
        </div>

        {/* Live Active Crawl Card */}
        {activeJob && (
          <div className="rounded-xl border border-blue-100 bg-blue-50/50 p-4">
            <div className="mb-2 flex items-center justify-between text-sm">
              <div className="flex items-center gap-2 font-medium text-blue-900">
                <RefreshCw className="animate-spin text-blue-600" size={16} />
                <span>Crawl In Progress ({activeJob.status})</span>
              </div>
              <span className="font-mono text-xs font-semibold text-blue-800">
                {activeJob.pages_crawled} / {activeJob.pages_discovered || activeJob.pages_crawled} pages
              </span>
            </div>
            <div className="h-2 w-full overflow-hidden rounded-full bg-blue-100">
              <div
                className="h-full bg-blue-600 transition-all duration-300"
                style={{
                  width: `${
                    activeJob.pages_discovered > 0
                      ? Math.min(100, Math.round((activeJob.pages_crawled / activeJob.pages_discovered) * 100))
                      : 25
                  }%`,
                }}
              />
            </div>
            <div className="mt-3 grid grid-cols-4 gap-2 text-center text-xs">
              <div className="rounded bg-white/80 p-1.5 shadow-sm">
                <span className="text-[var(--muted)]">Discovered</span>
                <p className="m-0 font-bold text-[var(--ink)]">{activeJob.pages_discovered}</p>
              </div>
              <div className="rounded bg-white/80 p-1.5 shadow-sm">
                <span className="text-[var(--muted)]">Crawled</span>
                <p className="m-0 font-bold text-emerald-700">{activeJob.pages_crawled}</p>
              </div>
              <div className="rounded bg-white/80 p-1.5 shadow-sm">
                <span className="text-[var(--muted)]">Failed</span>
                <p className="m-0 font-bold text-red-700">{activeJob.pages_failed}</p>
              </div>
              <div className="rounded bg-white/80 p-1.5 shadow-sm">
                <span className="text-[var(--muted)]">Skipped</span>
                <p className="m-0 font-bold text-amber-700">{activeJob.pages_skipped}</p>
              </div>
            </div>
          </div>
        )}
      </Card>

      {/* Crawl History */}
      <Card className="overflow-hidden p-0">
        <div className="border-b border-[var(--border)] px-5 py-4">
          <h4 className="font-bold text-[var(--ink)]">Crawl History</h4>
        </div>
        {jobs.length > 0 ? (
          <Table>
            <thead>
              <tr>
                <TableHead>Status</TableHead>
                <TableHead>Pages Crawled</TableHead>
                <TableHead>Discovered</TableHead>
                <TableHead>Failed</TableHead>
                <TableHead>Started</TableHead>
              </tr>
            </thead>
            <tbody>
              {jobs.map((job) => (
                <tr key={job.id}>
                  <TableCell>
                    <span
                      className={`inline-flex rounded-full px-2.5 py-0.5 text-xs font-bold capitalize ${
                        job.status === "completed"
                          ? "bg-emerald-50 text-emerald-700"
                          : job.status === "running"
                          ? "bg-blue-50 text-blue-700"
                          : job.status === "failed"
                          ? "bg-red-50 text-red-700"
                          : "bg-gray-100 text-gray-700"
                      }`}
                    >
                      {job.status}
                    </span>
                  </TableCell>
                  <TableCell className="font-semibold">{job.pages_crawled}</TableCell>
                  <TableCell>{job.pages_discovered}</TableCell>
                  <TableCell className={job.pages_failed > 0 ? "text-red-600 font-semibold" : ""}>
                    {job.pages_failed}
                  </TableCell>
                  <TableCell className="text-xs text-[var(--muted)]">
                    {new Date(job.created_at).toLocaleString()}
                  </TableCell>
                </tr>
              ))}
            </tbody>
          </Table>
        ) : (
          <div className="p-8 text-center text-sm text-[var(--muted)]">
            No previous crawl jobs recorded.
          </div>
        )}
      </Card>

      {/* Verification Modal */}
      {isVerifyModalOpen && (
        <Modal
          onClose={() => setIsVerifyModalOpen(false)}
          open={isVerifyModalOpen}
          title="Verify Website Ownership"
        >
          {verificationInfo ? (
            <div className="grid gap-4">
              <p className="text-sm text-[var(--muted)]">
                Choose a verification method to prove ownership of{" "}
                <strong className="text-[var(--ink)]">{website.base_url}</strong>.
              </p>

              <div className="grid gap-2">
                <label className="text-xs font-bold uppercase tracking-wider text-[var(--muted)]">
                  Verification Method
                </label>
                <select
                  className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-2 text-sm text-[var(--ink)]"
                  onChange={(e) => setVerifyMethod(e.target.value)}
                  value={verifyMethod}
                >
                  <option value="http_meta">HTML Meta Tag (Recommended)</option>
                  <option value="verification_file">Well-Known Text File</option>
                  <option value="http_header">Custom HTTP Header</option>
                </select>
              </div>

              {verifyMethod === "http_meta" && (
                <div className="grid gap-2">
                  <label className="text-xs font-bold text-[var(--ink)]">
                    Add this meta tag inside your homepage &lt;head&gt; section:
                  </label>
                  <div className="flex items-center gap-2 rounded-lg bg-[var(--surface-soft)] p-2.5 font-mono text-xs text-[var(--ink)]">
                    <span className="flex-1 select-all break-all">{verificationInfo.meta_tag_snippet}</span>
                    <button
                      className="rounded p-1 text-[var(--muted)] hover:text-[var(--ink)]"
                      onClick={() => {
                        navigator.clipboard.writeText(verificationInfo.meta_tag_snippet);
                        setCopied(true);
                        setTimeout(() => setCopied(false), 2000);
                      }}
                      type="button"
                    >
                      <Copy size={16} />
                    </button>
                  </div>
                  {copied && <p className="text-xs text-emerald-600">Copied to clipboard!</p>}
                </div>
              )}

              {verifyMethod === "verification_file" && (
                <div className="grid gap-2">
                  <label className="text-xs font-bold text-[var(--ink)]">
                    Create a file at <code className="text-xs text-blue-600">/.well-known/antigravity-verification.txt</code> containing:
                  </label>
                  <div className="flex items-center gap-2 rounded-lg bg-[var(--surface-soft)] p-2.5 font-mono text-xs text-[var(--ink)]">
                    <span className="flex-1 select-all">{verificationInfo.file_snippet}</span>
                    <button
                      className="rounded p-1 text-[var(--muted)] hover:text-[var(--ink)]"
                      onClick={() => {
                        navigator.clipboard.writeText(verificationInfo.file_snippet);
                        setCopied(true);
                        setTimeout(() => setCopied(false), 2000);
                      }}
                      type="button"
                    >
                      <Copy size={16} />
                    </button>
                  </div>
                </div>
              )}

              {verifyMethod === "http_header" && (
                <div className="grid gap-2">
                  <label className="text-xs font-bold text-[var(--ink)]">
                    Configure your web server to return this HTTP response header:
                  </label>
                  <div className="flex items-center gap-2 rounded-lg bg-[var(--surface-soft)] p-2.5 font-mono text-xs text-[var(--ink)]">
                    <span className="flex-1 select-all break-all">
                      X-Antigravity-Verification: {verificationInfo.verification_token}
                    </span>
                    <button
                      className="rounded p-1 text-[var(--muted)] hover:text-[var(--ink)]"
                      onClick={() => {
                        navigator.clipboard.writeText(`X-Antigravity-Verification: ${verificationInfo.verification_token}`);
                        setCopied(true);
                        setTimeout(() => setCopied(false), 2000);
                      }}
                      type="button"
                    >
                      <Copy size={16} />
                    </button>
                  </div>
                </div>
              )}

              {verifyError && (
                <p className="rounded-lg bg-red-50 p-2.5 text-xs text-red-600">{verifyError}</p>
              )}

              <div className="mt-2 flex flex-wrap items-center justify-between gap-2">
                <Button
                  disabled={verifying}
                  onClick={handleDevBypassVerify}
                  size="sm"
                  variant="secondary"
                >
                  ⚡ Instant Verify (Dev Mode)
                </Button>
                <div className="flex gap-2">
                  <Button
                    onClick={() => setIsVerifyModalOpen(false)}
                    variant="secondary"
                  >
                    Cancel
                  </Button>
                  <Button disabled={verifying} onClick={handleVerify}>
                    {verifying ? "Verifying..." : "Verify Ownership"}
                  </Button>
                </div>
              </div>
            </div>
          ) : (
            <div className="flex flex-col items-center justify-center gap-3 py-8">
              <RefreshCw className="animate-spin text-blue-600" size={24} />
              <p className="text-sm text-[var(--muted)]">Loading verification snippet...</p>
            </div>
          )}
        </Modal>
      )}

      {/* Crawl Settings Modal */}
      {isCrawlModalOpen && (
        <Modal
          onClose={() => setIsCrawlModalOpen(false)}
          open={isCrawlModalOpen}
          title="Configure & Start Crawl"
        >
          <div className="grid gap-4">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="text-xs font-bold text-[var(--ink)]">Max Pages</label>
                <Input
                  max={2000}
                  min={1}
                  onChange={(e) => setMaxPages(Number(e.target.value))}
                  type="number"
                  value={maxPages}
                />
              </div>
              <div>
                <label className="text-xs font-bold text-[var(--ink)]">Max Depth</label>
                <Input
                  max={10}
                  min={1}
                  onChange={(e) => setMaxDepth(Number(e.target.value))}
                  type="number"
                  value={maxDepth}
                />
              </div>
            </div>

            <div className="grid gap-2">
              <label className="flex items-center gap-2 text-sm text-[var(--ink)]">
                <input
                  checked={respectRobots}
                  onChange={(e) => setRespectRobots(e.target.checked)}
                  type="checkbox"
                />
                Respect robots.txt rules
              </label>

              <label className="flex items-center gap-2 text-sm text-[var(--ink)]">
                <input
                  checked={includeSubdomains}
                  onChange={(e) => setIncludeSubdomains(e.target.checked)}
                  type="checkbox"
                />
                Include Subdomains (e.g. blog.example.com)
              </label>
            </div>

            {crawlError && (
              <p className="rounded-lg bg-red-50 p-2.5 text-xs text-red-600">{crawlError}</p>
            )}

            <div className="mt-2 flex justify-end gap-2">
              <Button
                onClick={() => setIsCrawlModalOpen(false)}
                variant="secondary"
              >
                Cancel
              </Button>
              <Button disabled={crawlStarting} onClick={handleStartCrawl}>
                {crawlStarting ? "Starting..." : "Launch Crawl"}
              </Button>
            </div>
          </div>
        </Modal>
      )}
    </div>
  );
}
