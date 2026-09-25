"""V3 card detail and the Bundle → Outline → G1 → Draft workflow (handoff §5.1-5.3, §6).

planned ──Build bundle──▶ bundled ──save first valid outline──▶ outlined
outlined ──G1 send back (feedback)──▶ outlined
outlined ──G1 approve──▶ drafting ──generate──▶ drafting + stored draft

The bundle comes from the shared ContentAgentContextBuilder and is stored as a
``v3_context_bundle`` JobRun that ``ContentCard.bundle_ref`` points at. The
outline comes from the shared OutlineGenerator and is only a proposal until a
human saves it. G1 is a human decision recorded as a ``v3_gate_decision`` JobRun
plus an audit event. Drafts come from the shared DraftGenerator against the
stored, current bundle and the approved outline. Every state change goes
through ``transition_content_card``.
"""

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID, uuid4

from app.ai.provider import AIProvider
from app.core.errors import ConflictError, DomainError, PermissionDenied, ResourceNotFound
from app.db.session import set_actor_context, transactional_session
from app.domains.ai.context import BundleClaim, CardContextBundle
from app.domains.ai.context_builder import ContentAgentContextBuilder, bundle_hash
from app.domains.ai.service import generation_model_options, get_ai_provider_for_model
from app.domains.audit.repository import AuditWriter
from app.domains.canvas.schemas import WorkspaceConfig
from app.domains.content_cards.draft import DraftInput, StoredDraft, unresolved_needs
from app.domains.content_cards.draft_generation import V3_DRAFT_PROMPT_VERSION, DraftGenerator
from app.domains.content_cards.hub_service import board_card, transition_content_card
from app.domains.content_cards.models import ContentCard
from app.domains.content_cards.outline import (
    OutlineIssue,
    OutlineV3,
    ReferenceSet,
    validate_references,
)
from app.domains.content_cards.outline_generation import (
    V3_OUTLINE_PROMPT_VERSION,
    OutlineGenerator,
)
from app.domains.content_cards.production_state import (
    QA_STATES,
    REGENERATE_STATES,
    g2_blockers,
    g2_status,
    qa_is_current,
    stored_qa_report,
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
    DraftGenerateRequest,
    DraftGenerateResponse,
    DraftRunStatus,
    G1ApproveRequest,
    G1DecisionResponse,
    G1Review,
    G1SendBackRequest,
    G1Status,
    G2Review,
    GateDecision,
    GenerationModel,
    GenerationOptions,
    OutlineGenerateRequest,
    OutlineProposal,
    OutlineSaveRequest,
    OutlineSaveResponse,
    QAState,
)
from app.domains.job_runs.models import JobRun, JobRunStatus
from app.domains.projects.models import Project
from app.domains.projects.service import ProjectService
from app.security.principal import AuthenticatedUser, PermissionCode
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

BUNDLE_JOB_TYPE = "v3_context_bundle"
BUNDLE_BUILDER_VERSION = "v3.bundle.v1"
OUTLINE_JOB_TYPE = "v3_outline_generation"
GATE_JOB_TYPE = "v3_gate_decision"
G1_GATE_VERSION = "v3.gate.g1.v1"
DRAFT_JOB_TYPE = "v3_draft_generation"
CLAIM_OPTION_LIMIT = 200
REVIEW_HISTORY_LIMIT = 20
# A bundle may be rebuilt after G1: a stale bundle blocks drafting until it is.
_BUNDLE_STATES = {
    ContentCardState.PLANNED,
    ContentCardState.BUNDLED,
    ContentCardState.OUTLINED,
    ContentCardState.DRAFTING,
}
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
    needs = [f"{s.section_id}: {text}" for s in outline.sections for text in s.needs_claim]
    checks.append(
        CardCheck(
            key="claims_needed",
            label="No unresolved claim needs",
            status="fail" if needs else "pass",
            detail="; ".join(needs[:3]),
        )
    )
    return checks


