"""Content domain application service for pages, architecture, mappings, and graph."""

import re
from uuid import UUID

from app.core.cursor import decode_cursor, encode_cursor
from app.core.errors import ConflictError, ResourceNotFound
from app.core.pagination import PageResult
from app.core.validators import normalize_slug
from app.db.session import set_actor_context, transactional_session
from app.domains.audit.repository import AuditWriter, OutboxWriter
from app.domains.content.extractors.html import ExtractedPageContent
from app.domains.content.models import (
    ArchitectureStatus,
    ContentStatus,
    MappingSource,
    MappingStatus,
    MappingType,
    OpportunityAction,
    OpportunityStatus,
)
from app.domains.content.repository import ContentRepository
from app.domains.content.schemas import (
    CannibalizationWarningDetail,
    CannibalizationWarningList,
    ContentArchitectureGraphEdge,
    ContentArchitectureGraphNode,
    ContentArchitectureGraphResponse,
    ContentOpportunityDetail,
    ContentOpportunityList,
    ContentOpportunityUpdate,
    ContentPageDetail,
    ContentPageSummary,
    ContentPillarCreate,
    ContentPillarDetail,
    ContentPillarList,
    ContentPillarUpdate,
    GraphNodeData,
    KeywordPageMappingDetail,
    KeywordPageMappingList,
    MappingAnalysisResponse,
    PageLinkDetail,
    TopicCreate,
    TopicDetail,
    TopicList,
    TopicUpdate,
)
from app.domains.keywords.repository import KeywordRepository
from app.domains.projects.models import Project
from app.domains.projects.service import ProjectService
from app.domains.websites.models import Website
from app.domains.websites.service import WebsiteService
from app.security.principal import AuthenticatedUser, PermissionCode
from sqlalchemy.ext.asyncio import AsyncSession


