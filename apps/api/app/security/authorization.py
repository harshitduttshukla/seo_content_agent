"""Resource-aware RBAC policy used by application services."""

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import PermissionDenied, ResourceNotFound
from app.domains.auth.repository import AuthorizationRepository
from app.security.principal import PermissionCode, RoleCode


class AuthorizationService:
    def __init__(self, repository: AuthorizationRepository | None = None) -> None:
        self._repository = repository or AuthorizationRepository()

    async def require_organization(
        self,
        session: AsyncSession,
        *,
        user_id: UUID,
        organization_id: UUID,
        permission: PermissionCode,
    ) -> RoleCode:
        role = await self._repository.organization_role(session, user_id, organization_id)
        if role is None:
            raise ResourceNotFound("organization")
        if not await self._repository.role_allows(session, role, permission):
            raise PermissionDenied()
        return role

    async def require_project(
        self,
        session: AsyncSession,
        *,
        user_id: UUID,
        organization_id: UUID,
        project_id: UUID,
        permission: PermissionCode,
    ) -> RoleCode:
        organization_role = await self._repository.organization_role(
            session, user_id, organization_id
        )
        if organization_role is None:
            raise ResourceNotFound("project")
        if not await self._repository.role_allows(session, organization_role, permission):
            raise PermissionDenied()
        if organization_role is RoleCode.ADMIN:
            return organization_role
        project_role = await self._repository.project_role(session, user_id, project_id)
        if project_role is None:
            raise ResourceNotFound("project")
        if not await self._repository.role_allows(session, project_role, permission):
            raise PermissionDenied()
        return project_role
