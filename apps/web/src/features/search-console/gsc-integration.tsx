"use client";

import { useCallback, useEffect, useState } from "react";

import type { GscAvailableProperty, GscStatus } from "@/lib/api-types";
import { ApiError } from "@/lib/client-api";
import { GscAPI } from "@/lib/gsc-api";

const btn =
  "rounded-[5px] border border-[var(--line)] bg-white px-[10px] py-[4px] text-[12.5px] text-[#12171A] hover:bg-[#F0F2F1] disabled:opacity-50";
const btnPrimary =
  "inline-block rounded-[5px] border border-[var(--teal)] bg-[var(--teal)] px-[10px] py-[4px] text-[12.5px] !text-white no-underline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--teal)] disabled:opacity-50";
const CHIP: Record<string, string> = {
  not_configured: "r",
  not_connected: "r",
  pending: "c",
  connected: "t",
  reauth_required: "c",
  disconnected: "r",
};

const STATE_LABEL: Record<GscStatus["state"] | "not_configured", string> = {
  not_configured: "Not configured",
  not_connected: "Not connected",
  pending: "Waiting for Google sign-in",
  connected: "Connected",
  reauth_required: "Reconnect needed",
  disconnected: "Disconnected",
};

/** Messages for codes the server or the OAuth redirect report. */
const ERROR_TEXT: Record<string, string> = {
  GSC_ACCESS_DENIED: "Google access was not granted.",
  GSC_AUTH_FAILED: "Google sign-in failed. Try again.",
  GSC_CONNECT_FAILED: "Could not start the Google sign-in.",
  GSC_NOT_CONFIGURED: "Google Search Console is not configured on the server.",
  GSC_OAUTH_STATE_INVALID: "That Google sign-in link was not valid. Start again.",
  GSC_OAUTH_STATE_EXPIRED: "The Google sign-in took too long. Start again.",
  GSC_NO_REFRESH_TOKEN: "Google did not grant offline access. Start again.",
  GSC_SCOPE_DENIED: "Search Console access was not granted. Start again and allow it.",
  PERMISSION_DENIED: "You do not have permission to manage this project's integrations.",
};

export function describeGscError(error: unknown, fallback: string): string {
  if (error instanceof ApiError) return ERROR_TEXT[error.code] ?? error.message ?? fallback;
  return error instanceof Error && error.message ? error.message : fallback;
}

