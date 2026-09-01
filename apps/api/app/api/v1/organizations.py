"""Organization and member routes; all behavior lives in services."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Header, Query, Request, status

from app.api.dependencies import CurrentUserDep, SessionDep
from app.api.responses import success
from app.domains.organizations.schemas import (
    OrganizationCreate,
    OrganizationDetail,
    OrganizationList,
    OrganizationMemberCreate,
    OrganizationMemberDetail,
    OrganizationMemberList,
    OrganizationMemberUpdate,
    OrganizationUpdate,
)
from app.domains.organizations.service import OrganizationService
from app.schemas.common import ApiResponse

router = APIRouter(prefix="/organizations", tags=["organizations"])


@router.post(
    "", response_model=ApiResponse[OrganizationDetail], status_code=status.HTTP_201_CREATED
)
async def create_organization(
    payload: OrganizationCreate,
    request: Request,
    session: SessionDep,
    actor: CurrentUserDep,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=8, max_length=200)],
) -> ApiResponse[OrganizationDetail]:
    detail = await OrganizationService().create(
        session,
        actor=actor,
        payload=payload,
        idempotency_key=idempotency_key,
        request_id=request.state.request_id,
    )
    return success(request, detail)


@router.get("", response_model=ApiResponse[OrganizationList])
async def list_organizations(
    request: Request,
    session: SessionDep,
    actor: CurrentUserDep,
    cursor: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=100),
) -> ApiResponse[OrganizationList]:
    page = await OrganizationService().list_page(session, actor=actor, cursor=cursor, limit=limit)
    return success(
        request,
        OrganizationList(items=page.items),
        next_cursor=page.next_cursor,
        has_more=page.has_more,
    )


@router.get("/{organization_id}", response_model=ApiResponse[OrganizationDetail])
async def get_organization(
    organization_id: UUID, request: Request, session: SessionDep, actor: CurrentUserDep
) -> ApiResponse[OrganizationDetail]:
    detail = await OrganizationService().get(session, actor=actor, organization_id=organization_id)
    return success(request, detail)


@router.put("/{organization_id}", response_model=ApiResponse[OrganizationDetail])
async def update_organization(
    organization_id: UUID,
    payload: OrganizationUpdate,
    request: Request,
    session: SessionDep,
    actor: CurrentUserDep,
) -> ApiResponse[OrganizationDetail]:
    detail = await OrganizationService().update(
        session,
        actor=actor,
        organization_id=organization_id,
        payload=payload,
        request_id=request.state.request_id,
    )
    return success(request, detail)


@router.get("/{organization_id}/members", response_model=ApiResponse[OrganizationMemberList])
async def list_members(
    organization_id: UUID, request: Request, session: SessionDep, actor: CurrentUserDep
) -> ApiResponse[OrganizationMemberList]:
    members = await OrganizationService().list_members(
        session, actor=actor, organization_id=organization_id
    )
    return success(request, OrganizationMemberList(items=members))


@router.post(
    "/{organization_id}/members",
    response_model=ApiResponse[OrganizationMemberDetail],
    status_code=status.HTTP_201_CREATED,
)
async def add_member(
    organization_id: UUID,
    payload: OrganizationMemberCreate,
    request: Request,
    session: SessionDep,
    actor: CurrentUserDep,
) -> ApiResponse[OrganizationMemberDetail]:
    member = await OrganizationService().add_member(
        session,
        actor=actor,
        organization_id=organization_id,
        payload=payload,
        request_id=request.state.request_id,
    )
    return success(request, member)


@router.patch(
    "/{organization_id}/members/{user_id}",
    response_model=ApiResponse[OrganizationMemberDetail],
)
async def update_member(
    organization_id: UUID,
    user_id: UUID,
    payload: OrganizationMemberUpdate,
    request: Request,
    session: SessionDep,
    actor: CurrentUserDep,
) -> ApiResponse[OrganizationMemberDetail]:
    member = await OrganizationService().update_member(
        session,
        actor=actor,
        organization_id=organization_id,
        user_id=user_id,
        payload=payload,
        request_id=request.state.request_id,
    )
    return success(request, member)
