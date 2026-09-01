"""API routes for content page inventory, details, and links."""

from uuid import UUID

from fastapi import APIRouter, Query, Request

from app.api.dependencies import CurrentUserDep, SessionDep
from app.api.responses import success
from app.domains.content.schemas import (
    ContentPageDetail,
    ContentPageList,
    PageLinkList,
)
from app.domains.content.service import ContentService
from app.schemas.common import ApiResponse

router = APIRouter(tags=["pages"])


@router.get(
    "/websites/{website_id}/pages",
    response_model=ApiResponse[ContentPageList],
)
async def list_pages(
    website_id: UUID,
    request: Request,
    session: SessionDep,
    actor: CurrentUserDep,
    status: str | None = Query(default=None),
    search: str | None = Query(default=None),
    cursor: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=100),
) -> ApiResponse[ContentPageList]:
    page = await ContentService().list_pages(
        session,
        actor=actor,
        website_id=website_id,
        status=status,
        search=search,
        cursor=cursor,
        limit=limit,
    )
    return success(
        request,
        ContentPageList(items=page.items),
        next_cursor=page.next_cursor,
        has_more=page.has_more,
    )


@router.get(
    "/websites/{website_id}/pages/{page_id}",
    response_model=ApiResponse[ContentPageDetail],
)
async def get_page(
    website_id: UUID,
    page_id: UUID,
    request: Request,
    session: SessionDep,
    actor: CurrentUserDep,
) -> ApiResponse[ContentPageDetail]:
    detail = await ContentService().get_page(
        session, actor=actor, website_id=website_id, page_id=page_id
    )
    return success(request, detail)


@router.get(
    "/websites/{website_id}/links",
    response_model=ApiResponse[PageLinkList],
)
async def list_links(
    website_id: UUID,
    request: Request,
    session: SessionDep,
    actor: CurrentUserDep,
    limit: int = Query(default=100, ge=1, le=500),
) -> ApiResponse[PageLinkList]:
    links = await ContentService().list_links(
        session, actor=actor, website_id=website_id, limit=limit
    )
    return success(request, PageLinkList(items=links))