function when(iso: string | null): string {
  return iso ? new Date(iso).toLocaleString("en-GB", { day: "numeric", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" }) : "never";
}

export function GscIntegration({ projectId, notice }: { projectId: string; notice?: { ok: boolean; code: string } }) {
  const [status, setStatus] = useState<GscStatus | null>(null);
  const [properties, setProperties] = useState<GscAvailableProperty[] | null>(null);
  const [choice, setChoice] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState<string | null>(null);
  const [message, setMessage] = useState<{ ok: boolean; text: string } | null>(
    notice ? { ok: notice.ok, text: notice.ok ? "Google Search Console connected." : ERROR_TEXT[notice.code] ?? `Google sign-in failed (${notice.code}).` } : null,
  );

  const load = useCallback(async () => {
    try {
      setStatus(await GscAPI.status(projectId));
    } catch (error) {
      setMessage({ ok: false, text: describeGscError(error, "Could not load the integration.") });
    }
  }, [projectId]);

  useEffect(() => {
    let active = true;
    GscAPI.status(projectId).then(
      (next) => active && setStatus(next),
      (error: unknown) => active && setMessage({ ok: false, text: describeGscError(error, "Could not load the integration.") }),
    );
    return () => {
      active = false;
    };
  }, [projectId]);

  const run = async (key: string, action: () => Promise<string>) => {
    setBusy(key);
    setMessage(null);
    try {
      const text = await action();
      setMessage({ ok: true, text });
    } catch (error) {
      setMessage({ ok: false, text: describeGscError(error, "The request failed.") });
    } finally {
      setBusy(null);
      await load();
    }
  };

  const connected = status?.state === "connected";
  const shownState = status ? (status.configured ? status.state : "not_configured") : null;
  const muted = "text-[var(--ink3)]";
  return (
    <section aria-label="Google Search Console" className="text-[12.8px]">
      <div className="flex flex-wrap items-center gap-[8px]">
        <h3 className="m-0 text-[13.5px] font-medium">Google Search Console</h3>
        {shownState ? (
          <span data-testid="gsc-state" className={`chip ${CHIP[shownState]}`}>
            {STATE_LABEL[shownState]}
          </span>
        ) : null}
      </div>
      <p className={`m-[3px_0_0] ${muted}`}>
        Read-only: imports clicks, impressions, CTR and position by date, query and page. Nothing is written to Google.
      </p>
      {message ? (
        <p role={message.ok ? "status" : "alert"} className={`mt-[8px] ${message.ok ? "text-[var(--teal)]" : "text-[var(--coral)]"}`}>
          {message.text}
        </p>
      ) : null}
      {!status ? (
        <p aria-label="Loading integration" className="mt-[10px] h-[64px] animate-pulse rounded-[6px] bg-[#EDF0EF]" />
      ) : !status.configured ? (
        <p className={`mt-[10px] ${muted}`}>
          Not configured on the server. An administrator sets the Google OAuth client and encryption key (GSC_* settings) first.
        </p>
      ) : (
        <>
          <div className="mt-[10px]">
            {status.google_account_email ? <div>Google account · {status.google_account_email}</div> : null}
            {status.connected_at ? <div className={muted}>Connected {when(status.connected_at)}</div> : null}
            {status.last_error && status.state === "reauth_required" ? <div className="text-[var(--coral)]">{status.last_error}</div> : null}
          </div>
          {status.can_manage ? (
            <div className="mt-[10px] flex flex-wrap gap-[6px]">
              {!connected ? (
                <a className={btnPrimary} href={GscAPI.connectUrl(projectId)}>
                  {status.state === "reauth_required" || status.state === "disconnected" ? "Reconnect Google" : "Connect Google"}
                </a>
              ) : (
                <>
                  <button type="button" className={btn} disabled={busy !== null}
                    onClick={() => run("properties", async () => {
                      const list = await GscAPI.properties(projectId);
                      setProperties(list.items);
                      return list.items.length ? `${list.items.length} Search Console propert${list.items.length === 1 ? "y" : "ies"} available.` : "This Google account has no verified Search Console properties.";
                    })}>
                    {busy === "properties" ? "Loading…" : "Load Search Console properties"}
                  </button>
                  <button type="button" className={btn} disabled={busy !== null}
                    onClick={() => run("disconnect", async () => {
                      await GscAPI.disconnect(projectId);
                      setProperties(null);
                      return "Disconnected. Synced data is kept.";
                    })}>
                    Disconnect
                  </button>
                </>
              )}
            </div>
          ) : (
            <p className={`mt-[10px] ${muted}`}>Only project managers can connect, map or sync.</p>
          )}

          <table className="mt-[14px] w-full border-collapse text-left" aria-label="Websites and Search Console properties">
            <thead>
              <tr className={`border-b border-[var(--line2)] text-[11.5px] ${muted}`}>
                <th className="py-[6px] pr-[10px] font-normal">Website</th>
                <th className="py-[6px] pr-[10px] font-normal">Search Console property</th>
                <th className="py-[6px] pr-[10px] font-normal">Sync</th>
                <th className="py-[6px] font-normal" />
              </tr>
            </thead>
            <tbody>
              {status.websites.length === 0 ? (
                <tr>
                  <td colSpan={4} className={`py-[10px] ${muted}`}>
                    This project has no websites yet. Add one in{" "}
                    <a className="text-[var(--teal)] underline" href={`/projects/${projectId}/website`}>Technical SEO › Websites</a>, then map it here.
                  </td>
                </tr>
              ) : (
                status.websites.map((w) => (
                  <tr key={w.website_id} className="border-b border-[var(--line2)] align-top last:border-b-0">
                    <td className="py-[8px] pr-[10px]">
                      <div className="font-medium">{w.website_name}</div>
                      <div className={`text-[11.5px] ${muted}`}>{w.base_url}</div>
                    </td>
                    <td className="py-[8px] pr-[10px]">
                      {w.property ? <div>{w.property.site_url}</div> : <div className={muted}>Not mapped</div>}
                      {connected && status.can_manage && properties ? (
                        <div className="mt-[4px] flex gap-[6px]">
                          <select aria-label={`Property for ${w.website_name}`} className="rounded-[5px] border border-[var(--line)] bg-white px-[6px] py-[3px] text-[12.5px]"
                            value={choice[w.website_id] ?? w.property?.site_url ?? ""}
                            onChange={(e) => setChoice((c) => ({ ...c, [w.website_id]: e.target.value }))}>
                            <option value="">Choose a property…</option>
                            {properties.map((p) => <option key={p.site_url} value={p.site_url}>{p.site_url}</option>)}
                          </select>
                          <button type="button" className={btn} disabled={busy !== null || !(choice[w.website_id] ?? "")}
                            onClick={() => run(`map-${w.website_id}`, async () => {
                              const mapped = await GscAPI.mapProperty(w.website_id, choice[w.website_id]);
                              return `${w.website_name} mapped to ${mapped.site_url}.`;
                            })}>
                            Save
                          </button>
                        </div>
                      ) : null}
                    </td>
                    <td className="py-[8px] pr-[10px] text-[11.8px]">
                      {busy === `sync-${w.website_id}` ? (
                        <span className="chip t" data-testid="sync-state">Syncing…</span>
                      ) : w.last_sync ? (
                        <>
                          <span className={`chip ${w.last_sync.status === "completed" ? "t" : "c"}`} data-testid="sync-state">
                            {w.last_sync.status === "completed" ? "Sync successful" : "Sync failed"}
                          </span>
                          <div className={`mt-[3px] ${muted}`}>
                            {when(w.last_sync.completed_at)} · {w.last_sync.start_date} → {w.last_sync.end_date} · {w.last_sync.rows_stored} rows
                            {w.last_sync.rows_rejected ? ` · ${w.last_sync.rows_rejected} rejected` : ""}
                            {w.last_sync.truncated ? " · truncated" : ""}
                          </div>
                          {w.last_sync.error ? <div className="text-[var(--coral)]">{w.last_sync.error}</div> : null}
                        </>
                      ) : (
                        <span className={muted}>Never synced</span>
                      )}
                      {w.property ? <div className={muted}>{w.property.stored_rows} rows stored</div> : null}
                    </td>
                    <td className="py-[8px] text-right">
                      {connected && status.can_manage && w.property ? (
                        <button type="button" className={btnPrimary} disabled={busy !== null}
                          onClick={() => run(`sync-${w.website_id}`, async () => {
                            const result = await GscAPI.sync(w.website_id);
                            return `Synced ${w.website_name}: ${result.rows_stored} rows for ${result.start_date} → ${result.end_date}${result.rows_rejected ? `, ${result.rows_rejected} rejected` : ""}.`;
                          })}>
                          {busy === `sync-${w.website_id}` ? "Syncing…" : "Sync last 28 days"}
                        </button>
                      ) : null}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
          {status.websites.length > 0 ? (
            <p className={`mt-[8px] text-[11.8px] ${muted}`}>
              Each website maps to one property. To map another property, add its website in{" "}
              <a className="text-[var(--teal)] underline" href={`/projects/${projectId}/website`}>Technical SEO › Websites</a>.
            </p>
          ) : null}
        </>
      )}
    </section>
  );
}
