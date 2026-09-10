"""API routes for Content Map graph projections, layout saving, validation, and versioning."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, Request

from app.api.dependencies import CurrentUserDep, SessionDep
from app.api.responses import success
from app.domains.content_map.schemas import (
    ContentArchitectureVersionCreate,
    ContentArchitectureVersionDetail,
    ContentArchitectureVersionList,
    ContentMapGraphResponse,
    ContentMapLayoutUpdate,
    ContentMapValidationResponse,
)
from app.domains.content_map.service import ContentMapService
from app.schemas.common import ApiResponse

router = APIRouter(tags=["content-map"])


@router.get(
    "/projects/{project_id}/content-map",
    response_model=ApiResponse[ContentMapGraphResponse],
)
async def get_content_map(
    project_id: UUID,
    request: Request,
    session: SessionDep,
    actor: CurrentUserDep,
    node_types: Annotated[list[str] | None, Query()] = None,
    statuses: Annotated[list[str] | None, Query()] = None,
    search: Annotated[str | None, Query()] = None,
    view_mode: Annotated[str, Query()] = "combined",
) -> ApiResponse[ContentMapGraphResponse]:
    res = await ContentMapService().get_content_map(
        session,
        actor=actor,
        project_id=project_id,
        node_types=node_types,
        statuses=statuses,
        search=search,
        view_mode=view_mode,
    )
    return success(request, res)


@router.post(
    "/projects/{project_id}/content-map/generate",
    response_model=ApiResponse[ContentMapGraphResponse],
)
async def generate_content_map(
    project_id: UUID,
    request: Request,
    session: SessionDep,
    actor: CurrentUserDep,
) -> ApiResponse[ContentMapGraphResponse]:
    res = await ContentMapService().generate_initial_map(
        session,
        actor=actor,
        project_id=project_id,
        request_id=getattr(request.state, "request_id", ""),
    )
    return success(request, res)


@router.put(
    "/projects/{project_id}/content-map/layout",
    response_model=ApiResponse[dict[str, str]],
)
async def save_content_map_layout(
    project_id: UUID,
    payload: ContentMapLayoutUpdate,
    request: Request,
    session: SessionDep,
    actor: CurrentUserDep,
) -> ApiResponse[dict[str, str]]:
    await ContentMapService().save_layout(
        session,
        actor=actor,
        project_id=project_id,
        payload=payload,
        request_id=getattr(request.state, "request_id", ""),
    )
    return success(request, {"message": "Content map layout saved successfully."})


@router.get(
    "/projects/{project_id}/content-map/validation",
    response_model=ApiResponse[ContentMapValidationResponse],
)
async def validate_content_map(
    project_id: UUID,
    request: Request,
    session: SessionDep,
    actor: CurrentUserDep,
) -> ApiResponse[ContentMapValidationResponse]:
    res = await ContentMapService().validate_architecture(
        session,
        actor=actor,
        project_id=project_id,
    )
    return success(request, res)


@router.post(
    "/projects/{project_id}/content-map/versions",
    response_model=ApiResponse[ContentArchitectureVersionDetail],
    status_code=201,
)
async def create_architecture_version(
    project_id: UUID,
    payload: ContentArchitectureVersionCreate,
    request: Request,
    session: SessionDep,
    actor: CurrentUserDep,
) -> ApiResponse[ContentArchitectureVersionDetail]:
    res = await ContentMapService().create_version(
        session,
        actor=actor,
        project_id=project_id,
        payload=payload,
        request_id=getattr(request.state, "request_id", ""),
    )
    return success(request, res)


@router.get(
    "/projects/{project_id}/content-map/versions",
    response_model=ApiResponse[ContentArchitectureVersionList],
)
async def list_architecture_versions(
    project_id: UUID,
    request: Request,
    session: SessionDep,
    actor: CurrentUserDep,
) -> ApiResponse[ContentArchitectureVersionList]:
    res = await ContentMapService().list_versions(
        session,
        actor=actor,
        project_id=project_id,
    )
    return success(request, res)
