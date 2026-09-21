import type {
  BulkUpdateResponse,
  Area,
  CanvasAnchorInput,
  CanvasArgumentInput,
  CanvasClaimInput,
  CanvasDetail,
  CanvasListResponse,
  ClaimBase,
  ClaimCitationInput,
  ClaimDrilldown,
  ClaimEditCheckResponse,
  ClaimEditConfirm,
  ClaimEditConfirmResponse,
  ContentCardStub,
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
  areas: {
    list: (scope: V3Scope, canvasId?: string): Promise<Area[]> => {
      const path = scopedPath(scope, "/areas");
      return clientApi(canvasId ? `${path}&canvas_id=${encodeURIComponent(canvasId)}` : path);
    },
  },
  canvas: {
    createCompany: (scope: V3Scope): Promise<CanvasDetail> =>
      clientApi(scopedPath(scope, "/canvases"), { method: "POST" }),
    upsertAnchor: (scope: V3Scope, canvasId: string, data: CanvasAnchorInput): Promise<CanvasDetail> =>
      clientApi(scopedPath(scope, `/canvases/${canvasId}/anchors`), {
        method: "POST",
        body: JSON.stringify(data),
      }),
    createArgument: (scope: V3Scope, canvasId: string, data: CanvasArgumentInput): Promise<CanvasDetail> =>
      clientApi(scopedPath(scope, `/canvases/${canvasId}/arguments`), {
        method: "POST",
        body: JSON.stringify(data),
      }),
    createClaim: (scope: V3Scope, canvasId: string, data: CanvasClaimInput): Promise<CanvasDetail> =>
      clientApi(scopedPath(scope, `/canvases/${canvasId}/claims`), {
        method: "POST",
        body: JSON.stringify(data),
      }),
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
    approveClaim: (scope: V3Scope, claimId: string): Promise<ClaimBase> =>
      clientApi(scopedPath(scope, `/claims/${claimId}/approve`), { method: "POST" }),
    listContentCards: (scope: V3Scope): Promise<ContentCardStub[]> =>
      clientApi(scopedPath(scope, "/content-cards")),
    addCitation: (
      scope: V3Scope,
      claimId: string,
      data: ClaimCitationInput,
    ): Promise<ClaimDrilldown> =>
      clientApi(scopedPath(scope, `/claims/${claimId}/citations`), {
        method: "POST",
        body: JSON.stringify(data),
      }),
  },
  demand: {
    list: (scope: V3Scope, filters: Record<string, string> = {}): Promise<DemandListResponse> => {
      const path = scopedPath(scope, "/demand");
      const query = new URLSearchParams(Object.entries(filters).filter(([, value]) => value));
      return clientApi(query.size ? `${path}&${query.toString()}` : path);
    },
    bulkSetPendingClassify: (
      scope: V3Scope,
      nodeIds: string[],
    ): Promise<BulkUpdateResponse> =>
      clientApi(scopedPath(scope, "/demand/bulk/pending-classify"), {
        method: "POST",
        body: JSON.stringify({ node_ids: nodeIds }),
      }),
    bulkAction: (scope: V3Scope, ids: string[], action: "keep" | "discard" | "reassign_area" | "set_argument", destinationId?: string): Promise<BulkUpdateResponse> =>
      clientApi(scopedPath(scope, "/demand/bulk"), {
        method: "POST",
        body: JSON.stringify({ ids, action, ...(action === "reassign_area" ? { area_id: destinationId } : action === "set_argument" ? { argument_id: destinationId } : {}) }),
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
