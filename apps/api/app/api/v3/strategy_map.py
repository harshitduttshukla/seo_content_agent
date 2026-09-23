"""V3 read-only strategy-map route (handoff §4.4)."""

from uuid import UUID

from fastapi import APIRouter, Request

from app.api.dependencies import CurrentUserDep, SessionDep
from app.api.responses import success
from app.domains.canvas.map_service import StrategyMapService
from app.domains.canvas.schemas import StrategyMapResponse
from app.schemas.common import ApiResponse

router = APIRouter(tags=["v3_strategy_map"])


@router.get("/strategy/map", response_model=ApiResponse[StrategyMapResponse])
async def get_strategy_map(
    organization_id: UUID,
    project_id: UUID,
    request: Request,
    session: SessionDep,
    actor: CurrentUserDep,
) -> ApiResponse[StrategyMapResponse]:
    """Return the whole strategy graph for one project in a single payload."""
    return success(
        request,
        await StrategyMapService(session).get_strategy_map(
            organization_id, project_id, actor=actor
        ),
    )
