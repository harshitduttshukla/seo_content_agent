"""V3 card detail and the Bundle → Outline workflow (handoff §5.1, §6.1-6.2).

planned ──Build bundle──▶ bundled ──save first valid outline──▶ outlined

The bundle comes from the shared ContentAgentContextBuilder and is stored as a
``v3_context_bundle`` JobRun that ``ContentCard.bundle_ref`` points at. The
outline comes from the shared OutlineGenerator and is only a proposal until a
human saves it. Every state change goes through ``transition_content_card``.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

from app.ai.provider import AIProvider
from app.core.errors import ConflictError, DomainError, ResourceNotFound
from app.db.session import set_actor_context, transactional_session
from app.domains.ai.context import CardContextBundle
from app.domains.ai.context_builder import ContentAgentContextBuilder, bundle_hash
from app.domains.ai.service import get_ai_provider
from app.domains.audit.repository import AuditWriter
from app.domains.content_cards.hub_service import board_card, transition_content_card
from app.domains.content_cards.models import ContentCard
from app.domains.content_cards.outline import OutlineV3, ReferenceSet, validate_references
from app.domains.content_cards.outline_generation import (
    V3_OUTLINE_PROMPT_VERSION,
    OutlineGenerator,
)
from app.domains.content_cards.repository import ContentCardRepository
from app.domains.content_cards.schemas import BoardCard, BoardFilters, ContentCardState
from app.domains.content_cards.workflow_schemas import (
    BundleBuildRequest,
    BundleBuildResponse,
    BundleStatus,
    CardActions,
    CardCheck,
    CardDetail,
    ClaimOption,
    OutlineGenerateRequest,
    OutlineProposal,
    OutlineSaveRequest,
    OutlineSaveResponse,
)
from app.domains.job_runs.models import JobRun, JobRunStatus
from app.domains.projects.service import ProjectService
from app.security.principal import AuthenticatedUser, PermissionCode
from sqlalchemy.ext.asyncio import AsyncSession

BUNDLE_JOB_TYPE = "v3_context_bundle"
BUNDLE_BUILDER_VERSION = "v3.bundle.v1"
OUTLINE_JOB_TYPE = "v3_outline_generation"
CLAIM_OPTION_LIMIT = 200
_BUNDLE_STATES = {ContentCardState.PLANNED, ContentCardState.BUNDLED, ContentCardState.OUTLINED}
_OUTLINE_STATES = {ContentCardState.BUNDLED, ContentCardState.OUTLINED}


def _stored_bundle(run: JobRun) -> tuple[CardContextBundle, str] | None:
    output = run.output_data or {}
    content_hash = output.get("content_hash")
    raw = output.get("bundle")
    if not isinstance(content_hash, str) or not isinstance(raw, dict):
        return None
    return CardContextBundle.model_validate(raw), content_hash


def _stored_outline(card: ContentCard) -> tuple[OutlineV3 | None, bool]:
    if card.outline is None:
        return None, False
    try:
        return OutlineV3.model_validate(card.outline), False
    except ValueError:
        return None, True


def card_checks(
    bundle: BundleStatus | None,
    outline: OutlineV3 | None,
    refs: ReferenceSet,
) -> list[CardCheck]:
    """Only checks backed by stored data; no QA or gate results (later phases)."""
    checks = [
        CardCheck(
            key="bundle_exists",
            label="Bundle exists",
            status="pass" if bundle else "fail",
        ),
        CardCheck(
            key="bundle_current",
            label="Bundle is current",
            status="not_applicable" if bundle is None else "pass" if bundle.is_current else "fail",
            detail="" if bundle is None or bundle.is_current else "Sources changed; rebuild.",
        ),
        CardCheck(
            key="outline_exists", label="Outline exists", status="pass" if outline else "fail"
        ),
    ]
    if outline is None:
        return checks
    issues = validate_references(outline, refs)

    def check(key: str, label: str, failing: set[str], applicable: bool = True) -> CardCheck:
        if not applicable:
            return CardCheck(key=key, label=label, status="not_applicable")
        bad = [i for i in issues if i.code in failing]
        return CardCheck(
            key=key,
            label=label,
            status="fail" if bad else "pass",
            detail="; ".join(f"{i.section_id or ''} {i.message}".strip() for i in bad[:3]),
        )

    prompt_mode = outline.primary_mode == "prompt"
    checks += [
        CardCheck(key="sections_exist", label="Sections exist", status="pass"),
        check("claims_resolve", "Claim IDs resolve", {"UNKNOWN_CLAIM"}),
        check("demand_resolves", "Demand IDs resolve", {"UNKNOWN_DEMAND", "UNKNOWN_PROMPT"}),
        check("links_resolve", "Internal links resolve", {"UNKNOWN_PAGE", "URL_MISMATCH"}),
        check(
            "citable_statements",
            "Citable statement per section",
            {"MISSING_CITABLE_STATEMENT"},
            applicable=prompt_mode,
        ),
    ]
    return checks


class CardWorkflowService:
    def __init__(self, session: AsyncSession, provider: AIProvider | None = None) -> None:
        self._session = session
        self._repository = ContentCardRepository(session)
        self._projects = ProjectService()
        self._builder = ContentAgentContextBuilder(project_service=self._projects)
        self._audit = AuditWriter()
        self._provider = provider

    # ── shared steps ───────────────────────────────────────────────

    async def _authorize(
        self,
        organization_id: UUID,
        project_id: UUID,
        actor: AuthenticatedUser,
        *permissions: PermissionCode,
    ) -> datetime | None:
        project = None
        for permission in permissions:
            project = await self._projects.get_model(
                self._session, actor=actor, project_id=project_id, permission=permission
            )
        if project is None or project.organization_id != organization_id:
            raise ResourceNotFound("project")
        return project.plan_locked_at

    async def _card(
        self, organization_id: UUID, project_id: UUID, card_id: UUID, *, lock: bool = False
    ) -> ContentCard:
        load = self._repository.get_for_update if lock else self._repository.get_scoped
        card = await load(organization_id, project_id, card_id)
        if card is None:
            raise ResourceNotFound("content_card")
        return card

    async def _face(self, card: ContentCard, locked_at: datetime | None) -> BoardCard:
        rows = await self._repository.list_board_rows(
            card.organization_id, card.project_id, BoardFilters(), card_id=card.id
        )
        return board_card(rows[0], locked_at)

    async def _bundle_status(
        self, card: ContentCard, fresh_hash: str
    ) -> tuple[BundleStatus | None, CardContextBundle | None]:
        if card.bundle_ref is None:
            return None, None
        run = await self._repository.get_job_run_of_type(
            card.organization_id, card.project_id, card.bundle_ref, BUNDLE_JOB_TYPE
        )
        stored = _stored_bundle(run) if run is not None else None
        if run is None or stored is None:
            return None, None
        bundle, content_hash = stored
        return (
            BundleStatus(
                bundle_ref=run.id,
                content_hash=content_hash,
                built_at=run.created_at,
                is_current=content_hash == fresh_hash,
            ),
            bundle,
        )

    @staticmethod
    def _require_revision(card: ContentCard, revision: int) -> None:
        if card.revision != revision:
            raise ConflictError(
                "VERSION_CONFLICT",
                "Your version is out of date. Reload before saving.",
                details={"current_revision": card.revision},
            )

    # ── read ───────────────────────────────────────────────────────

    async def get_detail(
        self, organization_id: UUID, project_id: UUID, card_id: UUID, *, actor: AuthenticatedUser
    ) -> CardDetail:
        async with transactional_session(self._session):
            await set_actor_context(self._session, actor.user_id)
            locked_at = await self._authorize(
                organization_id, project_id, actor, PermissionCode.CONTENT_READ
            )
            card = await self._card(organization_id, project_id, card_id)
            context = await self._builder.build_card_bundle(self._session, card=card)
            status, _ = await self._bundle_status(card, bundle_hash(context))
            outline, unreadable = _stored_outline(card)
            refs = await self._project_refs(card, outline)
            options = await self._repository.list_current_claim_options(
                organization_id, project_id, CLAIM_OPTION_LIMIT
            )
            state = ContentCardState(card.state)
            return CardDetail(
                card=await self._face(card, locked_at),
                outline=outline,
                outline_unreadable=unreadable,
                bundle=status,
                context=context,
                claim_options=[
                    ClaimOption(
                        id=claim.id,
                        text=claim.text,
                        evidence=claim.evidence,
                        row=claim.row,
                        argument_id=claim.argument_id,
                        argument_name=name,
                        version=claim.version,
                        approved=claim.approved,
                    )
                    for claim, name in options
                ],
                checks=card_checks(status, outline, refs),
                actions=CardActions(
                    can_build_bundle=state in _BUNDLE_STATES,
                    can_generate_outline=state in _OUTLINE_STATES
                    and status is not None
                    and status.is_current,
                    can_save_outline=state in _OUTLINE_STATES,
                ),
            )

    async def _project_refs(self, card: ContentCard, outline: OutlineV3 | None) -> ReferenceSet:
        """Resolve an outline's references against the project (the save-time rule)."""
        if outline is None:
            return ReferenceSet(frozenset(), frozenset(), frozenset())
        claim_ids = {cid for s in outline.sections for cid in s.claim_ids}
        demand_ids = {s.target_demand_id for s in outline.sections if s.target_demand_id}
        if outline.prompt_target_id is not None:
            demand_ids.add(outline.prompt_target_id)
        page_ids = {link.page_id for s in outline.sections for link in s.planned_internal_links}
        claims, demand, prompts, pages = await self._repository.resolve_outline_refs(
            card.organization_id,
            card.project_id,
            claim_ids=claim_ids,
            demand_ids=demand_ids,
            page_ids=page_ids,
        )
        return ReferenceSet(frozenset(claims), frozenset(demand), frozenset(prompts), pages)

    # ── Build bundle ───────────────────────────────────────────────

    async def build_bundle(
        self,
        organization_id: UUID,
        project_id: UUID,
        card_id: UUID,
        payload: BundleBuildRequest,
        *,
        actor: AuthenticatedUser,
        request_id: str,
    ) -> BundleBuildResponse:
        """Create or reuse the card's bundle; a planned card becomes bundled."""
        async with transactional_session(self._session):
            await set_actor_context(self._session, actor.user_id)
            locked_at = await self._authorize(
                organization_id, project_id, actor, PermissionCode.CONTENT_WRITE
            )
            card = await self._card(organization_id, project_id, card_id, lock=True)
            self._require_revision(card, payload.revision)
            if ContentCardState(card.state) not in _BUNDLE_STATES:
                raise ConflictError(
                    "BUNDLE_NOT_ALLOWED",
                    f"A bundle cannot be built for a card in {card.state}.",
                    details={"state": card.state},
                )
            bundle = await self._builder.build_card_bundle(self._session, card=card)
            content_hash = bundle_hash(bundle)
            status, _ = await self._bundle_status(card, content_hash)
            reused = status is not None and status.is_current
            if not reused:
                now = datetime.now(UTC)
                run = JobRun(
                    id=uuid4(),
                    organization_id=organization_id,
                    project_id=project_id,
                    job_type=BUNDLE_JOB_TYPE,
                    prompt_version=BUNDLE_BUILDER_VERSION,
                    model="deterministic",
                    provider="internal",
                    status=JobRunStatus.COMPLETED,
                    triggered_by=str(actor.user_id),
                    entity_type="content_card",
                    entity_id=card.id,
                    input_data={"card_id": str(card.id), "card_revision": card.revision},
                    output_data={
                        "content_hash": content_hash,
                        "bundle": bundle.model_dump(mode="json"),
                    },
                    started_at=now,
                    completed_at=now,
                )
                self._repository.add_job_run(run)
                card.bundle_ref = run.id
            if card.state == ContentCardState.PLANNED:
                transition_content_card(card, ContentCardState.BUNDLED)
            elif not reused:
                card.revision += 1
            await self._session.flush()
            await self._session.refresh(card)
            self._audit.add(
                self._session,
                actor_user_id=actor.user_id,
                organization_id=organization_id,
                project_id=project_id,
                action="content_card.bundle_built",
                resource_type="content_card",
                resource_id=card.id,
                request_id=request_id,
                metadata={"bundle_ref": str(card.bundle_ref), "reused": reused},
            )
            status, _ = await self._bundle_status(card, content_hash)
            assert status is not None
            return BundleBuildResponse(
                card=await self._face(card, locked_at), bundle=status, reused=reused
            )

    # ── Generate outline (proposal only) ───────────────────────────

    async def generate_outline(
        self,
        organization_id: UUID,
        project_id: UUID,
        card_id: UUID,
        payload: OutlineGenerateRequest,
        *,
        actor: AuthenticatedUser,
    ) -> OutlineProposal:
        """Generate from the stored, current bundle. Records a JobRun; never edits the card."""
        async with transactional_session(self._session):
            await set_actor_context(self._session, actor.user_id)
            await self._authorize(
                organization_id,
                project_id,
                actor,
                PermissionCode.CONTENT_WRITE,
                PermissionCode.AI_USE,
            )
            card = await self._card(organization_id, project_id, card_id)
            if ContentCardState(card.state) not in _OUTLINE_STATES:
                raise ConflictError(
                    "BUNDLE_REQUIRED",
                    "Build the bundle before generating an outline.",
                    details={"state": card.state},
                )
            fresh = await self._builder.build_card_bundle(self._session, card=card)
            status, bundle = await self._bundle_status(card, bundle_hash(fresh))
            if status is None or bundle is None:
                raise ConflictError("BUNDLE_REQUIRED", "This card has no bundle yet.")
            if not status.is_current:
                raise ConflictError(
                    "BUNDLE_STALE", "The bundle is out of date. Rebuild it before generating."
                )

        # The model call runs outside any database transaction.
        provider = self._provider or get_ai_provider()
        started = datetime.now(UTC)
        result = await OutlineGenerator(provider).generate(bundle, model=payload.model)
        completed = datetime.now(UTC)

        run = JobRun(
            id=uuid4(),
            organization_id=organization_id,
            project_id=project_id,
            job_type=OUTLINE_JOB_TYPE,
            prompt_version=V3_OUTLINE_PROMPT_VERSION,
            model=result.model,
            provider=result.provider,
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
            total_tokens=result.input_tokens + result.output_tokens,
            status=JobRunStatus.COMPLETED if result.ok else JobRunStatus.FAILED,
            triggered_by=str(actor.user_id),
            entity_type="content_card",
            entity_id=card_id,
            input_data={
                "card_id": str(card_id),
                "bundle_ref": str(status.bundle_ref),
                "bundle_hash": status.content_hash,
            },
            output_data={
                "outline": result.outline.model_dump(mode="json") if result.outline else None,
                "attempts": [a.model_dump(mode="json") for a in result.attempts],
            },
            error=None if result.ok else "; ".join(i.code for i in result.issues)[:2000],
            started_at=started,
            completed_at=completed,
        )
        async with transactional_session(self._session):
            await set_actor_context(self._session, actor.user_id)
            self._repository.add_job_run(run)
            await self._session.flush()

        if result.error_code == "PROVIDER_ERROR":
            raise DomainError(
                "AI_PROVIDER_ERROR",
                "The AI provider failed. Try again.",
                502,
                details={"job_run_id": str(run.id)},
            )
        if result.outline is None:
            raise DomainError(
                "OUTLINE_INVALID",
                "The generated outline was rejected and not saved.",
                422,
                details={
                    "job_run_id": str(run.id),
                    "issues": [issue.model_dump(mode="json") for issue in result.issues],
                },
            )
        return OutlineProposal(
            outline=result.outline,
            job_run_id=run.id,
            prompt_version=V3_OUTLINE_PROMPT_VERSION,
            provider=result.provider,
            model=result.model,
            attempts=len(result.attempts),
            bundle_ref=status.bundle_ref,
        )

    # ── Save outline ───────────────────────────────────────────────

    async def save_outline(
        self,
        organization_id: UUID,
        project_id: UUID,
        card_id: UUID,
        payload: OutlineSaveRequest,
        *,
        actor: AuthenticatedUser,
        request_id: str,
    ) -> OutlineSaveResponse:
        """Validate against the project, store on the card; first save: bundled → outlined."""
        async with transactional_session(self._session):
            await set_actor_context(self._session, actor.user_id)
            locked_at = await self._authorize(
                organization_id, project_id, actor, PermissionCode.CONTENT_WRITE
            )
            card = await self._card(organization_id, project_id, card_id, lock=True)
            self._require_revision(card, payload.revision)
            if ContentCardState(card.state) not in _OUTLINE_STATES:
                raise ConflictError(
                    "OUTLINE_NOT_ALLOWED",
                    f"An outline cannot be saved for a card in {card.state}.",
                    details={"state": card.state},
                )
            issues = validate_references(
                payload.outline, await self._project_refs(card, payload.outline)
            )
            if issues:
                raise DomainError(
                    "OUTLINE_INVALID",
                    "The outline references data this project does not have.",
                    422,
                    details={"issues": [issue.model_dump(mode="json") for issue in issues]},
                )
            previous = card.state
            card.outline = payload.outline.model_dump(mode="json")
            # ContentCardClaim is the relational projection Strategy counts citations
            # from; the outline JSON stays the structural source of truth.
            added, removed = await self._repository.sync_card_claims(
                organization_id,
                project_id,
                card.id,
                {
                    claim_id
                    for section in payload.outline.sections
                    for claim_id in section.claim_ids
                },
            )
            if card.state == ContentCardState.BUNDLED:
                transition_content_card(card, ContentCardState.OUTLINED)
            else:
                card.revision += 1
            await self._session.flush()
            await self._session.refresh(card)
            self._audit.add(
                self._session,
                actor_user_id=actor.user_id,
                organization_id=organization_id,
                project_id=project_id,
                action="content_card.outline_saved",
                resource_type="content_card",
                resource_id=card.id,
                request_id=request_id,
                metadata={
                    "sections": len(payload.outline.sections),
                    "claims_added": sorted(str(c) for c in added),
                    "claims_removed": sorted(str(c) for c in removed),
                    "from": previous,
                    "to": card.state,
                },
            )
            return OutlineSaveResponse(
                card=await self._face(card, locked_at), outline=payload.outline
            )
