"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { describeGscError } from "@/features/search-console/gsc-integration";
import type { GscAnalytics, GscStatus } from "@/lib/api-types";
import { GscAPI } from "@/lib/gsc-api";

const number = new Intl.NumberFormat("en-US");
const SORTS = [
  ["clicks", "Clicks"],
  ["impressions", "Impressions"],
  ["ctr", "CTR"],
  ["position", "Position"],
  ["date", "Date"],
] as const;

function Tile({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-[8px] border border-[var(--line)] bg-white px-[12px] py-[10px]">
      <div className="font-serif text-[22px] font-medium">{value}</div>
      <div className="text-[11.5px] text-[var(--ink3)]">{label}</div>
    </div>
  );
}

function Performance({ projectId }: { projectId: string }) {
  const [status, setStatus] = useState<GscStatus | null>(null);
  const [websiteId, setWebsiteId] = useState<string | null>(null);
  const [sort, setSort] = useState<(typeof SORTS)[number][0]>("clicks");
  // Tagged with the selection it was loaded for; a mismatch means a load is in flight.
  const [result, setResult] = useState<{ key: string; data: GscAnalytics } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const key = `${websiteId}|${sort}`;
  const data = result?.key === key ? result.data : null;
  const loading = websiteId !== null && data === null && error === null;

  useEffect(() => {
    let active = true;
    GscAPI.status(projectId).then(
      (next) => {
        if (!active) return;
        setStatus(next);
        setWebsiteId(next.websites.find((w) => w.property)?.website_id ?? null);
      },
      (cause: unknown) => active && setError(describeGscError(cause, "Could not load Search Console status.")),
    );
    return () => {
      active = false;
    };
  }, [projectId]);

  useEffect(() => {
    if (!websiteId) return;
    let active = true;
    const requested = `${websiteId}|${sort}`;
    GscAPI.analytics(websiteId, { sort, limit: 50 }).then(
      (next) => {
        if (!active) return;
        setResult({ key: requested, data: next });
        setError(null);
      },
      (cause: unknown) => active && setError(describeGscError(cause, "Could not load Search Console data.")),
    );
    return () => {
      active = false;
    };
  }, [websiteId, sort]);

  const loadMore = async () => {
    if (!websiteId || !data?.next_offset) return;
    const next = await GscAPI.analytics(websiteId, { sort, limit: 50, offset: data.next_offset });
    setResult({ key, data: { ...next, rows: [...data.rows, ...next.rows] } });
  };

  if (error && !status) return <p role="alert" className="text-sm text-[var(--coral)]">{error}</p>;
  if (!status) return <p aria-label="Loading performance" className="h-[200px] animate-pulse rounded-[8px] bg-[#EDF0EF]" />;
  const mapped = status.websites.filter((w) => w.property);
  const settings = `/projects/${projectId}/settings`;
  if (!mapped.length) {
    return (
      <div className="rounded-[8px] border border-[var(--line)] bg-white p-[14px] text-[12.8px] text-[#5C666C]">
        No Search Console data yet. {status.state === "connected" ? "Map a property to a website and sync it" : "Connect Google Search Console"} in{" "}
        <Link className="text-[var(--teal)] underline" href={settings}>project settings</Link>.
      </div>
    );
  }
  const site = mapped.find((w) => w.website_id === websiteId);
  return (
    <div>
      <div className="mb-[12px] flex flex-wrap items-center gap-[10px] text-[12.6px]">
        <label className="flex items-center gap-[6px]">
          Website
          <select aria-label="Website" className="rounded-[5px] border border-[var(--line)] bg-white px-[6px] py-[3px]"
            value={websiteId ?? ""} onChange={(e) => setWebsiteId(e.target.value)}>
            {mapped.map((w) => <option key={w.website_id} value={w.website_id}>{w.website_name} · {w.property?.site_url}</option>)}
          </select>
        </label>
        <label className="flex items-center gap-[6px]">
          Sort by
          <select aria-label="Sort by" className="rounded-[5px] border border-[var(--line)] bg-white px-[6px] py-[3px]"
            value={sort} onChange={(e) => setSort(e.target.value as typeof sort)}>
            {SORTS.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
          </select>
        </label>
        <span className="text-[var(--ink3)]">
          {site?.property?.last_synced_at ? `Last sync ${new Date(site.property.last_synced_at).toLocaleString("en-GB")}` : "Not synced yet"} ·{" "}
          <Link className="text-[var(--teal)] underline" href={settings}>Sync in settings</Link>
        </span>
      </div>
      {error ? <p role="alert" className="mb-[10px] text-[12.6px] text-[var(--coral)]">{error}</p> : null}
      {loading && !data ? <p aria-label="Loading rows" className="h-[160px] animate-pulse rounded-[8px] bg-[#EDF0EF]" /> : null}
      {data ? (
        data.totals.rows === 0 ? (
          <div className="rounded-[8px] border border-[var(--line)] bg-white p-[14px] text-[12.8px] text-[#5C666C]">
            No rows stored for {data.site_url} between {data.start_date} and {data.end_date}. Sync the website in project settings.
          </div>
        ) : (
          <>
            <div className="mb-[6px] text-[11.8px] text-[var(--ink3)]">
              {data.site_url} · {data.start_date} → {data.end_date} · by date, query and page
            </div>
            <div className="grid grid-cols-2 gap-[10px] md:grid-cols-4" aria-label="Totals">
              <Tile label="Clicks" value={number.format(data.totals.clicks)} />
              <Tile label="Impressions" value={number.format(data.totals.impressions)} />
              <Tile label="CTR" value={`${(data.totals.ctr * 100).toFixed(2)}%`} />
              <Tile label="Avg position (impression-weighted)" value={data.totals.position === null ? "—" : data.totals.position.toFixed(1)} />
            </div>
            <p className="m-[8px_0_12px] text-[11.5px] text-[var(--ink3)]">
              {number.format(data.totals.rows)} rows · {number.format(data.totals.queries)} queries · {number.format(data.totals.pages)} pages. Google
              leaves anonymized queries out of query-level data, so totals can be lower than the property totals in Search Console.
            </p>
            <div className="overflow-x-auto rounded-[8px] border border-[var(--line)] bg-white">
              <table className="w-full border-collapse text-left text-[12.4px]" aria-label="Search Console rows">
                <thead>
                  <tr className="border-b border-[var(--line2)] text-[11.5px] text-[var(--ink3)]">
                    {["Date", "Query", "Page", "Clicks", "Impressions", "CTR", "Position"].map((h) => (
                      <th key={h} className="px-[10px] py-[6px] font-normal">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {data.rows.map((r, i) => (
                    <tr key={`${r.date}-${r.query}-${r.page}-${i}`} className="border-b border-[var(--line2)] last:border-b-0">
                      <td className="whitespace-nowrap px-[10px] py-[5px]">{r.date}</td>
                      <td className="px-[10px] py-[5px]">{r.query || <span className="text-[var(--ink3)]">(empty)</span>}</td>
                      <td className="max-w-[320px] truncate px-[10px] py-[5px]" title={r.page}>{r.page}</td>
                      <td className="px-[10px] py-[5px]">{number.format(r.clicks)}</td>
                      <td className="px-[10px] py-[5px]">{number.format(r.impressions)}</td>
                      <td className="px-[10px] py-[5px]">{(r.ctr * 100).toFixed(2)}%</td>
                      <td className="px-[10px] py-[5px]">{r.position.toFixed(1)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {data.next_offset !== null ? (
              <button type="button" className="mt-[10px] rounded-[5px] border border-[var(--line)] bg-white px-[10px] py-[4px] text-[12.5px]" onClick={loadMore}>
                Load more rows
              </button>
            ) : null}
          </>
        )
      ) : null}
    </div>
  );
}

export function IterationLab({ projectId }: { projectId: string }) {
  return (
    <section className="animate-in fade-in duration-150">
      <div className="mb-[6px] text-[11.5px] text-[#8A949A]">Module · learned</div>
      <h1 className="m-0 font-serif text-[25px] font-medium tracking-tight text-[#12171A]">Iteration Lab</h1>
      <p className="m-[5px_0_0] max-w-[74ch] text-[13.4px] text-[#5C666C]">
        Search Console performance for this project&apos;s websites. Digest, experiments and detectors are not built yet.
      </p>
      <Tabs defaultValue="gsc" className="mt-[18px]">
        <TabsList variant="line" className="w-full justify-start rounded-none border-b border-[#D6DBD9] bg-transparent p-0">
          <TabsTrigger value="gsc">GSC Performance</TabsTrigger>
        </TabsList>
        <TabsContent value="gsc" className="mt-[18px]">
          <Performance projectId={projectId} />
        </TabsContent>
      </Tabs>
      <p className="mt-[18px] text-[12.4px] text-[#5C666C]">
        Evaluation runs for outlines, drafts and QA are in the{" "}
        <Link className="text-[var(--teal)] underline" href={`/projects/${projectId}/content-harness`}>Content Harness</Link>.
      </p>
    </section>
  );
}
