import type { GscAnalytics, GscAvailableProperty, GscMappedProperty, GscStatus, GscSyncRun } from "@/lib/api-types";
import { clientApi } from "@/lib/client-api";

/** Read-only Google Search Console endpoints (/api/v1). Tokens never reach the browser. */
export const GscAPI = {
  status: (projectId: string): Promise<GscStatus> => clientApi(`/projects/${projectId}/search-console`),
  /** Browser navigation target that starts Google consent (server-side route handler). */
  connectUrl: (projectId: string): string => `/api/integrations/google/start?project=${encodeURIComponent(projectId)}`,
  disconnect: (projectId: string): Promise<GscStatus> =>
    clientApi(`/projects/${projectId}/search-console/connection`, { method: "DELETE" }),
  properties: (projectId: string): Promise<{ items: GscAvailableProperty[] }> =>
    clientApi(`/projects/${projectId}/search-console/properties`),
  mapProperty: (websiteId: string, siteUrl: string): Promise<GscMappedProperty> =>
    clientApi(`/websites/${websiteId}/search-console/property`, {
      method: "PUT",
      body: JSON.stringify({ site_url: siteUrl }),
    }),
  /** No dates: the server uses the last 28 days ending two days ago. */
  sync: (websiteId: string): Promise<GscSyncRun> =>
    clientApi(`/websites/${websiteId}/search-console/sync`, { method: "POST", body: JSON.stringify({}) }),
  analytics: (
    websiteId: string,
    params: { sort?: string; limit?: number; offset?: number } = {},
  ): Promise<GscAnalytics> => {
    const query = new URLSearchParams(
      Object.entries(params)
        .filter(([, v]) => v !== undefined)
        .map(([k, v]) => [k, String(v)]),
    );
    return clientApi(`/websites/${websiteId}/search-console/analytics${query.size ? `?${query}` : ""}`);
  },
};
