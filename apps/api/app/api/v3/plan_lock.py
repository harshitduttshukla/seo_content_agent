"""V3 Content Hub "Lock plan" route (handoff §5.1). Persistence only; no board."""

from uuid import UUID

from fastapi import APIRouter, Request

from app.api.dependencies import CurrentUserDep, SessionDep
from app.api.responses import success
from app.domains.projects.schemas import PlanLockState
from app.domains.projects.service import ProjectService
from app.schemas.common import ApiResponse

router = APIRouter(tags=["v3_plan_lock"])


@router.post("/plan/lock", response_model=ApiResponse[PlanLockState])
async def lock_plan(
    organization_id: UUID,
    project_id: UUID,
    request: Request,
    session: SessionDep,
    actor: CurrentUserDep,
) -> ApiResponse[PlanLockState]:
    """Lock the plan once. Takes no body: the timestamp is the database's, never the client's."""
    result = await ProjectService().lock_plan(
        session,
        actor=actor,
        organization_id=organization_id,
        project_id=project_id,
        request_id=request.state.request_id,
    )
    return success(request, result)
