"""API routes for Content Architecture: Pillars, Topics, Mappings, Gaps, and Graph."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, Request

from app.api.dependencies import CurrentUserDep, SessionDep
from app.api.responses import success
from app.domains.content.schemas import (
    CannibalizationWarningList,
    ContentArchitectureGraphResponse,
    ContentOpportunityDetail,
    ContentOpportunityList,
    ContentOpportunityUpdate,
    ContentPillarCreate,
    ContentPillarDetail,
    ContentPillarList,
    ContentPillarUpdate,
    KeywordPageMappingList,
    MappingAnalysisResponse,
    TopicCreate,
    TopicDetail,
    TopicList,
    TopicUpdate,
)
from app.domains.content.service import ContentService
from app.schemas.common import ApiResponse

router = APIRouter(tags=["content-architecture"])


# --- Content Pillars ---


@router.post(
    "/projects/{project_id}/content-pillars",
    response_model=ApiResponse[ContentPillarDetail],
    status_code=201,
)
async def create_content_pillar(
    project_id: UUID,
    payload: ContentPillarCreate,
    request: Request,
    session: SessionDep,
    actor: CurrentUserDep,
) -> ApiResponse[ContentPillarDetail]:
    pillar = await ContentService().create_pillar(
        session,
        actor=actor,
        project_id=project_id,
        payload=payload,
        request_id=request.state.request_id if hasattr(request.state, "request_id") else "",
    )
    return success(request, pillar)


@router.get(
    "/projects/{project_id}/content-pillars",
    response_model=ApiResponse[ContentPillarList],
)
async def list_content_pillars(
    project_id: UUID,
    request: Request,
    session: SessionDep,
    actor: CurrentUserDep,
) -> ApiResponse[ContentPillarList]:
    pillars = await ContentService().list_pillars(
        session,
        actor=actor,
        project_id=project_id,
    )
    return success(request, pillars)


@router.put(
    "/projects/{project_id}/content-pillars/{pillar_id}",
    response_model=ApiResponse[ContentPillarDetail],
)
async def update_content_pillar(
    project_id: UUID,
    pillar_id: UUID,
    payload: ContentPillarUpdate,
    request: Request,
    session: SessionDep,
    actor: CurrentUserDep,
) -> ApiResponse[ContentPillarDetail]:
    pillar = await ContentService().update_pillar(
        session,
        actor=actor,
        project_id=project_id,
        pillar_id=pillar_id,
        payload=payload,
        request_id=request.state.request_id if hasattr(request.state, "request_id") else "",
    )
    return success(request, pillar)


# --- Topics ---


@router.post(
    "/projects/{project_id}/topics",
    response_model=ApiResponse[TopicDetail],
    status_code=201,
)
async def create_topic(
    project_id: UUID,
    payload: TopicCreate,
    request: Request,
    session: SessionDep,
    actor: CurrentUserDep,
) -> ApiResponse[TopicDetail]:
    topic = await ContentService().create_topic(
        session,
        actor=actor,
        project_id=project_id,
        payload=payload,
        request_id=request.state.request_id if hasattr(request.state, "request_id") else "",
    )
    return success(request, topic)


@router.get(
    "/projects/{project_id}/topics",
    response_model=ApiResponse[TopicList],
)
async def list_topics(
    project_id: UUID,
    request: Request,
    session: SessionDep,
    actor: CurrentUserDep,
    pillar_id: Annotated[UUID | None, Query()] = None,
) -> ApiResponse[TopicList]:
    topics = await ContentService().list_topics(
        session,
        actor=actor,
        project_id=project_id,
        pillar_id=pillar_id,
    )
    return success(request, topics)


@router.put(
    "/projects/{project_id}/topics/{topic_id}",
    response_model=ApiResponse[TopicDetail],
)
async def update_topic(
    project_id: UUID,
    topic_id: UUID,
    payload: TopicUpdate,
    request: Request,
    session: SessionDep,
    actor: CurrentUserDep,
) -> ApiResponse[TopicDetail]:
    topic = await ContentService().update_topic(
        session,
        actor=actor,
        project_id=project_id,
        topic_id=topic_id,
        payload=payload,
        request_id=request.state.request_id if hasattr(request.state, "request_id") else "",
    )
    return success(request, topic)


# --- Keyword Mappings & Cannibalization ---


@router.post(
    "/projects/{project_id}/keyword-mappings/analyze",
    response_model=ApiResponse[MappingAnalysisResponse],
)
async def analyze_keyword_mappings(
    project_id: UUID,
    request: Request,
    session: SessionDep,
    actor: CurrentUserDep,
    website_id: Annotated[UUID, Query()],
) -> ApiResponse[MappingAnalysisResponse]:
    res = await ContentService().analyze_keyword_mappings(
        session,
        actor=actor,
        project_id=project_id,
        website_id=website_id,
        request_id=request.state.request_id if hasattr(request.state, "request_id") else "",
    )
    return success(request, res)


@router.get(
    "/projects/{project_id}/keyword-mappings",
    response_model=ApiResponse[KeywordPageMappingList],
)
async def list_keyword_mappings(
    project_id: UUID,
    request: Request,
    session: SessionDep,
    actor: CurrentUserDep,
) -> ApiResponse[KeywordPageMappingList]:
    mappings = await ContentService().list_mappings(
        session,
        actor=actor,
        project_id=project_id,
    )
    return success(request, mappings)


@router.get(
    "/projects/{project_id}/cannibalization-warnings",
    response_model=ApiResponse[CannibalizationWarningList],
)
async def get_cannibalization_warnings(
    project_id: UUID,
    request: Request,
    session: SessionDep,
    actor: CurrentUserDep,
    website_id: Annotated[UUID, Query()],
) -> ApiResponse[CannibalizationWarningList]:
    warnings = await ContentService().detect_cannibalization(
        session,
        actor=actor,
        project_id=project_id,
        website_id=website_id,
    )
    return success(request, warnings)


# --- Content Opportunities & Gaps ---


@router.get(
    "/projects/{project_id}/content-opportunities",
    response_model=ApiResponse[ContentOpportunityList],
)
async def list_content_opportunities(
    project_id: UUID,
    request: Request,
    session: SessionDep,
    actor: CurrentUserDep,
    status: Annotated[str | None, Query()] = None,
) -> ApiResponse[ContentOpportunityList]:
    opps = await ContentService().list_opportunities(
        session,
        actor=actor,
        project_id=project_id,
        status=status,
    )
    return success(request, opps)


@router.put(
    "/projects/{project_id}/content-opportunities/{opportunity_id}",
    response_model=ApiResponse[ContentOpportunityDetail],
)
async def update_content_opportunity(
    project_id: UUID,
    opportunity_id: UUID,
    payload: ContentOpportunityUpdate,
    request: Request,
    session: SessionDep,
    actor: CurrentUserDep,
) -> ApiResponse[ContentOpportunityDetail]:
    opp = await ContentService().update_opportunity(
        session,
        actor=actor,
        project_id=project_id,
        opportunity_id=opportunity_id,
        payload=payload,
        request_id=request.state.request_id if hasattr(request.state, "request_id") else "",
    )
    return success(request, opp)


# --- Architecture Graph ---


@router.get(
    "/projects/{project_id}/content-architecture/graph",
    response_model=ApiResponse[ContentArchitectureGraphResponse],
)
async def get_architecture_graph(
    project_id: UUID,
    request: Request,
    session: SessionDep,
    actor: CurrentUserDep,
) -> ApiResponse[ContentArchitectureGraphResponse]:
    graph = await ContentService().get_architecture_graph(
        session,
        actor=actor,
        project_id=project_id,
    )
    return success(request, graph)
