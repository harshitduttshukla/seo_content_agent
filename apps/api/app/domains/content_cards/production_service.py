"""V3 Production quality workflow on the ContentCard (handoff §5.2, §6.4, §6.8 calls 3-5).

drafting / qa_failed ──QA──▶ qa_passed | qa_failed
qa_failed ──repair──▶ drafting            (new draft version; QA must run again)
drafting / qa_failed / qa_passed ──regenerate section──▶ drafting
qa_passed ──G2 approve──▶ approved        (never published here)
qa_passed ──G2 send back (feedback)──▶ drafting

Every model call runs outside a transaction and is recorded as a JobRun. Results are
persisted only after validation, under a row lock, when the card revision is still
the one the caller saw. State changes go through ``transition_content_card``.
"""

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal
from uuid import UUID, uuid4

from app.ai.provider import AIProvider
from app.core.errors import ConflictError, DomainError, ResourceNotFound
from app.db.session import set_actor_context, transactional_session
from app.domains.ai.context_builder import bundle_hash
from app.domains.ai.service import get_ai_provider_for_model
from app.domains.canvas.schemas import WorkspaceConfig
from app.domains.content_cards.draft import DraftInput, DraftV3, StoredDraft, unresolved_needs
from app.domains.content_cards.draft_revision import DraftReviser, RevisionResult
from app.domains.content_cards.hub_service import transition_content_card
from app.domains.content_cards.models import ContentCard
from app.domains.content_cards.outline import OutlineIssue
from app.domains.content_cards.production_state import (
    QA_STATES,
    REGENERATE_STATES,
    g2_blockers,
    qa_is_current,
    stored_qa_report,
)
from app.domains.content_cards.qa import (
    V3_QA_VERSION,
    QAExtractor,
    QAFinding,
    QAReport,
    WarningDismissal,
    deterministic_findings,
    report_status,
)
from app.domains.content_cards.schemas import ContentCardState
from app.domains.content_cards.workflow_schemas import (
    BundleStatus,
    DraftRevisionResponse,
    G1DecisionResponse,
    G2ApproveRequest,
    G2SendBackRequest,
    QARunRequest,
    QARunResponse,
    RepairRequest,
    SectionRegenerateRequest,
    WarningDismissRequest,
    WarningDismissResponse,
)
from app.domains.content_cards.workflow_service import (
    CardWorkflowService,
    _gate_decision,
    _stored_draft,
)
from app.domains.job_runs.models import JobRun, JobRunStatus
from app.domains.projects.models import Project
from app.security.principal import AuthenticatedUser, PermissionCode
from sqlalchemy.ext.asyncio import AsyncSession

QA_JOB_TYPE = "v3_qa"
REPAIR_JOB_TYPE = "v3_draft_repair"
SECTION_JOB_TYPE = "v3_section_regeneration"
RevisionType = Literal["repair", "section_regeneration"]


@dataclass(frozen=True, slots=True)
class ProductionContext:
    """What QA, repair and regeneration work from, resolved once per request."""

    card: ContentCard
    project: Project
    status: BundleStatus
    source: DraftInput
    reference_issues: list[OutlineIssue]
    stored: StoredDraft


def _word_budget(card: ContentCard, config: WorkspaceConfig) -> tuple[int | None, bool]:
    if card.word_budget:
        return card.word_budget, True
    default = getattr(config.word_budgets, card.kind, None)
    return (default, False) if isinstance(default, int) and default > 0 else (None, False)


def qa_deterministic(
    card: ContentCard,
    project: Project,
    stored: StoredDraft,
    source: DraftInput,
    reference_issues: list[OutlineIssue],
) -> list[QAFinding]:
    """The deterministic QA layer with the project's rules; shared with the Harness."""
    config = WorkspaceConfig.model_validate(project.workspace_config or {})
    budget, explicit = _word_budget(card, config)
    return deterministic_findings(
        stored,
        source,
        reference_issues=reference_issues,
        banned_words=[*source.bundle.rules.brand.words_to_avoid, *config.banned_words],
        word_budget=budget,
        budget_is_explicit=explicit,
    )


