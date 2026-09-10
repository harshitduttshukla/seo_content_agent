"""SEO domain application service for SEO Guides, outlines, deterministic
guidelines, and approvals."""

from datetime import UTC, datetime
from uuid import UUID

from app.core.errors import ResourceNotFound
from app.db.session import set_actor_context
from app.domains.audit.repository import AuditWriter
from app.domains.content.repository import ContentRepository
from app.domains.keywords.repository import KeywordRepository
from app.domains.projects.service import ProjectService
from app.domains.seo.models import SEOGuide, SEOGuideStatus, SEOGuideVersion
from app.domains.seo.repository import SEOGuideRepository
from app.domains.seo.schemas import (
    SEOGuideDetail,
    SEOGuideUpdate,
    SEOGuideVersionDetail,
    SEOGuideVersionList,
)
from app.domains.strategy.repository import SEOStrategyRepository
from app.security.principal import AuthenticatedUser, PermissionCode
from sqlalchemy.ext.asyncio import AsyncSession


class SEOGuideService:
    def __init__(self) -> None:
        self._seo = SEOGuideRepository()
        self._content = ContentRepository()
        self._keywords = KeywordRepository()
        self._strategy = SEOStrategyRepository()
        self._projects = ProjectService()
        self._audit = AuditWriter()

    def _generate_default_outline(self, title: str, keyword: str) -> list[dict[str, object]]:
        kw = keyword or title
        return [
            {"level": 1, "title": title, "required": True},
            {"level": 2, "title": f"Introduction to {kw.title()}", "required": True},
            {"level": 2, "title": "Core Concepts & Fundamentals", "required": True},
            {"level": 2, "title": "Step-by-Step Implementation Guide", "required": True},
            {"level": 3, "title": "Key Requirements and Essential Checklist", "required": True},
            {"level": 3, "title": "Common Pitfalls and How to Avoid Them", "required": True},
            {"level": 2, "title": "Measuring Results & Strategic Impact", "required": False},
            {"level": 2, "title": "Frequently Asked Questions (FAQ)", "required": True},
        ]

    def _generate_default_rules(self, keyword: str) -> dict[str, object]:
        return {
            "title_keyword_placement": {
                "rule": "Primary keyword should appear near the beginning of title",
                "passed": True,
            },
            "title_length_bounds": {
                "min_chars": 50,
                "max_chars": 60,
                "recommendation": "Keep between 50-60 characters",
            },
            "h1_presence": {
                "rule": "Exactly one H1 heading containing target primary keyword",
                "passed": True,
            },
            "meta_description_length": {
                "min_chars": 135,
                "max_chars": 160,
                "recommendation": "Provide compelling CTR-focused summary",
            },
            "url_slug_rules": {
                "rule": "URL slug must be concise, lowercase, hyphenated, and include primary term",
                "passed": True,
            },
            "heading_hierarchy": {
                "rule": "Strict H1 -> H2 -> H3 hierarchy without skipped levels",
                "passed": True,
            },
            "internal_links_target": {
                "min_inbound": 3,
                "min_outbound": 3,
                "recommendation": "Connect to parent pillar and supporting pages",
            },
            "schema_markup": {
                "type": "Article",
                "recommendation": "Implement JSON-LD Article or TechArticle schema",
            },
        }

    async def get_or_create_guide(
        self,
        session: AsyncSession,
        *,
        actor: AuthenticatedUser,
        page_id: UUID,
    ) -> SEOGuideDetail:
        async with session.begin():
            await set_actor_context(session, actor.user_id)
            page = await self._content.get_planned_page_by_id(session, page_id=page_id)
            if not page:
                raise ResourceNotFound(f"Planned content page {page_id} was not found.")

            await self._projects.get_model(
                session,
                actor=actor,
                project_id=page.project_id,
                permission=PermissionCode.SEO_READ,
            )

            existing = await self._seo.get_guide_by_page_id(session, page_id=page.id)
            if existing:
                return SEOGuideDetail.model_validate(existing)

            # Auto-initialize a default guide
            primary_kw = page.primary_keyword or page.title
            target_audience = "Industry practitioners, managers, and decision makers"
            strategy = await self._strategy.get_by_project_id(session, project_id=page.project_id)
            if strategy:
                strategy_version = await self._strategy.get_latest_version(
                    session,
                    strategy_id=strategy.id,
                )
                if strategy_version and strategy_version.strategy_data:
                    audience = strategy_version.strategy_data.get("audience")
                    if isinstance(audience, dict):
                        segments = audience.get("segments")
                        if isinstance(segments, list):
                            audience_segments = [
                                segment.strip()
                                for segment in segments
                                if isinstance(segment, str) and segment.strip()
                            ]
                            if audience_segments:
                                target_audience = ", ".join(audience_segments)[:500]

                        if target_audience.startswith("Industry practitioners"):
                            personas = audience.get("personas")
                            if isinstance(personas, list):
                                for persona in personas:
                                    if not isinstance(persona, dict):
                                        continue
                                    persona_name = persona.get("name")
                                    if isinstance(persona_name, str) and persona_name.strip():
                                        target_audience = persona_name.strip()[:500]
                                        break

            # Retrieve secondary keywords
            kw_members = await self._content.list_page_keywords(session, page_id=page.id)
            secondary_kws = []
            for km in kw_members:
                kw_obj = await self._keywords.get_by_id(
                    session,
                    keyword_id=km.keyword_id,
                    project_id=page.project_id,
                )
                if kw_obj:
                    secondary_kws.append(kw_obj.keyword)

            rec_title = (
                f"{page.title}: Complete {page.content_type.replace('_', ' ').title()} Guide"
            )
            if len(rec_title) > 60:
                rec_title = f"{page.title} Guide"

            meta_desc = (
                f"Learn all about {primary_kw}. Complete walkthrough, step-by-step best practices, "
                "actionable takeaways, and expert recommendations."
            )

            outline = self._generate_default_outline(page.title, primary_kw)
            rules = self._generate_default_rules(primary_kw)

            word_count = 1500
            if page.content_type in ("PILLAR_PAGE", "GUIDE"):
                word_count = 2500
            elif page.content_type in ("COMPARISON", "SERVICE_PAGE"):
                word_count = 1800
            elif page.content_type in ("FAQ", "LANDING_PAGE"):
                word_count = 1000

            guide = SEOGuide(
                organization_id=page.organization_id,
                project_id=page.project_id,
                page_id=page.id,
                version=1,
                status=SEOGuideStatus.DRAFT,
                primary_keyword=primary_kw,
                secondary_keywords=secondary_kws,
                search_intent=page.intent,
                target_audience=target_audience,
                recommended_title=rec_title,
                meta_title=rec_title,
                meta_description=meta_desc[:160],
                recommended_url=page.url or f"/{page.slug}",
                content_type=page.content_type,
                word_count_target=word_count,
                required_topics=[
                    primary_kw,
                    f"{primary_kw} best practices",
                    f"{primary_kw} checklist",
                ],
                key_entities=[primary_kw, "strategy", "architecture", "analysis"],
                serp_notes=(
                    "Top ranking results feature actionable checklists, "
                    "structured FAQs, and clear step-by-step examples."
                ),
                content_requirements=[
                    "Include an executive summary at the start",
                    "Provide actionable implementation steps with clear headers",
                    "Add structured FAQ section answering key search queries",
                ],
                outline=outline,
                seo_rules=rules,
            )
            created = await self._seo.create_guide(session, guide)
            await session.refresh(created)
            created_detail = SEOGuideDetail.model_validate(created)

            # Record version 1 snapshot
            v_obj = SEOGuideVersion(
                guide_id=created.id,
                page_id=created.page_id,
                version=1,
                snapshot_data=created_detail.model_dump(mode="json"),
                change_summary="Initial auto-generated SEO guide",
                created_by_id=actor.user_id,
            )
            await self._seo.create_version(session, v_obj)

            return created_detail

    async def update_guide(
        self,
        session: AsyncSession,
        *,
        actor: AuthenticatedUser,
        page_id: UUID,
        payload: SEOGuideUpdate,
        request_id: str = "",
    ) -> SEOGuideDetail:
        async with session.begin():
            await set_actor_context(session, actor.user_id)
            page = await self._content.get_planned_page_by_id(session, page_id=page_id)
            if not page:
                raise ResourceNotFound(f"Planned content page {page_id} was not found.")

            await self._projects.get_model(
                session,
                actor=actor,
                project_id=page.project_id,
                permission=PermissionCode.SEO_WRITE,
            )

            guide = await self._seo.get_guide_by_page_id(session, page_id=page.id)
            if not guide:
                raise ResourceNotFound(f"SEO guide for page {page_id} does not exist.")

            if payload.primary_keyword is not None:
                guide.primary_keyword = payload.primary_keyword
            if payload.secondary_keywords is not None:
                guide.secondary_keywords = payload.secondary_keywords
            if payload.search_intent is not None:
                guide.search_intent = payload.search_intent
            if payload.target_audience is not None:
                guide.target_audience = payload.target_audience
            if payload.recommended_title is not None:
                guide.recommended_title = payload.recommended_title
            if payload.meta_title is not None:
                guide.meta_title = payload.meta_title
            if payload.meta_description is not None:
                guide.meta_description = payload.meta_description
            if payload.recommended_url is not None:
                guide.recommended_url = payload.recommended_url
            if payload.content_type is not None:
                guide.content_type = payload.content_type
            if payload.word_count_target is not None:
                guide.word_count_target = payload.word_count_target
            if payload.required_topics is not None:
                guide.required_topics = payload.required_topics
            if payload.key_entities is not None:
                guide.key_entities = payload.key_entities
            if payload.serp_notes is not None:
                guide.serp_notes = payload.serp_notes
            if payload.content_requirements is not None:
                guide.content_requirements = payload.content_requirements
            if payload.outline is not None:
                guide.outline = [sec.model_dump() for sec in payload.outline]
            if payload.seo_rules is not None:
                guide.seo_rules = payload.seo_rules
            if payload.status is not None:
                guide.status = payload.status

            guide.version += 1
            guide.revision += 1
            updated = await self._seo.update_guide(session, guide)
            await session.refresh(updated)

            # Record new version snapshot
            snapshot = {
                "version": updated.version,
                "status": updated.status,
                "primary_keyword": updated.primary_keyword,
                "recommended_title": updated.recommended_title,
                "meta_description": updated.meta_description,
                "word_count_target": updated.word_count_target,
                "outline": updated.outline,
                "updated_at": datetime.now(UTC).isoformat(),
            }
            v_obj = SEOGuideVersion(
                guide_id=updated.id,
                page_id=updated.page_id,
                version=updated.version,
                snapshot_data=snapshot,
                change_summary="User update to SEO guide",
                created_by_id=actor.user_id,
            )
            await self._seo.create_version(session, v_obj)

            self._audit.add(
                session,
                organization_id=guide.organization_id,
                project_id=guide.project_id,
                actor_user_id=actor.user_id,
                action="seo.guide.update",
                resource_type="seo_guide",
                resource_id=guide.id,
                outcome="success",
                request_id=request_id,
                metadata={"page_id": str(page.id), "version": updated.version},
            )

            return SEOGuideDetail.model_validate(updated)

    async def approve_guide(
        self,
        session: AsyncSession,
        *,
        actor: AuthenticatedUser,
        page_id: UUID,
        request_id: str = "",
    ) -> SEOGuideDetail:
        async with session.begin():
            await set_actor_context(session, actor.user_id)
            page = await self._content.get_planned_page_by_id(session, page_id=page_id)
            if not page:
                raise ResourceNotFound(f"Planned content page {page_id} was not found.")

            await self._projects.get_model(
                session,
                actor=actor,
                project_id=page.project_id,
                permission=PermissionCode.SEO_WRITE,
            )

            guide = await self._seo.get_guide_by_page_id(session, page_id=page.id)
            if not guide:
                raise ResourceNotFound(f"SEO guide for page {page_id} does not exist.")

            guide.status = SEOGuideStatus.APPROVED
            guide.revision += 1
            updated = await self._seo.update_guide(session, guide)
            await session.refresh(updated)

            self._audit.add(
                session,
                organization_id=guide.organization_id,
                project_id=guide.project_id,
                actor_user_id=actor.user_id,
                action="seo.guide.approve",
                resource_type="seo_guide",
                resource_id=guide.id,
                outcome="success",
                request_id=request_id,
                metadata={"page_id": str(page.id), "status": guide.status},
            )

            return SEOGuideDetail.model_validate(updated)

    async def list_versions(
        self,
        session: AsyncSession,
        *,
        actor: AuthenticatedUser,
        page_id: UUID,
    ) -> SEOGuideVersionList:
        async with session.begin():
            await set_actor_context(session, actor.user_id)
            page = await self._content.get_planned_page_by_id(session, page_id=page_id)
            if not page:
                raise ResourceNotFound(f"Planned content page {page_id} was not found.")

            await self._projects.get_model(
                session,
                actor=actor,
                project_id=page.project_id,
                permission=PermissionCode.SEO_READ,
            )

            versions = await self._seo.list_versions(session, page_id=page.id)
            items = [SEOGuideVersionDetail.model_validate(v) for v in versions]
            return SEOGuideVersionList(items=items)
