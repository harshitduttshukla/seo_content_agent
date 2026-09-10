"""API routes for Internal Linking, page relationships, link opportunities, and orphan detection."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, Request

from app.api.dependencies import CurrentUserDep, SessionDep
from app.api.responses import success
from app.domains.internal_linking.schemas import (
    InternalLinksSummary,
    LinkOpportunityDetail,
    LinkOpportunityList,
    OrphanPageList,
    PageRelationshipCreate,
    PageRelationshipDetail,
    PageRelationshipList,
)
from app.domains.internal_linking.service import InternalLinkingService
from app.schemas.common import ApiResponse

router = APIRouter(tags=["internal-linking"])


@router.get(
    "/projects/{project_id}/page-relationships",
    response_model=ApiResponse[PageRelationshipList],
)
async def list_page_relationships(
    project_id: UUID,
    request: Request,
    session: SessionDep,
    actor: CurrentUserDep,
    status: Annotated[str | None, Query()] = None,
) -> ApiResponse[PageRelationshipList]:
    rels = await InternalLinkingService().list_relationships(
        session,
        actor=actor,
        project_id=project_id,
        status=status,
    )
    return success(request, rels)


@router.post(
    "/projects/{project_id}/page-relationships",
    response_model=ApiResponse[PageRelationshipDetail],
    status_code=201,
)
async def create_page_relationship(
    project_id: UUID,
    payload: PageRelationshipCreate,
    request: Request,
    session: SessionDep,
    actor: CurrentUserDep,
) -> ApiResponse[PageRelationshipDetail]:
    rel = await InternalLinkingService().create_relationship(
        session,
        actor=actor,
        project_id=project_id,
        payload=payload,
        request_id=getattr(request.state, "request_id", ""),
    )
    return success(request, rel)


@router.delete(
    "/projects/{project_id}/page-relationships/{relationship_id}",
    response_model=ApiResponse[dict[str, str]],
)
async def delete_page_relationship(
    project_id: UUID,
    relationship_id: UUID,
    request: Request,
    session: SessionDep,
    actor: CurrentUserDep,
) -> ApiResponse[dict[str, str]]:
    await InternalLinkingService().delete_relationship(
        session,
        actor=actor,
        project_id=project_id,
        relationship_id=relationship_id,
        request_id=getattr(request.state, "request_id", ""),
    )
    return success(request, {"message": "Page relationship deleted successfully."})


@router.get(
    "/projects/{project_id}/link-opportunities",
    response_model=ApiResponse[LinkOpportunityList],
)
async def list_link_opportunities(
    project_id: UUID,
    request: Request,
    session: SessionDep,
    actor: CurrentUserDep,
    status: Annotated[str | None, Query()] = None,
) -> ApiResponse[LinkOpportunityList]:
    opps = await InternalLinkingService().list_opportunities(
        session,
        actor=actor,
        project_id=project_id,
        status=status,
    )
    return success(request, opps)


@router.post(
    "/projects/{project_id}/link-opportunities/analyze",
    response_model=ApiResponse[LinkOpportunityList],
)
async def analyze_link_opportunities(
    project_id: UUID,
    request: Request,
    session: SessionDep,
    actor: CurrentUserDep,
) -> ApiResponse[LinkOpportunityList]:
    res = await InternalLinkingService().analyze_link_opportunities(
        session,
        actor=actor,
        project_id=project_id,
        request_id=getattr(request.state, "request_id", ""),
    )
    return success(request, res)


@router.post(
    "/projects/{project_id}/link-opportunities/{opportunity_id}/approve",
    response_model=ApiResponse[LinkOpportunityDetail],
)
async def approve_link_opportunity(
    project_id: UUID,
    opportunity_id: UUID,
    request: Request,
    session: SessionDep,
    actor: CurrentUserDep,
) -> ApiResponse[LinkOpportunityDetail]:
    opp = await InternalLinkingService().approve_opportunity(
        session,
        actor=actor,
        project_id=project_id,
        opportunity_id=opportunity_id,
        request_id=getattr(request.state, "request_id", ""),
    )
    return success(request, opp)


@router.post(
    "/projects/{project_id}/link-opportunities/{opportunity_id}/reject",
    response_model=ApiResponse[LinkOpportunityDetail],
)
async def reject_link_opportunity(
    project_id: UUID,
    opportunity_id: UUID,
    request: Request,
    session: SessionDep,
    actor: CurrentUserDep,
) -> ApiResponse[LinkOpportunityDetail]:
    opp = await InternalLinkingService().reject_opportunity(
        session,
        actor=actor,
        project_id=project_id,
        opportunity_id=opportunity_id,
        request_id=getattr(request.state, "request_id", ""),
    )
    return success(request, opp)


@router.get(
    "/projects/{project_id}/orphan-pages",
    response_model=ApiResponse[OrphanPageList],
)
async def detect_orphan_pages(
    project_id: UUID,
    request: Request,
    session: SessionDep,
    actor: CurrentUserDep,
) -> ApiResponse[OrphanPageList]:
    orphans = await InternalLinkingService().detect_orphan_pages(
        session,
        actor=actor,
        project_id=project_id,
    )
    return success(request, orphans)


@router.get(
    "/content-pages/{page_id}/internal-links",
    response_model=ApiResponse[InternalLinksSummary],
)
async def get_page_internal_links(
    page_id: UUID,
    request: Request,
    session: SessionDep,
    actor: CurrentUserDep,
) -> ApiResponse[InternalLinksSummary]:
    summary = await InternalLinkingService().get_page_internal_links(
        session,
        actor=actor,
        page_id=page_id,
    )
    return success(request, summary)
