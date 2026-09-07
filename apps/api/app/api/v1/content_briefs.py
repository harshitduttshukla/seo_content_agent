"""API routes for Content Briefs, lifecycle management, and versioning."""

from uuid import UUID

from fastapi import APIRouter, Request

from app.api.dependencies import CurrentUserDep, SessionDep
from app.api.responses import success
from app.domains.content.brief_schemas import (
    ContentBriefApproveRequest,
    ContentBriefDetail,
    ContentBriefUpdate,
    ContentBriefVersionList,
)
from app.domains.content.brief_service import ContentBriefService
from app.schemas.common import ApiResponse

router = APIRouter(tags=["content-briefs"])


@router.get(
    "/content-pages/{page_id}/brief",
    response_model=ApiResponse[ContentBriefDetail],
)
async def get_or_create_content_brief(
    page_id: UUID,
    request: Request,
    session: SessionDep,
    actor: CurrentUserDep,
) -> ApiResponse[ContentBriefDetail]:
    brief = await ContentBriefService().get_or_create_brief(
        session,
        actor=actor,
        page_id=page_id,
    )
    return success(request, brief)


@router.post(
    "/content-pages/{page_id}/brief",
    response_model=ApiResponse[ContentBriefDetail],
    status_code=201,
)
async def generate_content_brief(
    page_id: UUID,
    request: Request,
    session: SessionDep,
    actor: CurrentUserDep,
) -> ApiResponse[ContentBriefDetail]:
    brief = await ContentBriefService().get_or_create_brief(
        session,
        actor=actor,
        page_id=page_id,
    )
    return success(request, brief)


@router.put(
    "/content-briefs/{brief_id}",
    response_model=ApiResponse[ContentBriefDetail],
)
async def update_content_brief(
    brief_id: UUID,
    payload: ContentBriefUpdate,
    request: Request,
    session: SessionDep,
    actor: CurrentUserDep,
) -> ApiResponse[ContentBriefDetail]:
    brief = await ContentBriefService().update_brief_endpoint(
        session,
        actor=actor,
        brief_id=brief_id,
        payload=payload,
    )
    return success(request, brief)


@router.post(
    "/content-briefs/{brief_id}/approve",
    response_model=ApiResponse[ContentBriefDetail],
)
async def approve_content_brief(
    brief_id: UUID,
    payload: ContentBriefApproveRequest,
    request: Request,
    session: SessionDep,
    actor: CurrentUserDep,
) -> ApiResponse[ContentBriefDetail]:
    brief = await ContentBriefService().approve_brief_endpoint(
        session,
        actor=actor,
        brief_id=brief_id,
        change_summary=payload.change_summary,
    )
    return success(request, brief)


@router.get(
    "/content-briefs/{brief_id}/versions",
    response_model=ApiResponse[ContentBriefVersionList],
)
async def list_content_brief_versions(
    brief_id: UUID,
    request: Request,
    session: SessionDep,
    actor: CurrentUserDep,
) -> ApiResponse[ContentBriefVersionList]:
    versions = await ContentBriefService().list_versions_endpoint(
        session,
        actor=actor,
        brief_id=brief_id,
    )
    return success(request, versions)
