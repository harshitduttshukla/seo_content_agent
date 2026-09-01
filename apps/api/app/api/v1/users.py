"""Current-user API."""

from fastapi import APIRouter, Request

from app.api.dependencies import CurrentUserDep, SessionDep
from app.api.responses import success
from app.domains.users.schemas import UserDetail
from app.domains.users.service import UserService
from app.schemas.common import ApiResponse

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=ApiResponse[UserDetail])
async def current_user(
    request: Request, session: SessionDep, actor: CurrentUserDep
) -> ApiResponse[UserDetail]:
    detail = await UserService().detail(session, actor.user_id, request_id=request.state.request_id)
    return success(request, detail)
