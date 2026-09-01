"""Website routes."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Header, Query, Request, status

from app.api.dependencies import CurrentUserDep, SessionDep
from app.api.responses import success
from app.domains.websites.schemas import WebsiteCreate, WebsiteDetail, WebsiteList, WebsiteUpdate
from app.domains.websites.service import WebsiteService
from app.schemas.common import ApiResponse

router = APIRouter(tags=["websites"])


@router.post(
    "/projects/{project_id}/websites",
    response_model=ApiResponse[WebsiteDetail],
    status_code=status.HTTP_201_CREATED,
)
async def create_website(
    project_id: UUID,
    payload: WebsiteCreate,
    request: Request,
    session: SessionDep,
    actor: CurrentUserDep,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=8, max_length=200)],
) -> ApiResponse[WebsiteDetail]:
    detail = await WebsiteService().create(
        session,
        actor=actor,
        project_id=project_id,
        payload=payload,
        idempotency_key=idempotency_key,
        request_id=request.state.request_id,
    )
    return success(request, detail)


@router.get("/projects/{project_id}/websites", response_model=ApiResponse[WebsiteList])
async def list_websites(
    project_id: UUID,
    request: Request,
    session: SessionDep,
    actor: CurrentUserDep,
    cursor: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=100),
) -> ApiResponse[WebsiteList]:
    page = await WebsiteService().list(
        session,
        actor=actor,
        project_id=project_id,
        cursor=cursor,
        limit=limit,
    )
    return success(
        request,
        WebsiteList(items=page.items),
        next_cursor=page.next_cursor,
        has_more=page.has_more,
    )


@router.get("/websites/{website_id}", response_model=ApiResponse[WebsiteDetail])
async def get_website(
    website_id: UUID, request: Request, session: SessionDep, actor: CurrentUserDep
) -> ApiResponse[WebsiteDetail]:
    detail = await WebsiteService().get(session, actor=actor, website_id=website_id)
    return success(request, detail)


@router.put("/websites/{website_id}", response_model=ApiResponse[WebsiteDetail])
async def update_website(
    website_id: UUID,
    payload: WebsiteUpdate,
    request: Request,
    session: SessionDep,
    actor: CurrentUserDep,
) -> ApiResponse[WebsiteDetail]:
    detail = await WebsiteService().update(
        session,
        actor=actor,
        website_id=website_id,
        payload=payload,
        request_id=request.state.request_id,
    )
    return success(request, detail)


@router.delete("/websites/{website_id}", response_model=ApiResponse[WebsiteDetail])
async def archive_website(
    website_id: UUID, request: Request, session: SessionDep, actor: CurrentUserDep
) -> ApiResponse[WebsiteDetail]:
    detail = await WebsiteService().archive(
        session,
        actor=actor,
        website_id=website_id,
        request_id=request.state.request_id,
    )
    return success(request, detail)
