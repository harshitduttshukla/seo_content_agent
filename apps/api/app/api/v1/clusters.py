"""API routes for Keyword Clustering and cluster management."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, Request

from app.api.dependencies import CurrentUserDep, SessionDep
from app.api.responses import success
from app.domains.keywords.schemas import (
    ClusteringRunRequest,
    ClusteringRunResponse,
    ClusterMergeRequest,
    ClusterUpdateRequest,
    KeywordClusterDetail,
    KeywordClusterList,
    MoveKeywordsRequest,
)
from app.domains.keywords.service import KeywordService
from app.schemas.common import ApiResponse

router = APIRouter(tags=["keyword-clusters"])


@router.post(
    "/projects/{project_id}/clustering-runs",
    response_model=ApiResponse[ClusteringRunResponse],
    status_code=201,
)
async def run_clustering(
    project_id: UUID,
    payload: ClusteringRunRequest,
    request: Request,
    session: SessionDep,
    actor: CurrentUserDep,
) -> ApiResponse[ClusteringRunResponse]:
    run_res = await KeywordService().run_clustering(
        session,
        actor=actor,
        project_id=project_id,
        payload=payload,
        request_id=request.state.request_id if hasattr(request.state, "request_id") else "",
    )
    return success(request, run_res)


@router.get(
    "/projects/{project_id}/clusters",
    response_model=ApiResponse[KeywordClusterList],
)
@router.get(
    "/projects/{project_id}/keyword-clusters",
    response_model=ApiResponse[KeywordClusterList],
    include_in_schema=False,
)
async def list_clusters(
    project_id: UUID,
    request: Request,
    session: SessionDep,
    actor: CurrentUserDep,
    status: Annotated[str | None, Query()] = None,
) -> ApiResponse[KeywordClusterList]:
    clusters = await KeywordService().list_clusters(
        session,
        actor=actor,
        project_id=project_id,
        status=status,
    )
    return success(request, clusters)


@router.get(
    "/projects/{project_id}/clusters/{cluster_id}",
    response_model=ApiResponse[KeywordClusterDetail],
)
@router.get(
    "/projects/{project_id}/keyword-clusters/{cluster_id}",
    response_model=ApiResponse[KeywordClusterDetail],
    include_in_schema=False,
)
async def get_cluster(
    project_id: UUID,
    cluster_id: UUID,
    request: Request,
    session: SessionDep,
    actor: CurrentUserDep,
) -> ApiResponse[KeywordClusterDetail]:
    cluster = await KeywordService().get_cluster(
        session,
        actor=actor,
        project_id=project_id,
        cluster_id=cluster_id,
    )
    return success(request, cluster)


@router.put(
    "/projects/{project_id}/clusters/{cluster_id}",
    response_model=ApiResponse[KeywordClusterDetail],
)
@router.put(
    "/projects/{project_id}/keyword-clusters/{cluster_id}",
    response_model=ApiResponse[KeywordClusterDetail],
    include_in_schema=False,
)
async def update_cluster(
    project_id: UUID,
    cluster_id: UUID,
    payload: ClusterUpdateRequest,
    request: Request,
    session: SessionDep,
    actor: CurrentUserDep,
) -> ApiResponse[KeywordClusterDetail]:
    cluster = await KeywordService().update_cluster(
        session,
        actor=actor,
        project_id=project_id,
        cluster_id=cluster_id,
        payload=payload,
        request_id=request.state.request_id if hasattr(request.state, "request_id") else "",
    )
    return success(request, cluster)


@router.post(
    "/projects/{project_id}/clusters/merge",
    response_model=ApiResponse[KeywordClusterDetail],
)
@router.post(
    "/projects/{project_id}/keyword-clusters/merge",
    response_model=ApiResponse[KeywordClusterDetail],
    include_in_schema=False,
)
async def merge_clusters(
    project_id: UUID,
    payload: ClusterMergeRequest,
    request: Request,
    session: SessionDep,
    actor: CurrentUserDep,
) -> ApiResponse[KeywordClusterDetail]:
    merged = await KeywordService().merge_clusters(
        session,
        actor=actor,
        project_id=project_id,
        payload=payload,
        request_id=request.state.request_id if hasattr(request.state, "request_id") else "",
    )
    return success(request, merged)


@router.post(
    "/projects/{project_id}/clusters/move-keywords",
    response_model=ApiResponse[KeywordClusterDetail],
)
@router.post(
    "/projects/{project_id}/keyword-clusters/move-keywords",
    response_model=ApiResponse[KeywordClusterDetail],
    include_in_schema=False,
)
async def move_keywords(
    project_id: UUID,
    payload: MoveKeywordsRequest,
    request: Request,
    session: SessionDep,
    actor: CurrentUserDep,
) -> ApiResponse[KeywordClusterDetail]:
    target = await KeywordService().move_keywords(
        session,
        actor=actor,
        project_id=project_id,
        payload=payload,
        request_id=request.state.request_id if hasattr(request.state, "request_id") else "",
    )
    return success(request, target)
