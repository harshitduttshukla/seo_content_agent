"""Strategy domain repository for database operations."""

from uuid import UUID

from app.domains.strategy.models import SEOStrategy, SEOStrategyVersion
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession


class SEOStrategyRepository:
    """Encapsulates database queries for SEO strategies and strategy versions."""

    async def get_by_project_id(
        self, session: AsyncSession, *, project_id: UUID
    ) -> SEOStrategy | None:
        stmt = select(SEOStrategy).where(SEOStrategy.project_id == project_id)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_id(self, session: AsyncSession, *, strategy_id: UUID) -> SEOStrategy | None:
        stmt = select(SEOStrategy).where(SEOStrategy.id == strategy_id)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def create_strategy(
        self,
        session: AsyncSession,
        *,
        organization_id: UUID,
        project_id: UUID,
        current_version: int = 1,
        status: str = "active",
    ) -> SEOStrategy:
        strategy = SEOStrategy(
            organization_id=organization_id,
            project_id=project_id,
            current_version=current_version,
            status=status,
        )
        session.add(strategy)
        await session.flush()
        return strategy

    async def create_version(
        self,
        session: AsyncSession,
        *,
        strategy_id: UUID,
        organization_id: UUID,
        project_id: UUID,
        version: int,
        created_by_id: UUID | None,
        change_summary: str,
        strategy_data: dict[str, object],
    ) -> SEOStrategyVersion:
        strategy_version = SEOStrategyVersion(
            strategy_id=strategy_id,
            organization_id=organization_id,
            project_id=project_id,
            version=version,
            created_by_id=created_by_id,
            change_summary=change_summary,
            strategy_data=strategy_data,
        )
        session.add(strategy_version)
        await session.flush()
        return strategy_version

    async def get_latest_version(
        self, session: AsyncSession, *, strategy_id: UUID
    ) -> SEOStrategyVersion | None:
        stmt = (
            select(SEOStrategyVersion)
            .where(SEOStrategyVersion.strategy_id == strategy_id)
            .order_by(desc(SEOStrategyVersion.version))
            .limit(1)
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_version_by_number(
        self, session: AsyncSession, *, strategy_id: UUID, version: int
    ) -> SEOStrategyVersion | None:
        stmt = select(SEOStrategyVersion).where(
            SEOStrategyVersion.strategy_id == strategy_id,
            SEOStrategyVersion.version == version,
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_versions(
        self, session: AsyncSession, *, strategy_id: UUID
    ) -> list[SEOStrategyVersion]:
        stmt = (
            select(SEOStrategyVersion)
            .where(SEOStrategyVersion.strategy_id == strategy_id)
            .order_by(desc(SEOStrategyVersion.version))
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())
