"""Async engine and request-session lifecycle."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config.settings import Settings


def build_engine(settings: Settings) -> AsyncEngine:
    """Build the process-scoped engine without connecting eagerly."""

    return create_async_engine(
        settings.DATABASE_URL,
        pool_pre_ping=True,
        pool_recycle=1_800,
    )


def build_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """Build request sessions; application services delimit transactions."""

    return async_sessionmaker(engine, expire_on_commit=False, autoflush=False)


async def session_scope(
    factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncSession]:
    """Yield one session without choosing an application transaction boundary."""

    async with factory() as session:
        yield session


_global_engine: AsyncEngine | None = None
_global_session_factory: async_sessionmaker[AsyncSession] | None = None


def async_session_factory() -> async_sessionmaker[AsyncSession]:
    """Provide process-level session factory for background tasks and workers."""
    global _global_engine, _global_session_factory
    if _global_session_factory is None:
        from app.config.settings import get_settings

        _global_engine = build_engine(get_settings())
        _global_session_factory = build_session_factory(_global_engine)
    return _global_session_factory


@asynccontextmanager
async def background_session_scope() -> AsyncIterator[AsyncSession]:
    """Provide an async context session for background execution."""
    factory = async_session_factory()
    async with factory() as session:
        yield session


@asynccontextmanager
async def transactional_session(session: AsyncSession) -> AsyncIterator[AsyncSession]:
    """Execute safely within an existing transaction or begin a new one."""
    if session.in_transaction():
        yield session
    else:
        async with session.begin():
            yield session


async def set_actor_context(session: AsyncSession, user_id: UUID) -> None:
    """Set trusted transaction-local context consumed by PostgreSQL RLS policies."""

    await session.execute(
        text("SELECT set_config('app.user_id', :user_id, true)"),
        {"user_id": str(user_id)},
    )


async def set_organization_bootstrap_context(session: AsyncSession, organization_id: UUID) -> None:
    """Authorize one organization ID for creation in the current transaction."""

    await session.execute(
        text("SELECT set_config('app.bootstrap_organization_id', :organization_id, true)"),
        {"organization_id": str(organization_id)},
    )
