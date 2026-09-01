"""Repository for content pages, versions, and links."""

from datetime import UTC, datetime
from uuid import UUID

from app.core.cursor import Cursor
from app.domains.content.models import (
    ContentPage,
    ContentPageVersion,
    ContentStatus,
    PageLink,
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