def g1_ready(outline: OutlineV3 | None, checks: list[CardCheck]) -> bool:
    """G1 may pass only on a stored, valid outline with every check passing."""
    return outline is not None and all(check.status != "fail" for check in checks)


def is_named_reviewer(config: WorkspaceConfig, gate: str, actor: AuthenticatedUser) -> bool:
    """``workspace_config.reviewers[gate]`` narrows who may decide; empty means anyone
    holding content.review. Entries are user ids or emails."""
    named = {entry.strip().casefold() for entry in config.reviewers.get(gate, []) if entry.strip()}
    return not named or {str(actor.user_id), actor.email.casefold()} & named != set()


def _gate_decision(run: JobRun, names: dict[UUID, str]) -> GateDecision:
    data = run.input_data or {}
    output = run.output_data or {}
    reviewer = UUID(run.triggered_by) if _is_uuid(run.triggered_by) else None
    return GateDecision.model_validate(
        {
            "id": run.id,
            "gate": data.get("gate", "G1"),
            "action": data.get("action"),
            "reviewer_id": reviewer,
            "reviewer_name": names.get(reviewer) if reviewer else None,
            "decided_at": run.created_at,
            "card_revision": data.get("card_revision"),
            "reason": data.get("reason"),
            "feedback": output.get("feedback"),
        }
    )


def _is_uuid(value: str) -> bool:
    try:
        UUID(value)
    except ValueError:
        return False
    return True


def _stored_draft(card: ContentCard) -> tuple[StoredDraft | None, bool]:
    if card.draft is None:
        return None, False
    try:
        return StoredDraft.model_validate(card.draft), False
    except ValidationError:
        return None, True


def _draft_run_status(run: JobRun) -> DraftRunStatus:
    output = run.output_data or {}
    attempts = output.get("attempts")
    issues = output.get("issues")
    return DraftRunStatus(
        job_run_id=run.id,
        status=run.status,
        prompt_version=run.prompt_version,
        provider=run.provider,
        model=run.model,
        attempts=len(attempts) if isinstance(attempts, list) else 0,
        error=run.error,
        issues=[OutlineIssue.model_validate(i) for i in issues] if isinstance(issues, list) else [],
        created_at=run.created_at,
        stored=output.get("stored") is True,
    )


@dataclass(frozen=True, slots=True)
class CardEvaluation:
    context: CardContextBundle
    status: BundleStatus | None
    stored_bundle: CardContextBundle | None
    outline: OutlineV3 | None
    outline_unreadable: bool
    checks: list[CardCheck]


