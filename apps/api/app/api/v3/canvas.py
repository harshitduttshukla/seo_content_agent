"""V3 Canvas and immutable claim-edit routes."""

from uuid import UUID

from fastapi import APIRouter, Request, status

from app.api.dependencies import CurrentUserDep, SessionDep
from app.api.responses import success
from app.domains.canvas.schemas import (
    AreaResponse,
    ArgumentCreateRequest,
    CanvasAnchorUpsertRequest,
    CanvasClaimCreateRequest,
    CanvasFullResponse,
    CanvasListResponse,
    ClaimCitationCreateRequest,
    ClaimEditCheckResponse,
    ClaimEditConfirmRequest,
    ClaimEditConfirmResponse,
    ClaimResponse,
    ContentCardStub,
    DrilldownResponse,
)
from app.domains.canvas.service import CanvasService
from app.schemas.common import ApiResponse

router = APIRouter(tags=["v3_canvas"])


@router.get("/areas", response_model=ApiResponse[list[AreaResponse]])
async def list_areas(
    organization_id: UUID,
    project_id: UUID,
    request: Request,
    session: SessionDep,
    actor: CurrentUserDep,
    canvas_id: UUID | None = None,
) -> ApiResponse[list[AreaResponse]]:
    return success(
        request,
        await CanvasService(session).list_areas(
            organization_id, project_id, canvas_id=canvas_id, actor=actor
        ),
    )


@router.post(
    "/canvases",
    response_model=ApiResponse[CanvasFullResponse],
    status_code=status.HTTP_201_CREATED,
)
async def create_company_canvas(
    organization_id: UUID,
    project_id: UUID,
    request: Request,
    session: SessionDep,
    actor: CurrentUserDep,
) -> ApiResponse[CanvasFullResponse]:
    result = await CanvasService(session).create_company_canvas(
        organization_id,
        project_id,
        actor=actor,
    )
    return success(request, result)


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
    result = await CanvasService(session).get_canvas(
        organization_id, project_id, canvas_id, actor=actor
    )
    return success(request, result)


@router.post(
    "/canvases/{canvas_id}/anchors",
    response_model=ApiResponse[CanvasFullResponse],
    status_code=status.HTTP_201_CREATED,
)
async def upsert_canvas_anchor(
    canvas_id: UUID,
    payload: CanvasAnchorUpsertRequest,
    organization_id: UUID,
    project_id: UUID,
    request: Request,
    session: SessionDep,
    actor: CurrentUserDep,
) -> ApiResponse[CanvasFullResponse]:
    result = await CanvasService(session).upsert_anchor(
        organization_id, project_id, canvas_id, payload, actor=actor
    )
    return success(request, result)


@router.post(
    "/canvases/{canvas_id}/arguments",
    response_model=ApiResponse[CanvasFullResponse],
    status_code=status.HTTP_201_CREATED,
)
async def create_canvas_argument(
    canvas_id: UUID,
    payload: ArgumentCreateRequest,
    organization_id: UUID,
    project_id: UUID,
    request: Request,
    session: SessionDep,
    actor: CurrentUserDep,
) -> ApiResponse[CanvasFullResponse]:
    result = await CanvasService(session).create_argument(
        organization_id, project_id, canvas_id, payload, actor=actor
    )
    return success(request, result)


@router.post(
    "/canvases/{canvas_id}/claims",
    response_model=ApiResponse[CanvasFullResponse],
    status_code=status.HTTP_201_CREATED,
)
async def create_canvas_claim(
    canvas_id: UUID,
    payload: CanvasClaimCreateRequest,
    organization_id: UUID,
    project_id: UUID,
    request: Request,
    session: SessionDep,
    actor: CurrentUserDep,
) -> ApiResponse[CanvasFullResponse]:
    result = await CanvasService(session).create_claim(
        organization_id, project_id, canvas_id, payload, actor=actor
    )
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
    result = await CanvasService(session).get_claim_drilldown(
        organization_id, project_id, claim_id, actor=actor
    )
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
    result = await CanvasService(session).check_claim_edit(
        organization_id, project_id, claim_id, actor=actor
    )
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


@router.post(
    "/claims/{claim_id}/approve",
    response_model=ApiResponse[ClaimResponse],
)
async def approve_claim(
    claim_id: UUID,
    organization_id: UUID,
    project_id: UUID,
    request: Request,
    session: SessionDep,
    actor: CurrentUserDep,
) -> ApiResponse[ClaimResponse]:
    result = await CanvasService(session).approve_claim(
        organization_id, project_id, claim_id, actor=actor
    )
    return success(request, result)


@router.get(
    "/content-cards",
    response_model=ApiResponse[list[ContentCardStub]],
)
async def list_content_cards(
    organization_id: UUID,
    project_id: UUID,
    request: Request,
    session: SessionDep,
    actor: CurrentUserDep,
) -> ApiResponse[list[ContentCardStub]]:
    result = await CanvasService(session).list_content_cards(
        organization_id, project_id, actor=actor
    )
    return success(request, result)


@router.post(
    "/claims/{claim_id}/citations",
    response_model=ApiResponse[DrilldownResponse],
    status_code=status.HTTP_201_CREATED,
)
async def add_claim_citation(
    claim_id: UUID,
    payload: ClaimCitationCreateRequest,
    organization_id: UUID,
    project_id: UUID,
    request: Request,
    session: SessionDep,
    actor: CurrentUserDep,
) -> ApiResponse[DrilldownResponse]:
    result = await CanvasService(session).add_citation(
        organization_id, project_id, claim_id, payload, actor=actor
    )
    return success(request, result)
