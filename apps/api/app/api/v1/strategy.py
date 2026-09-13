"""API routes for SEO Strategy management and versioning."""

from uuid import UUID

from fastapi import APIRouter, Request

from app.api.dependencies import CurrentUserDep, SessionDep
from app.api.responses import success
from app.domains.strategy.schemas import (
    StrategyDataSchema,
    StrategyResponse,
    StrategyUpdateRequest,
    StrategyVersionListResponse,
    StrategyVersionResponse,
)
from app.domains.strategy.service import SEOStrategyService
from app.schemas.common import ApiResponse

router = APIRouter(tags=["strategy"])


@router.get(
    "/projects/{project_id}/strategy",
    response_model=ApiResponse[StrategyResponse],
)
async def get_strategy(
    project_id: UUID,
    request: Request,
    session: SessionDep,
    actor: CurrentUserDep,
) -> ApiResponse[StrategyResponse]:
    strategy = await SEOStrategyService().get_or_create_strategy(
        session,
        actor=actor,
        project_id=project_id,
        request_id=request.state.request_id if hasattr(request.state, "request_id") else "",
    )
    return success(request, strategy)


@router.put(
    "/projects/{project_id}/strategy",
    response_model=ApiResponse[StrategyResponse],
)
async def update_strategy(
    project_id: UUID,
    payload: StrategyUpdateRequest,
    request: Request,
    session: SessionDep,
    actor: CurrentUserDep,
) -> ApiResponse[StrategyResponse]:
    strategy = await SEOStrategyService().update_strategy(
        session,
        actor=actor,
        project_id=project_id,
        payload=payload,
        request_id=request.state.request_id if hasattr(request.state, "request_id") else "",
    )
    return success(request, strategy)


@router.post(
    "/projects/{project_id}/strategy/generate",
    response_model=ApiResponse[StrategyDataSchema],
)
async def generate_strategy_draft(
    project_id: UUID,
    request: Request,
    session: SessionDep,
    actor: CurrentUserDep,
) -> ApiResponse[StrategyDataSchema]:
    draft = await SEOStrategyService().generate_initial_strategy_draft(
        session,
        actor=actor,
        project_id=project_id,
        request_id=request.state.request_id if hasattr(request.state, "request_id") else "",
    )
    return success(request, draft)


@router.get(
    "/projects/{project_id}/strategy/versions",
    response_model=ApiResponse[StrategyVersionListResponse],
)
async def list_strategy_versions(
    project_id: UUID,
    request: Request,
    session: SessionDep,
    actor: CurrentUserDep,
) -> ApiResponse[StrategyVersionListResponse]:
    versions = await SEOStrategyService().list_versions(
        session,
        actor=actor,
        project_id=project_id,
    )
    return success(request, versions)


@router.get(
    "/projects/{project_id}/strategy/versions/{version}",
    response_model=ApiResponse[StrategyVersionResponse],
)
async def get_strategy_version(
    project_id: UUID,
    version: int,
    request: Request,
    session: SessionDep,
    actor: CurrentUserDep,
) -> ApiResponse[StrategyVersionResponse]:
    version_detail = await SEOStrategyService().get_version(
        session,
        actor=actor,
        project_id=project_id,
        version=version,
    )
    return success(request, version_detail)
