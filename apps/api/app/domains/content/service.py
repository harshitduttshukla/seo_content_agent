"""Content application service for page management and indexing."""

from uuid import UUID

from app.core.cursor import decode_cursor, encode_cursor
from app.core.errors import ResourceNotFound
from app.core.pagination import PageResult
from app.db.session import set_actor_context, transactional_session
from app.domains.content.extractors.html import ExtractedPageContent
from app.domains.content.models import ContentStatus
from app.domains.content.repository import ContentRepository
from app.domains.content.schemas import (
    ContentPageDetail,
    ContentPageSummary,
    PageLinkDetail,
)
from app.domains.websites.service import WebsiteService
from app.security.principal import AuthenticatedUser, PermissionCode
from sqlalchemy.ext.asyncio import AsyncSession


class ContentService:
    def __init__(self) -> None:
        self._content = ContentRepository()
        self._websites = WebsiteService()

    async def list_pages(
        self,
        session: AsyncSession,
        *,
        actor: AuthenticatedUser,
        website_id: UUID,
        status: str | None = None,
        search: str | None = None,
        cursor: str | None = None,
        limit: int = 50,
    ) -> PageResult[ContentPageSummary]:
        async with transactional_session(session):
            await set_actor_context(session, actor.user_id)
            website = await self._websites.get_model(
                session,
                actor=actor,
                website_id=website_id,
                permission=PermissionCode.WEBSITE_READ,
            )
            rows = await self._content.list_pages(
                session,
                website_id=website.id,
                status=status,
                search=search,
                cursor=decode_cursor(cursor),
                limit=limit,
            )
            has_more = len(rows) > limit
            visible = rows[:limit]
            return PageResult(
                items=[ContentPageSummary.model_validate(row) for row in visible],
                next_cursor=(
                    encode_cursor(visible[-1].created_at, visible[-1].id)
                    if has_more and visible
                    else None
                ),
                has_more=has_more,
            )

    async def get_page(
        self,
        session: AsyncSession,
        *,
        actor: AuthenticatedUser,
        website_id: UUID,
        page_id: UUID,
    ) -> ContentPageDetail:
        async with transactional_session(session):
            await set_actor_context(session, actor.user_id)
            website = await self._websites.get_model(
                session,
                actor=actor,
                website_id=website_id,
                permission=PermissionCode.WEBSITE_READ,
            )
            page = await self._content.get_page_by_id(
                session, page_id=page_id, organization_id=website.organization_id
            )
            if page is None or page.website_id != website.id:
                raise ResourceNotFound("page")
            return ContentPageDetail.model_validate(page)

    async def list_links(
        self,
        session: AsyncSession,
        *,
        actor: AuthenticatedUser,
        website_id: UUID,
        limit: int = 100,
    ) -> list[PageLinkDetail]:
        async with transactional_session(session):
            await set_actor_context(session, actor.user_id)
            website = await self._websites.get_model(
                session,
                actor=actor,
                website_id=website_id,
                permission=PermissionCode.WEBSITE_READ,
            )
            links = await self._content.list_links_for_website(
                session, website_id=website.id, limit=limit
            )
            return [PageLinkDetail.model_validate(link) for link in links]

    async def index_extracted_page(
        self,
        session: AsyncSession,
        *,
        organization_id: UUID,
        project_id: UUID,
        website_id: UUID,
        url: str,
        normalized_url: str,
        http_status: int,
        content_type: str,
        extracted: ExtractedPageContent,
        crawl_job_id: UUID | None = None,
    ) -> None:
        """Persist structured page content, version if changed, and update links."""
        content_status = (
            ContentStatus.INDEXED
            if (http_status >= 200 and http_status < 300)
            else ContentStatus.FAILED
        )

        page, _ = await self._content.upsert_page(
            session,
            organization_id=organization_id,
            project_id=project_id,
            website_id=website_id,
            url=url,
            normalized_url=normalized_url,
            canonical_url=extracted.canonical_url,
            title=extracted.title,
            meta_description=extracted.meta_description,
            language=extracted.language,
            http_status=http_status,
            content_type=content_type,
            word_count=extracted.word_count,
            content_hash=extracted.content_hash,
            content_status=content_status,
            cleaned_content=extracted.cleaned_content,
            structured_content=extracted.structured_content,
            metadata=extracted.metadata,
            headings=extracted.headings,
            images=extracted.images,
            crawl_job_id=crawl_job_id,
        )

        if extracted.links:
            links_data: list[dict[str, object]] = [
                {
                    "target_url": link.target_url,
                    "normalized_target_url": link.normalized_target_url,
                    "anchor_text": link.anchor_text,
                    "rel": link.rel,
                    "is_internal": link.is_internal,
                    "nofollow": link.nofollow,
                    "ugc": link.ugc,
                    "sponsored": link.sponsored,
                }
                for link in extracted.links
            ]
            await self._content.replace_page_links(
                session,
                website_id=website_id,
                source_page_id=page.id,
                links=links_data,
            )
