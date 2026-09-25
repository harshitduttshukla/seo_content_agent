"""V3 Content Hub plan board routes (handoff §5.1).

Read the board; move a card Backlog ↔ Planned; reorder Planned. Locking the plan
stays on ``POST /plan/lock``. No route here sets an arbitrary state.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request

from app.api.dependencies import CurrentUserDep, SessionDep
from app.api.responses import success
from app.domains.content_cards.hub_service import ContentHubService
from app.domains.content_cards.schemas import (
    BoardCard,
    BoardFilters,
    BoardMoveRequest,
    ContentHubBoard,
    PlannedOrderRequest,
)
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
