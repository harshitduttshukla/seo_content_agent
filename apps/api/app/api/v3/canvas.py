"""V3 Canvas and immutable claim-edit routes."""

from uuid import UUID

from fastapi import APIRouter, Request

from app.api.dependencies import CurrentUserDep, SessionDep
from app.api.responses import success
from app.domains.canvas.schemas import (
    CanvasFullResponse,
    CanvasListResponse,
    ClaimEditCheckResponse,
    ClaimEditConfirmRequest,
    ClaimEditConfirmResponse,
    DrilldownResponse,
)
from app.domains.canvas.service import CanvasService
from app.schemas.common import ApiResponse

router = APIRouter(tags=["v3_canvas"])


@router.get("/canvases", response_model=ApiResponse[CanvasListResponse])
async def list_canvases(
    organization_id: UUID,
    project_id: UUID,
    request: Request,
    session: SessionDep,
    actor: CurrentUserDep,
) -> ApiResponse[CanvasListResponse]:
    result = await CanvasService(session).list_canvases(organization_id, project_id, actor=actor)
    return success(request, result)


@router.get("/canvases/{canvas_id}", response_model=ApiResponse[CanvasFullResponse])
async def get_canvas(
    canvas_id: UUID,
    organization_id: UUID,
    project_id: UUID,
    request: Request,
    session: SessionDep,
    actor: CurrentUserDep,
) -> ApiResponse[CanvasFullResponse]:
    result = await CanvasService(session).get_canvas(organization_id, project_id, canvas_id, actor=actor)
    return success(request, result)


@router.get(
    "/claims/{claim_id}/drilldown",
    response_model=ApiResponse[DrilldownResponse],
)
async def get_claim_drilldown(
    claim_id: UUID,
    organization_id: UUID,
    project_id: UUID,
    request: Request,
    session: SessionDep,
    actor: CurrentUserDep,
) -> ApiResponse[DrilldownResponse]:
    result = await CanvasService(session).get_claim_drilldown(organization_id, project_id, claim_id, actor=actor)
    return success(request, result)


@router.post(
    "/claims/{claim_id}/edit/check",
    response_model=ApiResponse[ClaimEditCheckResponse],
)
async def check_claim_edit(
    claim_id: UUID,
    organization_id: UUID,
    project_id: UUID,
    request: Request,
    session: SessionDep,
    actor: CurrentUserDep,
) -> ApiResponse[ClaimEditCheckResponse]:
    result = await CanvasService(session).check_claim_edit(organization_id, project_id, claim_id, actor=actor)
    return success(request, result)


@router.post(
    "/claims/{claim_id}/edit/confirm",
    response_model=ApiResponse[ClaimEditConfirmResponse],
)
async def confirm_claim_edit(
    claim_id: UUID,
    payload: ClaimEditConfirmRequest,
    organization_id: UUID,
    project_id: UUID,
    request: Request,
    session: SessionDep,
    actor: CurrentUserDep,
) -> ApiResponse[ClaimEditConfirmResponse]:
    result = await CanvasService(session).confirm_claim_edit(
        organization_id,
        project_id,
        claim_id,
        payload.text,
        payload.evidence,
        actor=actor,
    )
    return success(request, result)
