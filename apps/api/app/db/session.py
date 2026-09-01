"""Async engine and request-session lifecycle."""

from collections.abc import AsyncIterator
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


async def set_actor_context(session: AsyncSession, user_id: UUID) -> None:
    """Set trusted transaction-local context consumed by PostgreSQL RLS policies."""

    await session.execute(
        text("SELECT set_config('app.user_id', :user_id, true)"),
        {"user_id": str(user_id)},
    )
