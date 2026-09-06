"""API routes for Planned Content Pages, secondary keywords, and opportunity conversion."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, Request

from app.api.dependencies import CurrentUserDep, SessionDep
from app.api.responses import success
from app.domains.content.schemas import (
    ConvertOpportunityToPageRequest,
    PageKeywordAssign,
    PageKeywordDetail,
    PageKeywordList,
    PlannedContentPageCreate,
    PlannedContentPageDetail,
    PlannedContentPageList,
    PlannedContentPageUpdate,
)
from app.domains.content.service import ContentService
from app.schemas.common import ApiResponse

router = APIRouter(tags=["content-pages"])


@router.post(
    "/projects/{project_id}/content-pages",
    response_model=ApiResponse[PlannedContentPageDetail],
    status_code=201,
)
async def create_planned_content_page(
    project_id: UUID,
    payload: PlannedContentPageCreate,
    request: Request,
    session: SessionDep,
    actor: CurrentUserDep,
) -> ApiResponse[PlannedContentPageDetail]:
    page = await ContentService().create_planned_page(
        session,
        actor=actor,
        project_id=project_id,
        payload=payload,
        request_id=getattr(request.state, "request_id", ""),
    )
    return success(request, page)


@router.get(
    "/projects/{project_id}/content-pages",
    response_model=ApiResponse[PlannedContentPageList],
)
async def list_planned_content_pages(
    project_id: UUID,
    request: Request,
    session: SessionDep,
    actor: CurrentUserDep,
    status: Annotated[str | None, Query()] = None,
    cluster_id: Annotated[UUID | None, Query()] = None,
    topic_id: Annotated[UUID | None, Query()] = None,
    pillar_id: Annotated[UUID | None, Query()] = None,
    page_type: Annotated[str | None, Query()] = None,
    search: Annotated[str | None, Query()] = None,
) -> ApiResponse[PlannedContentPageList]:
    pages = await ContentService().list_planned_pages(
        session,
        actor=actor,
        project_id=project_id,
        status=status,
        cluster_id=cluster_id,
        topic_id=topic_id,
        pillar_id=pillar_id,
        page_type=page_type,
        search=search,
    )
    return success(request, pages)


@router.post(
    "/projects/{project_id}/content-opportunities/{opportunity_id}/convert-to-page",
    response_model=ApiResponse[PlannedContentPageDetail],
    status_code=201,
)
async def convert_opportunity_to_page(
    project_id: UUID,
    opportunity_id: UUID,
    payload: ConvertOpportunityToPageRequest,
    request: Request,
    session: SessionDep,
    actor: CurrentUserDep,
) -> ApiResponse[PlannedContentPageDetail]:
    page = await ContentService().convert_opportunity_to_page(
        session,
        actor=actor,
        project_id=project_id,
        opportunity_id=opportunity_id,
        payload=payload,
        request_id=getattr(request.state, "request_id", ""),
    )
    return success(request, page)


@router.get(
    "/content-pages/{page_id}",
    response_model=ApiResponse[PlannedContentPageDetail],
)
async def get_planned_content_page(
    page_id: UUID,
    request: Request,
    session: SessionDep,
    actor: CurrentUserDep,
) -> ApiResponse[PlannedContentPageDetail]:
    page = await ContentService().get_planned_page(
        session,
        actor=actor,
        page_id=page_id,
    )
    return success(request, page)


@router.put(
    "/content-pages/{page_id}",
    response_model=ApiResponse[PlannedContentPageDetail],
)
async def update_planned_content_page(
    page_id: UUID,
    payload: PlannedContentPageUpdate,
    request: Request,
    session: SessionDep,
    actor: CurrentUserDep,
) -> ApiResponse[PlannedContentPageDetail]:
    page = await ContentService().update_planned_page(
        session,
        actor=actor,
        page_id=page_id,
        payload=payload,
        request_id=getattr(request.state, "request_id", ""),
    )
    return success(request, page)


@router.delete(
    "/content-pages/{page_id}",
    response_model=ApiResponse[dict[str, str]],
)
async def delete_planned_content_page(
    page_id: UUID,
    request: Request,
    session: SessionDep,
    actor: CurrentUserDep,
) -> ApiResponse[dict[str, str]]:
    await ContentService().delete_planned_page(
        session,
        actor=actor,
        page_id=page_id,
        request_id=getattr(request.state, "request_id", ""),
    )
    return success(request, {"message": f"Planned page {page_id} successfully deleted."})


# --- Page Keywords ---


@router.post(
    "/content-pages/{page_id}/keywords",
    response_model=ApiResponse[PageKeywordDetail],
    status_code=201,
)
async def assign_page_keyword(
    page_id: UUID,
    payload: PageKeywordAssign,
    request: Request,
    session: SessionDep,
    actor: CurrentUserDep,
) -> ApiResponse[PageKeywordDetail]:
    res = await ContentService().assign_page_keyword(
        session,
        actor=actor,
        page_id=page_id,
        payload=payload,
        request_id=getattr(request.state, "request_id", ""),
    )
    return success(request, res)


@router.get(
    "/content-pages/{page_id}/keywords",
    response_model=ApiResponse[PageKeywordList],
)
async def list_page_keywords(
    page_id: UUID,
    request: Request,
    session: SessionDep,
    actor: CurrentUserDep,
) -> ApiResponse[PageKeywordList]:
    res = await ContentService().list_page_keywords(
        session,
        actor=actor,
        page_id=page_id,
    )
    return success(request, res)


@router.delete(
    "/content-pages/{page_id}/keywords/{keyword_id}",
    response_model=ApiResponse[dict[str, str]],
)
async def remove_page_keyword(
    page_id: UUID,
    keyword_id: UUID,
    request: Request,
    session: SessionDep,
    actor: CurrentUserDep,
) -> ApiResponse[dict[str, str]]:
    await ContentService().remove_page_keyword(
        session,
        actor=actor,
        page_id=page_id,
        keyword_id=keyword_id,
        request_id=getattr(request.state, "request_id", ""),
    )
    return success(request, {"message": "Keyword removed from page."})
