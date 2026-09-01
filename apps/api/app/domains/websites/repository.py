"""Tenant-scoped website persistence."""

from uuid import UUID

from app.core.cursor import Cursor
from app.domains.auth.models import OrganizationMember
from app.domains.websites.models import Website
from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession


class WebsiteRepository:
    async def list_for_project(
        self,
        session: AsyncSession,
        *,
        organization_id: UUID,
        project_id: UUID,
        cursor: Cursor | None,
        limit: int,
    ) -> list[Website]:
        statement = (
            select(Website)
            .where(
                Website.organization_id == organization_id,
                Website.project_id == project_id,
                Website.archived_at.is_(None),
            )
            .order_by(Website.created_at.desc(), Website.id.desc())
            .limit(limit + 1)
        )
        if cursor:
            statement = statement.where(
                or_(
                    Website.created_at < cursor.created_at,
                    and_(
                        Website.created_at == cursor.created_at,
                        Website.id < cursor.resource_id,
                    ),
                )
            )
        return list((await session.scalars(statement)).all())

    async def get_for_organization_member(
        self, session: AsyncSession, *, user_id: UUID, website_id: UUID
    ) -> Website | None:
        result: Website | None = await session.scalar(
            select(Website)
            .join(
                OrganizationMember,
                OrganizationMember.organization_id == Website.organization_id,
            )
            .where(
                Website.id == website_id,
                Website.archived_at.is_(None),
                OrganizationMember.user_id == user_id,
                OrganizationMember.status == "active",
            )
        )
        return result
