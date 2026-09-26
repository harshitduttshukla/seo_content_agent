"""Google Search Console routes (read-only integration, Phase 6A).

Project routes resolve the organization server-side from the project; website routes
resolve organization and project from the website. Nothing returns a credential.
"""

from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, Request
from pydantic import ValidationError

from app.api.dependencies import CurrentUserDep, SessionDep
from app.api.responses import success
from app.core.errors import DomainError
from app.domains.search_console.schemas import (
    AnalyticsResponse,
    AnalyticsSort,
    AvailablePropertyList,
    ConnectStartResponse,
    DateRange,
    MappedProperty,
    OAuthCallbackRequest,
    OAuthCallbackResponse,
    PropertyMapRequest,
    SearchConsoleStatus,
    SyncRequest,
    SyncRun,
)
from app.domains.search_console.service import SearchConsoleService
from app.schemas.common import ApiResponse

router = APIRouter(tags=["search_console"])


@router.get(
    "/projects/{project_id}/search-console", response_model=ApiResponse[SearchConsoleStatus]
)
async def get_status(
    project_id: UUID, request: Request, session: SessionDep, actor: CurrentUserDep
) -> ApiResponse[SearchConsoleStatus]:
    return success(request, await SearchConsoleService(session).get_status(project_id, actor=actor))


@router.post(
    "/projects/{project_id}/search-console/connect",
    response_model=ApiResponse[ConnectStartResponse],
)
async def start_connect(
    project_id: UUID, request: Request, session: SessionDep, actor: CurrentUserDep
) -> ApiResponse[ConnectStartResponse]:
    result = await SearchConsoleService(session).start_connect(
        project_id, actor=actor, request_id=request.state.request_id
    )
    return success(request, result)


@router.post("/search-console/oauth/callback", response_model=ApiResponse[OAuthCallbackResponse])
async def oauth_callback(
    payload: OAuthCallbackRequest, request: Request, session: SessionDep, actor: CurrentUserDep
) -> ApiResponse[OAuthCallbackResponse]:
    result = await SearchConsoleService(session).complete_connect(
        payload.code, payload.state, actor=actor, request_id=request.state.request_id
    )
    return success(request, result)


@router.delete(
    "/projects/{project_id}/search-console/connection",
    response_model=ApiResponse[SearchConsoleStatus],
)
async def disconnect(
    project_id: UUID, request: Request, session: SessionDep, actor: CurrentUserDep
) -> ApiResponse[SearchConsoleStatus]:
    service = SearchConsoleService(session)
    await service.disconnect(project_id, actor=actor, request_id=request.state.request_id)
    return success(request, await service.get_status(project_id, actor=actor))


@router.get(
    "/projects/{project_id}/search-console/properties",
    response_model=ApiResponse[AvailablePropertyList],
)
async def list_properties(
    project_id: UUID, request: Request, session: SessionDep, actor: CurrentUserDep
) -> ApiResponse[AvailablePropertyList]:
    return success(
        request, await SearchConsoleService(session).list_properties(project_id, actor=actor)
    )


@router.put(
    "/websites/{website_id}/search-console/property", response_model=ApiResponse[MappedProperty]
)
async def map_property(
    website_id: UUID,
    payload: PropertyMapRequest,
    request: Request,
    session: SessionDep,
    actor: CurrentUserDep,
) -> ApiResponse[MappedProperty]:
    result = await SearchConsoleService(session).map_property(
        website_id, payload.site_url, actor=actor, request_id=request.state.request_id
    )
    return success(request, result)


@router.post("/websites/{website_id}/search-console/sync", response_model=ApiResponse[SyncRun])
async def sync(
    website_id: UUID,
    payload: SyncRequest,
    request: Request,
    session: SessionDep,
    actor: CurrentUserDep,
) -> ApiResponse[SyncRun]:
    result = await SearchConsoleService(session).sync(
        website_id, payload, actor=actor, request_id=request.state.request_id
    )
    return success(request, result)


@router.get(
    "/websites/{website_id}/search-console/analytics",
    response_model=ApiResponse[AnalyticsResponse],
)
async def analytics(
    website_id: UUID,
    request: Request,
    session: SessionDep,
    actor: CurrentUserDep,
    start_date: date | None = None,
    end_date: date | None = None,
    sort: AnalyticsSort = "clicks",
    limit: Annotated[int, Query(ge=1, le=500)] = 50,
    offset: Annotated[int, Query(ge=0, le=1_000_000)] = 0,
) -> ApiResponse[AnalyticsResponse]:
    try:
        dates = DateRange(start_date=start_date, end_date=end_date)
    except ValidationError as exc:
        raise DomainError(
            "INVALID_DATE_RANGE", "Give both start_date and end_date, or neither.", 422
        ) from exc
    result = await SearchConsoleService(session).analytics(
        website_id, dates, actor=actor, sort=sort, limit=limit, offset=offset
    )
    return success(request, result)
