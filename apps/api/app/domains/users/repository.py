"""Persistence operations for global external identities."""

from datetime import UTC, datetime

from app.domains.users.models import User, UserStatus
from app.security.oidc import IdentityClaims
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


class UserRepository:
    async def upsert_identity(self, session: AsyncSession, identity: IdentityClaims) -> User:
        statement = select(User).where(
            User.identity_issuer == identity.issuer,
            User.identity_subject == identity.subject,
        )
        user = await session.scalar(statement)
        now = datetime.now(UTC)
        if user is None:
            user = User(
                identity_issuer=identity.issuer,
                identity_subject=identity.subject,
                email=identity.email,
                normalized_email=identity.email.casefold(),
                display_name=identity.display_name,
                status=UserStatus.ACTIVE,
                last_seen_at=now,
            )
            session.add(user)
            await session.flush()
            return user
        user.email = identity.email
        user.normalized_email = identity.email.casefold()
        user.display_name = identity.display_name
        user.last_seen_at = now
        await session.flush()
        return user
