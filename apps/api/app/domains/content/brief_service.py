"""Service layer for Content Brief generation, lifecycle management, and versioning."""

from datetime import UTC, datetime
from uuid import UUID

from app.core.errors import ConflictError, ResourceNotFound
from app.db.session import set_actor_context
from app.domains.audit.repository import AuditWriter
from app.domains.content.brief_schemas import (
    BrandRequirements,
    ContentBriefCreate,
    ContentBriefDetail,
    ContentBriefUpdate,
    ContentBriefVersionDetail,
    ContentBriefVersionList,
    InternalLinkTarget,
)
from app.domains.content.editor_models import (
    BriefStatus,
    ContentBrief,
    ContentBriefVersion,
)
from app.domains.content.models import (
    PageKeyword,
    PlannedContentPage,
)
from app.domains.internal_linking.models import LinkOpportunity, PageRelationship
from app.domains.keywords.models import Keyword
from app.domains.projects.service import ProjectService
from app.domains.seo.models import SEOGuide
from app.domains.strategy.models import SEOStrategy, SEOStrategyVersion
from app.security.principal import AuthenticatedUser, PermissionCode
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


class ContentBriefService:
    def __init__(self) -> None:
        self._audit = AuditWriter()
        self._projects = ProjectService()

    async def get_brief_by_page_id(
        self,
        session: AsyncSession,
        *,
        page_id: UUID,
        project_id: UUID,
    ) -> ContentBrief | None:
        stmt = (
            select(ContentBrief)
            .where(
                ContentBrief.page_id == page_id,
                ContentBrief.project_id == project_id,
            )
            .order_by(ContentBrief.created_at.desc())
        )
        res = await session.execute(stmt)
        return res.scalars().first()

    async def get_brief_by_id(
        self,
        session: AsyncSession,
        *,
        brief_id: UUID,
        project_id: UUID,
    ) -> ContentBrief | None:
        stmt = select(ContentBrief).where(
            ContentBrief.id == brief_id,
            ContentBrief.project_id == project_id,
        )
        res = await session.execute(stmt)
        return res.scalars().first()

    async def generate_brief(
        self,
        session: AsyncSession,
        *,
        page_id: UUID,
        project_id: UUID,
        user_id: UUID | None = None,
        override_payload: ContentBriefCreate | None = None,
    ) -> ContentBrief:
        # 1. Verify planned content page exists in project
        page_stmt = select(PlannedContentPage).where(
            PlannedContentPage.id == page_id,
            PlannedContentPage.project_id == project_id,
        )
        page_res = await session.execute(page_stmt)
        page = page_res.scalars().first()
        if not page:
            raise ResourceNotFound(f"Planned page {page_id} not found in project {project_id}")

        # Check if brief already exists
        existing_brief = await self.get_brief_by_page_id(
            session, page_id=page_id, project_id=project_id
        )
        if existing_brief:
            return existing_brief

        # 2. Extract SEO Guide if present
        guide_stmt = select(SEOGuide).where(
            SEOGuide.page_id == page_id,
            SEOGuide.project_id == project_id,
        )
        guide_res = await session.execute(guide_stmt)
        seo_guide = guide_res.scalars().first()

        # 3. Extract Secondary Keywords
        kw_stmt = (
            select(Keyword.keyword)
            .join(PageKeyword, PageKeyword.keyword_id == Keyword.id)
            .where(PageKeyword.page_id == page_id)
        )
        kw_res = await session.execute(kw_stmt)
        secondary_kws = list(kw_res.scalars().all())

        if seo_guide and seo_guide.secondary_keywords:
            for kw in seo_guide.secondary_keywords:
                if kw not in secondary_kws:
                    secondary_kws.append(kw)

        # 4. Extract Strategy Context
        strat_stmt = (
            select(SEOStrategyVersion)
            .join(SEOStrategy, SEOStrategy.id == SEOStrategyVersion.strategy_id)
            .where(SEOStrategy.project_id == project_id)
            .order_by(SEOStrategyVersion.version.desc())
        )
        strat_res = await session.execute(strat_stmt)
        strategy_version = strat_res.scalars().first()
        strategy_data = strategy_version.strategy_data if strategy_version else {}

        # 5. Extract Internal Link targets
        link_targets: list[dict[str, object]] = []

        # From approved opportunities or active relationships
        rel_stmt = (
            select(PageRelationship, PlannedContentPage)
            .join(PlannedContentPage, PlannedContentPage.id == PageRelationship.target_page_id)
            .where(
                PageRelationship.source_page_id == page_id,
                PageRelationship.project_id == project_id,
            )
        )
        rel_res = await session.execute(rel_stmt)
        for rel, tgt_page in rel_res.all():
            link_targets.append(
                InternalLinkTarget(
                    target_page_id=tgt_page.id,
                    title=tgt_page.title,
                    url=tgt_page.url or f"/{tgt_page.slug}",
                    anchor_text=rel.anchor_text or tgt_page.primary_keyword or tgt_page.title,
                    reason=rel.reason or "Approved relationship target",
                ).model_dump()
            )

        # From suggested opportunities if relationships are sparse
        if len(link_targets) < 3:
            opp_stmt = (
                select(LinkOpportunity, PlannedContentPage)
                .join(PlannedContentPage, PlannedContentPage.id == LinkOpportunity.target_page_id)
                .where(
                    LinkOpportunity.source_page_id == page_id,
                    LinkOpportunity.project_id == project_id,
                )
                .limit(5)
            )
            opp_res = await session.execute(opp_stmt)
            for opp, tgt_page in opp_res.all():
                if not any(t["target_page_id"] == str(tgt_page.id) for t in link_targets):
                    anchor = opp.anchor_suggestion or tgt_page.primary_keyword or tgt_page.title
                    link_targets.append(
                        InternalLinkTarget(
                            target_page_id=tgt_page.id,
                            title=tgt_page.title,
                            url=tgt_page.url or f"/{tgt_page.slug}",
                            anchor_text=anchor,
                            reason=opp.reason or "Algorithmic link opportunity",
                        ).model_dump()
                    )

        # 6. Assemble default topics & questions
        primary_kw = page.primary_keyword or (seo_guide.primary_keyword if seo_guide else "")
        recommended_title = (
            seo_guide.recommended_title
            if (seo_guide and seo_guide.recommended_title)
            else page.title
        )
        meta_title = (
            seo_guide.meta_title if (seo_guide and seo_guide.meta_title) else recommended_title
        )
        meta_description = (
            seo_guide.meta_description
            if (seo_guide and seo_guide.meta_description)
            else f"Comprehensive, practical guide on {primary_kw or page.title}."
        )
        recommended_url = (
            seo_guide.recommended_url
            if (seo_guide and seo_guide.recommended_url)
            else (page.url or f"/{page.slug}")
        )
        target_word_count = (
            seo_guide.word_count_target if (seo_guide and seo_guide.word_count_target) else 1500
        )
        required_topics = (
            list(seo_guide.required_topics)
            if (seo_guide and seo_guide.required_topics)
            else [
                f"Core fundamentals of {primary_kw or page.title}",
                "Step-by-step practical implementation",
                "Best practices and key considerations",
                "Common pitfalls and remediation",
            ]
        )
        key_entities = (
            list(seo_guide.key_entities)
            if (seo_guide and seo_guide.key_entities)
            else [primary_kw]
            if primary_kw
            else []
        )
        topic_term = primary_kw or page.title
        questions_to_answer = [
            f"What is {topic_term} and why is it important?",
            f"How do you implement {primary_kw or 'this strategy'} effectively?",
            f"What are the most critical mistakes to avoid with {primary_kw or 'this topic'}?",
            f"How do you measure success and return on investment for {topic_term}?",
        ]
        content_requirements = (
            list(seo_guide.content_requirements)
            if (seo_guide and seo_guide.content_requirements)
            else [
                "Include actionable examples and structured checklists.",
                "Ensure logical H1 -> H2 -> H3 heading progression.",
                "Incorporate defined target entities and secondary search terms naturally.",
            ]
        )

        brand_req = BrandRequirements()
        if strategy_data:
            biz_ctx = strategy_data.get("business_context", {})
            if isinstance(biz_ctx, dict) and biz_ctx.get("business_name"):
                b_name = biz_ctx.get("business_name")
                brand_req.voice = f"Authoritative, clear voice representing {b_name}"

        # 7. Construct ContentBrief record
        default_audience = "Target buyers, professionals, and decision makers"
        target_aud = (
            seo_guide.target_audience
            if (seo_guide and seo_guide.target_audience)
            else default_audience
        )
        biz_goal = (
            f"Establish domain authority and drive qualified organic search traffic for "
            f"{primary_kw or page.title}"
        )
        brief = ContentBrief(
            organization_id=page.organization_id,
            project_id=project_id,
            website_id=page.website_id,
            page_id=page_id,
            seo_guide_id=seo_guide.id if seo_guide else None,
            version=1,
            status=BriefStatus.DRAFT,
            primary_keyword=primary_kw,
            secondary_keywords=secondary_kws,
            search_intent=page.intent or "INFORMATIONAL",
            target_audience=target_aud,
            business_goal=biz_goal,
            content_type=page.content_type or "GUIDE",
            recommended_title=recommended_title,
            recommended_url=recommended_url,
            meta_title=meta_title,
            meta_description=meta_description,
            target_word_count=target_word_count,
            required_topics=required_topics,
            key_entities=key_entities,
            questions_to_answer=questions_to_answer,
            internal_link_targets=link_targets,
            external_source_requirements=[
                "Reference reputable industry publications and authoritative research.",
                "Cite official standards, documentation, or verifiable case studies.",
            ],
            content_requirements=content_requirements,
            brand_requirements=brand_req.model_dump(),
            created_by_id=user_id,
            updated_by_id=user_id,
        )

        session.add(brief)
        await session.flush()

        await self._audit.log_event(
            session=session,
            organization_id=page.organization_id,
            project_id=project_id,
            user_id=user_id,
            action="content_brief.created",
            resource_type="content_brief",
            resource_id=brief.id,
            metadata={"page_id": str(page_id), "version": 1},
        )

        return brief

    async def update_brief(
        self,
        session: AsyncSession,
        *,
        brief_id: UUID,
        project_id: UUID,
        payload: ContentBriefUpdate,
        user_id: UUID | None = None,
    ) -> ContentBrief:
        brief = await self.get_brief_by_id(session, brief_id=brief_id, project_id=project_id)
        if not brief:
            raise ResourceNotFound(f"Content brief {brief_id} not found")

        if payload.primary_keyword is not None:
            brief.primary_keyword = payload.primary_keyword
        if payload.secondary_keywords is not None:
            brief.secondary_keywords = payload.secondary_keywords
        if payload.search_intent is not None:
            brief.search_intent = payload.search_intent
        if payload.target_audience is not None:
            brief.target_audience = payload.target_audience
        if payload.business_goal is not None:
            brief.business_goal = payload.business_goal
        if payload.content_type is not None:
            brief.content_type = payload.content_type
        if payload.recommended_title is not None:
            brief.recommended_title = payload.recommended_title
        if payload.recommended_url is not None:
            brief.recommended_url = payload.recommended_url
        if payload.meta_title is not None:
            brief.meta_title = payload.meta_title
        if payload.meta_description is not None:
            brief.meta_description = payload.meta_description
        if payload.target_word_count is not None:
            brief.target_word_count = payload.target_word_count
        if payload.required_topics is not None:
            brief.required_topics = payload.required_topics
        if payload.key_entities is not None:
            brief.key_entities = payload.key_entities
        if payload.questions_to_answer is not None:
            brief.questions_to_answer = payload.questions_to_answer
        if payload.internal_link_targets is not None:
            brief.internal_link_targets = [t.model_dump() for t in payload.internal_link_targets]
        if payload.external_source_requirements is not None:
            brief.external_source_requirements = payload.external_source_requirements
        if payload.content_requirements is not None:
            brief.content_requirements = payload.content_requirements
        if payload.brand_requirements is not None:
            brief.brand_requirements = payload.brand_requirements.model_dump()
        if payload.status is not None:
            brief.status = payload.status

        brief.updated_by_id = user_id
        brief.updated_at = datetime.now(UTC)
        await session.flush()

        await self._audit.log_event(
            session=session,
            organization_id=brief.organization_id,
            project_id=project_id,
            user_id=user_id,
            action="content_brief.updated",
            resource_type="content_brief",
            resource_id=brief.id,
            metadata={"version": brief.version, "status": brief.status},
        )

        return brief

    async def approve_brief(
        self,
        session: AsyncSession,
        *,
        brief_id: UUID,
        project_id: UUID,
        change_summary: str = "Content brief approved for production",
        user_id: UUID | None = None,
    ) -> tuple[ContentBrief, ContentBriefVersion]:
        brief = await self.get_brief_by_id(session, brief_id=brief_id, project_id=project_id)
        if not brief:
            raise ResourceNotFound(f"Content brief {brief_id} not found")

        if brief.status == BriefStatus.ARCHIVED:
            raise ConflictError("Cannot approve an archived content brief")

        # Snapshot current brief state
        snapshot_data = {
            "id": str(brief.id),
            "page_id": str(brief.page_id),
            "version": brief.version,
            "primary_keyword": brief.primary_keyword,
            "secondary_keywords": brief.secondary_keywords,
            "search_intent": brief.search_intent,
            "target_audience": brief.target_audience,
            "business_goal": brief.business_goal,
            "content_type": brief.content_type,
            "recommended_title": brief.recommended_title,
            "recommended_url": brief.recommended_url,
            "meta_title": brief.meta_title,
            "meta_description": brief.meta_description,
            "target_word_count": brief.target_word_count,
            "required_topics": brief.required_topics,
            "key_entities": brief.key_entities,
            "questions_to_answer": brief.questions_to_answer,
            "internal_link_targets": brief.internal_link_targets,
            "external_source_requirements": brief.external_source_requirements,
            "content_requirements": brief.content_requirements,
            "brand_requirements": brief.brand_requirements,
        }

        # Create immutable version record
        brief_version = ContentBriefVersion(
            organization_id=brief.organization_id,
            project_id=project_id,
            brief_id=brief.id,
            version=brief.version,
            snapshot_data=snapshot_data,
            change_summary=change_summary,
            created_by_id=user_id,
            created_at=datetime.now(UTC),
        )
        session.add(brief_version)

        # Transition brief to APPROVED and bump next version number
        brief.status = BriefStatus.APPROVED
        brief.version += 1
        brief.updated_by_id = user_id
        brief.updated_at = datetime.now(UTC)

        await session.flush()

        await self._audit.log_event(
            session=session,
            organization_id=brief.organization_id,
            project_id=project_id,
            user_id=user_id,
            action="content_brief.approved",
            resource_type="content_brief",
            resource_id=brief.id,
            metadata={"version_created": brief_version.version, "summary": change_summary},
        )

        return brief, brief_version

    async def list_brief_versions(
        self,
        session: AsyncSession,
        *,
        brief_id: UUID,
        project_id: UUID,
    ) -> list[ContentBriefVersion]:
        stmt = (
            select(ContentBriefVersion)
            .where(
                ContentBriefVersion.brief_id == brief_id,
                ContentBriefVersion.project_id == project_id,
            )
            .order_by(ContentBriefVersion.version.desc())
        )
        res = await session.execute(stmt)
        return list(res.scalars().all())

    async def get_or_create_brief(
        self,
        session: AsyncSession,
        *,
        actor: AuthenticatedUser,
        page_id: UUID,
    ) -> ContentBriefDetail:
        async with session.begin():
            await set_actor_context(session, actor.user_id)
            page_stmt = select(PlannedContentPage).where(PlannedContentPage.id == page_id)
            page_res = await session.execute(page_stmt)
            page = page_res.scalars().first()
            if not page:
                raise ResourceNotFound(f"Planned page {page_id} not found")

            await self._projects.get_model(
                session,
                actor=actor,
                project_id=page.project_id,
                permission=PermissionCode.CONTENT_READ,
            )

            existing = await self.get_brief_by_page_id(
                session, page_id=page_id, project_id=page.project_id
            )
            if existing:
                return ContentBriefDetail.model_validate(existing)

            brief = await self.generate_brief(
                session,
                page_id=page_id,
                project_id=page.project_id,
                user_id=actor.user_id,
            )
            return ContentBriefDetail.model_validate(brief)

    async def update_brief_endpoint(
        self,
        session: AsyncSession,
        *,
        actor: AuthenticatedUser,
        brief_id: UUID,
        payload: ContentBriefUpdate,
    ) -> ContentBriefDetail:
        async with session.begin():
            await set_actor_context(session, actor.user_id)
            brief_stmt = select(ContentBrief).where(ContentBrief.id == brief_id)
            brief_res = await session.execute(brief_stmt)
            brief = brief_res.scalars().first()
            if not brief:
                raise ResourceNotFound(f"Content brief {brief_id} not found")

            await self._projects.get_model(
                session,
                actor=actor,
                project_id=brief.project_id,
                permission=PermissionCode.CONTENT_WRITE,
            )

            updated = await self.update_brief(
                session,
                brief_id=brief_id,
                project_id=brief.project_id,
                payload=payload,
                user_id=actor.user_id,
            )
            return ContentBriefDetail.model_validate(updated)

    async def approve_brief_endpoint(
        self,
        session: AsyncSession,
        *,
        actor: AuthenticatedUser,
        brief_id: UUID,
        change_summary: str = "Content brief approved for production",
    ) -> ContentBriefDetail:
        async with session.begin():
            await set_actor_context(session, actor.user_id)
            brief_stmt = select(ContentBrief).where(ContentBrief.id == brief_id)
            brief_res = await session.execute(brief_stmt)
            brief = brief_res.scalars().first()
            if not brief:
                raise ResourceNotFound(f"Content brief {brief_id} not found")

            await self._projects.get_model(
                session,
                actor=actor,
                project_id=brief.project_id,
                permission=PermissionCode.CONTENT_WRITE,
            )

            approved_brief, _ = await self.approve_brief(
                session,
                brief_id=brief_id,
                project_id=brief.project_id,
                change_summary=change_summary,
                user_id=actor.user_id,
            )
            return ContentBriefDetail.model_validate(approved_brief)

    async def list_versions_endpoint(
        self,
        session: AsyncSession,
        *,
        actor: AuthenticatedUser,
        brief_id: UUID,
    ) -> ContentBriefVersionList:
        async with session.begin():
            await set_actor_context(session, actor.user_id)
            brief_stmt = select(ContentBrief).where(ContentBrief.id == brief_id)
            brief_res = await session.execute(brief_stmt)
            brief = brief_res.scalars().first()
            if not brief:
                raise ResourceNotFound(f"Content brief {brief_id} not found")

            await self._projects.get_model(
                session,
                actor=actor,
                project_id=brief.project_id,
                permission=PermissionCode.CONTENT_READ,
            )

            versions = await self.list_brief_versions(
                session, brief_id=brief_id, project_id=brief.project_id
            )
            return ContentBriefVersionList(
                items=[ContentBriefVersionDetail.model_validate(v) for v in versions]
            )
