import type {
  BoardCard,
  BoardFilters,
  BundleBuildResponse,
  CardDetail,
  DraftGenerateResponse,
  G1DecisionResponse,
  G1Reason,
  OutlineProposal,
  OutlineSaveResponse,
  OutlineV3,
  BulkUpdateResponse,
  BrandKit,
  BrandKitDetail,
  BrandKitInput,
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
  ContentHubBoard,
  DemandImportItem,
  DemandImportResponse,
  DemandListResponse,
  SiteImportResponse,
  SiteImportStatusResponse,
  SocialProof,
  PlanLockState,
  PlanPreview,
  PlanResult,
  StrategyMap,
  SocialProofInput,
  VoiceSnippet,
  VoiceSnippetInput,
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
    /** Plan preview: what cards the selection would create. Writes nothing. */
    previewPlan: (scope: V3Scope, nodeIds: string[]): Promise<PlanPreview> =>
      clientApi(scopedPath(scope, "/demand/plan/preview"), {
        method: "POST",
        body: JSON.stringify({ node_ids: nodeIds }),
      }),
    /** Plan confirm: creates the planned cards atomically. */
    confirmPlan: (scope: V3Scope, nodeIds: string[]): Promise<PlanResult> =>
      clientApi(scopedPath(scope, "/demand/plan"), {
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
  planLock: {
    /** Lock the Content Hub plan. No body: the server sets the time, once. */
    lock: (scope: V3Scope): Promise<PlanLockState> =>
      clientApi(scopedPath(scope, "/plan/lock"), { method: "POST" }),
  },
  contentHub: {
    board: (scope: V3Scope, filters: BoardFilters = {}): Promise<ContentHubBoard> => {
      const path = scopedPath(scope, "/content-hub/board");
      const query = new URLSearchParams(
        Object.entries(filters).filter((entry): entry is [string, string] => Boolean(entry[1])),
      );
      return clientApi(query.size ? `${path}&${query.toString()}` : path);
    },
    /** Backlog ↔ Planned only; the server refuses every other move. */
    moveCard: (
      scope: V3Scope,
      cardId: string,
      targetState: "backlog" | "planned",
      revision: number,
    ): Promise<BoardCard> =>
      clientApi(scopedPath(scope, `/content-hub/cards/${cardId}/move`), {
        method: "POST",
        body: JSON.stringify({ target_state: targetState, revision }),
      }),
    card: (scope: V3Scope, cardId: string): Promise<CardDetail> =>
      clientApi(scopedPath(scope, `/content-hub/cards/${cardId}`)),
    /** planned → bundled on first build; reuses the stored bundle while it is current. */
    buildBundle: (scope: V3Scope, cardId: string, revision: number): Promise<BundleBuildResponse> =>
      clientApi(scopedPath(scope, `/content-hub/cards/${cardId}/bundle`), {
        method: "POST",
        body: JSON.stringify({ revision }),
      }),
    /** A proposal only: the card is not changed until saveOutline. */
    generateOutline: (scope: V3Scope, cardId: string): Promise<OutlineProposal> =>
      clientApi(scopedPath(scope, `/content-hub/cards/${cardId}/outline/generate`), {
        method: "POST",
        body: JSON.stringify({}),
      }),
    /** First valid save moves bundled → outlined. 409 when `revision` is stale. */
    saveOutline: (scope: V3Scope, cardId: string, outline: OutlineV3, revision: number): Promise<OutlineSaveResponse> =>
      clientApi(scopedPath(scope, `/content-hub/cards/${cardId}/outline`), {
        method: "PUT",
        body: JSON.stringify({ outline, revision }),
      }),
    /** G1 pass: outlined → drafting. 409 when checks fail or `revision` is stale. */
    approveG1: (scope: V3Scope, cardId: string, revision: number): Promise<G1DecisionResponse> =>
      clientApi(scopedPath(scope, `/content-hub/cards/${cardId}/g1/approve`), {
        method: "POST",
        body: JSON.stringify({ revision }),
      }),
    /** G1 send-back: the card stays outlined; feedback is required. */
    sendBackG1: (
      scope: V3Scope,
      cardId: string,
      revision: number,
      reason: G1Reason,
      feedback: string,
    ): Promise<G1DecisionResponse> =>
      clientApi(scopedPath(scope, `/content-hub/cards/${cardId}/g1/send-back`), {
        method: "POST",
        body: JSON.stringify({ revision, reason, feedback }),
      }),
    /** Drafts a G1-approved card from its stored, current bundle; stores only a valid draft. */
    generateDraft: (scope: V3Scope, cardId: string, revision: number): Promise<DraftGenerateResponse> =>
      clientApi(scopedPath(scope, `/content-hub/cards/${cardId}/draft/generate`), {
        method: "POST",
        body: JSON.stringify({ revision }),
      }),
    /** The whole Planned column, top first; returns the refreshed unfiltered board. */
    reorderPlanned: (scope: V3Scope, cardIds: string[]): Promise<ContentHubBoard> =>
      clientApi(scopedPath(scope, "/content-hub/planned/order"), {
        method: "PUT",
        body: JSON.stringify({ card_ids: cardIds }),
      }),
  },
  strategyMap: {
    get: (scope: V3Scope): Promise<StrategyMap> => clientApi(scopedPath(scope, "/strategy/map")),
  },
  brandKit: {
    get: (scope: V3Scope): Promise<BrandKitDetail> => clientApi(scopedPath(scope, "/brand-kit")),
    save: (scope: V3Scope, data: BrandKitInput): Promise<BrandKit> =>
      clientApi(scopedPath(scope, "/brand-kit"), { method: "PUT", body: JSON.stringify(data) }),
    addVoiceSnippet: (scope: V3Scope, data: VoiceSnippetInput): Promise<VoiceSnippet> =>
      clientApi(scopedPath(scope, "/brand-kit/voice-snippets"), { method: "POST", body: JSON.stringify(data) }),
    addSocialProof: (scope: V3Scope, data: SocialProofInput): Promise<SocialProof> =>
      clientApi(scopedPath(scope, "/brand-kit/social-proofs"), { method: "POST", body: JSON.stringify(data) }),
  },
};