class ProductionService(CardWorkflowService):
    def __init__(self, session: AsyncSession, provider: AIProvider | None = None) -> None:
        super().__init__(session, provider=provider)

    def _ai(self, model: str | None) -> AIProvider:
        return self._provider or get_ai_provider_for_model(model)

    async def _context(
        self,
        organization_id: UUID,
        project_id: UUID,
        card_id: UUID,
        actor: AuthenticatedUser,
        *permissions: PermissionCode,
    ) -> ProductionContext:
        project = await self._authorized_project(organization_id, project_id, actor, *permissions)
        card = await self._card(organization_id, project_id, card_id)
        fresh = await self._builder.build_card_bundle(self._session, card=card)
        status, bundle = await self._bundle_status(card, bundle_hash(fresh))
        if status is None or bundle is None:
            raise ConflictError("BUNDLE_REQUIRED", "This card has no bundle yet.")
        if not status.is_current:
            raise ConflictError(
                "BUNDLE_STALE", "The bundle is out of date. Rebuild it before continuing."
            )
        stored, unreadable = _stored_draft(card)
        if stored is None:
            raise ConflictError(
                "DRAFT_REQUIRED",
                "The stored draft is unreadable." if unreadable else "This card has no draft yet.",
            )
        source, issues = await self.resolve_draft_input(card, bundle)
        return ProductionContext(card, project, status, source, issues, stored)

    def _job(
        self,
        card: ContentCard,
        actor: AuthenticatedUser,
        job_type: str,
        prompt_version: str,
        *,
        provider: str,
        model: str,
        tokens: tuple[int, int] = (0, 0),
        ok: bool,
        input_data: dict[str, object],
        output_data: dict[str, object],
        error: str | None,
        started: datetime,
        completed: datetime,
        run_id: UUID | None = None,
    ) -> JobRun:
        run = JobRun(
            id=run_id or uuid4(),
            organization_id=card.organization_id,
            project_id=card.project_id,
            job_type=job_type,
            prompt_version=prompt_version,
            model=model,
            provider=provider,
            input_tokens=tokens[0],
            output_tokens=tokens[1],
            total_tokens=sum(tokens),
            status=JobRunStatus.COMPLETED if ok else JobRunStatus.FAILED,
            triggered_by=str(actor.user_id),
            entity_type="content_card",
            entity_id=card.id,
            input_data=input_data,
            output_data=output_data,
            error=error[:2000] if error else None,
            started_at=started,
            completed_at=completed,
        )
        self._repository.add_job_run(run)
        return run

    # ── QA ─────────────────────────────────────────────────────────

    async def run_qa(
        self,
        organization_id: UUID,
        project_id: UUID,
        card_id: UUID,
        payload: QARunRequest,
        *,
        actor: AuthenticatedUser,
        request_id: str,
    ) -> QARunResponse:
        """Deterministic checks, then (only if they pass) model extraction; store the report
        and move drafting/qa_failed → qa_passed | qa_failed."""
        self._require_allowed_model(payload.model)
        async with transactional_session(self._session):
            await set_actor_context(self._session, actor.user_id)
            ctx = await self._context(
                organization_id,
                project_id,
                card_id,
                actor,
                PermissionCode.CONTENT_WRITE,
                PermissionCode.AI_USE,
            )
            self._require_revision(ctx.card, payload.revision)
            if ContentCardState(ctx.card.state) not in QA_STATES:
                raise ConflictError(
                    "QA_NOT_ALLOWED",
                    f"QA runs on drafting or qa_failed cards; this card is {ctx.card.state}.",
                    details={"state": ctx.card.state},
                )
            findings = qa_deterministic(
                ctx.card, ctx.project, ctx.stored, ctx.source, ctx.reference_issues
            )

        started = datetime.now(UTC)
        blocking = any(f.severity == "error" for f in findings)
        model_result = None
        if not blocking:  # the model is only asked what code could not settle
            model_result = await QAExtractor(self._ai(payload.model)).extract(
                ctx.stored, ctx.source, model=payload.model
            )
        completed = datetime.now(UTC)
        model_failed = model_result is not None and not model_result.ok
        if model_result is not None and model_result.findings:
            findings = [*findings, *model_result.findings]

        async with transactional_session(self._session):
            await set_actor_context(self._session, actor.user_id)
            await self._authorize(
                organization_id,
                project_id,
                actor,
                PermissionCode.CONTENT_WRITE,
                PermissionCode.AI_USE,
            )
            card = await self._card(organization_id, project_id, card_id, lock=True)
            conflict = (
                card.revision != payload.revision or ContentCardState(card.state) not in QA_STATES
            )
            run_id = uuid4()
            report: QAReport | None = None
            previous = card.state
            if not conflict and not model_failed:
                status = report_status(findings)
                target = (
                    ContentCardState.QA_PASSED if status == "passed" else ContentCardState.QA_FAILED
                )
                if ContentCardState(card.state) == target:
                    card.revision += 1  # a re-run with the same outcome still moves the revision
                else:
                    transition_content_card(card, target)
                report = QAReport(
                    status=status,
                    run_at=completed,
                    job_run_id=run_id,
                    card_revision=card.revision,
                    draft_version=ctx.stored.version,
                    bundle_ref=ctx.status.bundle_ref,
                    bundle_hash=ctx.status.content_hash,
                    findings=findings,
                    model_layer="skipped" if model_result is None else "ran",
                    model_note=(
                        "Skipped: deterministic errors must be fixed first."
                        if model_result is None
                        else ""
                    ),
                    provider=model_result.provider if model_result else None,
                    model=model_result.model if model_result else None,
                )
                card.qa_report = report.model_dump(mode="json")
            error = None
            if model_failed and model_result is not None:
                error = model_result.error_code or "QA_OUTPUT_INVALID"
            elif conflict:
                error = "VERSION_CONFLICT: the card changed during QA; not stored"
            run = self._job(
                card,
                actor,
                QA_JOB_TYPE,
                V3_QA_VERSION,
                provider=model_result.provider if model_result else "internal",
                model=model_result.model if model_result else "deterministic",
                tokens=(
                    (model_result.input_tokens, model_result.output_tokens)
                    if model_result
                    else (0, 0)
                ),
                ok=report is not None,
                input_data={
                    "card_revision": payload.revision,
                    "draft_version": ctx.stored.version,
                    "bundle_ref": str(ctx.status.bundle_ref),
                    "bundle_hash": ctx.status.content_hash,
                },
                output_data={
                    "report": report.model_dump(mode="json") if report else None,
                    "deterministic": [
                        f.model_dump(mode="json") for f in findings if f.layer == "deterministic"
                    ],
                    "model_attempts": (
                        [a.model_dump(mode="json") for a in model_result.attempts]
                        if model_result
                        else []
                    ),
                    "stored": report is not None,
                },
                error=error,
                started=started,
                completed=completed,
                run_id=run_id,
            )
            await self._session.flush()
            if report is not None:
                await self._session.refresh(card)
                self._audit.add(
                    self._session,
                    actor_user_id=actor.user_id,
                    organization_id=organization_id,
                    project_id=project_id,
                    action="content_card.qa_run",
                    resource_type="content_card",
                    resource_id=card.id,
                    request_id=request_id,
                    metadata={
                        "job_run_id": str(run.id),
                        "status": report.status,
                        "errors": report.error_count,
                        "warnings": report.warning_count,
                        "from": previous,
                        "to": card.state,
                    },
                )
                face = await self._face(card, ctx.project.plan_locked_at)

        if model_failed and model_result is not None:
            if model_result.error_code == "PROVIDER_ERROR":
                raise DomainError(
                    "AI_PROVIDER_ERROR",
                    "The AI provider failed during QA. Try again.",
                    502,
                    details={"job_run_id": str(run.id)},
                )
            raise DomainError(
                "QA_OUTPUT_INVALID",
                "The model's QA output was rejected; nothing was stored.",
                422,
                details={
                    "job_run_id": str(run.id),
                    "issues": [i.model_dump(mode="json") for i in model_result.issues],
                },
            )
        if report is None:
            raise ConflictError(
                "VERSION_CONFLICT",
                "The card changed while QA ran. Reload and run QA again.",
                details={"job_run_id": str(run.id)},
            )
        return QARunResponse(card=face, report=report)

    # ── Repair and section regeneration ────────────────────────────

    async def _store_revision(
        self,
        organization_id: UUID,
        project_id: UUID,
        card_id: UUID,
        *,
        actor: AuthenticatedUser,
        request_id: str,
        revision: int,
        allowed_states: set[ContentCardState],
        ctx: ProductionContext,
        result: RevisionResult,
        job_type: str,
        generation_type: RevisionType,
        trigger: dict[str, object],
        started: datetime,
        completed: datetime,
    ) -> DraftRevisionResponse:
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
                card.revision != revision or ContentCardState(card.state) not in allowed_states
            )
            run_id = uuid4()
            if result.draft is not None and not conflict:
                stored = self._next_version(
                    ctx,
                    result,
                    result.draft,
                    run_id,
                    actor,
                    revision,
                    generation_type,
                    trigger,
                    completed,
                )
                card.draft = stored.model_dump(mode="json")
                if ContentCardState(card.state) == ContentCardState.DRAFTING:
                    card.revision += 1
                else:  # qa_failed / qa_passed → drafting; the QA report is now stale
                    transition_content_card(card, ContentCardState.DRAFTING)
            error = None
            if not result.ok:
                error = "; ".join(i.code for i in result.issues) or result.error_code
            elif conflict:
                error = "VERSION_CONFLICT: the card changed during generation; not stored"
            run = self._job(
                card,
                actor,
                job_type,
                result.prompt_version,
                provider=result.provider,
                model=result.model,
                tokens=(result.input_tokens, result.output_tokens),
                ok=result.ok,
                input_data={
                    "card_revision": revision,
                    "draft_version": ctx.stored.version,
                    "bundle_ref": str(ctx.status.bundle_ref),
                    "bundle_hash": ctx.status.content_hash,
                    "trigger": trigger,
                    "previous_draft": ctx.stored.draft.model_dump(mode="json"),
                },
                output_data={
                    "draft": result.draft.model_dump(mode="json") if result.draft else None,
                    "attempts": [a.model_dump(mode="json") for a in result.attempts],
                    "issues": [i.model_dump(mode="json") for i in result.issues],
                    "stored": stored is not None,
                },
                error=error,
                started=started,
                completed=completed,
                run_id=run_id,
            )
            await self._session.flush()
            if stored is not None:
                await self._session.refresh(card)
                self._audit.add(
                    self._session,
                    actor_user_id=actor.user_id,
                    organization_id=organization_id,
                    project_id=project_id,
                    action=f"content_card.{generation_type}",
                    resource_type="content_card",
                    resource_id=card.id,
                    request_id=request_id,
                    metadata={
                        "job_run_id": str(run.id),
                        "from_version": ctx.stored.version,
                        "to_version": stored.version,
                        "trigger": trigger,
                    },
                )
                face = await self._face(card, locked_at)

        if result.error_code == "PROVIDER_ERROR":
            raise DomainError(
                "AI_PROVIDER_ERROR",
                "The AI provider failed. The previous draft is unchanged.",
                502,
                details={"job_run_id": str(run.id)},
            )
        if result.draft is None:
            raise DomainError(
                "REVISION_INVALID",
                "The rewritten draft was rejected; the previous draft is unchanged.",
                422,
                details={
                    "job_run_id": str(run.id),
                    "issues": [i.model_dump(mode="json") for i in result.issues],
                },
            )
        if stored is None:
            raise ConflictError(
                "VERSION_CONFLICT",
                "The card changed while the draft was rewritten. Reload and try again.",
                details={"job_run_id": str(run.id)},
            )
        return DraftRevisionResponse(card=face, draft=stored)

    @staticmethod
    def _next_version(
        ctx: ProductionContext,
        result: RevisionResult,
        draft: DraftV3,
        run_id: UUID,
        actor: AuthenticatedUser,
        revision: int,
        generation_type: RevisionType,
        trigger: dict[str, object],
        completed: datetime,
    ) -> StoredDraft:
        return StoredDraft(
            version=ctx.stored.version + 1,
            draft=draft,
            unresolved=unresolved_needs(draft),
            job_run_id=run_id,
            prompt_version=result.prompt_version,
            provider=result.provider,
            model=result.model,
            bundle_ref=ctx.status.bundle_ref,
            bundle_hash=ctx.status.content_hash,
            source_revision=revision,
            generated_at=completed,
            generated_by=actor.user_id,
            generation_type=generation_type,
            previous_version=ctx.stored.version,
            trigger=trigger,
        )

    async def repair_draft(
        self,
        organization_id: UUID,
        project_id: UUID,
        card_id: UUID,
        payload: RepairRequest,
        *,
        actor: AuthenticatedUser,
        request_id: str,
    ) -> DraftRevisionResponse:
        """Rewrite only the sections the current QA report's errors point at."""
        self._require_allowed_model(payload.model)
        async with transactional_session(self._session):
            await set_actor_context(self._session, actor.user_id)
            ctx = await self._context(
                organization_id,
                project_id,
                card_id,
                actor,
                PermissionCode.CONTENT_WRITE,
                PermissionCode.AI_USE,
            )
            self._require_revision(ctx.card, payload.revision)
            if ContentCardState(ctx.card.state) != ContentCardState.QA_FAILED:
                raise ConflictError(
                    "REPAIR_NOT_ALLOWED",
                    f"Repair follows a failed QA run; this card is {ctx.card.state}.",
                    details={"state": ctx.card.state},
                )
            report = stored_qa_report(ctx.card)
            if report is None or not qa_is_current(ctx.card, report, ctx.stored):
                raise ConflictError("QA_STALE", "Run QA again before repairing.")
            errors = [f for f in report.findings if f.severity == "error"]
            targets = sorted({f.section_id for f in errors if f.section_id})
            fix_answer = any(f.section_id is None and "DIRECT_ANSWER" in f.code for f in errors)
            if not targets and not fix_answer:
                raise ConflictError(
                    "REPAIR_NOT_POSSIBLE",
                    "These errors are not in the draft text (e.g. the outline or claims changed); "
                    "they need a Strategy or outline change.",
                    details={"codes": sorted({f.code for f in errors})},
                )
        instructions: list[dict[str, object]] = [_finding_brief(f) for f in errors]
        started = datetime.now(UTC)
        result = await DraftReviser(self._ai(payload.model)).revise(
            "repair",
            ctx.source,
            ctx.stored,
            targets,
            instructions,
            fix_direct_answer=fix_answer,
            model=payload.model,
        )
        completed = datetime.now(UTC)
        return await self._store_revision(
            organization_id,
            project_id,
            card_id,
            actor=actor,
            request_id=request_id,
            revision=payload.revision,
            allowed_states={ContentCardState.QA_FAILED},
            ctx=ctx,
            result=result,
            job_type=REPAIR_JOB_TYPE,
            generation_type="repair",
            trigger={
                "qa_job_run_id": str(report.job_run_id),
                "finding_ids": [f.id for f in errors],
                "sections": targets,
            },
            started=started,
            completed=completed,
        )

    async def regenerate_section(
        self,
        organization_id: UUID,
        project_id: UUID,
        card_id: UUID,
        section_id: str,
        payload: SectionRegenerateRequest,
        *,
        actor: AuthenticatedUser,
        request_id: str,
    ) -> DraftRevisionResponse:
        """Rewrite one section from reviewer/QA feedback; every other section is kept."""
        self._require_allowed_model(payload.model)
        async with transactional_session(self._session):
            await set_actor_context(self._session, actor.user_id)
            ctx = await self._context(
                organization_id,
                project_id,
                card_id,
                actor,
                PermissionCode.CONTENT_WRITE,
                PermissionCode.AI_USE,
            )
            self._require_revision(ctx.card, payload.revision)
            if ContentCardState(ctx.card.state) not in REGENERATE_STATES:
                raise ConflictError(
                    "REGENERATE_NOT_ALLOWED",
                    f"Sections are regenerated while drafting; this card is {ctx.card.state}.",
                    details={"state": ctx.card.state},
                )
            if section_id not in {s.section_id for s in ctx.stored.draft.sections}:
                raise ResourceNotFound("section")
            report = stored_qa_report(ctx.card)
        open_findings = [
            _finding_brief(f)
            for f in (report.findings if report else [])
            if f.section_id == section_id
        ]
        instructions: list[dict[str, object]] = [{"feedback": payload.feedback}, *open_findings]
        started = datetime.now(UTC)
        result = await DraftReviser(self._ai(payload.model)).revise(
            "section", ctx.source, ctx.stored, [section_id], instructions, model=payload.model
        )
        completed = datetime.now(UTC)
        return await self._store_revision(
            organization_id,
            project_id,
            card_id,
            actor=actor,
            request_id=request_id,
            revision=payload.revision,
            allowed_states=REGENERATE_STATES,
            ctx=ctx,
            result=result,
            job_type=SECTION_JOB_TYPE,
            generation_type="section_regeneration",
            trigger={"section_id": section_id, "feedback": payload.feedback},
            started=started,
            completed=completed,
        )

    # ── G2 ─────────────────────────────────────────────────────────

    async def _g2_ready_card(
        self, organization_id: UUID, project_id: UUID, card_id: UUID, revision: int
    ) -> tuple[ContentCard, QAReport, StoredDraft]:
        card = await self._card(organization_id, project_id, card_id, lock=True)
        self._require_revision(card, revision)
        if ContentCardState(card.state) != ContentCardState.QA_PASSED:
            raise ConflictError(
                "G2_NOT_ALLOWED",
                f"G2 applies to qa_passed cards; this card is {card.state}.",
                details={"state": card.state},
            )
        stored, _ = _stored_draft(card)
        report = stored_qa_report(card)
        if stored is None or report is None:
            raise ConflictError("QA_STALE", "Run QA before G2.")
        return card, report, stored

    async def approve_g2(
        self,
        organization_id: UUID,
        project_id: UUID,
        card_id: UUID,
        payload: G2ApproveRequest,
        *,
        actor: AuthenticatedUser,
        request_id: str,
    ) -> G1DecisionResponse:
        """qa_passed → approved on a current, passed QA report. Nothing is published."""
        async with transactional_session(self._session):
            await set_actor_context(self._session, actor.user_id)
            project = await self._authorize_gate(organization_id, project_id, actor, "G2")
            card, report, stored = await self._g2_ready_card(
                organization_id, project_id, card_id, payload.revision
            )
            fresh = await self._builder.build_card_bundle(self._session, card=card)
            status, _ = await self._bundle_status(card, bundle_hash(fresh))
            config = WorkspaceConfig.model_validate(project.workspace_config or {})
            blockers = g2_blockers(
                card,
                report,
                stored,
                status,
                warnings_require_dismissal=config.soft_warnings_require_dismissal,
            )
            if blockers:
                raise ConflictError(
                    "G2_BLOCKED", " ".join(blockers), details={"blockers": blockers}
                )
            run = self._gate_run(card, actor, action="approve", revision=card.revision)
            _mark_g2(run, report=report, draft=stored)
            transition_content_card(card, ContentCardState.APPROVED)
            await self._session.flush()
            await self._session.refresh(card)
            self._audit.add(
                self._session,
                actor_user_id=actor.user_id,
                organization_id=organization_id,
                project_id=project_id,
                action="content_card.g2_approved",
                resource_type="content_card",
                resource_id=card.id,
                request_id=request_id,
                metadata={
                    "job_run_id": str(run.id),
                    "card_revision": payload.revision,
                    "qa_job_run_id": str(report.job_run_id),
                    "draft_version": stored.version,
                },
            )
            names = await self._repository.get_user_names({actor.user_id})
            return G1DecisionResponse(
                card=await self._face(card, project.plan_locked_at),
                decision=_gate_decision(run, names),
            )

    async def send_back_g2(
        self,
        organization_id: UUID,
        project_id: UUID,
        card_id: UUID,
        payload: G2SendBackRequest,
        *,
        actor: AuthenticatedUser,
        request_id: str,
    ) -> G1DecisionResponse:
        """qa_passed → drafting with typed, required feedback."""
        async with transactional_session(self._session):
            await set_actor_context(self._session, actor.user_id)
            project = await self._authorize_gate(organization_id, project_id, actor, "G2")
            card, report, stored = await self._g2_ready_card(
                organization_id, project_id, card_id, payload.revision
            )
            run = self._gate_run(
                card,
                actor,
                action="send_back",
                revision=card.revision,
                reason=payload.reason,
                feedback=payload.feedback,
            )
            _mark_g2(run, report=report, draft=stored)
            transition_content_card(card, ContentCardState.DRAFTING)
            await self._session.flush()
            await self._session.refresh(card)
            self._audit.add(
                self._session,
                actor_user_id=actor.user_id,
                organization_id=organization_id,
                project_id=project_id,
                action="content_card.g2_sent_back",
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

    async def dismiss_warning(
        self,
        organization_id: UUID,
        project_id: UUID,
        card_id: UUID,
        payload: WarningDismissRequest,
        *,
        actor: AuthenticatedUser,
        request_id: str,
    ) -> WarningDismissResponse:
        """Record a reviewer's dismissal of one warning; errors cannot be dismissed."""
        async with transactional_session(self._session):
            await set_actor_context(self._session, actor.user_id)
            project = await self._authorize_gate(organization_id, project_id, actor, "G2")
            card, report, stored = await self._g2_ready_card(
                organization_id, project_id, card_id, payload.revision
            )
            if not qa_is_current(card, report, stored):
                raise ConflictError("QA_STALE", "Run QA again before dismissing warnings.")
            finding = next((f for f in report.findings if f.id == payload.finding_id), None)
            if finding is None:
                raise ResourceNotFound("qa_finding")
            if finding.severity != "warning":
                raise ConflictError(
                    "NOT_DISMISSIBLE", "Only warnings can be dismissed; errors must be fixed."
                )
            if any(d.finding_id == finding.id for d in report.dismissals):
                raise ConflictError("ALREADY_DISMISSED", "This warning is already dismissed.")
            names = await self._repository.get_user_names({actor.user_id})
            card.revision += 1
            report = report.model_copy(
                update={
                    "card_revision": card.revision,  # a dismissal keeps the report current
                    "dismissals": [
                        *report.dismissals,
                        WarningDismissal(
                            finding_id=finding.id,
                            reviewer_id=actor.user_id,
                            reviewer_name=names.get(actor.user_id),
                            dismissed_at=datetime.now(UTC),
                            reason=payload.reason,
                            card_revision=payload.revision,
                        ),
                    ],
                }
            )
            card.qa_report = report.model_dump(mode="json")
            await self._session.flush()
            await self._session.refresh(card)
            self._audit.add(
                self._session,
                actor_user_id=actor.user_id,
                organization_id=organization_id,
                project_id=project_id,
                action="content_card.qa_warning_dismissed",
                resource_type="content_card",
                resource_id=card.id,
                request_id=request_id,
                metadata={
                    "finding_id": finding.id,
                    "code": finding.code,
                    "card_revision": payload.revision,
                },
            )
            return WarningDismissResponse(
                card=await self._face(card, project.plan_locked_at), report=report
            )


def _finding_brief(finding: QAFinding) -> dict[str, object]:
    return {
        "id": finding.id,
        "code": finding.code,
        "section_id": finding.section_id,
        "message": finding.message,
        "claim_id": str(finding.claim_id) if finding.claim_id else None,
        "url": finding.url,
        "evidence": finding.evidence,
        "suggested_repair": finding.suggested_repair,
    }


def _mark_g2(run: JobRun, *, report: QAReport, draft: StoredDraft) -> None:
    """Turn a gate JobRun into a G2 decision with its QA and draft snapshots."""
    run.prompt_version = "v3.gate.g2.v1"
    run.input_data = {
        **(run.input_data or {}),
        "gate": "G2",
        "outline": None,
        "qa_report": report.model_dump(mode="json"),
        "draft_version": draft.version,
        "draft": draft.draft.model_dump(mode="json"),
    }
