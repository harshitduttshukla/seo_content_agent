"""Repository for internal linking relationships, link opportunities, and crawled link checks."""

from uuid import UUID

from app.domains.content.models import PageLink
from app.domains.internal_linking.models import (
    LinkOpportunity,
    PageRelationship,
)
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession


class InternalLinkingRepository:
    # --- Page Relationships ---

    async def list_relationships(
        self, session: AsyncSession, *, project_id: UUID, status: str | None = None
    ) -> list[PageRelationship]:
        stmt = select(PageRelationship).where(PageRelationship.project_id == project_id)
        if status:
            stmt = stmt.where(PageRelationship.status == status)
        stmt = stmt.order_by(desc(PageRelationship.created_at))
        res = await session.execute(stmt)
        return list(res.scalars().all())

    async def get_relationship_by_id(
        self, session: AsyncSession, *, rel_id: UUID
    ) -> PageRelationship | None:
        stmt = select(PageRelationship).where(PageRelationship.id == rel_id)
        res = await session.execute(stmt)
        return res.scalar_one_or_none()

    async def get_relationship_by_pair(
        self,
        session: AsyncSession,
        *,
        source_id: UUID,
        target_id: UUID,
        rel_type: str,
    ) -> PageRelationship | None:
        stmt = select(PageRelationship).where(
            PageRelationship.source_page_id == source_id,
            PageRelationship.target_page_id == target_id,
            PageRelationship.relationship_type == rel_type,
        )
        res = await session.execute(stmt)
        return res.scalar_one_or_none()

    async def create_relationship(
        self, session: AsyncSession, rel: PageRelationship
    ) -> PageRelationship:
        session.add(rel)
        await session.flush()
        return rel

    async def delete_relationship(self, session: AsyncSession, rel: PageRelationship) -> None:
        await session.delete(rel)
        await session.flush()

    # --- Link Opportunities ---

    async def list_opportunities(
        self, session: AsyncSession, *, project_id: UUID, status: str | None = None
    ) -> list[LinkOpportunity]:
        stmt = select(LinkOpportunity).where(LinkOpportunity.project_id == project_id)
        if status:
            stmt = stmt.where(LinkOpportunity.status == status)
        stmt = stmt.order_by(desc(LinkOpportunity.priority), desc(LinkOpportunity.confidence))
        res = await session.execute(stmt)
        return list(res.scalars().all())

    async def get_opportunity_by_id(
        self, session: AsyncSession, *, opp_id: UUID
    ) -> LinkOpportunity | None:
        stmt = select(LinkOpportunity).where(LinkOpportunity.id == opp_id)
        res = await session.execute(stmt)
        return res.scalar_one_or_none()

    async def get_opportunity_by_pair(
        self, session: AsyncSession, *, project_id: UUID, source_id: UUID, target_id: UUID
    ) -> LinkOpportunity | None:
        stmt = select(LinkOpportunity).where(
            LinkOpportunity.project_id == project_id,
            LinkOpportunity.source_page_id == source_id,
            LinkOpportunity.target_page_id == target_id,
        )
        res = await session.execute(stmt)
        return res.scalar_one_or_none()

    async def create_opportunity(
        self, session: AsyncSession, opp: LinkOpportunity
    ) -> LinkOpportunity:
        session.add(opp)
        await session.flush()
        return opp

    async def update_opportunity(
        self, session: AsyncSession, opp: LinkOpportunity
    ) -> LinkOpportunity:
        await session.flush()
        return opp

    # --- Crawled Link Checks ---

    async def get_crawled_inbound_links(
        self, session: AsyncSession, *, target_page_id: UUID
    ) -> list[PageLink]:
        stmt = select(PageLink).where(PageLink.target_page_id == target_page_id)
        res = await session.execute(stmt)
        return list(res.scalars().all())

    async def get_crawled_outbound_links(
        self, session: AsyncSession, *, source_page_id: UUID
    ) -> list[PageLink]:
        stmt = select(PageLink).where(PageLink.source_page_id == source_page_id)
        res = await session.execute(stmt)
        return list(res.scalars().all())
