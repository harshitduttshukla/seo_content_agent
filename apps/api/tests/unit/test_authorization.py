from uuid import uuid4

import pytest
from app.core.errors import PermissionDenied, ResourceNotFound
from app.security.authorization import AuthorizationService
from app.security.principal import PermissionCode, RoleCode


class FakeAuthorizationRepository:
    def __init__(
        self,
        *,
        organization_role: RoleCode | None,
        project_role: RoleCode | None = None,
        allowed: set[tuple[RoleCode, PermissionCode]] | None = None,
    ) -> None:
        self._organization_role = organization_role
        self._project_role = project_role
        self._allowed = allowed or set()

    async def organization_role(self, *_: object) -> RoleCode | None:
        return self._organization_role

    async def project_role(self, *_: object) -> RoleCode | None:
        return self._project_role

    async def role_allows(
        self, _session: object, role: RoleCode, permission: PermissionCode
    ) -> bool:
        return (role, permission) in self._allowed


@pytest.mark.asyncio
async def test_foreign_organization_is_non_disclosing() -> None:
    service = AuthorizationService(FakeAuthorizationRepository(organization_role=None))  # type: ignore[arg-type]

    with pytest.raises(ResourceNotFound):
        await service.require_organization(
            object(),  # type: ignore[arg-type]
            user_id=uuid4(),
            organization_id=uuid4(),
            permission=PermissionCode.PROJECT_READ,
        )


@pytest.mark.asyncio
async def test_project_permission_is_intersection_of_org_and_assignment() -> None:
    permission = PermissionCode.PROJECT_UPDATE
    repository = FakeAuthorizationRepository(
        organization_role=RoleCode.SEO_MANAGER,
        project_role=RoleCode.VIEWER,
        allowed={(RoleCode.SEO_MANAGER, permission)},
    )
    service = AuthorizationService(repository)  # type: ignore[arg-type]

    with pytest.raises(PermissionDenied):
        await service.require_project(
            object(),  # type: ignore[arg-type]
            user_id=uuid4(),
            organization_id=uuid4(),
            project_id=uuid4(),
            permission=permission,
        )
