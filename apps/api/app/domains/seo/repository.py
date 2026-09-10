"""Repository for SEO Guides and version history."""

from uuid import UUID

from app.domains.seo.models import SEOGuide, SEOGuideVersion
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession


class SEOGuideRepository:
    async def get_guide_by_page_id(
        self, session: AsyncSession, *, page_id: UUID
    ) -> SEOGuide | None:
        stmt = select(SEOGuide).where(SEOGuide.page_id == page_id)
        res = await session.execute(stmt)
        return res.scalar_one_or_none()

    async def get_guide_by_id(self, session: AsyncSession, *, guide_id: UUID) -> SEOGuide | None:
        stmt = select(SEOGuide).where(SEOGuide.id == guide_id)
        res = await session.execute(stmt)
        return res.scalar_one_or_none()

    async def create_guide(self, session: AsyncSession, guide: SEOGuide) -> SEOGuide:
        session.add(guide)
        await session.flush()
        return guide

    async def update_guide(self, session: AsyncSession, guide: SEOGuide) -> SEOGuide:
        await session.flush()
        return guide

    async def create_version(
        self, session: AsyncSession, version_obj: SEOGuideVersion
    ) -> SEOGuideVersion:
        session.add(version_obj)
        await session.flush()
        return version_obj

    async def list_versions(self, session: AsyncSession, *, page_id: UUID) -> list[SEOGuideVersion]:
        stmt = (
            select(SEOGuideVersion)
            .where(SEOGuideVersion.page_id == page_id)
            .order_by(desc(SEOGuideVersion.version))
        )
        res = await session.execute(stmt)
        return list(res.scalars().all())
