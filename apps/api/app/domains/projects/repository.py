"""Tenant- and assignment-scoped project persistence."""

from uuid import UUID

from app.core.cursor import Cursor
from app.domains.auth.models import OrganizationMember, ProjectMember, Role
from app.domains.projects.models import Project
from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession


class ProjectRepository:
    async def list_for_user(
        self,
        session: AsyncSession,
        *,
        user_id: UUID,
        organization_id: UUID,
        cursor: Cursor | None,
        limit: int,
    ) -> list[Project]:
        statement = (
            select(Project)
            .join(
                OrganizationMember,
                OrganizationMember.organization_id == Project.organization_id,
            )
            .join(Role, Role.id == OrganizationMember.role_id)
            .outerjoin(
                ProjectMember,
                (ProjectMember.project_id == Project.id) & (ProjectMember.user_id == user_id),
            )
            .where(
                Project.organization_id == organization_id,
                OrganizationMember.user_id == user_id,
                OrganizationMember.status == "active",
                Project.archived_at.is_(None),
                or_(Role.code == "admin", ProjectMember.id.is_not(None)),
            )
            .order_by(Project.created_at.desc(), Project.id.desc())
            .limit(limit + 1)
        )
        if cursor:
            statement = statement.where(
                or_(
                    Project.created_at < cursor.created_at,
                    and_(
                        Project.created_at == cursor.created_at,
                        Project.id < cursor.resource_id,
                    ),
                )
            )
        return list((await session.scalars(statement)).unique().all())

    async def get_for_organization_member(
        self, session: AsyncSession, *, user_id: UUID, project_id: UUID
    ) -> Project | None:
        result: Project | None = await session.scalar(
            select(Project)
            .join(
                OrganizationMember,
                OrganizationMember.organization_id == Project.organization_id,
            )
            .where(
                Project.id == project_id,
                Project.archived_at.is_(None),
                OrganizationMember.user_id == user_id,
                OrganizationMember.status == "active",
            )
        )
        return result
