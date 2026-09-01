"""FastAPI dependency adapters for sessions and verified identities."""

from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.errors import AuthenticationRequired
from app.db.session import session_scope
from app.domains.users.service import UserService
from app.security.oidc import IdentityClaims, TokenVerifier
from app.security.principal import AuthenticatedUser

bearer_scheme = HTTPBearer(auto_error=False)


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    factory: async_sessionmaker[AsyncSession] = request.app.state.session_factory
    async for session in session_scope(factory):
        yield session


async def get_verified_identity(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> IdentityClaims:
    if credentials is None or credentials.scheme.casefold() != "bearer":
        raise AuthenticationRequired()
    verifier: TokenVerifier = request.app.state.token_verifier
    return await verifier.verify(credentials.credentials)


async def get_current_user(
    identity: Annotated[IdentityClaims, Depends(get_verified_identity)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> AuthenticatedUser:
    return await UserService().resolve_identity(session, identity)


SessionDep = Annotated[AsyncSession, Depends(get_session)]
CurrentUserDep = Annotated[AuthenticatedUser, Depends(get_current_user)]
