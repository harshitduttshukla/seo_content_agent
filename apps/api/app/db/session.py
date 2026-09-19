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
from sqlalchemy.orm import SessionTransaction, SessionTransactionOrigin

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
    """Own a short transaction, or participate in an explicit caller transaction.

    SQLAlchemy records whether the current root transaction came from autobegin
    or an explicit begin. Helper nesting is tracked separately; depth alone never
    grants ownership of a caller's transaction.
    """
    info = session.info

    depth = info.get("_tx_depth", 0)
    info["_tx_depth"] = depth + 1
    try:
        if depth:
            yield session
            return

        transaction = session.sync_session.get_transaction()
        nested_transaction = session.sync_session.get_nested_transaction()
        if not isinstance(transaction, SessionTransaction):
            async with session.begin():
                yield session
            return

        if transaction.origin is not SessionTransactionOrigin.AUTOBEGIN or isinstance(
            nested_transaction, SessionTransaction
        ):
            # The caller's explicit begin context owns commit and rollback.
            yield session
            return

        try:
            yield session
            if session.sync_session.get_transaction() is not transaction:
                raise RuntimeError("transactional_session transaction changed before commit")
            await session.commit()
        except BaseException:
            if session.sync_session.get_transaction() is transaction:
                await session.rollback()
            raise
    finally:
        info["_tx_depth"] = depth


def has_explicit_transaction(session: AsyncSession) -> bool:
    """Identify a caller-managed transaction before starting a long-running agent."""
    transaction = session.sync_session.get_transaction()
    nested_transaction = session.sync_session.get_nested_transaction()
    return isinstance(nested_transaction, SessionTransaction) or (
        isinstance(transaction, SessionTransaction)
        and transaction.origin is not SessionTransactionOrigin.AUTOBEGIN
    )


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
