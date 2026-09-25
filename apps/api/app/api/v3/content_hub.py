"""V3 Content Hub plan board routes (handoff §5.1).

Read the board; move a card Backlog ↔ Planned; reorder Planned. Locking the plan
stays on ``POST /plan/lock``. Card detail and the Bundle → Outline → G1 → Draft
workflow (planned → bundled → outlined → drafting), QA, repair, section regeneration
and G2 (→ qa_failed / qa_passed → approved) live under ``/cards/{card_id}``; the
detail read carries review state, the stored draft and the QA report. Nothing here
publishes. No route here
sets an arbitrary state.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Path, Request

from app.api.dependencies import CurrentUserDep, SessionDep
from app.api.responses import success
from app.domains.content_cards.hub_service import ContentHubService
from app.domains.content_cards.production_service import ProductionService
from app.domains.content_cards.schemas import (
    BoardCard,
    BoardFilters,
    BoardMoveRequest,
    ContentHubBoard,
    PlannedOrderRequest,
)
from app.domains.content_cards.workflow_schemas import (
    BundleBuildRequest,
    BundleBuildResponse,
    CardDetail,
    DraftGenerateRequest,
    DraftGenerateResponse,
    DraftRevisionResponse,
    G1ApproveRequest,
    G1DecisionResponse,
    G1SendBackRequest,
    G2ApproveRequest,
    G2SendBackRequest,
    OutlineGenerateRequest,
    OutlineProposal,
    OutlineSaveRequest,
    OutlineSaveResponse,
    QARunRequest,
    QARunResponse,
    RepairRequest,
    SectionRegenerateRequest,
    WarningDismissRequest,
    WarningDismissResponse,
)
from app.domains.content_cards.workflow_service import CardWorkflowService
from app.schemas.common import ApiResponse

router = APIRouter(prefix="/content-hub", tags=["v3_content_hub"])


@router.get("/board", response_model=ApiResponse[ContentHubBoard])
async def get_board(
    organization_id: UUID,
    project_id: UUID,
    filters: Annotated[BoardFilters, Depends()],
    request: Request,
    session: SessionDep,
    actor: CurrentUserDep,
) -> ApiResponse[ContentHubBoard]:
    result = await ContentHubService(session).get_board(
        organization_id, project_id, filters, actor=actor
    )
    return success(request, result)


@router.post("/cards/{card_id}/move", response_model=ApiResponse[BoardCard])
async def move_card(
    card_id: UUID,
    payload: BoardMoveRequest,
    organization_id: UUID,
    project_id: UUID,
    request: Request,
    session: SessionDep,
    actor: CurrentUserDep,
) -> ApiResponse[BoardCard]:
    result = await ContentHubService(session).move_card(
        organization_id,
        project_id,
        card_id,
        payload,
        actor=actor,
        request_id=request.state.request_id,
    )
    return success(request, result)


@router.put("/planned/order", response_model=ApiResponse[ContentHubBoard])
async def reorder_planned(
    payload: PlannedOrderRequest,
    organization_id: UUID,
    project_id: UUID,
    request: Request,
    session: SessionDep,
    actor: CurrentUserDep,
) -> ApiResponse[ContentHubBoard]:
    result = await ContentHubService(session).reorder_planned(
        organization_id, project_id, payload, actor=actor, request_id=request.state.request_id
    )
    return success(request, result)


@router.get("/cards/{card_id}", response_model=ApiResponse[CardDetail])
async def get_card(
    card_id: UUID,
    organization_id: UUID,
    project_id: UUID,
    request: Request,
    session: SessionDep,
    actor: CurrentUserDep,
) -> ApiResponse[CardDetail]:
    result = await CardWorkflowService(session).get_detail(
        organization_id, project_id, card_id, actor=actor
    )
    return success(request, result)


@router.post("/cards/{card_id}/bundle", response_model=ApiResponse[BundleBuildResponse])
async def build_bundle(
    card_id: UUID,
    payload: BundleBuildRequest,
    organization_id: UUID,
    project_id: UUID,
    request: Request,
    session: SessionDep,
    actor: CurrentUserDep,
) -> ApiResponse[BundleBuildResponse]:
    result = await CardWorkflowService(session).build_bundle(
        organization_id,
        project_id,
        card_id,
        payload,
        actor=actor,
        request_id=request.state.request_id,
    )
    return success(request, result)


@router.post("/cards/{card_id}/outline/generate", response_model=ApiResponse[OutlineProposal])
async def generate_outline(
    card_id: UUID,
    payload: OutlineGenerateRequest,
    organization_id: UUID,
    project_id: UUID,
    request: Request,
    session: SessionDep,
    actor: CurrentUserDep,
) -> ApiResponse[OutlineProposal]:
    result = await CardWorkflowService(session).generate_outline(
        organization_id, project_id, card_id, payload, actor=actor
    )
    return success(request, result)


@router.put("/cards/{card_id}/outline", response_model=ApiResponse[OutlineSaveResponse])
async def save_outline(
    card_id: UUID,
    payload: OutlineSaveRequest,
    organization_id: UUID,
    project_id: UUID,
    request: Request,
    session: SessionDep,
    actor: CurrentUserDep,
) -> ApiResponse[OutlineSaveResponse]:
    result = await CardWorkflowService(session).save_outline(
        organization_id,
        project_id,
        card_id,
        payload,
        actor=actor,
        request_id=request.state.request_id,
    )
    return success(request, result)


@router.post("/cards/{card_id}/g1/approve", response_model=ApiResponse[G1DecisionResponse])
async def approve_g1(
    card_id: UUID,
    payload: G1ApproveRequest,
    organization_id: UUID,
    project_id: UUID,
    request: Request,
    session: SessionDep,
    actor: CurrentUserDep,
) -> ApiResponse[G1DecisionResponse]:
    result = await CardWorkflowService(session).approve_g1(
        organization_id,
        project_id,
        card_id,
        payload,
        actor=actor,
        request_id=request.state.request_id,
    )
    return success(request, result)


@router.post("/cards/{card_id}/g1/send-back", response_model=ApiResponse[G1DecisionResponse])
async def send_back_g1(
    card_id: UUID,
    payload: G1SendBackRequest,
    organization_id: UUID,
    project_id: UUID,
    request: Request,
    session: SessionDep,
    actor: CurrentUserDep,
) -> ApiResponse[G1DecisionResponse]:
    result = await CardWorkflowService(session).send_back_g1(
        organization_id,
        project_id,
        card_id,
        payload,
        actor=actor,
        request_id=request.state.request_id,
    )
    return success(request, result)


@router.post("/cards/{card_id}/draft/generate", response_model=ApiResponse[DraftGenerateResponse])
async def generate_draft(
    card_id: UUID,
    payload: DraftGenerateRequest,
    organization_id: UUID,
    project_id: UUID,
    request: Request,
    session: SessionDep,
    actor: CurrentUserDep,
) -> ApiResponse[DraftGenerateResponse]:
    result = await CardWorkflowService(session).generate_draft(
        organization_id,
        project_id,
        card_id,
        payload,
        actor=actor,
        request_id=request.state.request_id,
    )
    return success(request, result)


@router.post("/cards/{card_id}/qa/run", response_model=ApiResponse[QARunResponse])
async def run_qa(
    card_id: UUID,
    payload: QARunRequest,
    organization_id: UUID,
    project_id: UUID,
    request: Request,
    session: SessionDep,
    actor: CurrentUserDep,
) -> ApiResponse[QARunResponse]:
    result = await ProductionService(session).run_qa(
        organization_id,
        project_id,
        card_id,
        payload,
        actor=actor,
        request_id=request.state.request_id,
    )
    return success(request, result)


@router.post("/cards/{card_id}/qa/repair", response_model=ApiResponse[DraftRevisionResponse])
async def repair_draft(
    card_id: UUID,
    payload: RepairRequest,
    organization_id: UUID,
    project_id: UUID,
    request: Request,
    session: SessionDep,
    actor: CurrentUserDep,
) -> ApiResponse[DraftRevisionResponse]:
    result = await ProductionService(session).repair_draft(
        organization_id,
        project_id,
        card_id,
        payload,
        actor=actor,
        request_id=request.state.request_id,
    )
    return success(request, result)


@router.post("/cards/{card_id}/g2/approve", response_model=ApiResponse[G1DecisionResponse])
async def approve_g2(
    card_id: UUID,
    payload: G2ApproveRequest,
    organization_id: UUID,
    project_id: UUID,
    request: Request,
    session: SessionDep,
    actor: CurrentUserDep,
) -> ApiResponse[G1DecisionResponse]:
    result = await ProductionService(session).approve_g2(
        organization_id,
        project_id,
        card_id,
        payload,
        actor=actor,
        request_id=request.state.request_id,
    )
    return success(request, result)


@router.post("/cards/{card_id}/g2/send-back", response_model=ApiResponse[G1DecisionResponse])
async def send_back_g2(
    card_id: UUID,
    payload: G2SendBackRequest,
    organization_id: UUID,
    project_id: UUID,
    request: Request,
    session: SessionDep,
    actor: CurrentUserDep,
) -> ApiResponse[G1DecisionResponse]:
    result = await ProductionService(session).send_back_g2(
        organization_id,
        project_id,
        card_id,
        payload,
        actor=actor,
        request_id=request.state.request_id,
    )
    return success(request, result)


@router.post(
    "/cards/{card_id}/g2/warning-dismiss", response_model=ApiResponse[WarningDismissResponse]
)
async def dismiss_warning(
    card_id: UUID,
    payload: WarningDismissRequest,
    organization_id: UUID,
    project_id: UUID,
    request: Request,
    session: SessionDep,
    actor: CurrentUserDep,
) -> ApiResponse[WarningDismissResponse]:
    result = await ProductionService(session).dismiss_warning(
        organization_id,
        project_id,
        card_id,
        payload,
        actor=actor,
        request_id=request.state.request_id,
    )
    return success(request, result)


@router.post(
    "/cards/{card_id}/sections/{section_id}/regenerate",
    response_model=ApiResponse[DraftRevisionResponse],
)
async def regenerate_section(
    card_id: UUID,
    section_id: Annotated[str, Path(min_length=1, max_length=64)],
    payload: SectionRegenerateRequest,
    organization_id: UUID,
    project_id: UUID,
    request: Request,
    session: SessionDep,
    actor: CurrentUserDep,
) -> ApiResponse[DraftRevisionResponse]:
    result = await ProductionService(session).regenerate_section(
        organization_id,
        project_id,
        card_id,
        section_id,
        payload,
        actor=actor,
        request_id=request.state.request_id,
    )
    return success(request, result)