class ContentService:
    def __init__(self) -> None:
        self._content = ContentRepository()
        self._keywords = KeywordRepository()
        self._websites = WebsiteService()
        self._projects = ProjectService()
        self._audit = AuditWriter()
        self._outbox = OutboxWriter()

    # --- Page management ---

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
            ContentStatus.INDEXED if (200 <= http_status < 300) else ContentStatus.FAILED
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

    # --- Content Pillars ---

    async def create_pillar(
        self,
        session: AsyncSession,
        *,
        actor: AuthenticatedUser,
        project_id: UUID,
        payload: ContentPillarCreate,
        request_id: str = "",
    ) -> ContentPillarDetail:
        slug = normalize_slug(payload.slug or payload.name)
        async with session.begin():
            await set_actor_context(session, actor.user_id)
            project = await self._projects.get_model(
                session,
                actor=actor,
                project_id=project_id,
                permission=PermissionCode.CONTENT_WRITE,
            )
            existing = await self._content.get_pillar_by_slug(
                session, project_id=project.id, slug=slug
            )
            if existing:
                raise ConflictError(
                    "PILLAR_SLUG_CONFLICT",
                    f"Pillar with slug '{slug}' already exists.",
                )

            pillar = await self._content.create_pillar(
                session,
                organization_id=project.organization_id,
                project_id=project.id,
                name=payload.name.strip(),
                slug=slug,
                description=payload.description.strip(),
                business_goal=payload.business_goal.strip(),
                priority=payload.priority,
                status=ArchitectureStatus.PROPOSED,
            )
            self._audit.add(
                session,
                actor_user_id=actor.user_id,
                organization_id=project.organization_id,
                project_id=project.id,
                action="pillar.created",
                resource_type="content_pillar",
                resource_id=pillar.id,
                request_id=request_id,
            )
            return ContentPillarDetail.model_validate(pillar)

    async def list_pillars(
        self,
        session: AsyncSession,
        *,
        actor: AuthenticatedUser,
        project_id: UUID,
    ) -> ContentPillarList:
        async with session.begin():
            await set_actor_context(session, actor.user_id)
            project = await self._projects.get_model(
                session,
                actor=actor,
                project_id=project_id,
                permission=PermissionCode.CONTENT_READ,
            )
            pillars = await self._content.list_pillars(session, project_id=project.id)
            topics = await self._content.list_topics(session, project_id=project.id)
            topic_count_by_pillar: dict[UUID, int] = {}
            for t in topics:
                if t.pillar_id:
                    cnt = topic_count_by_pillar.get(t.pillar_id, 0)
                    topic_count_by_pillar[t.pillar_id] = cnt + 1

            items = []
            for p in pillars:
                item = ContentPillarDetail.model_validate(p)
                item.topic_count = topic_count_by_pillar.get(p.id, 0)
                items.append(item)
            return ContentPillarList(items=items)

    async def update_pillar(
        self,
        session: AsyncSession,
        *,
        actor: AuthenticatedUser,
        project_id: UUID,
        pillar_id: UUID,
        payload: ContentPillarUpdate,
        request_id: str = "",
    ) -> ContentPillarDetail:
        async with session.begin():
            await set_actor_context(session, actor.user_id)
            project = await self._projects.get_model(
                session,
                actor=actor,
                project_id=project_id,
                permission=PermissionCode.CONTENT_WRITE,
            )
            p = await self._content.get_pillar_by_id(
                session, pillar_id=pillar_id, project_id=project.id
            )
            if not p:
                raise ResourceNotFound("content_pillar")

            if payload.name is not None:
                p.name = payload.name.strip()
            if payload.slug is not None:
                p.slug = normalize_slug(payload.slug)
            if payload.description is not None:
                p.description = payload.description.strip()
            if payload.business_goal is not None:
                p.business_goal = payload.business_goal.strip()
            if payload.priority is not None:
                p.priority = payload.priority
            if payload.status is not None:
                p.status = str(payload.status).lower()

            p.revision += 1
            await session.flush()
            return ContentPillarDetail.model_validate(p)

    # --- Topics ---

    async def create_topic(
        self,
        session: AsyncSession,
        *,
        actor: AuthenticatedUser,
        project_id: UUID,
        payload: TopicCreate,
        request_id: str = "",
    ) -> TopicDetail:
        slug = normalize_slug(payload.slug or payload.name)
        async with session.begin():
            await set_actor_context(session, actor.user_id)
            project = await self._projects.get_model(
                session,
                actor=actor,
                project_id=project_id,
                permission=PermissionCode.CONTENT_WRITE,
            )
            existing = await self._content.get_topic_by_slug(
                session, project_id=project.id, slug=slug
            )
            if existing:
                raise ConflictError(
                    "TOPIC_SLUG_CONFLICT",
                    f"Topic with slug '{slug}' already exists.",
                )

            topic = await self._content.create_topic(
                session,
                organization_id=project.organization_id,
                project_id=project.id,
                pillar_id=payload.pillar_id,
                name=payload.name.strip(),
                slug=slug,
                description=payload.description.strip(),
                priority=payload.priority,
                status=ArchitectureStatus.PROPOSED,
            )
            self._audit.add(
                session,
                actor_user_id=actor.user_id,
                organization_id=project.organization_id,
                project_id=project.id,
                action="topic.created",
                resource_type="topic",
                resource_id=topic.id,
                request_id=request_id,
            )
            return TopicDetail.model_validate(topic)

    async def list_topics(
        self,
        session: AsyncSession,
        *,
        actor: AuthenticatedUser,
        project_id: UUID,
        pillar_id: UUID | None = None,
    ) -> TopicList:
        async with session.begin():
            await set_actor_context(session, actor.user_id)
            project = await self._projects.get_model(
                session,
                actor=actor,
                project_id=project_id,
                permission=PermissionCode.CONTENT_READ,
            )
            topics = await self._content.list_topics(
                session, project_id=project.id, pillar_id=pillar_id
            )
            pillars = await self._content.list_pillars(session, project_id=project.id)
            pillar_names = {p.id: p.name for p in pillars}
            clusters = await self._keywords.list_clusters(session, project_id=project.id)
            cluster_count_by_topic: dict[UUID, int] = {}
            for c in clusters:
                if c.topic_id:
                    cnt = cluster_count_by_topic.get(c.topic_id, 0)
                    cluster_count_by_topic[c.topic_id] = cnt + 1

            items = []
            for t in topics:
                item = TopicDetail.model_validate(t)
                item.pillar_name = pillar_names.get(t.pillar_id) if t.pillar_id else None
                item.cluster_count = cluster_count_by_topic.get(t.id, 0)
                items.append(item)
            return TopicList(items=items)

    async def update_topic(
        self,
        session: AsyncSession,
        *,
        actor: AuthenticatedUser,
        project_id: UUID,
        topic_id: UUID,
        payload: TopicUpdate,
        request_id: str = "",
    ) -> TopicDetail:
        async with session.begin():
            await set_actor_context(session, actor.user_id)
            project = await self._projects.get_model(
                session,
                actor=actor,
                project_id=project_id,
                permission=PermissionCode.CONTENT_WRITE,
            )
            t = await self._content.get_topic_by_id(
                session, topic_id=topic_id, project_id=project.id
            )
            if not t:
                raise ResourceNotFound("topic")

            if payload.name is not None:
                t.name = payload.name.strip()
            if payload.slug is not None:
                t.slug = normalize_slug(payload.slug)
            if payload.pillar_id is not None:
                t.pillar_id = payload.pillar_id
            if payload.description is not None:
                t.description = payload.description.strip()
            if payload.priority is not None:
                t.priority = payload.priority
            if payload.status is not None:
                t.status = str(payload.status).lower()

            t.revision += 1
            await session.flush()
            return TopicDetail.model_validate(t)

    # --- Keyword-Page Mapping & Cannibalization Engine ---

    async def analyze_keyword_mappings(
        self,
        session: AsyncSession,
        *,
        actor: AuthenticatedUser,
        project_id: UUID,
        website_id: UUID,
        request_id: str = "",
    ) -> MappingAnalysisResponse:
        """Deterministic mapping of project keywords to existing crawled website content pages."""
        async with session.begin():
            await set_actor_context(session, actor.user_id)
            project = await self._projects.get_model(
                session,
                actor=actor,
                project_id=project_id,
                permission=PermissionCode.KEYWORD_WRITE,
            )
            website = await self._websites.get_model(
                session,
                actor=actor,
                website_id=website_id,
                permission=PermissionCode.WEBSITE_READ,
            )
            keywords = await self._keywords.list_all_active_for_project(
                session, project_id=project.id
            )
            pages = await self._content.list_all_pages_for_website(session, website_id=website.id)

            mapped_count = 0
            unmapped_count = 0
            created_count = 0
            updated_count = 0

            for kw in keywords:
                best_page = None
                best_score = 0.0
                best_reason = ""

                kw_terms = set(re.findall(r"\b\w+\b", kw.normalized_keyword))

                for p in pages:
                    score = 0.0
                    reasons = []

                    url_clean = p.normalized_url.lower().replace("-", " ").replace("/", " ")
                    if kw.normalized_keyword in url_clean:
                        score += 0.50
                        reasons.append("URL slug matches keyword")

                    title_clean = p.title.lower()
                    if kw.normalized_keyword in title_clean:
                        score += 0.40
                        reasons.append("Page title matches keyword")
                    elif kw_terms and kw_terms.issubset(set(re.findall(r"\b\w+\b", title_clean))):
                        score += 0.30
                        reasons.append("All keyword tokens found in page title")

                    for h in p.headings:
                        h_text = str(h.get("text", "")).lower()
                        if kw.normalized_keyword in h_text:
                            score += 0.30
                            reasons.append(f"H{h.get('level', 1)} heading match")
                            break

                    content_clean = p.cleaned_content.lower()
                    if kw.normalized_keyword in content_clean:
                        score += 0.20
                        reasons.append("Exact phrase found in body content")

                    total_score = min(1.0, score)
                    if total_score > best_score:
                        best_score = total_score
                        best_page = p
                        best_reason = "; ".join(reasons)

                if best_page and best_score >= 0.45:
                    mapped_count += 1
                    mapping_type = (
                        MappingType.PRIMARY_TARGET
                        if best_score >= 0.70
                        else MappingType.SECONDARY_TARGET
                    )
                    await self._content.create_or_update_mapping(
                        session,
                        organization_id=project.organization_id,
                        project_id=project.id,
                        website_id=website.id,
                        keyword_id=kw.id,
                        page_id=best_page.id,
                        mapping_type=mapping_type,
                        confidence=best_score,
                        source=MappingSource.DETERMINISTIC,
                        status=MappingStatus.PROPOSED,
                        rationale=best_reason or f"Semantic match score: {int(best_score * 100)}%",
                    )
                    created_count += 1
                else:
                    unmapped_count += 1
                    await self._content.create_or_update_mapping(
                        session,
                        organization_id=project.organization_id,
                        project_id=project.id,
                        website_id=website.id,
                        keyword_id=kw.id,
                        page_id=None,
                        mapping_type=MappingType.NEW_PAGE_REQUIRED,
                        confidence=1.0,
                        source=MappingSource.DETERMINISTIC,
                        status=MappingStatus.PROPOSED,
                        rationale="No existing indexed page sufficiently matches this intent.",
                    )
                    created_count += 1

            self._audit.add(
                session,
                actor_user_id=actor.user_id,
                organization_id=project.organization_id,
                project_id=project.id,
                action="keyword_mappings.analyzed",
                resource_type="project",
                resource_id=project.id,
                request_id=request_id,
                metadata={"mapped": mapped_count, "unmapped": unmapped_count},
            )

            await self._generate_opportunities_internal(session, project=project, website=website)

            return MappingAnalysisResponse(
                total_keywords=len(keywords),
                mapped_count=mapped_count,
                unmapped_count=unmapped_count,
                new_mappings_created=created_count,
                updated_mappings=updated_count,
            )

    async def _generate_opportunities_internal(
        self, session: AsyncSession, *, project: Project, website: Website
    ) -> None:
        """Internal generator for content gaps and opportunities."""
        clusters = await self._keywords.list_clusters(session, project_id=project.id)
        mappings = await self._content.list_mappings_for_project(session, project_id=project.id)
        mapping_by_kw = {m.keyword_id: m for m in mappings}

        for c in clusters:
            memberships = await self._keywords.get_cluster_memberships(session, cluster_id=c.id)
            if not memberships:
                continue

            primary_kw = next((kw for m, kw in memberships if m.is_primary), memberships[0][1])
            mapping = mapping_by_kw.get(primary_kw.id)

            if (
                not mapping
                or mapping.page_id is None
                or mapping.mapping_type == MappingType.NEW_PAGE_REQUIRED
            ):
                await self._content.create_or_update_opportunity(
                    session,
                    organization_id=project.organization_id,
                    project_id=project.id,
                    website_id=website.id,
                    cluster_id=c.id,
                    keyword_id=primary_kw.id,
                    action=OpportunityAction.NEW_PAGE,
                    priority=c.cluster_score,
                    business_value_score=primary_kw.business_value_score,
                    existing_page_id=None,
                    reason=f"Cluster '{c.cluster_name}' has no suitable target page on site.",
                    confidence=0.90,
                    status=OpportunityStatus.PROPOSED,
                )
            elif mapping.mapping_type == MappingType.SECONDARY_TARGET:
                await self._content.create_or_update_opportunity(
                    session,
                    organization_id=project.organization_id,
                    project_id=project.id,
                    website_id=website.id,
                    cluster_id=c.id,
                    keyword_id=primary_kw.id,
                    action=OpportunityAction.UPDATE_EXISTING_PAGE,
                    priority=c.cluster_score * 0.85,
                    business_value_score=primary_kw.business_value_score,
                    existing_page_id=mapping.page_id,
                    reason=f"Page partially covers cluster '{c.cluster_name}'. Expand content.",
                    confidence=mapping.confidence,
                    status=OpportunityStatus.PROPOSED,
                )

    async def list_mappings(
        self,
        session: AsyncSession,
        *,
        actor: AuthenticatedUser,
        project_id: UUID,
    ) -> KeywordPageMappingList:
        async with session.begin():
            await set_actor_context(session, actor.user_id)
            project = await self._projects.get_model(
                session,
                actor=actor,
                project_id=project_id,
                permission=PermissionCode.KEYWORD_READ,
            )
            mappings = await self._content.list_mappings_for_project(session, project_id=project.id)
            keywords = await self._keywords.list_all_active_for_project(
                session, project_id=project.id
            )
            kw_map = {k.id: k for k in keywords}

            items = []
            for m in mappings:
                kw = kw_map.get(m.keyword_id)
                page = (
                    await self._content.get_page_by_id(session, page_id=m.page_id)
                    if m.page_id
                    else None
                )
                items.append(
                    KeywordPageMappingDetail(
                        id=m.id,
                        organization_id=m.organization_id,
                        project_id=m.project_id,
                        website_id=m.website_id,
                        keyword_id=m.keyword_id,
                        keyword=kw.keyword if kw else "Unknown",
                        search_volume=kw.search_volume if kw else 0,
                        intent=kw.intent if kw else "",
                        page_id=m.page_id,
                        page_url=page.url if page else None,
                        page_title=page.title if page else None,
                        mapping_type=m.mapping_type,
                        confidence=m.confidence,
                        source=m.source,
                        status=m.status,
                        rationale=m.rationale,
                        created_at=m.created_at,
                        updated_at=m.updated_at,
                    )
                )
            return KeywordPageMappingList(items=items)

    async def detect_cannibalization(
        self,
        session: AsyncSession,
        *,
        actor: AuthenticatedUser,
        project_id: UUID,
        website_id: UUID,
    ) -> CannibalizationWarningList:
        """Detect when multiple pages appear to target the exact same keyword or cluster intent."""
        async with session.begin():
            await set_actor_context(session, actor.user_id)
            project = await self._projects.get_model(
                session,
                actor=actor,
                project_id=project_id,
                permission=PermissionCode.KEYWORD_READ,
            )
            website = await self._websites.get_model(
                session,
                actor=actor,
                website_id=website_id,
                permission=PermissionCode.WEBSITE_READ,
            )
            pages = await self._content.list_all_pages_for_website(session, website_id=website.id)
            keywords = await self._keywords.list_all_active_for_project(
                session, project_id=project.id
            )

            warnings: list[CannibalizationWarningDetail] = []

            for kw in keywords:
                competing_pages = []
                for p in pages:
                    title_match = kw.normalized_keyword in p.title.lower()
                    h1_match = any(
                        kw.normalized_keyword in str(h.get("text", "")).lower()
                        for h in p.headings
                        if h.get("level") == 1
                    )
                    if title_match or h1_match:
                        competing_pages.append(
                            {
                                "page_id": str(p.id),
                                "url": p.url,
                                "title": p.title,
                                "title_match": title_match,
                                "h1_match": h1_match,
                            }
                        )

                if len(competing_pages) > 1:
                    reason_text = (
                        f"{len(competing_pages)} pages have competing Title or H1 tags "
                        f"targeting '{kw.keyword}'"
                    )
                    warnings.append(
                        CannibalizationWarningDetail(
                            keyword_id=kw.id,
                            keyword=kw.keyword,
                            intent=kw.intent,
                            competing_pages=competing_pages,
                            severity="HIGH" if len(competing_pages) > 2 else "MEDIUM",
                            reason=reason_text,
                        )
                    )

            return CannibalizationWarningList(items=warnings)

    async def list_opportunities(
        self,
        session: AsyncSession,
        *,
        actor: AuthenticatedUser,
        project_id: UUID,
        status: str | None = None,
    ) -> ContentOpportunityList:
        async with session.begin():
            await set_actor_context(session, actor.user_id)
            project = await self._projects.get_model(
                session,
                actor=actor,
                project_id=project_id,
                permission=PermissionCode.CONTENT_READ,
            )
            opps = await self._content.list_opportunities(
                session, project_id=project.id, status=status
            )
            clusters = await self._keywords.list_clusters(session, project_id=project.id)
            cluster_map = {c.id: c for c in clusters}
            keywords = await self._keywords.list_all_active_for_project(
                session, project_id=project.id
            )
            kw_map = {k.id: k for k in keywords}

            items = []
            for o in opps:
                c = cluster_map.get(o.cluster_id) if o.cluster_id else None
                kw = kw_map.get(o.keyword_id) if o.keyword_id else None
                page = (
                    await self._content.get_page_by_id(session, page_id=o.existing_page_id)
                    if o.existing_page_id
                    else None
                )
                items.append(
                    ContentOpportunityDetail(
                        id=o.id,
                        organization_id=o.organization_id,
                        project_id=o.project_id,
                        website_id=o.website_id,
                        cluster_id=o.cluster_id,
                        cluster_name=c.cluster_name if c else None,
                        keyword_id=o.keyword_id,
                        keyword=kw.keyword if kw else None,
                        action=o.action,
                        priority=o.priority,
                        business_value_score=o.business_value_score,
                        existing_page_id=o.existing_page_id,
                        existing_page_url=page.url if page else None,
                        reason=o.reason,
                        confidence=o.confidence,
                        status=o.status,
                        created_at=o.created_at,
                        updated_at=o.updated_at,
                    )
                )
            return ContentOpportunityList(items=items)

    async def update_opportunity(
        self,
        session: AsyncSession,
        *,
        actor: AuthenticatedUser,
        project_id: UUID,
        opportunity_id: UUID,
        payload: ContentOpportunityUpdate,
        request_id: str = "",
    ) -> ContentOpportunityDetail:
        async with session.begin():
            await set_actor_context(session, actor.user_id)
            project = await self._projects.get_model(
                session,
                actor=actor,
                project_id=project_id,
                permission=PermissionCode.CONTENT_WRITE,
            )
            opp = await self._content.get_opportunity_by_id(
                session, opportunity_id=opportunity_id, project_id=project.id
            )
            if not opp:
                raise ResourceNotFound("content_opportunity")

            opp.status = str(payload.status).lower()
            opp.revision += 1
            await session.flush()

            self._audit.add(
                session,
                actor_user_id=actor.user_id,
                organization_id=project.organization_id,
                project_id=project.id,
                action="opportunity.reviewed",
                resource_type="content_opportunity",
                resource_id=opp.id,
                request_id=request_id,
                metadata={"status": opp.status},
            )

            cluster = (
                await self._keywords.get_cluster_by_id(
                    session, cluster_id=opp.cluster_id, project_id=project.id
                )
                if opp.cluster_id
                else None
            )
            kw = (
                await self._keywords.get_by_id(
                    session, keyword_id=opp.keyword_id, project_id=project.id
                )
                if opp.keyword_id
                else None
            )
            page = (
                await self._content.get_page_by_id(session, page_id=opp.existing_page_id)
                if opp.existing_page_id
                else None
            )

            return ContentOpportunityDetail(
                id=opp.id,
                organization_id=opp.organization_id,
                project_id=opp.project_id,
                website_id=opp.website_id,
                cluster_id=opp.cluster_id,
                cluster_name=cluster.cluster_name if cluster else None,
                keyword_id=opp.keyword_id,
                keyword=kw.keyword if kw else None,
                action=opp.action,
                priority=opp.priority,
                business_value_score=opp.business_value_score,
                existing_page_id=opp.existing_page_id,
                existing_page_url=page.url if page else None,
                reason=opp.reason,
                confidence=opp.confidence,
                status=opp.status,
                created_at=opp.created_at,
                updated_at=opp.updated_at,
            )

    # --- React Flow Graph Projection ---

    async def get_architecture_graph(
        self,
        session: AsyncSession,
        *,
        actor: AuthenticatedUser,
        project_id: UUID,
    ) -> ContentArchitectureGraphResponse:
        """Construct graph nodes and edges for Pillars -> Topics -> Clusters -> Pages."""
        async with session.begin():
            await set_actor_context(session, actor.user_id)
            project = await self._projects.get_model(
                session,
                actor=actor,
                project_id=project_id,
                permission=PermissionCode.CONTENT_READ,
            )
            pillars = await self._content.list_pillars(session, project_id=project.id)
            topics = await self._content.list_topics(session, project_id=project.id)
            clusters = await self._keywords.list_clusters(session, project_id=project.id)
            mappings = await self._content.list_mappings_for_project(session, project_id=project.id)

            nodes: list[ContentArchitectureGraphNode] = []
            edges: list[ContentArchitectureGraphEdge] = []

            for p in pillars:
                nodes.append(
                    ContentArchitectureGraphNode(
                        id=f"pillar-{p.id}",
                        type="pillar",
                        data=GraphNodeData(
                            label=p.name,
                            subtitle=p.business_goal or "Pillar",
                            status=p.status,
                            metrics={"priority": p.priority},
                        ),
                    )
                )

            for t in topics:
                nodes.append(
                    ContentArchitectureGraphNode(
                        id=f"topic-{t.id}",
                        type="topic",
                        data=GraphNodeData(
                            label=t.name,
                            subtitle=t.slug,
                            status=t.status,
                            metrics={"priority": t.priority},
                        ),
                    )
                )
                if t.pillar_id:
                    edges.append(
                        ContentArchitectureGraphEdge(
                            id=f"edge-pillar-{t.pillar_id}-topic-{t.id}",
                            source=f"pillar-{t.pillar_id}",
                            target=f"topic-{t.id}",
                            type="contains",
                            label="contains",
                        )
                    )

            for c in clusters:
                nodes.append(
                    ContentArchitectureGraphNode(
                        id=f"cluster-{c.id}",
                        type="cluster",
                        data=GraphNodeData(
                            label=c.cluster_name,
                            subtitle=c.intent,
                            status=c.status,
                            metrics={"score": c.cluster_score},
                        ),
                    )
                )
                if c.topic_id:
                    edges.append(
                        ContentArchitectureGraphEdge(
                            id=f"edge-topic-{c.topic_id}-cluster-{c.id}",
                            source=f"topic-{c.topic_id}",
                            target=f"cluster-{c.id}",
                            type="contains",
                            label="contains",
                        )
                    )

            seen_page_nodes = set()
            for m in mappings:
                if m.page_id:
                    page_node_id = f"page-{m.page_id}"
                    if page_node_id not in seen_page_nodes:
                        page = await self._content.get_page_by_id(session, page_id=m.page_id)
                        if page:
                            nodes.append(
                                ContentArchitectureGraphNode(
                                    id=page_node_id,
                                    type="page",
                                    data=GraphNodeData(
                                        label=page.title or page.url,
                                        subtitle=page.url,
                                        status=page.content_status,
                                        metrics={"word_count": page.word_count},
                                    ),
                                )
                            )
                            seen_page_nodes.add(page_node_id)

                    edges.append(
                        ContentArchitectureGraphEdge(
                            id=f"edge-kw-{m.keyword_id}-page-{m.page_id}",
                            source=f"kw-{m.keyword_id}",
                            target=page_node_id,
                            type="targets",
                            label=m.mapping_type,
                        )
                    )

            return ContentArchitectureGraphResponse(nodes=nodes, edges=edges)
