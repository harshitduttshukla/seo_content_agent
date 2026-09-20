"""V3 Demand read and bulk-action routes."""

from uuid import UUID

from fastapi import APIRouter, Query, Request

from app.api.dependencies import CurrentUserDep, SessionDep
from app.api.responses import success
from app.domains.demand.schemas import (
    BulkUpdateResponse,
    DemandImportRequest,
    DemandImportResponse,
    DemandNodeListResponse,
    DemandReassignRequest,
    PendingClassifyRequest,
)
from app.domains.demand.service import DemandService
from app.schemas.common import ApiResponse

router = APIRouter(tags=["v3_demand"])


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


@router.get("/demand", response_model=ApiResponse[DemandNodeListResponse])
async def list_demand(
    organization_id: UUID,
    project_id: UUID,
    request: Request,
    session: SessionDep,
    actor: CurrentUserDep,
    status: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=100, ge=1, le=100),
) -> ApiResponse[DemandNodeListResponse]:
    result = await DemandService(session).list_nodes(
        organization_id,
        project_id,
        status=status,
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
