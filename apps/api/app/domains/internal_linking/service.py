"""Internal linking application service for page relationships, link scoring,
and opportunity management."""

from collections import defaultdict
from uuid import UUID

from app.core.errors import ConflictError, DomainError, ResourceNotFound
from app.db.session import set_actor_context
from app.domains.audit.repository import AuditWriter
from app.domains.content.repository import ContentRepository
from app.domains.internal_linking.models import (
    LinkOpportunity,
    LinkOpportunityStatus,
    PageRelationship,
    PageRelationshipStatus,
    PageRelationshipType,
)
from app.domains.internal_linking.repository import InternalLinkingRepository
from app.domains.internal_linking.schemas import (
    InternalLinksSummary,
    LinkOpportunityDetail,
    LinkOpportunityList,
    OrphanPageDetail,
    OrphanPageList,
    PageRelationshipCreate,
    PageRelationshipDetail,
    PageRelationshipList,
)
from app.domains.projects.service import ProjectService
from app.security.principal import AuthenticatedUser, PermissionCode
from sqlalchemy.ext.asyncio import AsyncSession


class InternalLinkingService:
    def __init__(self) -> None:
        self._linking = InternalLinkingRepository()
        self._content = ContentRepository()
        self._projects = ProjectService()
        self._audit = AuditWriter()

    async def _to_relationship_detail(
        self, session: AsyncSession, rel: PageRelationship
    ) -> PageRelationshipDetail:
        src = await self._content.get_planned_page_by_id(session, page_id=rel.source_page_id)
        tgt = await self._content.get_planned_page_by_id(session, page_id=rel.target_page_id)
        return PageRelationshipDetail(
            id=rel.id,
            organization_id=rel.organization_id,
            project_id=rel.project_id,
            source_page_id=rel.source_page_id,
            source_page_title=src.title if src else "",
            source_page_url=src.url if src else "",
            target_page_id=rel.target_page_id,
            target_page_title=tgt.title if tgt else "",
            target_page_url=tgt.url if tgt else "",
            relationship_type=rel.relationship_type,
            anchor_text=rel.anchor_text,
            priority=rel.priority,
            reason=rel.reason,
            confidence=rel.confidence,
            status=rel.status,
            created_at=rel.created_at,
        )

    async def _to_opportunity_detail(
        self, session: AsyncSession, opp: LinkOpportunity
    ) -> LinkOpportunityDetail:
        src = await self._content.get_planned_page_by_id(session, page_id=opp.source_page_id)
        tgt = await self._content.get_planned_page_by_id(session, page_id=opp.target_page_id)
        return LinkOpportunityDetail(
            id=opp.id,
            organization_id=opp.organization_id,
            project_id=opp.project_id,
            source_page_id=opp.source_page_id,
            source_page_title=src.title if src else "",
            source_page_url=opp.source_url or (src.url if src else ""),
            target_page_id=opp.target_page_id,
            target_page_title=tgt.title if tgt else "",
            target_page_url=opp.target_url or (tgt.url if tgt else ""),
            anchor_suggestion=opp.anchor_suggestion,
            reason=opp.reason,
            confidence=opp.confidence,
            priority=opp.priority,
            status=opp.status,
            created_at=opp.created_at,
        )

    async def list_relationships(
        self,
        session: AsyncSession,
        *,
        actor: AuthenticatedUser,
        project_id: UUID,
        status: str | None = None,
    ) -> PageRelationshipList:
        async with session.begin():
            await set_actor_context(session, actor.user_id)
            project = await self._projects.get_model(
                session,
                actor=actor,
                project_id=project_id,
                permission=PermissionCode.CONTENT_READ,
            )

            rels = await self._linking.list_relationships(
                session, project_id=project.id, status=status
            )
            items = [await self._to_relationship_detail(session, r) for r in rels]
            return PageRelationshipList(items=items)

    async def create_relationship(
        self,
        session: AsyncSession,
        *,
        actor: AuthenticatedUser,
        project_id: UUID,
        payload: PageRelationshipCreate,
        request_id: str = "",
    ) -> PageRelationshipDetail:
        async with session.begin():
            await set_actor_context(session, actor.user_id)
            project = await self._projects.get_model(
                session,
                actor=actor,
                project_id=project_id,
                permission=PermissionCode.CONTENT_WRITE,
            )

            if payload.source_page_id == payload.target_page_id:
                raise DomainError("SELF_LINK_FORBIDDEN", "A page cannot link or relate to itself.")

            src = await self._content.get_planned_page_by_id(
                session, page_id=payload.source_page_id, project_id=project.id
            )
            if not src:
                raise ResourceNotFound(f"Source page {payload.source_page_id} was not found.")

            tgt = await self._content.get_planned_page_by_id(
                session, page_id=payload.target_page_id, project_id=project.id
            )
            if not tgt:
                raise ResourceNotFound(f"Target page {payload.target_page_id} was not found.")

            existing = await self._linking.get_relationship_by_pair(
                session,
                source_id=src.id,
                target_id=tgt.id,
                rel_type=payload.relationship_type,
            )
            if existing:
                raise ConflictError("RELATIONSHIP_EXISTS", "This page relationship already exists.")

            rel = PageRelationship(
                organization_id=project.organization_id,
                project_id=project.id,
                source_page_id=src.id,
                target_page_id=tgt.id,
                relationship_type=payload.relationship_type,
                anchor_text=payload.anchor_text or tgt.primary_keyword or tgt.title,
                priority=payload.priority,
                reason=payload.reason or "Strategic content relationship",
                confidence=1.0,
                status=PageRelationshipStatus.ACTIVE,
            )
            created = await self._linking.create_relationship(session, rel)

            self._audit.add(
                session,
                organization_id=project.organization_id,
                project_id=project.id,
                actor_user_id=actor.user_id,
                action="internal_linking.relationship.create",
                resource_type="page_relationship",
                resource_id=created.id,
                outcome="success",
                request_id=request_id,
                metadata={"source_id": str(src.id), "target_id": str(tgt.id)},
            )

            return await self._to_relationship_detail(session, created)

    async def delete_relationship(
        self,
        session: AsyncSession,
        *,
        actor: AuthenticatedUser,
        project_id: UUID,
        relationship_id: UUID,
        request_id: str = "",
    ) -> None:
        async with session.begin():
            await set_actor_context(session, actor.user_id)
            project = await self._projects.get_model(
                session,
                actor=actor,
                project_id=project_id,
                permission=PermissionCode.CONTENT_WRITE,
            )

            rel = await self._linking.get_relationship_by_id(session, rel_id=relationship_id)
            if not rel or rel.project_id != project.id:
                raise ResourceNotFound(f"Relationship {relationship_id} was not found.")

            await self._linking.delete_relationship(session, rel)
            self._audit.add(
                session,
                organization_id=project.organization_id,
                project_id=project.id,
                actor_user_id=actor.user_id,
                action="internal_linking.relationship.delete",
                resource_type="page_relationship",
                resource_id=rel.id,
                outcome="success",
                request_id=request_id,
                metadata={"relationship_id": str(rel.id)},
            )

    async def analyze_link_opportunities(
        self,
        session: AsyncSession,
        *,
        actor: AuthenticatedUser,
        project_id: UUID,
        request_id: str = "",
    ) -> LinkOpportunityList:
        """Runs the deterministic internal linking recommendation engine."""
        async with session.begin():
            await set_actor_context(session, actor.user_id)
            project = await self._projects.get_model(
                session,
                actor=actor,
                project_id=project_id,
                permission=PermissionCode.CONTENT_WRITE,
            )

            pages = await self._content.list_planned_pages(session, project_id=project.id)
            relationships = await self._linking.list_relationships(session, project_id=project.id)

            # Map existing relationships to avoid duplicates
            existing_pairs = {(r.source_page_id, r.target_page_id) for r in relationships}

            # Map inbound link counts for orphan detection
            inbound_counts: dict[UUID, int] = defaultdict(int)
            for r in relationships:
                inbound_counts[r.target_page_id] += 1

            new_opportunities: list[LinkOpportunity] = []

            for src in pages:
                for tgt in pages:
                    if src.id == tgt.id:
                        continue
                    if (src.id, tgt.id) in existing_pairs:
                        continue

                    # Evaluate deterministic recommendation signals:
                    score = 0.0
                    reason_parts = []

                    # Signal 1: Pillar Page to Cluster / Supporting Page
                    if src.content_type == "PILLAR_PAGE" and tgt.pillar_id == src.pillar_id:
                        score += 0.40
                        reason_parts.append("Pillar page should link down to topic cluster content")
                    elif tgt.content_type == "PILLAR_PAGE" and src.pillar_id == tgt.pillar_id:
                        score += 0.35
                        reason_parts.append(
                            "Supporting cluster page should link up to parent pillar page"
                        )

                    # Signal 2: Same Topic
                    if src.topic_id and tgt.topic_id and src.topic_id == tgt.topic_id:
                        score += 0.30
                        reason_parts.append("Pages share the same strategic topic")

                    # Signal 3: Orphan Page Inbound Boost
                    if inbound_counts[tgt.id] == 0:
                        score += 0.25
                        reason_parts.append(
                            "Target is currently an orphan page with 0 inbound links"
                        )

                    # Signal 4: Intent Complementarity (Informational -> Commercial/Transactional)
                    if src.intent == "INFORMATIONAL" and tgt.intent in (
                        "COMMERCIAL",
                        "TRANSACTIONAL",
                    ):
                        score += 0.15
                        reason_parts.append(
                            "Natural user journey progression from informational guide "
                            "to commercial page"
                        )

                    # Signal 5: Priority & Business Value Boost
                    if tgt.business_value >= 70.0:
                        score += 0.10
                        reason_parts.append("Target page carries high strategic business value")

                    if score >= 0.50:
                        confidence = min(0.98, score)
                        anchor = tgt.primary_keyword or tgt.title
                        existing_opp = await self._linking.get_opportunity_by_pair(
                            session, project_id=project.id, source_id=src.id, target_id=tgt.id
                        )
                        if existing_opp:
                            existing_opp.confidence = confidence
                            existing_opp.reason = "; ".join(reason_parts)
                            existing_opp.anchor_suggestion = anchor
                            await self._linking.update_opportunity(session, existing_opp)
                            new_opportunities.append(existing_opp)
                        else:
                            opp = LinkOpportunity(
                                organization_id=project.organization_id,
                                project_id=project.id,
                                source_page_id=src.id,
                                target_page_id=tgt.id,
                                source_url=src.url or f"/{src.slug}",
                                target_url=tgt.url or f"/{tgt.slug}",
                                anchor_suggestion=anchor,
                                reason="; ".join(reason_parts),
                                confidence=confidence,
                                priority=tgt.priority,
                                status=LinkOpportunityStatus.PROPOSED,
                            )
                            created = await self._linking.create_opportunity(session, opp)
                            new_opportunities.append(created)

            self._audit.add(
                session,
                organization_id=project.organization_id,
                project_id=project.id,
                actor_user_id=actor.user_id,
                action="internal_linking.opportunities.analyze",
                resource_type="link_opportunities",
                resource_id=project.id,
                outcome="success",
                request_id=request_id,
                metadata={"total_recommended": len(new_opportunities)},
            )

        return await self.list_opportunities(session, actor=actor, project_id=project_id)

    async def list_opportunities(
        self,
        session: AsyncSession,
        *,
        actor: AuthenticatedUser,
        project_id: UUID,
        status: str | None = None,
    ) -> LinkOpportunityList:
        async with session.begin():
            await set_actor_context(session, actor.user_id)
            project = await self._projects.get_model(
                session,
                actor=actor,
                project_id=project_id,
                permission=PermissionCode.CONTENT_READ,
            )

            opps = await self._linking.list_opportunities(
                session, project_id=project.id, status=status
            )
            items = [await self._to_opportunity_detail(session, o) for o in opps]
            return LinkOpportunityList(items=items, total=len(items))

    async def approve_opportunity(
        self,
        session: AsyncSession,
        *,
        actor: AuthenticatedUser,
        project_id: UUID,
        opportunity_id: UUID,
        request_id: str = "",
    ) -> LinkOpportunityDetail:
        """Approves a link opportunity and promotes it to an active PageRelationship."""
        async with session.begin():
            await set_actor_context(session, actor.user_id)
            project = await self._projects.get_model(
                session,
                actor=actor,
                project_id=project_id,
                permission=PermissionCode.CONTENT_WRITE,
            )

            opp = await self._linking.get_opportunity_by_id(session, opp_id=opportunity_id)
            if not opp or opp.project_id != project.id:
                raise ResourceNotFound(f"Link opportunity {opportunity_id} was not found.")

            opp.status = LinkOpportunityStatus.APPROVED
            opp.revision += 1
            await self._linking.update_opportunity(session, opp)

            # Promote to PageRelationship
            existing_rel = await self._linking.get_relationship_by_pair(
                session,
                source_id=opp.source_page_id,
                target_id=opp.target_page_id,
                rel_type=PageRelationshipType.SUPPORTS,
            )
            if not existing_rel:
                rel = PageRelationship(
                    organization_id=project.organization_id,
                    project_id=project.id,
                    source_page_id=opp.source_page_id,
                    target_page_id=opp.target_page_id,
                    relationship_type=PageRelationshipType.SUPPORTS,
                    anchor_text=opp.anchor_suggestion,
                    priority=opp.priority,
                    reason=opp.reason,
                    confidence=opp.confidence,
                    status=PageRelationshipStatus.ACTIVE,
                )
                await self._linking.create_relationship(session, rel)

            self._audit.add(
                session,
                organization_id=project.organization_id,
                project_id=project.id,
                actor_user_id=actor.user_id,
                action="internal_linking.opportunity.approve",
                resource_type="link_opportunity",
                resource_id=opp.id,
                outcome="success",
                request_id=request_id,
                metadata={
                    "source_id": str(opp.source_page_id),
                    "target_id": str(opp.target_page_id),
                },
            )

            return await self._to_opportunity_detail(session, opp)

    async def reject_opportunity(
        self,
        session: AsyncSession,
        *,
        actor: AuthenticatedUser,
        project_id: UUID,
        opportunity_id: UUID,
        request_id: str = "",
    ) -> LinkOpportunityDetail:
        async with session.begin():
            await set_actor_context(session, actor.user_id)
            project = await self._projects.get_model(
                session,
                actor=actor,
                project_id=project_id,
                permission=PermissionCode.CONTENT_WRITE,
            )

            opp = await self._linking.get_opportunity_by_id(session, opp_id=opportunity_id)
            if not opp or opp.project_id != project.id:
                raise ResourceNotFound(f"Link opportunity {opportunity_id} was not found.")

            opp.status = LinkOpportunityStatus.REJECTED
            opp.revision += 1
            await self._linking.update_opportunity(session, opp)

            self._audit.add(
                session,
                organization_id=project.organization_id,
                project_id=project.id,
                actor_user_id=actor.user_id,
                action="internal_linking.opportunity.reject",
                resource_type="link_opportunity",
                resource_id=opp.id,
                outcome="success",
                request_id=request_id,
                metadata={"opportunity_id": str(opp.id)},
            )

            return await self._to_opportunity_detail(session, opp)

    async def get_page_internal_links(
        self,
        session: AsyncSession,
        *,
        actor: AuthenticatedUser,
        page_id: UUID,
    ) -> InternalLinksSummary:
        """Retrieves crawled links, planned relationships, and recommendations for a page."""
        async with session.begin():
            await set_actor_context(session, actor.user_id)
            page = await self._content.get_planned_page_by_id(session, page_id=page_id)
            if not page:
                raise ResourceNotFound(f"Planned content page {page_id} was not found.")

            await self._projects.get_model(
                session,
                actor=actor,
                project_id=page.project_id,
                permission=PermissionCode.CONTENT_READ,
            )

            # Planned relationships
            all_rels = await self._linking.list_relationships(session, project_id=page.project_id)
            inbound_rels = [
                await self._to_relationship_detail(session, r)
                for r in all_rels
                if r.target_page_id == page.id
            ]
            outbound_rels = [
                await self._to_relationship_detail(session, r)
                for r in all_rels
                if r.source_page_id == page.id
            ]

            # Link opportunities
            all_opps = await self._linking.list_opportunities(session, project_id=page.project_id)
            recommended = [
                await self._to_opportunity_detail(session, o)
                for o in all_opps
                if o.source_page_id == page.id or o.target_page_id == page.id
            ]

            # Crawled links if existing_page_id is bound
            crawled_inbound: list[dict[str, object]] = []
            crawled_outbound: list[dict[str, object]] = []
            if page.existing_page_id:
                in_links = await self._linking.get_crawled_inbound_links(
                    session, target_page_id=page.existing_page_id
                )
                out_links = await self._linking.get_crawled_outbound_links(
                    session, source_page_id=page.existing_page_id
                )
                crawled_inbound = [
                    {
                        "id": str(link_item.id),
                        "source_page_id": str(link_item.source_page_id),
                        "anchor_text": link_item.anchor_text,
                    }
                    for link_item in in_links
                ]
                crawled_outbound = [
                    {
                        "id": str(link_item.id),
                        "target_url": link_item.target_url,
                        "anchor_text": link_item.anchor_text,
                    }
                    for link_item in out_links
                ]

            return InternalLinksSummary(
                page_id=page.id,
                crawled_inbound_links=crawled_inbound,
                crawled_outbound_links=crawled_outbound,
                planned_inbound_relationships=inbound_rels,
                planned_outbound_relationships=outbound_rels,
                recommended_opportunities=recommended,
            )

    async def detect_orphan_pages(
        self,
        session: AsyncSession,
        *,
        actor: AuthenticatedUser,
        project_id: UUID,
    ) -> OrphanPageList:
        """Detects pages with zero internal inbound link relationships."""
        async with session.begin():
            await set_actor_context(session, actor.user_id)
            project = await self._projects.get_model(
                session,
                actor=actor,
                project_id=project_id,
                permission=PermissionCode.CONTENT_READ,
            )

            pages = await self._content.list_planned_pages(session, project_id=project.id)
            relationships = await self._linking.list_relationships(session, project_id=project.id)

            inbound_counts: dict[UUID, int] = defaultdict(int)
            for r in relationships:
                inbound_counts[r.target_page_id] += 1

            orphans: list[OrphanPageDetail] = []
            for p in pages:
                count = inbound_counts[p.id]
                if count == 0:
                    orphans.append(
                        OrphanPageDetail(
                            page_id=p.id,
                            title=p.title,
                            url=p.url or f"/{p.slug}",
                            page_type=p.page_type,
                            inbound_links=0,
                            priority=p.priority,
                            primary_keyword=p.primary_keyword,
                        )
                    )

            return OrphanPageList(items=orphans, total=len(orphans))
