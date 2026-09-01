"""Project routes."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Header, Query, Request, status

from app.api.dependencies import CurrentUserDep, SessionDep
from app.api.responses import success
from app.domains.projects.schemas import ProjectCreate, ProjectDetail, ProjectList, ProjectUpdate
from app.domains.projects.service import ProjectService
from app.schemas.common import ApiResponse

router = APIRouter(prefix="/projects", tags=["projects"])


@router.post("", response_model=ApiResponse[ProjectDetail], status_code=status.HTTP_201_CREATED)
async def create_project(
    payload: ProjectCreate,
    request: Request,
    session: SessionDep,
    actor: CurrentUserDep,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=8, max_length=200)],
) -> ApiResponse[ProjectDetail]:
    detail = await ProjectService().create(
        session,
        actor=actor,
        payload=payload,
        idempotency_key=idempotency_key,
        request_id=request.state.request_id,
    )
    return success(request, detail)


@router.get("", response_model=ApiResponse[ProjectList])
async def list_projects(
    organization_id: UUID,
    request: Request,
    session: SessionDep,
    actor: CurrentUserDep,
    cursor: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=100),
) -> ApiResponse[ProjectList]:
    page = await ProjectService().list(
        session,
        actor=actor,
        organization_id=organization_id,
        cursor=cursor,
        limit=limit,
    )
    return success(
        request,
        ProjectList(items=page.items),
        next_cursor=page.next_cursor,
        has_more=page.has_more,
    )


@router.get("/{project_id}", response_model=ApiResponse[ProjectDetail])
async def get_project(
    project_id: UUID, request: Request, session: SessionDep, actor: CurrentUserDep
) -> ApiResponse[ProjectDetail]:
    detail = await ProjectService().get(session, actor=actor, project_id=project_id)
    return success(request, detail)


@router.put("/{project_id}", response_model=ApiResponse[ProjectDetail])
async def update_project(
    project_id: UUID,
    payload: ProjectUpdate,
    request: Request,
    session: SessionDep,
    actor: CurrentUserDep,
) -> ApiResponse[ProjectDetail]:
    detail = await ProjectService().update(
        session,
        actor=actor,
        project_id=project_id,
        payload=payload,
        request_id=request.state.request_id,
    )
    return success(request, detail)


@router.delete("/{project_id}", response_model=ApiResponse[ProjectDetail])
async def archive_project(
    project_id: UUID, request: Request, session: SessionDep, actor: CurrentUserDep
) -> ApiResponse[ProjectDetail]:
    detail = await ProjectService().archive(
        session,
        actor=actor,
        project_id=project_id,
        request_id=request.state.request_id,
    )
    return success(request, detail)
