import type {
  BulkUpdateResponse,
  CanvasDetail,
  CanvasListResponse,
  ClaimDrilldown,
  ClaimEditCheckResponse,
  ClaimEditConfirm,
  ClaimEditConfirmResponse,
  DemandImportItem,
  DemandImportResponse,
  DemandListResponse,
  SiteImportResponse,
  SiteImportStatusResponse,
} from "./api-types";
import { clientApi } from "./client-api";

export interface V3Scope {
  organizationId: string;
  projectId: string;
}

function scopedPath(scope: V3Scope, path: string): string {
  const query = new URLSearchParams({
    organization_id: scope.organizationId,
    project_id: scope.projectId,
  });
  return `/v3${path}?${query.toString()}`;
}

export const V3API = {
  canvas: {
    list: (scope: V3Scope): Promise<CanvasListResponse> =>
      clientApi(scopedPath(scope, "/canvases")),
    get: (scope: V3Scope, canvasId: string): Promise<CanvasDetail> =>
      clientApi(scopedPath(scope, `/canvases/${canvasId}`)),
    getClaimDrilldown: (scope: V3Scope, claimId: string): Promise<ClaimDrilldown> =>
      clientApi(scopedPath(scope, `/claims/${claimId}/drilldown`)),
    checkClaimEdit: (scope: V3Scope, claimId: string): Promise<ClaimEditCheckResponse> =>
      clientApi(scopedPath(scope, `/claims/${claimId}/edit/check`), { method: "POST" }),
    confirmClaimEdit: (
      scope: V3Scope,
      claimId: string,
      data: ClaimEditConfirm,
    ): Promise<ClaimEditConfirmResponse> =>
      clientApi(scopedPath(scope, `/claims/${claimId}/edit/confirm`), {
        method: "POST",
        body: JSON.stringify(data),
      }),
  },
  demand: {
    list: (scope: V3Scope, status?: string): Promise<DemandListResponse> => {
      const path = scopedPath(scope, "/demand");
      return clientApi(status ? `${path}&status=${encodeURIComponent(status)}` : path);
    },
    bulkSetPendingClassify: (
      scope: V3Scope,
      nodeIds: string[],
    ): Promise<BulkUpdateResponse> =>
      clientApi(scopedPath(scope, "/demand/bulk/pending-classify"), {
        method: "POST",
        body: JSON.stringify({ node_ids: nodeIds }),
      }),
    importCsv: (scope: V3Scope, items: DemandImportItem[]): Promise<DemandImportResponse> =>
      clientApi(scopedPath(scope, "/demand/import"), {
        method: "POST",
        body: JSON.stringify({ items }),
      }),
    bulkReassign: (
      scope: V3Scope,
      nodeIds: string[],
      areaId: string,
    ): Promise<BulkUpdateResponse> =>
      clientApi(scopedPath(scope, "/demand/bulk/reassign"), {
        method: "POST",
        body: JSON.stringify({ node_ids: nodeIds, area_id: areaId }),
      }),
  },
  siteImport: {
    runImport: (scope: V3Scope, url: string): Promise<SiteImportResponse> =>
      clientApi(scopedPath(scope, "/site-import/run"), {
        method: "POST",
        body: JSON.stringify({ url }),
      }),
    getStatus: (scope: V3Scope, jobId: string): Promise<SiteImportStatusResponse> =>
      clientApi(scopedPath(scope, `/site-import/${jobId}/status`)),
  },
};
