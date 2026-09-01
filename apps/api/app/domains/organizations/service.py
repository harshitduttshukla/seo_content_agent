"""Organization aggregate and membership application services."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from app.core.cursor import decode_cursor, encode_cursor
from app.core.errors import ConflictError, ResourceNotFound
from app.core.pagination import PageResult
from app.core.validators import normalize_slug
from app.db.session import set_actor_context
from app.domains.audit.repository import (
    AuditWriter,
    IdempotencyRepository,
    OutboxWriter,
    request_fingerprint,
)
from app.domains.auth.models import MembershipStatus, OrganizationMember
from app.domains.auth.repository import AuthorizationRepository
from app.domains.organizations.models import Organization, OrganizationStatus
from app.domains.organizations.repository import OrganizationRepository
from app.domains.organizations.schemas import (
    OrganizationCreate,
    OrganizationDetail,
    OrganizationMemberCreate,
    OrganizationMemberDetail,
    OrganizationMemberUpdate,
    OrganizationUpdate,
)
from app.security.authorization import AuthorizationService
from app.security.principal import AuthenticatedUser, PermissionCode, RoleCode
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession


class OrganizationService:
    def __init__(self) -> None:
        self._organizations = OrganizationRepository()
        self._access_repository = AuthorizationRepository()
        self._authorization = AuthorizationService(self._access_repository)
        self._audit = AuditWriter()
        self._outbox = OutboxWriter()
        self._idempotency = IdempotencyRepository()

    async def create(
        self,
        session: AsyncSession,
        *,
        actor: AuthenticatedUser,
        payload: OrganizationCreate,
        idempotency_key: str,
        request_id: str,
    ) -> OrganizationDetail:
        slug = normalize_slug(payload.slug or payload.name)
        fingerprint = request_fingerprint(payload.model_dump(mode="json"))
        try:
            async with session.begin():
                await set_actor_context(session, actor.user_id)
                record, created = await self._idempotency.claim(
                    session,
                    organization_id=None,
                    actor_user_id=actor.user_id,
                    route="POST /organizations",
                    idempotency_key=idempotency_key,
                    request_hash=fingerprint,
                )
                if not created:
                    return OrganizationDetail.model_validate(record.response_data)
                organization = Organization(
                    name=payload.name.strip(),
                    slug=slug,
                    status=OrganizationStatus.ACTIVE,
                    settings={},
                )
                session.add(organization)
                await session.flush()
                admin_role_id = await self._access_repository.role_id(session, RoleCode.ADMIN)
                session.add(
                    OrganizationMember(
                        organization_id=organization.id,
                        user_id=actor.user_id,
                        role_id=admin_role_id,
                        status=MembershipStatus.ACTIVE,
                        invited_by_id=actor.user_id,
                        joined_at=datetime.now(UTC),
                    )
                )
                detail = OrganizationDetail.model_validate(organization)
                self._audit.add(
                    session,
                    actor_user_id=actor.user_id,
                    organization_id=organization.id,
                    action="organization.created",
                    resource_type="organization",
                    resource_id=organization.id,
                    request_id=request_id,
                )
                self._outbox.add(
                    session,
                    organization_id=organization.id,
                    project_id=None,
                    aggregate_type="organization",
                    aggregate_id=organization.id,
                    event_type="organization.created",
                )
                self._idempotency.complete(record, detail.model_dump(mode="json"), 201)
                return detail
        except IntegrityError as exc:
            raise ConflictError(
                "ORGANIZATION_SLUG_CONFLICT", "An active organization already uses this slug."
            ) from exc

    async def list_page(
        self,
        session: AsyncSession,
        *,
        actor: AuthenticatedUser,
        cursor: str | None,
        limit: int,
    ) -> PageResult[OrganizationDetail]:
        async with session.begin():
            await set_actor_context(session, actor.user_id)
            rows = await self._organizations.list_for_user(
                session,
                user_id=actor.user_id,
                cursor=decode_cursor(cursor),
                limit=limit,
            )
            has_more = len(rows) > limit
            visible = rows[:limit]
            next_cursor = (
                encode_cursor(visible[-1].created_at, visible[-1].id)
                if has_more and visible
                else None
            )
            return PageResult(
                items=[OrganizationDetail.model_validate(row) for row in visible],
                next_cursor=next_cursor,
                has_more=has_more,
            )

    async def get(
        self, session: AsyncSession, *, actor: AuthenticatedUser, organization_id: UUID
    ) -> OrganizationDetail:
        async with session.begin():
            await set_actor_context(session, actor.user_id)
            organization = await self._organizations.get_for_user(
                session, user_id=actor.user_id, organization_id=organization_id
            )
            if organization is None:
                raise ResourceNotFound("organization")
            await self._authorization.require_organization(
                session,
                user_id=actor.user_id,
                organization_id=organization_id,
                permission=PermissionCode.ORGANIZATION_READ,
            )
            return OrganizationDetail.model_validate(organization)

    async def update(
        self,
        session: AsyncSession,
        *,
        actor: AuthenticatedUser,
        organization_id: UUID,
        payload: OrganizationUpdate,
        request_id: str,
    ) -> OrganizationDetail:
        try:
            async with session.begin():
                await set_actor_context(session, actor.user_id)
                organization = await self._organizations.get_for_user(
                    session, user_id=actor.user_id, organization_id=organization_id
                )
                if organization is None:
                    raise ResourceNotFound("organization")
                await self._authorization.require_organization(
                    session,
                    user_id=actor.user_id,
                    organization_id=organization_id,
                    permission=PermissionCode.ORGANIZATION_UPDATE,
                )
                if organization.revision != payload.revision:
                    raise ConflictError(
                        "VERSION_CONFLICT",
                        "The organization changed; refresh and retry.",
                        details={"current_revision": organization.revision},
                    )
                organization.name = payload.name.strip()
                organization.slug = normalize_slug(payload.slug)
                organization.status = payload.status
                organization.revision += 1
                await session.flush()
                self._audit.add(
                    session,
                    actor_user_id=actor.user_id,
                    organization_id=organization.id,
                    action="organization.updated",
                    resource_type="organization",
                    resource_id=organization.id,
                    request_id=request_id,
                )
                return OrganizationDetail.model_validate(organization)
        except IntegrityError as exc:
            raise ConflictError(
                "ORGANIZATION_SLUG_CONFLICT", "An active organization already uses this slug."
            ) from exc

    async def list_members(
        self, session: AsyncSession, *, actor: AuthenticatedUser, organization_id: UUID
    ) -> list[OrganizationMemberDetail]:
        async with session.begin():
            await set_actor_context(session, actor.user_id)
            await self._authorization.require_organization(
                session,
                user_id=actor.user_id,
                organization_id=organization_id,
                permission=PermissionCode.MEMBERS_READ,
            )
            rows = await self._organizations.list_members(session, organization_id)
            return [
                OrganizationMemberDetail(
                    id=membership.id,
                    user_id=user.id,
                    email=user.email,
                    display_name=user.display_name,
                    role=RoleCode(role.code),
                    status=membership.status,
                    joined_at=membership.joined_at,
                )
                for membership, user, role in rows
            ]

    async def add_member(
        self,
        session: AsyncSession,
        *,
        actor: AuthenticatedUser,
        organization_id: UUID,
        payload: OrganizationMemberCreate,
        request_id: str,
    ) -> OrganizationMemberDetail:
        try:
            async with session.begin():
                await set_actor_context(session, actor.user_id)
                await self._authorization.require_organization(
                    session,
                    user_id=actor.user_id,
                    organization_id=organization_id,
                    permission=PermissionCode.MEMBERS_MANAGE,
                )
                from app.domains.users.models import User

                user = await session.get(User, payload.user_id)
                if user is None:
                    raise ResourceNotFound("user")
                role_id = await self._access_repository.role_id(session, payload.role)
                membership = OrganizationMember(
                    organization_id=organization_id,
                    user_id=user.id,
                    role_id=role_id,
                    status=MembershipStatus.ACTIVE,
                    invited_by_id=actor.user_id,
                    joined_at=datetime.now(UTC),
                )
                session.add(membership)
                await session.flush()
                self._audit.add(
                    session,
                    actor_user_id=actor.user_id,
                    organization_id=organization_id,
                    action="member.added",
                    resource_type="user",
                    resource_id=user.id,
                    request_id=request_id,
                    metadata={"role": payload.role.value},
                )
                return OrganizationMemberDetail(
                    id=membership.id,
                    user_id=user.id,
                    email=user.email,
                    display_name=user.display_name,
                    role=payload.role,
                    status=membership.status,
                    joined_at=membership.joined_at,
                )
        except IntegrityError as exc:
            raise ConflictError(
                "MEMBERSHIP_EXISTS", "This user is already a member of the organization."
            ) from exc

    async def update_member(
        self,
        session: AsyncSession,
        *,
        actor: AuthenticatedUser,
        organization_id: UUID,
        user_id: UUID,
        payload: OrganizationMemberUpdate,
        request_id: str,
    ) -> OrganizationMemberDetail:
        async with session.begin():
            await set_actor_context(session, actor.user_id)
            await self._authorization.require_organization(
                session,
                user_id=actor.user_id,
                organization_id=organization_id,
                permission=PermissionCode.MEMBERS_MANAGE,
            )
            row = await self._organizations.get_member(session, organization_id, user_id)
            if row is None:
                raise ResourceNotFound("member")
            membership, user, current_role = row
            removes_admin = current_role.code == "admin" and (
                payload.role is not RoleCode.ADMIN or payload.status != MembershipStatus.ACTIVE
            )
            if (
                removes_admin
                and await self._organizations.count_active_admins(session, organization_id) <= 1
            ):
                raise ConflictError(
                    "LAST_ADMIN_REQUIRED", "An organization must retain at least one active admin."
                )
            membership.role_id = await self._access_repository.role_id(session, payload.role)
            membership.status = payload.status
            await session.flush()
            self._audit.add(
                session,
                actor_user_id=actor.user_id,
                organization_id=organization_id,
                action="permission.changed",
                resource_type="user",
                resource_id=user.id,
                request_id=request_id,
                metadata={"role": payload.role.value, "status": payload.status},
            )
            return OrganizationMemberDetail(
                id=membership.id,
                user_id=user.id,
                email=user.email,
                display_name=user.display_name,
                role=payload.role,
                status=membership.status,
                joined_at=membership.joined_at,
            )
