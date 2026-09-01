"""Centralized RBAC and membership persistence queries."""

from uuid import UUID

from app.domains.auth.models import (
    OrganizationMember,
    Permission,
    ProjectMember,
    Role,
    RolePermission,
)
from app.security.principal import PermissionCode, RoleCode
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession


class AuthorizationRepository:
    async def role_id(self, session: AsyncSession, code: RoleCode) -> UUID:
        role_id = await session.scalar(select(Role.id).where(Role.code == code.value))
        if role_id is None:
            raise RuntimeError(f"Seeded role is missing: {code.value}")
        return role_id

    async def organization_role(
        self, session: AsyncSession, user_id: UUID, organization_id: UUID
    ) -> RoleCode | None:
        code = await session.scalar(
            select(Role.code)
            .join(OrganizationMember, OrganizationMember.role_id == Role.id)
            .where(
                OrganizationMember.organization_id == organization_id,
                OrganizationMember.user_id == user_id,
                OrganizationMember.status == "active",
            )
        )
        return RoleCode(code) if code else None

    async def project_role(
        self, session: AsyncSession, user_id: UUID, project_id: UUID
    ) -> RoleCode | None:
        code = await session.scalar(
            select(Role.code)
            .join(ProjectMember, ProjectMember.role_id == Role.id)
            .where(ProjectMember.project_id == project_id, ProjectMember.user_id == user_id)
        )
        return RoleCode(code) if code else None

    async def role_allows(
        self, session: AsyncSession, role: RoleCode, permission: PermissionCode
    ) -> bool:
        statement = (
            select(func.count())
            .select_from(RolePermission)
            .join(Role, Role.id == RolePermission.role_id)
            .join(Permission, Permission.id == RolePermission.permission_id)
            .where(Role.code == role.value, Permission.code == permission.value)
        )
        return bool(await session.scalar(statement))

    async def add_project_member(
        self,
        session: AsyncSession,
        *,
        organization_id: UUID,
        project_id: UUID,
        user_id: UUID,
        role_id: UUID,
    ) -> ProjectMember:
        membership = ProjectMember(
            organization_id=organization_id,
            project_id=project_id,
            user_id=user_id,
            role_id=role_id,
        )
        session.add(membership)
        await session.flush()
        return membership
