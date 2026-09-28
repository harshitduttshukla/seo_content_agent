"""V3 Demand read and bulk-action routes."""

from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Query, Request

from app.api.dependencies import CurrentUserDep, SessionDep
from app.api.responses import success
from app.domains.demand.schemas import (
    BulkActionRequest,
    BulkUpdateResponse,
    DemandCsvMappingResponse,
    DemandImportRequest,
    DemandImportResponse,
    DemandNodeListResponse,
    DemandReassignRequest,
    PendingClassifyRequest,
    PlanPreviewResponse,
    PlanRequest,
    PlanResultResponse,
)
from app.domains.demand.service import DemandService
from app.schemas.common import ApiResponse

router = APIRouter(tags=["v3_demand"])


@router.post("/demand/bulk", response_model=ApiResponse[BulkUpdateResponse])
async def bulk_action(
    payload: BulkActionRequest,
    organization_id: UUID,
    project_id: UUID,
    request: Request,
    session: SessionDep,
    actor: CurrentUserDep,
) -> ApiResponse[BulkUpdateResponse]:
    return success(
        request,
        await DemandService(session).bulk_action(organization_id, project_id, payload, actor),
    )


@router.post("/demand/import", response_model=ApiResponse[DemandImportResponse])
async def import_demand(
    payload: DemandImportRequest,
    organization_id: UUID,
    project_id: UUID,
    request: Request,
    session: SessionDep,
    actor: CurrentUserDep,
) -> ApiResponse[DemandImportResponse]:
    result = await DemandService(session).import_nodes(
        organization_id, project_id, payload, actor=actor
    )
    return success(request, result)


@router.get("/demand/csv-mapping", response_model=ApiResponse[DemandCsvMappingResponse])
async def get_demand_csv_mapping(
    organization_id: UUID,
    project_id: UUID,
    request: Request,
    session: SessionDep,
    actor: CurrentUserDep,
) -> ApiResponse[DemandCsvMappingResponse]:
    return success(
        request, await DemandService(session).get_csv_mapping(organization_id, project_id, actor)
    )


@router.get("/demand", response_model=ApiResponse[DemandNodeListResponse])
async def list_demand(
    organization_id: UUID,
    project_id: UUID,
    request: Request,
    session: SessionDep,
    actor: CurrentUserDep,
    status: str | None = None,
    origin: str | None = None,
    area_id: UUID | None = None,
    argument_id: UUID | None = None,
    type: str | None = None,
    funnel: str | None = None,
    sort: Literal["confidence_asc"] = "confidence_asc",
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=100, ge=1, le=100),
) -> ApiResponse[DemandNodeListResponse]:
    # The repository currently supports this single, review-queue ordering.
    # Keeping it explicit in the public contract prevents callers from
    # assuming that arbitrary field ordering is available.
    del sort
    result = await DemandService(session).list_nodes(
        organization_id,
        project_id,
        status=status,
        origin=origin,
        area_id=area_id,
        argument_id=argument_id,
        node_type=type,
        funnel=funnel,
        page=page,
        page_size=page_size,
        actor=actor,
    )
    return success(request, result)


@router.post(
    "/demand/bulk/pending-classify",
    response_model=ApiResponse[BulkUpdateResponse],
)
async def bulk_pending_classify(
    payload: PendingClassifyRequest,
    organization_id: UUID,
    project_id: UUID,
    request: Request,
    session: SessionDep,
    actor: CurrentUserDep,
) -> ApiResponse[BulkUpdateResponse]:
    result = await DemandService(session).bulk_set_pending_classify(
        organization_id, project_id, payload.node_ids, actor=actor
    )
    return success(request, result)


@router.post(
    "/demand/bulk/reassign",
    response_model=ApiResponse[BulkUpdateResponse],
)
async def bulk_reassign(
    payload: DemandReassignRequest,
    organization_id: UUID,
    project_id: UUID,
    request: Request,
    session: SessionDep,
    actor: CurrentUserDep,
) -> ApiResponse[BulkUpdateResponse]:
    result = await DemandService(session).bulk_reassign_area(
        organization_id,
        project_id,
        payload.node_ids,
        payload.area_id,
        actor=actor,
    )
    return success(request, result)


@router.post("/demand/plan/preview", response_model=ApiResponse[PlanPreviewResponse])
async def preview_plan(
    payload: PlanRequest,
    organization_id: UUID,
    project_id: UUID,
    request: Request,
    session: SessionDep,
    actor: CurrentUserDep,
) -> ApiResponse[PlanPreviewResponse]:
    """What Plan would create from the selected nodes. Writes nothing."""
    result = await DemandService(session).preview_plan(
        organization_id, project_id, payload.node_ids, actor=actor
    )
    return success(request, result)


@router.post("/demand/plan", response_model=ApiResponse[PlanResultResponse])
async def confirm_plan(
    payload: PlanRequest,
    organization_id: UUID,
    project_id: UUID,
    request: Request,
    session: SessionDep,
    actor: CurrentUserDep,
) -> ApiResponse[PlanResultResponse]:
    """Create the planned cards atomically, after a human confirmed the preview."""
    result = await DemandService(session).confirm_plan(
        organization_id, project_id, payload.node_ids, actor=actor
    )
    return success(request, result)
