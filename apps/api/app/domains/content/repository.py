"""Repository for content pages, versions, links, pillars, topics, mappings, and opportunities."""

from datetime import UTC, datetime
from uuid import UUID

from app.core.cursor import Cursor
from app.domains.content.models import (
    ArchitectureStatus,
    ContentOpportunity,
    ContentPage,
    ContentPageVersion,
    ContentPillar,
    ContentStatus,
    KeywordPageMapping,
    MappingSource,
    MappingStatus,
    MappingType,
    OpportunityAction,
    OpportunityStatus,
    PageKeyword,
    PageLink,
    PlannedContentPage,
    Topic,
)
from sqlalchemy import desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession


class ContentRepository:
    async def get_page_by_url(
        self, session: AsyncSession, *, website_id: UUID, normalized_url: str
    ) -> ContentPage | None:
        stmt = select(ContentPage).where(
            ContentPage.website_id == website_id,
            ContentPage.normalized_url == normalized_url,
        )
        result = await session.execute(stmt)
        return result.scalars().first()

    async def get_page_by_id(
        self, session: AsyncSession, *, page_id: UUID, organization_id: UUID | None = None
    ) -> ContentPage | None:
        stmt = select(ContentPage).where(ContentPage.id == page_id)
        if organization_id is not None:
            stmt = stmt.where(ContentPage.organization_id == organization_id)
        result = await session.execute(stmt)
        return result.scalars().first()

    async def list_pages(
        self,
        session: AsyncSession,
        *,
        website_id: UUID,
        status: str | None = None,
        search: str | None = None,
        cursor: Cursor | None = None,
        limit: int = 50,
    ) -> list[ContentPage]:
        stmt = select(ContentPage).where(ContentPage.website_id == website_id)

        if status:
            stmt = stmt.where(ContentPage.content_status == status)

        if search:
            search_pattern = f"%{search.strip()}%"
            stmt = stmt.where(
                or_(
                    ContentPage.url.ilike(search_pattern),
                    ContentPage.title.ilike(search_pattern),
                )
            )

        if cursor is not None:
            stmt = stmt.where(
                or_(
                    ContentPage.created_at < cursor.created_at,
                    (ContentPage.created_at == cursor.created_at)
                    & (ContentPage.id < cursor.resource_id),
                )
            )

        stmt = stmt.order_by(desc(ContentPage.created_at), desc(ContentPage.id)).limit(limit + 1)
        result = await session.execute(stmt)
        return list(result.scalars().all())

    async def list_all_pages_for_website(
        self, session: AsyncSession, *, website_id: UUID
    ) -> list[ContentPage]:
        stmt = (
            select(ContentPage)
            .where(
                ContentPage.website_id == website_id,
                ContentPage.content_status == ContentStatus.INDEXED,
            )
            .order_by(desc(ContentPage.created_at))
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())

    async def count_pages(self, session: AsyncSession, *, website_id: UUID) -> int:
        stmt = select(func.count(ContentPage.id)).where(ContentPage.website_id == website_id)
        result = await session.execute(stmt)
        return result.scalar_one()

    async def upsert_page(
        self,
        session: AsyncSession,
        *,
        organization_id: UUID,
        project_id: UUID,
        website_id: UUID,
        url: str,
        normalized_url: str,
        canonical_url: str | None,
        title: str,
        meta_description: str,
        language: str,
        http_status: int | None,
        content_type: str,
        word_count: int,
        content_hash: str,
        content_status: str,
        cleaned_content: str,
        structured_content: dict[str, object],
        metadata: dict[str, object],
        headings: list[dict[str, object]],
        images: list[dict[str, object]],
        raw_html: str | None = None,
        crawl_job_id: UUID | None = None,
    ) -> tuple[ContentPage, bool]:
        """Upsert page; if content_hash changes, create a new ContentPageVersion."""
        now = datetime.now(UTC)
        page = await self.get_page_by_url(
            session, website_id=website_id, normalized_url=normalized_url
        )

        if page is None:
            # Check duplicate content hash across the website
            hash_match_stmt = select(ContentPage.id).where(
                ContentPage.website_id == website_id,
                ContentPage.content_hash == content_hash,
                ContentPage.content_hash != "",
            )
            existing_hash = (await session.execute(hash_match_stmt)).scalars().first()
            if existing_hash and content_status == ContentStatus.INDEXED:
                content_status = ContentStatus.DUPLICATE

            page = ContentPage(
                organization_id=organization_id,
                project_id=project_id,
                website_id=website_id,
                url=url,
                normalized_url=normalized_url,
                canonical_url=canonical_url,
                title=title,
                meta_description=meta_description,
                language=language,
                http_status=http_status,
                content_type=content_type,
                word_count=word_count,
                content_hash=content_hash,
                content_status=content_status,
                raw_html=raw_html,
                cleaned_content=cleaned_content,
                structured_content=structured_content,
                metadata_=metadata,
                headings=headings,
                images=images,
                first_seen_at=now,
                last_crawled_at=now,
            )
            session.add(page)
            await session.flush()

            # Create initial version
            version = ContentPageVersion(
                page_id=page.id,
                crawl_job_id=crawl_job_id,
                content_hash=content_hash,
                title=title,
                structured_content=structured_content,
                cleaned_content=cleaned_content,
                metadata_=metadata,
                created_at=now,
            )
            session.add(version)
            await session.flush()
            return page, True
        else:
            # Existing page update
            content_changed = page.content_hash != content_hash

            page.url = url
            page.canonical_url = canonical_url
            page.title = title
            page.meta_description = meta_description
            page.language = language
            page.http_status = http_status
            page.content_type = content_type
            page.word_count = word_count
            page.content_hash = content_hash
            page.content_status = content_status
            page.cleaned_content = cleaned_content
            page.structured_content = structured_content
            page.metadata_ = metadata
            page.headings = headings
            page.images = images
            page.last_crawled_at = now
            page.revision += 1

            if content_changed:
                version = ContentPageVersion(
                    page_id=page.id,
                    crawl_job_id=crawl_job_id,
                    content_hash=content_hash,
                    title=title,
                    structured_content=structured_content,
                    cleaned_content=cleaned_content,
                    metadata_=metadata,
                    created_at=now,
                )
                session.add(version)

            await session.flush()
            return page, content_changed

    async def replace_page_links(
        self,
        session: AsyncSession,
        *,
        website_id: UUID,
        source_page_id: UUID,
        links: list[dict[str, object]],
    ) -> None:
        """Clear and insert links discovered for a source page."""
        delete_stmt = select(PageLink).where(
            PageLink.website_id == website_id, PageLink.source_page_id == source_page_id
        )
        existing_links = (await session.execute(delete_stmt)).scalars().all()
        for link in existing_links:
            await session.delete(link)

        now = datetime.now(UTC)
        for link_data in links:
            page_link = PageLink(
                website_id=website_id,
                source_page_id=source_page_id,
                target_url=str(link_data["target_url"]),
                normalized_target_url=str(link_data["normalized_target_url"]),
                anchor_text=str(link_data.get("anchor_text", "")),
                rel=str(link_data["rel"]) if link_data.get("rel") else None,
                is_internal=bool(link_data.get("is_internal", True)),
                nofollow=bool(link_data.get("nofollow", False)),
                ugc=bool(link_data.get("ugc", False)),
                sponsored=bool(link_data.get("sponsored", False)),
                discovered_at=now,
            )
            session.add(page_link)
        await session.flush()

    async def list_links_for_website(
        self, session: AsyncSession, *, website_id: UUID, limit: int = 100
    ) -> list[PageLink]:
        stmt = (
            select(PageLink)
            .where(PageLink.website_id == website_id)
            .order_by(desc(PageLink.discovered_at))
            .limit(limit)
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())

    # --- Content Pillars ---

    async def create_pillar(
        self,
        session: AsyncSession,
        *,
        organization_id: UUID,
        project_id: UUID,
        name: str,
        slug: str,
        description: str = "",
        business_goal: str = "",
        priority: int = 1,
        status: str = ArchitectureStatus.PROPOSED,
    ) -> ContentPillar:
        pillar = ContentPillar(
            organization_id=organization_id,
            project_id=project_id,
            name=name,
            slug=slug,
            description=description,
            business_goal=business_goal,
            priority=priority,
            status=status,
        )
        session.add(pillar)
        await session.flush()
        return pillar

    async def get_pillar_by_id(
        self, session: AsyncSession, *, pillar_id: UUID, project_id: UUID
    ) -> ContentPillar | None:
        stmt = select(ContentPillar).where(
            ContentPillar.id == pillar_id, ContentPillar.project_id == project_id
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_pillar_by_slug(
        self, session: AsyncSession, *, project_id: UUID, slug: str
    ) -> ContentPillar | None:
        stmt = select(ContentPillar).where(
            ContentPillar.project_id == project_id, ContentPillar.slug == slug
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_pillars(self, session: AsyncSession, *, project_id: UUID) -> list[ContentPillar]:
        stmt = (
            select(ContentPillar)
            .where(ContentPillar.project_id == project_id)
            .order_by(ContentPillar.priority, ContentPillar.name)
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())

    # --- Topics ---

    async def create_topic(
        self,
        session: AsyncSession,
        *,
        organization_id: UUID,
        project_id: UUID,
        pillar_id: UUID | None,
        name: str,
        slug: str,
        description: str = "",
        priority: int = 1,
        status: str = ArchitectureStatus.PROPOSED,
    ) -> Topic:
        topic = Topic(
            organization_id=organization_id,
            project_id=project_id,
            pillar_id=pillar_id,
            name=name,
            slug=slug,
            description=description,
            priority=priority,
            status=status,
        )
        session.add(topic)
        await session.flush()
        return topic

    async def get_topic_by_id(
        self, session: AsyncSession, *, topic_id: UUID, project_id: UUID
    ) -> Topic | None:
        stmt = select(Topic).where(Topic.id == topic_id, Topic.project_id == project_id)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_topic_by_slug(
        self, session: AsyncSession, *, project_id: UUID, slug: str
    ) -> Topic | None:
        stmt = select(Topic).where(Topic.project_id == project_id, Topic.slug == slug)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_topics(
        self, session: AsyncSession, *, project_id: UUID, pillar_id: UUID | None = None
    ) -> list[Topic]:
        stmt = select(Topic).where(Topic.project_id == project_id)
        if pillar_id is not None:
            stmt = stmt.where(Topic.pillar_id == pillar_id)
        stmt = stmt.order_by(Topic.priority, Topic.name)
        result = await session.execute(stmt)
        return list(result.scalars().all())

    # --- Keyword to Page Mappings ---

    async def create_or_update_mapping(
        self,
        session: AsyncSession,
        *,
        organization_id: UUID,
        project_id: UUID,
        website_id: UUID,
        keyword_id: UUID,
        page_id: UUID | None,
        mapping_type: str = MappingType.PRIMARY_TARGET,
        confidence: float = 1.0,
        source: str = MappingSource.DETERMINISTIC,
        status: str = MappingStatus.PROPOSED,
        rationale: str = "",
    ) -> KeywordPageMapping:
        stmt = select(KeywordPageMapping).where(
            KeywordPageMapping.project_id == project_id,
            KeywordPageMapping.keyword_id == keyword_id,
        )
        existing = (await session.execute(stmt)).scalar_one_or_none()
        if existing:
            existing.page_id = page_id
            existing.mapping_type = mapping_type
            existing.confidence = confidence
            existing.source = source
            existing.status = status
            existing.rationale = rationale
            existing.revision += 1
            await session.flush()
            return existing

        mapping = KeywordPageMapping(
            organization_id=organization_id,
            project_id=project_id,
            website_id=website_id,
            keyword_id=keyword_id,
            page_id=page_id,
            mapping_type=mapping_type,
            confidence=confidence,
            source=source,
            status=status,
            rationale=rationale,
        )
        session.add(mapping)
        await session.flush()
        return mapping

    async def list_mappings_for_project(
        self, session: AsyncSession, *, project_id: UUID
    ) -> list[KeywordPageMapping]:
        stmt = select(KeywordPageMapping).where(KeywordPageMapping.project_id == project_id)
        result = await session.execute(stmt)
        return list(result.scalars().all())

    # --- Content Opportunities ---

    async def create_or_update_opportunity(
        self,
        session: AsyncSession,
        *,
        organization_id: UUID,
        project_id: UUID,
        website_id: UUID,
        cluster_id: UUID | None,
        keyword_id: UUID | None,
        action: str = OpportunityAction.NEW_PAGE,
        priority: float = 0.0,
        business_value_score: float = 0.0,
        existing_page_id: UUID | None = None,
        reason: str = "",
        confidence: float = 1.0,
        status: str = OpportunityStatus.PROPOSED,
    ) -> ContentOpportunity:
        stmt = select(ContentOpportunity).where(
            ContentOpportunity.project_id == project_id,
        )
        if cluster_id:
            stmt = stmt.where(ContentOpportunity.cluster_id == cluster_id)
        elif keyword_id:
            stmt = stmt.where(ContentOpportunity.keyword_id == keyword_id)

        existing = (await session.execute(stmt)).scalar_one_or_none()
        if existing:
            existing.action = action
            existing.priority = priority
            existing.business_value_score = business_value_score
            existing.existing_page_id = existing_page_id
            existing.reason = reason
            existing.confidence = confidence
            existing.status = status
            existing.revision += 1
            await session.flush()
            return existing

        opp = ContentOpportunity(
            organization_id=organization_id,
            project_id=project_id,
            website_id=website_id,
            cluster_id=cluster_id,
            keyword_id=keyword_id,
            action=action,
            priority=priority,
            business_value_score=business_value_score,
            existing_page_id=existing_page_id,
            reason=reason,
            confidence=confidence,
            status=status,
        )
        session.add(opp)
        await session.flush()
        return opp

    async def list_opportunities(
        self, session: AsyncSession, *, project_id: UUID, status: str | None = None
    ) -> list[ContentOpportunity]:
        stmt = select(ContentOpportunity).where(ContentOpportunity.project_id == project_id)
        if status:
            stmt = stmt.where(ContentOpportunity.status == status)
        stmt = stmt.order_by(desc(ContentOpportunity.priority))
        result = await session.execute(stmt)
        return list(result.scalars().all())

    async def get_opportunity_by_id(
        self, session: AsyncSession, *, opportunity_id: UUID, project_id: UUID
    ) -> ContentOpportunity | None:
        stmt = select(ContentOpportunity).where(
            ContentOpportunity.id == opportunity_id,
            ContentOpportunity.project_id == project_id,
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    # --- Phase 4 Planned Content Pages ---

    async def create_planned_page(
        self, session: AsyncSession, page: PlannedContentPage
    ) -> PlannedContentPage:
        session.add(page)
        await session.flush()
        return page

    async def get_planned_page_by_id(
        self, session: AsyncSession, *, page_id: UUID, project_id: UUID | None = None
    ) -> PlannedContentPage | None:
        stmt = select(PlannedContentPage).where(PlannedContentPage.id == page_id)
        if project_id is not None:
            stmt = stmt.where(PlannedContentPage.project_id == project_id)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_planned_page_by_slug(
        self, session: AsyncSession, *, project_id: UUID, slug: str
    ) -> PlannedContentPage | None:
        stmt = select(PlannedContentPage).where(
            PlannedContentPage.project_id == project_id,
            PlannedContentPage.slug == slug,
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_planned_pages(
        self,
        session: AsyncSession,
        *,
        project_id: UUID,
        status: str | None = None,
        cluster_id: UUID | None = None,
        topic_id: UUID | None = None,
        pillar_id: UUID | None = None,
        page_type: str | None = None,
        search: str | None = None,
    ) -> list[PlannedContentPage]:
        stmt = select(PlannedContentPage).where(PlannedContentPage.project_id == project_id)
        if status:
            stmt = stmt.where(PlannedContentPage.status == status)
        if cluster_id:
            stmt = stmt.where(PlannedContentPage.cluster_id == cluster_id)
        if topic_id:
            stmt = stmt.where(PlannedContentPage.topic_id == topic_id)
        if pillar_id:
            stmt = stmt.where(PlannedContentPage.pillar_id == pillar_id)
        if page_type:
            stmt = stmt.where(PlannedContentPage.page_type == page_type)
        if search:
            search_pat = f"%{search.strip()}%"
            stmt = stmt.where(
                or_(
                    PlannedContentPage.title.ilike(search_pat),
                    PlannedContentPage.primary_keyword.ilike(search_pat),
                    PlannedContentPage.slug.ilike(search_pat),
                )
            )
        stmt = stmt.order_by(desc(PlannedContentPage.priority), desc(PlannedContentPage.created_at))
        result = await session.execute(stmt)
        return list(result.scalars().all())

    async def update_planned_page(
        self, session: AsyncSession, page: PlannedContentPage
    ) -> PlannedContentPage:
        await session.flush()
        return page

    async def delete_planned_page(self, session: AsyncSession, page: PlannedContentPage) -> None:
        await session.delete(page)
        await session.flush()

    # --- Phase 4 Page Keywords ---

    async def assign_page_keyword(self, session: AsyncSession, page_kw: PageKeyword) -> PageKeyword:
        session.add(page_kw)
        await session.flush()
        return page_kw

    async def list_page_keywords(
        self, session: AsyncSession, *, page_id: UUID
    ) -> list[PageKeyword]:
        stmt = (
            select(PageKeyword)
            .where(PageKeyword.page_id == page_id)
            .order_by(PageKeyword.created_at)
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())

    async def remove_page_keyword(
        self, session: AsyncSession, *, page_id: UUID, keyword_id: UUID
    ) -> None:
        stmt = select(PageKeyword).where(
            PageKeyword.page_id == page_id,
            PageKeyword.keyword_id == keyword_id,
        )
        res = await session.execute(stmt)
        row = res.scalar_one_or_none()
        if row:
            await session.delete(row)
            await session.flush()
