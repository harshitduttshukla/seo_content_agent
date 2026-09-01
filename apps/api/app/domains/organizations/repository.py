"""Tenant-scoped organization and member queries."""

from uuid import UUID

from app.core.cursor import Cursor
from app.domains.auth.models import OrganizationMember, Role
from app.domains.organizations.models import Organization
from app.domains.users.models import User
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession


class OrganizationRepository:
    async def list_for_user(
        self,
        session: AsyncSession,
        *,
        user_id: UUID,
        cursor: Cursor | None,
        limit: int,
    ) -> list[Organization]:
        statement = (
            select(Organization)
            .join(
                OrganizationMember,
                OrganizationMember.organization_id == Organization.id,
            )
            .where(
                OrganizationMember.user_id == user_id,
                OrganizationMember.status == "active",
                Organization.archived_at.is_(None),
            )
            .order_by(Organization.created_at.desc(), Organization.id.desc())
            .limit(limit + 1)
        )
        if cursor:
            statement = statement.where(
                or_(
                    Organization.created_at < cursor.created_at,
                    and_(
                        Organization.created_at == cursor.created_at,
                        Organization.id < cursor.resource_id,
                    ),
                )
            )
        return list((await session.scalars(statement)).all())

    async def get_for_user(
        self, session: AsyncSession, *, user_id: UUID, organization_id: UUID
    ) -> Organization | None:
        result: Organization | None = await session.scalar(
            select(Organization)
            .join(
                OrganizationMember,
                OrganizationMember.organization_id == Organization.id,
            )
            .where(
                Organization.id == organization_id,
                OrganizationMember.user_id == user_id,
                OrganizationMember.status == "active",
                Organization.archived_at.is_(None),
            )
        )
        return result

    async def list_members(
        self, session: AsyncSession, organization_id: UUID
    ) -> list[tuple[OrganizationMember, User, Role]]:
        rows = await session.execute(
            select(OrganizationMember, User, Role)
            .join(User, User.id == OrganizationMember.user_id)
            .join(Role, Role.id == OrganizationMember.role_id)
            .where(OrganizationMember.organization_id == organization_id)
            .order_by(User.display_name.asc(), User.id.asc())
        )
        return [(membership, user, role) for membership, user, role in rows.all()]

    async def get_member(
        self, session: AsyncSession, organization_id: UUID, user_id: UUID
    ) -> tuple[OrganizationMember, User, Role] | None:
        row = (
            await session.execute(
                select(OrganizationMember, User, Role)
                .join(User, User.id == OrganizationMember.user_id)
                .join(Role, Role.id == OrganizationMember.role_id)
                .where(
                    OrganizationMember.organization_id == organization_id,
                    OrganizationMember.user_id == user_id,
                )
            )
        ).one_or_none()
        if row is None:
            return None
        membership, user, role = row
        return membership, user, role

    async def count_active_admins(self, session: AsyncSession, organization_id: UUID) -> int:
        count = await session.scalar(
            select(func.count())
            .select_from(OrganizationMember)
            .join(Role, Role.id == OrganizationMember.role_id)
            .where(
                OrganizationMember.organization_id == organization_id,
                OrganizationMember.status == "active",
                Role.code == "admin",
            )
        )
        return int(count or 0)
