"""OIDC identity provisioning and current-user projection."""

from uuid import UUID

from app.core.errors import PermissionDenied
from app.db.session import set_actor_context
from app.domains.audit.repository import AuditWriter
from app.domains.users.models import User, UserStatus
from app.domains.users.repository import UserRepository
from app.domains.users.schemas import UserDetail
from app.security.oidc import IdentityClaims
from app.security.principal import AuthenticatedUser
from sqlalchemy.ext.asyncio import AsyncSession


class UserService:
    def __init__(self, repository: UserRepository | None = None) -> None:
        self._repository = repository or UserRepository()
        self._audit = AuditWriter()

    async def resolve_identity(
        self, session: AsyncSession, identity: IdentityClaims
    ) -> AuthenticatedUser:
        async with session.begin():
            user = await self._repository.upsert_identity(session, identity)
            if user.status != UserStatus.ACTIVE:
                raise PermissionDenied("This user account is suspended.")
        return AuthenticatedUser(
            user_id=user.id,
            issuer=user.identity_issuer,
            subject=user.identity_subject,
            email=user.email,
            display_name=user.display_name,
        )

    async def detail(self, session: AsyncSession, user_id: UUID, *, request_id: str) -> UserDetail:
        async with session.begin():
            await set_actor_context(session, user_id)
            user = await session.get(User, user_id)
            if user is None:
                raise RuntimeError("Authenticated user disappeared")
            self._audit.add(
                session,
                actor_user_id=user.id,
                organization_id=None,
                action="user.login",
                resource_type="user",
                resource_id=user.id,
                request_id=request_id,
            )
            return UserDetail.model_validate(user)
