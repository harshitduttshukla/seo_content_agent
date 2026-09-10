"""Crawling and domain verification application service."""

import asyncio
import hashlib
import logging
from datetime import UTC, datetime
from typing import ClassVar
from uuid import UUID

from app.config.settings import get_settings
from app.core.errors import ConflictError, DomainError, ResourceNotFound
from app.db.session import background_session_scope, set_actor_context, transactional_session
from app.domains.audit.repository import AuditWriter, OutboxWriter
from app.domains.content.extractors.html import HtmlContentExtractor
from app.domains.content.repository import ContentRepository
from app.domains.content.service import ContentService
from app.domains.crawling.fetcher import HttpFetcher
from app.domains.crawling.frontier import CrawlFrontier
from app.domains.crawling.models import (
    CrawlJobStatus,
    CrawlUrlStatus,
)
from app.domains.crawling.parsers.robots import RobotsParser
from app.domains.crawling.parsers.sitemap import SitemapParser
from app.domains.crawling.repository import CrawlRepository
from app.domains.crawling.schemas import (
    CrawlConfiguration,
    CrawlJobDetail,
    CrawlJobList,
    CrawlStatusSummary,
    WebsiteVerificationDetail,
)
from app.domains.websites.models import Website
from app.domains.websites.service import WebsiteService
from app.security.principal import AuthenticatedUser, PermissionCode
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class CrawlService:
    _background_tasks: ClassVar[set[asyncio.Task[None]]] = set()

    def __init__(self) -> None:
        self._crawling = CrawlRepository()
        self._content = ContentRepository()
        self._content_service = ContentService()
        self._websites = WebsiteService()
        self._audit = AuditWriter()
        self._outbox = OutboxWriter()

    @staticmethod
    def compute_verification_token(website: Website) -> str:
        secret = f"{website.id}:{website.organization_id}:{website.normalized_host}"
        return "ag-verify-" + hashlib.sha256(secret.encode("utf-8")).hexdigest()[:24]

    async def get_verification_info(
        self, session: AsyncSession, *, actor: AuthenticatedUser, website_id: UUID
    ) -> WebsiteVerificationDetail:
        async with transactional_session(session):
            await set_actor_context(session, actor.user_id)
            website = await self._websites.get_model(
                session,
                actor=actor,
                website_id=website_id,
                permission=PermissionCode.WEBSITE_READ,
            )
            token = self.compute_verification_token(website)
            return WebsiteVerificationDetail(
                website_id=website.id,
                verification_status=website.verification_status,
                verified_at=website.verified_at,
                verification_token=token,
                meta_tag_snippet=f'<meta name="antigravity-verification" content="{token}">',
                file_snippet=token,
            )

    async def verify_website(
        self,
        session: AsyncSession,
        *,
        actor: AuthenticatedUser,
        website_id: UUID,
        method: str,
        request_id: str,
    ) -> WebsiteVerificationDetail:
        """Verify domain ownership via meta tag, HTTP header, or verification file."""
        async with transactional_session(session):
            await set_actor_context(session, actor.user_id)
            website = await self._websites.get_model(
                session,
                actor=actor,
                website_id=website_id,
                permission=PermissionCode.WEBSITE_UPDATE,
            )

            expected_token = self.compute_verification_token(website)
            fetcher = HttpFetcher(timeout=10.0)

            verified = False

            if method == "dev_bypass" and get_settings().APP_ENV != "production":
                verified = True
            else:
                # Check Homepage meta tag or header
                result = await fetcher.fetch(website.base_url)
                if result.is_success:
                    if method == "http_header":
                        header_val = (result.headers or {}).get("x-antigravity-verification", "")
                        if expected_token in header_val:
                            verified = True
                    else:
                        # Default: search in HTML body for verification meta tag
                        if expected_token in result.text_content:
                            verified = True

                # If not verified and method allows file check:
                if not verified and method in ("verification_file", "http_meta"):
                    file_url = (
                        f"{website.base_url.rstrip('/')}/.well-known/antigravity-verification.txt"
                    )
                    file_result = await fetcher.fetch(file_url)
                    if file_result.is_success and expected_token in file_result.text_content:
                        verified = True

            now = datetime.now(UTC)
            if verified:
                website.verification_status = "verified"
                website.verified_at = now
                website.revision += 1
                await session.flush()

                self._audit.add(
                    session,
                    actor_user_id=actor.user_id,
                    organization_id=website.organization_id,
                    project_id=website.project_id,
                    action="website.verified",
                    resource_type="website",
                    resource_id=website.id,
                    request_id=request_id,
                    metadata={"method": method},
                )
                self._outbox.add(
                    session,
                    organization_id=website.organization_id,
                    project_id=website.project_id,
                    aggregate_type="website",
                    aggregate_id=website.id,
                    event_type="website.verified",
                )
            else:
                website.verification_status = "failed"
                website.revision += 1
                await session.flush()

            snippet = f'<meta name="antigravity-verification" content="{expected_token}">'
            return WebsiteVerificationDetail(
                website_id=website.id,
                verification_status=website.verification_status,
                verified_at=website.verified_at,
                verification_token=expected_token,
                meta_tag_snippet=snippet,
                file_snippet=expected_token,
            )

    async def get_crawl_status(
        self, session: AsyncSession, *, actor: AuthenticatedUser, website_id: UUID
    ) -> CrawlStatusSummary:
        async with transactional_session(session):
            await set_actor_context(session, actor.user_id)
            website = await self._websites.get_model(
                session,
                actor=actor,
                website_id=website_id,
                permission=PermissionCode.WEBSITE_READ,
            )
            active_job = await self._crawling.get_active_job_for_website(
                session, website_id=website.id
            )
            jobs = await self._crawling.list_jobs_for_website(
                session, website_id=website.id, limit=5
            )
            last_job = jobs[0] if jobs else None
            total_pages = await self._content.count_pages(session, website_id=website.id)

            return CrawlStatusSummary(
                website_id=website.id,
                verification_status=website.verification_status,
                active_job=CrawlJobDetail.model_validate(active_job) if active_job else None,
                last_job=CrawlJobDetail.model_validate(last_job) if last_job else None,
                total_indexed_pages=total_pages,
            )

    async def list_crawl_jobs(
        self, session: AsyncSession, *, actor: AuthenticatedUser, website_id: UUID, limit: int = 50
    ) -> CrawlJobList:
        async with transactional_session(session):
            await set_actor_context(session, actor.user_id)
            website = await self._websites.get_model(
                session,
                actor=actor,
                website_id=website_id,
                permission=PermissionCode.WEBSITE_READ,
            )
            jobs = await self._crawling.list_jobs_for_website(
                session, website_id=website.id, limit=limit
            )
            return CrawlJobList(items=[CrawlJobDetail.model_validate(j) for j in jobs])

    async def get_crawl_job(
        self, session: AsyncSession, *, actor: AuthenticatedUser, crawl_job_id: UUID
    ) -> CrawlJobDetail:
        async with transactional_session(session):
            await set_actor_context(session, actor.user_id)
            job = await self._crawling.get_job(session, crawl_job_id=crawl_job_id)
            if job is None:
                raise ResourceNotFound("crawl_job")
            # Authorize project access
            await self._websites.get_model(
                session,
                actor=actor,
                website_id=job.website_id,
                permission=PermissionCode.WEBSITE_READ,
            )
            return CrawlJobDetail.model_validate(job)

    async def start_crawl(
        self,
        session: AsyncSession,
        *,
        actor: AuthenticatedUser,
        website_id: UUID,
        config: CrawlConfiguration,
        request_id: str,
    ) -> CrawlJobDetail:
        """Create and initiate an asynchronous crawl job for a verified website."""
        async with transactional_session(session):
            await set_actor_context(session, actor.user_id)
            website = await self._websites.get_model(
                session,
                actor=actor,
                website_id=website_id,
                permission=PermissionCode.WEBSITE_UPDATE,
            )

            if website.verification_status != "verified":
                raise DomainError(
                    "WEBSITE_NOT_VERIFIED",
                    "The website must be verified before crawling can begin.",
                    http_status=400,
                )

            # Prevent concurrent active crawls on the same website
            active = await self._crawling.get_active_job_for_website(session, website_id=website.id)
            if active:
                raise ConflictError(
                    "CRAWL_IN_PROGRESS",
                    "An active crawl job is already queued or running for this website.",
                    details={"active_job_id": str(active.id)},
                )

            job = await self._crawling.create_job(
                session,
                organization_id=website.organization_id,
                project_id=website.project_id,
                website_id=website.id,
                requested_by_id=actor.user_id,
                configuration=config.model_dump(mode="json"),
            )

            await session.flush()
            await session.refresh(job)

            self._audit.add(
                session,
                actor_user_id=actor.user_id,
                organization_id=website.organization_id,
                project_id=website.project_id,
                action="crawl.started",
                resource_type="crawl_job",
                resource_id=job.id,
                request_id=request_id,
            )

            job_detail = CrawlJobDetail.model_validate(job)

        # Launch crawl worker in background task
        task = asyncio.create_task(self._execute_crawl(job_detail.id, actor.user_id))
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)

        return job_detail

    async def cancel_crawl(
        self,
        session: AsyncSession,
        *,
        actor: AuthenticatedUser,
        crawl_job_id: UUID,
        request_id: str,
    ) -> CrawlJobDetail:
        """Mark an active crawl job as cancelled."""
        async with transactional_session(session):
            await set_actor_context(session, actor.user_id)
            job = await self._crawling.get_job(session, crawl_job_id=crawl_job_id)
            if job is None:
                raise ResourceNotFound("crawl_job")

            await self._websites.get_model(
                session,
                actor=actor,
                website_id=job.website_id,
                permission=PermissionCode.WEBSITE_UPDATE,
            )

            if job.status in (
                CrawlJobStatus.COMPLETED,
                CrawlJobStatus.FAILED,
                CrawlJobStatus.CANCELLED,
            ):
                return CrawlJobDetail.model_validate(job)

            job.status = CrawlJobStatus.CANCELLED
            job.completed_at = datetime.now(UTC)
            await session.flush()
            await session.refresh(job)

            self._audit.add(
                session,
                actor_user_id=actor.user_id,
                organization_id=job.organization_id,
                project_id=job.project_id,
                action="crawl.cancelled",
                resource_type="crawl_job",
                resource_id=job.id,
                request_id=request_id,
            )
            return CrawlJobDetail.model_validate(job)

    async def _execute_crawl(self, crawl_job_id: UUID, actor_user_id: UUID) -> None:
        """Execute the full crawling loop asynchronously in background.

        Every background database session sets the RLS actor context so that
        PostgreSQL row-level security policies on tables like ``websites``
        can resolve the requesting user.
        """
        try:
            await self._run_crawl_loop(crawl_job_id, actor_user_id)
        except Exception as exc:
            logger.exception("Crawl job %s failed with unhandled error", crawl_job_id)
            try:
                async with background_session_scope() as err_session, err_session.begin():
                    await set_actor_context(err_session, actor_user_id)
                    failed_job = await self._crawling.get_job(
                        err_session, crawl_job_id=crawl_job_id
                    )
                    if failed_job and failed_job.status not in (
                        CrawlJobStatus.COMPLETED,
                        CrawlJobStatus.FAILED,
                        CrawlJobStatus.CANCELLED,
                    ):
                        failed_job.status = CrawlJobStatus.FAILED
                        failed_job.error_summary = str(exc)[:500]
                        failed_job.error_count += 1
                        failed_job.completed_at = datetime.now(UTC)
                        await self._crawling.add_event(
                            err_session,
                            crawl_job_id=crawl_job_id,
                            event_type="crawl.error",
                            message=f"Unhandled error: {exc!s}"[:500],
                        )
            except Exception:
                logger.exception("Could not persist failure for crawl job %s", crawl_job_id)

    async def _run_crawl_loop(self, crawl_job_id: UUID, actor_user_id: UUID) -> None:
        """Inner crawl loop extracted for clean error boundary."""
        async with background_session_scope() as session, session.begin():
            await set_actor_context(session, actor_user_id)
            job = await self._crawling.get_job(session, crawl_job_id=crawl_job_id)
            if not job or job.status == CrawlJobStatus.CANCELLED:
                return

            job.status = CrawlJobStatus.RUNNING
            job.started_at = datetime.now(UTC)
            await session.flush()

            website = await session.get(Website, job.website_id)
            if not website:
                job.status = CrawlJobStatus.FAILED
                job.error_summary = "Website entity not found"
                job.completed_at = datetime.now(UTC)
                return

            config = CrawlConfiguration.model_validate(job.configuration)
            base_host = website.normalized_host
            base_url = website.base_url
            website_id = website.id
            organization_id = website.organization_id
            project_id = website.project_id

        frontier = CrawlFrontier(
            base_host=base_host,
            max_depth=config.max_depth,
            max_pages=config.max_pages,
            include_subdomains=config.include_subdomains,
            allowed_paths=config.allowed_paths,
            blocked_paths=config.blocked_paths,
        )

        fetcher = HttpFetcher(user_agent=config.user_agent)
        extractor = HtmlContentExtractor(
            base_host=base_host, include_subdomains=config.include_subdomains
        )

        # 1. Discover robots.txt
        robots_parser = RobotsParser()
        if config.respect_robots:
            robots_url = f"{base_url.rstrip('/')}/robots.txt"
            robots_res = await fetcher.fetch(robots_url)
            if robots_res.is_success and robots_res.text_content:
                robots_parser.parse(robots_res.text_content)

        # 2. Discover Sitemaps
        sitemap_candidates = list(robots_parser.sitemaps)
        sitemap_candidates.append(f"{base_url.rstrip('/')}/sitemap.xml")

        for sm_url in sitemap_candidates:
            sm_res = await fetcher.fetch(sm_url)
            if sm_res.is_success and sm_res.text_content:
                parsed_sm = SitemapParser.parse(sm_res.text_content)
                if parsed_sm.is_index:
                    for child_sm in parsed_sm.child_sitemaps[:10]:
                        child_res = await fetcher.fetch(child_sm)
                        if child_res.is_success and child_res.text_content:
                            child_parsed = SitemapParser.parse(child_res.text_content)
                            for entry in child_parsed.urls:
                                frontier.add(entry.loc, depth=1, source="sitemap")
                else:
                    for entry in parsed_sm.urls:
                        frontier.add(entry.loc, depth=1, source="sitemap")

        # 3. Seed Homepage
        frontier.add(base_url, depth=0, source="seed")

        pages_crawled = 0
        pages_failed = 0
        pages_skipped = 0

        # Main crawl loop
        while not frontier.is_empty and pages_crawled < config.max_pages:
            # Check cancellation flag
            async with background_session_scope() as check_session:
                await set_actor_context(check_session, actor_user_id)
                current_job = await self._crawling.get_job(check_session, crawl_job_id=crawl_job_id)
                if not current_job or current_job.status == CrawlJobStatus.CANCELLED:
                    return

            item = frontier.pop_next()
            if item is None:
                break

            # Respect robots.txt
            if config.respect_robots and not robots_parser.can_fetch(item.url):
                pages_skipped += 1
                async with background_session_scope() as session, session.begin():
                    await set_actor_context(session, actor_user_id)
                    await self._crawling.add_url(
                        session,
                        crawl_job_id=crawl_job_id,
                        website_id=website_id,
                        url=item.url,
                        normalized_url=item.normalized_url,
                        depth=item.depth,
                        source=item.source,
                        status=CrawlUrlStatus.BLOCKED,
                    )
                continue

            # Fetch page
            fetch_res = await fetcher.fetch(item.url)

            async with background_session_scope() as session, session.begin():
                await set_actor_context(session, actor_user_id)
                if fetch_res.is_success:
                    pages_crawled += 1
                    # Extract content
                    extracted = extractor.extract(fetch_res.text_content, fetch_res.final_url)

                    # Persist page & links
                    await self._content_service.index_extracted_page(
                        session,
                        organization_id=organization_id,
                        project_id=project_id,
                        website_id=website_id,
                        url=item.url,
                        normalized_url=item.normalized_url,
                        http_status=fetch_res.status_code,
                        content_type=fetch_res.content_type,
                        extracted=extracted,
                        crawl_job_id=crawl_job_id,
                    )

                    await self._crawling.add_url(
                        session,
                        crawl_job_id=crawl_job_id,
                        website_id=website_id,
                        url=item.url,
                        normalized_url=item.normalized_url,
                        depth=item.depth,
                        source=item.source,
                        status=CrawlUrlStatus.CRAWLED,
                    )

                    # Discover links for frontier
                    for link in extracted.links:
                        if link.is_internal and not link.nofollow:
                            frontier.add(
                                link.target_url,
                                depth=item.depth + 1,
                                source="internal_link",
                            )
                else:
                    pages_failed += 1
                    await self._crawling.add_url(
                        session,
                        crawl_job_id=crawl_job_id,
                        website_id=website_id,
                        url=item.url,
                        normalized_url=item.normalized_url,
                        depth=item.depth,
                        source=item.source,
                        status=CrawlUrlStatus.FAILED,
                    )

                # Update progressive job counts
                db_job = await self._crawling.get_job(session, crawl_job_id=crawl_job_id)
                if db_job:
                    if db_job.status == CrawlJobStatus.CANCELLED:
                        return
                    db_job.pages_discovered = frontier.total_seen
                    db_job.pages_crawled = pages_crawled
                    db_job.pages_failed = pages_failed
                    db_job.pages_skipped = pages_skipped

            # Politeness delay
            if config.crawl_delay > 0:
                await asyncio.sleep(config.crawl_delay)

        # Mark job finished
        async with background_session_scope() as session, session.begin():
            await set_actor_context(session, actor_user_id)
            final_job = await self._crawling.get_job(session, crawl_job_id=crawl_job_id)
            if final_job and final_job.status == CrawlJobStatus.RUNNING:
                final_job.status = CrawlJobStatus.COMPLETED
                final_job.completed_at = datetime.now(UTC)
                final_job.pages_discovered = frontier.total_seen
                final_job.pages_crawled = pages_crawled
                final_job.pages_failed = pages_failed
                final_job.pages_skipped = pages_skipped
                await session.flush()