class CardWorkflowService:
    def __init__(self, session: AsyncSession, provider: AIProvider | None = None) -> None:
        self._session = session
        self._repository = ContentCardRepository(session)
        self._projects = ProjectService()
        self._builder = ContentAgentContextBuilder(project_service=self._projects)
        self._audit = AuditWriter()
        self._provider = provider

    # ── shared steps ───────────────────────────────────────────────

    async def _authorized_project(
        self,
        organization_id: UUID,
        project_id: UUID,
        actor: AuthenticatedUser,
        *permissions: PermissionCode,
    ) -> Project:
        project = None
        for permission in permissions:
            project = await self._projects.get_model(
                self._session, actor=actor, project_id=project_id, permission=permission
            )
        if project is None or project.organization_id != organization_id:
            raise ResourceNotFound("project")
        return project

    async def _authorize(
        self,
        organization_id: UUID,
        project_id: UUID,
        actor: AuthenticatedUser,
        *permissions: PermissionCode,
    ) -> datetime | None:
        project = await self._authorized_project(organization_id, project_id, actor, *permissions)
        return project.plan_locked_at

    async def _authorize_gate(
        self, organization_id: UUID, project_id: UUID, actor: AuthenticatedUser, gate: str
    ) -> Project:
        """content.review, then the workspace's named reviewers for ``gate`` when configured."""
        project = await self._authorized_project(
            organization_id, project_id, actor, PermissionCode.CONTENT_REVIEW
        )
        config = WorkspaceConfig.model_validate(project.workspace_config or {})
        if not is_named_reviewer(config, gate, actor):
            raise PermissionDenied(f"You are not a {gate} reviewer for this project.")
        return project

    async def _authorize_g1(
        self, organization_id: UUID, project_id: UUID, actor: AuthenticatedUser
    ) -> Project:
        return await self._authorize_gate(organization_id, project_id, actor, "G1")

    async def _may_review_g1(self, project: Project, actor: AuthenticatedUser) -> bool:
        return await self._may_review(project, actor, "G1")

    async def _may_review(self, project: Project, actor: AuthenticatedUser, gate: str) -> bool:
        try:
            await self._projects.get_model(
                self._session,
                actor=actor,
                project_id=project.id,
                permission=PermissionCode.CONTENT_REVIEW,
            )
        except PermissionDenied:
            return False
        config = WorkspaceConfig.model_validate(project.workspace_config or {})
        return is_named_reviewer(config, gate, actor)

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
    def _require_allowed_model(model: str | None) -> None:
        """Only models offered for the configured provider may be requested."""
        if model is None:
            return
        _, options = generation_model_options()
        models = [option.model for option in options]
        if model not in models:
            raise DomainError(
                "MODEL_NOT_ALLOWED",
                "That model is not available for generation.",
                422,
                details={"model": model, "allowed": models},
            )

    @staticmethod
    def _require_revision(card: ContentCard, revision: int) -> None:
        if card.revision != revision:
            raise ConflictError(
                "VERSION_CONFLICT",
                "Your version is out of date. Reload before saving.",
                details={"current_revision": card.revision},
            )

    async def _evaluate(self, card: ContentCard) -> CardEvaluation:
        """The card's current context, stored bundle, outline and checks: one definition
        shared by the detail view, G1 and drafting."""
        context = await self._builder.build_card_bundle(self._session, card=card)
        status, stored = await self._bundle_status(card, bundle_hash(context))
        outline, unreadable = _stored_outline(card)
        refs = await self._project_refs(card, outline)
        return CardEvaluation(
            context=context,
            status=status,
            stored_bundle=stored,
            outline=outline,
            outline_unreadable=unreadable,
            checks=card_checks(status, outline, refs),
        )

    async def _gate_history(self, card: ContentCard) -> list[GateDecision]:
        runs = await self._repository.list_card_job_runs(
            card.organization_id, card.project_id, card.id, GATE_JOB_TYPE, REVIEW_HISTORY_LIMIT
        )
        names = await self._repository.get_user_names(
            {UUID(r.triggered_by) for r in runs if _is_uuid(r.triggered_by)}
        )
        return [_gate_decision(run, names) for run in runs]

    @staticmethod
    def _g1_status(card: ContentCard, ready: bool, last: GateDecision | None) -> G1Status:
        state = ContentCardState(card.state)
        if state in (ContentCardState.BACKLOG, ContentCardState.PLANNED, ContentCardState.BUNDLED):
            return "not_ready"
        if state != ContentCardState.OUTLINED:
            return "approved"
        # Sent back and not touched since: the feedback is still the open item.
        if (
            last is not None
            and last.action == "send_back"
            and card.revision == last.card_revision + 1
        ):
            return "sent_back"
        return "awaiting_review" if ready else "not_ready"

    # ── read ───────────────────────────────────────────────────────

    async def get_detail(
        self, organization_id: UUID, project_id: UUID, card_id: UUID, *, actor: AuthenticatedUser
    ) -> CardDetail:
        async with transactional_session(self._session):
            await set_actor_context(self._session, actor.user_id)
            project = await self._authorized_project(
                organization_id, project_id, actor, PermissionCode.CONTENT_READ
            )
            card = await self._card(organization_id, project_id, card_id)
            evaluation = await self._evaluate(card)
            context, status, outline = evaluation.context, evaluation.status, evaluation.outline
            checks = evaluation.checks
            options = await self._repository.list_current_claim_options(
                organization_id, project_id, CLAIM_OPTION_LIMIT
            )
            gate_history = await self._gate_history(card)
            history = [d for d in gate_history if d.gate == "G1"]
            g2_history = [d for d in gate_history if d.gate == "G2"]
            last = history[0] if history else None
            ready = g1_ready(outline, checks)
            can_review = await self._may_review_g1(project, actor)
            can_review_g2 = await self._may_review(project, actor, "G2")
            config = WorkspaceConfig.model_validate(project.workspace_config or {})
            draft, draft_unreadable = _stored_draft(card)
            default_option, model_options = generation_model_options()
            draft_runs = await self._repository.list_card_job_runs(
                organization_id, project_id, card.id, DRAFT_JOB_TYPE, 1
            )
            state = ContentCardState(card.state)
            bundle_current = status is not None and status.is_current
            report = stored_qa_report(card)
            qa_current = qa_is_current(card, report, draft)
            blockers = g2_blockers(
                card,
                report,
                draft,
                status,
                warnings_require_dismissal=config.soft_warnings_require_dismissal,
            )
            pending = report.undismissed_warnings() if report and qa_current else []
            return CardDetail(
                card=await self._face(card, project.plan_locked_at),
                outline=outline,
                outline_unreadable=evaluation.outline_unreadable,
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
                checks=checks,
                actions=CardActions(
                    can_build_bundle=state in _BUNDLE_STATES,
                    can_generate_outline=state in _OUTLINE_STATES and bundle_current,
                    can_save_outline=state in _OUTLINE_STATES,
                    can_review_g1=state == ContentCardState.OUTLINED and ready and can_review,
                    can_generate_draft=state == ContentCardState.DRAFTING
                    and bundle_current
                    and outline is not None,
                    can_run_qa=state in QA_STATES and draft is not None and bundle_current,
                    can_repair=state == ContentCardState.QA_FAILED
                    and qa_current
                    and report is not None
                    and report.status == "failed"
                    and bundle_current,
                    can_regenerate_section=state in REGENERATE_STATES
                    and draft is not None
                    and bundle_current,
                    can_review_g2=state == ContentCardState.QA_PASSED
                    and not blockers
                    and can_review_g2,
                    can_dismiss_warnings=state == ContentCardState.QA_PASSED
                    and qa_current
                    and can_review_g2,
                ),
                review=G1Review(
                    status=self._g1_status(card, ready, last),
                    ready=ready,
                    can_review=can_review,
                    reviewers_restricted=bool(config.reviewers.get("G1")),
                    last_decision=last,
                    history=history,
                ),
                qa=QAState(report=report, stale=report is not None and not qa_current),
                g2=G2Review(
                    status=g2_status(card, gate_history),
                    ready=not blockers,
                    blockers=blockers,
                    can_review=can_review_g2,
                    reviewers_restricted=bool(config.reviewers.get("G2")),
                    warnings_require_dismissal=config.soft_warnings_require_dismissal,
                    pending_warning_ids=[f.id for f in pending],
                    last_decision=g2_history[0] if g2_history else None,
                    history=g2_history,
                ),
                draft=draft,
                draft_unreadable=draft_unreadable,
                last_draft_run=_draft_run_status(draft_runs[0]) if draft_runs else None,
                generation=GenerationOptions(
                    default_model=default_option.model if default_option else None,
                    options=[
                        GenerationModel(provider=o.provider, model=o.model) for o in model_options
                    ],
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
        self._require_allowed_model(payload.model)
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
        provider = self._provider or get_ai_provider_for_model(payload.model)
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
            # from; the outline JSON stays the structural source of truth. Saving only
            # adds citations: manual Strategy citations are never removed here.
            added = await self._repository.add_card_claims(
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
                    "from": previous,
                    "to": card.state,
                },
            )
            return OutlineSaveResponse(
                card=await self._face(card, locked_at), outline=payload.outline
            )

    # ── G1 outline review ──────────────────────────────────────────

    def _gate_run(
        self,
        card: ContentCard,
        actor: AuthenticatedUser,
        *,
        action: str,
        revision: int,
        reason: str | None = None,
        feedback: str | None = None,
    ) -> JobRun:
        now = datetime.now(UTC)
        run = JobRun(
            id=uuid4(),
            organization_id=card.organization_id,
            project_id=card.project_id,
            job_type=GATE_JOB_TYPE,
            prompt_version=G1_GATE_VERSION,
            model="human",
            provider="internal",
            status=JobRunStatus.COMPLETED,
            triggered_by=str(actor.user_id),
            entity_type="content_card",
            entity_id=card.id,
            input_data={
                "gate": "G1",
                "action": action,
                "card_revision": revision,
                "reason": reason,
                "outline": card.outline,
            },
            output_data={"feedback": feedback},
            started_at=now,
            completed_at=now,
            created_at=now,
            updated_at=now,
        )
        self._repository.add_job_run(run)
        return run

    async def approve_g1(
        self,
        organization_id: UUID,
        project_id: UUID,
        card_id: UUID,
        payload: G1ApproveRequest,
        *,
        actor: AuthenticatedUser,
        request_id: str,
    ) -> G1DecisionResponse:
        """A reviewer passes G1 on a ready outline: outlined → drafting. Drafting is separate."""
        async with transactional_session(self._session):
            await set_actor_context(self._session, actor.user_id)
            project = await self._authorize_g1(organization_id, project_id, actor)
            card = await self._card(organization_id, project_id, card_id, lock=True)
            self._require_revision(card, payload.revision)
            if ContentCardState(card.state) != ContentCardState.OUTLINED:
                raise ConflictError(
                    "G1_NOT_ALLOWED",
                    f"G1 applies to outlined cards; this card is {card.state}.",
                    details={"state": card.state},
                )
            evaluation = await self._evaluate(card)
            checks = evaluation.checks
            if not g1_ready(evaluation.outline, checks):
                raise ConflictError(
                    "G1_CHECKS_FAILED",
                    "The outline cannot pass G1 until every check passes.",
                    details={
                        "checks": [c.model_dump() for c in checks if c.status == "fail"],
                    },
                )
            run = self._gate_run(card, actor, action="approve", revision=card.revision)
            transition_content_card(card, ContentCardState.DRAFTING)
            await self._session.flush()
            await self._session.refresh(card)
            self._audit.add(
                self._session,
                actor_user_id=actor.user_id,
                organization_id=organization_id,
                project_id=project_id,
                action="content_card.g1_approved",
                resource_type="content_card",
                resource_id=card.id,
                request_id=request_id,
                metadata={
                    "job_run_id": str(run.id),
                    "card_revision": payload.revision,
                    "from": ContentCardState.OUTLINED.value,
                    "to": card.state,
                },
            )
            names = await self._repository.get_user_names({actor.user_id})
            return G1DecisionResponse(
                card=await self._face(card, project.plan_locked_at),
                decision=_gate_decision(run, names),
            )

    async def send_back_g1(
        self,
        organization_id: UUID,
        project_id: UUID,
        card_id: UUID,
        payload: G1SendBackRequest,
        *,
        actor: AuthenticatedUser,
        request_id: str,
    ) -> G1DecisionResponse:
        """A reviewer returns the outline with typed feedback; the card stays outlined."""
        async with transactional_session(self._session):
            await set_actor_context(self._session, actor.user_id)
            project = await self._authorize_g1(organization_id, project_id, actor)
            card = await self._card(organization_id, project_id, card_id, lock=True)
            self._require_revision(card, payload.revision)
            if ContentCardState(card.state) != ContentCardState.OUTLINED:
                raise ConflictError(
                    "G1_NOT_ALLOWED",
                    f"G1 applies to outlined cards; this card is {card.state}.",
                    details={"state": card.state},
                )
            run = self._gate_run(
                card,
                actor,
                action="send_back",
                revision=card.revision,
                reason=payload.reason,
                feedback=payload.feedback,
            )
            # Stays outlined (handoff §5.2); the revision moves so a stale approve 409s.
            card.revision += 1
            await self._session.flush()
            await self._session.refresh(card)
            self._audit.add(
                self._session,
                actor_user_id=actor.user_id,
                organization_id=organization_id,
                project_id=project_id,
                action="content_card.g1_sent_back",
                resource_type="content_card",
                resource_id=card.id,
                request_id=request_id,
                metadata={
                    "job_run_id": str(run.id),
                    "card_revision": payload.revision,
                    "reason": payload.reason,
                },
            )
            names = await self._repository.get_user_names({actor.user_id})
            return G1DecisionResponse(
                card=await self._face(card, project.plan_locked_at),
                decision=_gate_decision(run, names),
            )

    # ── Draft ──────────────────────────────────────────────────────

    async def resolve_draft_input(
        self, card: ContentCard, bundle: CardContextBundle
    ) -> tuple[DraftInput, list[OutlineIssue]]:
        """The approved outline resolved against the project, plus any references that
        no longer resolve (e.g. a cited claim superseded after G1). Shared with QA and
        the Harness; callers decide whether stale references block or are findings."""
        outline, unreadable = _stored_outline(card)
        if outline is None:
            raise ConflictError(
                "OUTLINE_REQUIRED",
                "The stored outline is unreadable." if unreadable else "This card has no outline.",
            )
        refs = await self._project_refs(card, outline)
        issues = validate_references(outline, refs)
        claims = await self._repository.get_current_claims(
            card.organization_id,
            card.project_id,
            {cid for section in outline.sections for cid in section.claim_ids},
        )
        source = DraftInput(
            bundle=bundle,
            outline=outline,
            claims=tuple(
                BundleClaim(
                    id=claim.id,
                    text=claim.text,
                    evidence=claim.evidence,
                    row=claim.row,
                    argument_id=claim.argument_id,
                    version=claim.version,
                )
                for claim in claims
            ),
            pages=dict(refs.pages),
        )
        return source, issues

    async def draft_input(self, card: ContentCard, bundle: CardContextBundle) -> DraftInput:
        """Resolve the approved outline for drafting; raises when it no longer resolves."""
        source, issues = await self.resolve_draft_input(card, bundle)
        if issues:
            raise ConflictError(
                "OUTLINE_REFERENCES_STALE",
                "The approved outline references data that is no longer current.",
                details={"issues": [issue.model_dump(mode="json") for issue in issues]},
            )
        return source

    async def generate_draft(
        self,
        organization_id: UUID,
        project_id: UUID,
        card_id: UUID,
        payload: DraftGenerateRequest,
        *,
        actor: AuthenticatedUser,
        request_id: str,
    ) -> DraftGenerateResponse:
        """Draft a G1-approved card from its stored, current bundle and approved outline.

        The card stays ``drafting``. Only a validated draft is stored, and only when
        the card did not change during generation; every attempt is a JobRun.
        """
        self._require_allowed_model(payload.model)
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
            self._require_revision(card, payload.revision)
            if ContentCardState(card.state) != ContentCardState.DRAFTING:
                raise ConflictError(
                    "G1_APPROVAL_REQUIRED",
                    "Drafting starts after the outline passes G1.",
                    details={"state": card.state},
                )
            fresh = await self._builder.build_card_bundle(self._session, card=card)
            status, bundle = await self._bundle_status(card, bundle_hash(fresh))
            if status is None or bundle is None:
                raise ConflictError("BUNDLE_REQUIRED", "This card has no bundle yet.")
            if not status.is_current:
                raise ConflictError(
                    "BUNDLE_STALE", "The bundle is out of date. Rebuild it before drafting."
                )
            source = await self.draft_input(card, bundle)

        # The model call runs outside any database transaction.
        provider = self._provider or get_ai_provider_for_model(payload.model)
        started = datetime.now(UTC)
        result = await DraftGenerator(provider).generate(source, model=payload.model)
        completed = datetime.now(UTC)

        conflict = False
        stored: StoredDraft | None = None
        async with transactional_session(self._session):
            await set_actor_context(self._session, actor.user_id)
            locked_at = await self._authorize(
                organization_id,
                project_id,
                actor,
                PermissionCode.CONTENT_WRITE,
                PermissionCode.AI_USE,
            )
            card = await self._card(organization_id, project_id, card_id, lock=True)
            conflict = (
                card.revision != payload.revision
                or ContentCardState(card.state) != ContentCardState.DRAFTING
            )
            run_id = uuid4()
            if result.draft is not None and not conflict:
                previous, _ = _stored_draft(card)
                stored = StoredDraft(
                    version=(previous.version if previous else 0) + 1,
                    draft=result.draft,
                    unresolved=unresolved_needs(result.draft),
                    job_run_id=run_id,
                    prompt_version=V3_DRAFT_PROMPT_VERSION,
                    provider=result.provider,
                    model=result.model,
                    bundle_ref=status.bundle_ref,
                    bundle_hash=status.content_hash,
                    source_revision=payload.revision,
                    generated_at=completed,
                    generated_by=actor.user_id,
                )
            error = (
                None
                if result.ok
                else "; ".join(i.code for i in result.issues)[:2000] or result.error_code
            )
            if result.ok and conflict:
                error = "VERSION_CONFLICT: the card changed during generation; not stored"
            run = JobRun(
                id=run_id,
                organization_id=organization_id,
                project_id=project_id,
                job_type=DRAFT_JOB_TYPE,
                prompt_version=V3_DRAFT_PROMPT_VERSION,
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
                    "card_revision": payload.revision,
                    "bundle_ref": str(status.bundle_ref),
                    "bundle_hash": status.content_hash,
                    "outline": source.outline.model_dump(mode="json"),
                    "claim_ids": sorted(str(c.id) for c in source.claims),
                },
                output_data={
                    "draft": result.draft.model_dump(mode="json") if result.draft else None,
                    "attempts": [a.model_dump(mode="json") for a in result.attempts],
                    "issues": [i.model_dump(mode="json") for i in result.issues],
                    "stored": stored is not None,
                },
                error=error,
                started_at=started,
                completed_at=completed,
            )
            self._repository.add_job_run(run)
            if stored is not None:
                card.draft = stored.model_dump(mode="json")
                card.revision += 1
            await self._session.flush()
            if stored is not None:
                await self._session.refresh(card)
                self._audit.add(
                    self._session,
                    actor_user_id=actor.user_id,
                    organization_id=organization_id,
                    project_id=project_id,
                    action="content_card.draft_generated",
                    resource_type="content_card",
                    resource_id=card.id,
                    request_id=request_id,
                    metadata={
                        "job_run_id": str(run.id),
                        "version": stored.version,
                        "sections": len(stored.draft.sections),
                        "unresolved": len(stored.unresolved),
                    },
                )
                face = await self._face(card, locked_at)

        if result.error_code == "PROVIDER_ERROR":
            raise DomainError(
                "AI_PROVIDER_ERROR",
                "The AI provider failed. Try again.",
                502,
                details={"job_run_id": str(run.id)},
            )
        if result.draft is None:
            raise DomainError(
                "DRAFT_INVALID",
                "The generated draft was rejected and not saved.",
                422,
                details={
                    "job_run_id": str(run.id),
                    "issues": [issue.model_dump(mode="json") for issue in result.issues],
                },
            )
        if conflict or stored is None:
            raise ConflictError(
                "VERSION_CONFLICT",
                "The card changed while the draft was generated. Reload and try again.",
                details={"job_run_id": str(run.id)},
            )
        return DraftGenerateResponse(card=face, draft=stored)
