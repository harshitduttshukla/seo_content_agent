"use client";

import { useState } from "react";

import { Button } from "@/components/button";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import type { SiteImportStatusResponse } from "@/lib/api-types";
import { V3API, type V3Scope } from "@/lib/v3-api";

export function SiteImportTab({ scope }: { scope: V3Scope }) {
  const [importing, setImporting] = useState(false);
  const [url, setUrl] = useState("https://example.com");
  const [status, setStatus] = useState<SiteImportStatusResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function handleImport() {
    setImporting(true);
    setError(null);
    try {
      const started = await V3API.siteImport.runImport(scope, url);
      setStatus(await V3API.siteImport.getStatus(scope, started.job_run_id));
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Site import failed.");
    } finally {
      setImporting(false);
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <Alert>
        <AlertTitle>Import-first workspace</AlertTitle>
        <AlertDescription>
          Every imported URL becomes one idempotent Content Card; reruns update job history without duplicating cards.
        </AlertDescription>
      </Alert>
      {error ? (
        <Alert variant="destructive"><AlertTitle>Import failed</AlertTitle><AlertDescription>{error}</AlertDescription></Alert>
      ) : null}
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="text-[15px]">Site source</CardTitle>
            <CardDescription>Enter the canonical site URL, then run or re-run the import.</CardDescription>
          </CardHeader>
          <CardContent className="grid gap-4">
            <div className="flex gap-2">
              <Input value={url} onChange={(event) => setUrl(event.target.value)} placeholder="https://…" />
              <Button variant="primary" disabled={importing || !url} onClick={() => void handleImport()}>
                {importing ? "Importing…" : status ? "Re-run" : "Run import"}
              </Button>
            </div>
            <p className="text-xs text-muted-foreground">Job prompt contract: v3.site-import.v1</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle className="text-[15px]">Latest run</CardTitle>
            <CardDescription>Observed backend state for this browser session.</CardDescription>
          </CardHeader>
          <CardContent>
            {status ? (
              <dl className="grid grid-cols-2 gap-4 text-sm">
                <div><dt className="text-muted-foreground">Status</dt><dd className="font-medium">{status.status}</dd></div>
                <div><dt className="text-muted-foreground">Unmapped</dt><dd className="font-mono text-xl">{status.unmapped_count}</dd></div>
                <div><dt className="text-muted-foreground">Created</dt><dd>{status.created_count}</dd></div>
                <div><dt className="text-muted-foreground">Already existed</dt><dd>{status.existing_count}</dd></div>
              </dl>
            ) : (
              <p className="text-sm text-muted-foreground">Run an import to load live status.</p>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
