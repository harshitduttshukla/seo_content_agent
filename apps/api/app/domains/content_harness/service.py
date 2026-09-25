"""Application service for orchestrating Content Harness testing and evaluation."""

import json
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from app.ai.provider import AIMessage, AIProvider, GenerationRequest
from app.core.errors import ResourceNotFound
from app.db.session import set_actor_context
from app.domains.ai.context_builder import ContentAgentContextBuilder, bundle_hash
from app.domains.ai.service import get_ai_provider
from app.domains.audit.repository import AuditWriter
from app.domains.content.editor_models import ContentBrief
from app.domains.content_cards.draft_generation import (
    V3_DRAFT_PROMPT_VERSION,
    DraftGenerator,
    build_draft_messages,
)
from app.domains.content_cards.outline_generation import (
    V3_OUTLINE_PROMPT_VERSION,
    OutlineGenerator,
    build_outline_messages,
)
from app.domains.content_cards.repository import ContentCardRepository
from app.domains.content_harness.evaluator import evaluate_content, evaluate_with_ai
from app.domains.content_harness.v3_draft_evaluator import evaluate_v3_draft
from app.domains.content_harness.v3_outline_evaluator import evaluate_v3_outline

GOLDEN_TEST_CASES = {}
from app.domains.content_harness.models import ContentHarnessRun, HarnessRunStatus
from app.domains.content_harness.prompts import build_harness_prompts
from app.domains.content_harness.repository import ContentHarnessRepository
from app.domains.content_harness.schemas import (
    ContentHarnessComparison,
    ContentHarnessInput,
    ContentHarnessRunDetail,
    ContentHarnessRunListItem,
    EvaluateContentRequest,
    FindingStatus,
    HarnessGeneratedContent,
    HarnessScorecard,
    V3DraftHarnessInput,
    V3OutlineHarnessInput,
)
from app.domains.projects.service import ProjectService
from app.security.principal import AuthenticatedUser, PermissionCode
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


class ContentHarnessService:
    """Orchestrates content harness executions, scoring, comparisons, and run history."""

    def __init__(
        self,
        provider: AIProvider | None = None,
        repository: ContentHarnessRepository | None = None,
    ) -> None:
        self._provider = provider or get_ai_provider()
        self._repo = repository or ContentHarnessRepository()
        self._projects = ProjectService()
        self._audit = AuditWriter()

    async def run_harness(
        self,
        session: AsyncSession,
        *,
        actor: AuthenticatedUser,
        input_data: ContentHarnessInput,
    ) -> ContentHarnessRunDetail:
        """Executes a complete, isolated Content Harness test run."""
        # 1. Authorize tenant and project access
        project = await self._projects.get_model(
            session,
            actor=actor,
            project_id=input_data.project_id,
            permission=PermissionCode.AI_USE,
        )

        started_at = datetime.now(UTC)

        # 2. Enrich context if a Content Brief is referenced
        if input_data.content_brief_id:
            brief_stmt = select(ContentBrief).where(
                ContentBrief.id == input_data.content_brief_id,
                ContentBrief.project_id == input_data.project_id,
            )
            brief_res = await session.execute(brief_stmt)
            brief = brief_res.scalars().first()
            if brief:
                if not input_data.primary_keyword and brief.primary_keyword:
                    input_data.primary_keyword = brief.primary_keyword
                if not input_data.secondary_keywords and brief.secondary_keywords:
                    input_data.secondary_keywords = brief.secondary_keywords
                if not input_data.target_audience and brief.target_audience:
                    input_data.target_audience = brief.target_audience
                if not input_data.required_topics and brief.required_topics:
                    input_data.required_topics = brief.required_topics
                if not input_data.required_questions and brief.questions_to_answer:
                    input_data.required_questions = brief.questions_to_answer

        # Context snapshot for reproducibility
        context_data: dict[str, Any] = {
            "project_id": str(project.id),
            "project_name": project.name,
            "organization_id": str(project.organization_id),
            "primary_keyword": input_data.primary_keyword,
            "target_word_count": input_data.target_word_count,
            "has_website_context": bool(input_data.website_context),
            "has_brief": bool(input_data.content_brief_id),
        }

        # 3. Build Versioned Prompts
        system_prompt, user_prompt, prompt_data = build_harness_prompts(
            input_data,
            context_data,
        )

        # 4. Invoke AI Provider
        gen_req = GenerationRequest(
            messages=[
                AIMessage(role="system", content=system_prompt),
                AIMessage(role="user", content=user_prompt),
            ],
            model=input_data.model,
            temperature=input_data.temperature,
            max_output_tokens=8192,
        )

        output_data: dict[str, Any] = {}
        error_message: str | None = None
        generated_content: HarnessGeneratedContent | None = None

        try:
            gen_res = await self._provider.generate(gen_req)
            clean_text = gen_res.text.strip()
            if clean_text.startswith("```"):
                lines = clean_text.splitlines()
                if lines[0].startswith("```"):
                    lines = lines[1:]
                if lines and lines[-1].strip() == "```":
                    lines = lines[:-1]
                clean_text = "\n".join(lines).strip()

            try:
                raw_json = json.loads(clean_text)
                generated_content = HarnessGeneratedContent.model_validate(raw_json)
                output_data = generated_content.model_dump(mode="json")
            except (json.JSONDecodeError, ValidationError) as parse_err:
                error_message = f"AI output format validation failed: {parse_err}"
                # Create fallback structured content containing raw text for deterministic eval
                generated_content = HarnessGeneratedContent(
                    title="",
                    content="",
                    sections=[],
                )
                output_data = {
                    "raw_text": clean_text,
                    "parse_error": str(parse_err),
                }

            provider_name = gen_res.provider
            model_name = gen_res.model
        except Exception as gen_exc:
            error_message = f"AI Provider call failed: {gen_exc}"
            provider_name = "error"
            model_name = input_data.model or "unknown"
            generated_content = HarnessGeneratedContent(
                title="",
                content="",
                sections=[],
            )
            output_data = {"error": str(gen_exc)}

        # 5. Deterministic Evaluation
        scorecard = evaluate_content(
            generated_content,
            input_data,
            raw_text=output_data.get("raw_text", ""),
        )
        if error_message:
            scorecard.technical_validity = "FAIL"
            scorecard.status = "NEEDS IMPROVEMENT"

        # 6. Optional AI Evaluation
        if input_data.run_ai_evaluator and not error_message:
            ai_eval = await evaluate_with_ai(
                generated_content,
                input_data,
                self._provider,
            )
            scorecard.ai_evaluation = ai_eval

        completed_at = datetime.now(UTC)

        # 7. Persist Run to PostgreSQL
        run = ContentHarnessRun(
            id=uuid4(),
            organization_id=project.organization_id,
            project_id=project.id,
            created_by_id=actor.user_id,
            name=input_data.name or f"Run: {input_data.primary_keyword}",
            status=HarnessRunStatus.COMPLETED.value
            if not error_message
            else HarnessRunStatus.FAILED.value,
            prompt_version=input_data.prompt_version,
            model=model_name,
            provider=provider_name,
            input_data=input_data.model_dump(mode="json"),
            context_data=context_data,
            prompt_data=prompt_data,
            output_data=output_data,
            evaluation_data=scorecard.model_dump(mode="json"),
            score=scorecard.overall_score,
            error_message=error_message,
            started_at=started_at,
            completed_at=completed_at,
            created_at=completed_at,
            updated_at=completed_at,
        )

        await self._repo.create(session, run)

        return ContentHarnessRunDetail.model_validate(run)

    async def run_v3_outline(
        self,
        session: AsyncSession,
        *,
        actor: AuthenticatedUser,
        input_data: V3OutlineHarnessInput,
    ) -> ContentHarnessRunDetail:
        """Evaluate the production V3 outline contract on a real ContentCard.

        Same bundle builder, prompt, generator and validation as the Content Hub;
        the only difference is that the result is scored and stored as a Harness
        run instead of being offered for saving. The card is never modified.
        """
        await set_actor_context(session, actor.user_id)
        project = await self._projects.get_model(
            session,
            actor=actor,
            project_id=input_data.project_id,
            permission=PermissionCode.AI_USE,
        )
        card = await ContentCardRepository(session).get_scoped(
            project.organization_id, project.id, input_data.card_id
        )
        if card is None:
            raise ResourceNotFound("content_card")
        bundle = await ContentAgentContextBuilder(project_service=self._projects).build_card_bundle(
            session, card=card
        )
        started_at = datetime.now(UTC)
        result = await OutlineGenerator(self._provider).generate(
            bundle, model=input_data.model, temperature=input_data.temperature
        )
        evaluation = evaluate_v3_outline(result, bundle)
        completed_at = datetime.now(UTC)
        run = ContentHarnessRun(
            id=uuid4(),
            organization_id=project.organization_id,
            project_id=project.id,
            created_by_id=actor.user_id,
            name=input_data.name,
            status=HarnessRunStatus.COMPLETED.value if result.ok else HarnessRunStatus.FAILED.value,
            prompt_version=V3_OUTLINE_PROMPT_VERSION,
            model=result.model,
            provider=result.provider,
            input_data={"mode": "v3_outline", **input_data.model_dump(mode="json")},
            context_data={
                "bundle_hash": bundle_hash(bundle),
                "bundle": bundle.model_dump(mode="json"),
            },
            prompt_data={
                "prompt_version": V3_OUTLINE_PROMPT_VERSION,
                "messages": [m.model_dump() for m in build_outline_messages(bundle)],
            },
            output_data={
                "outline": result.outline.model_dump(mode="json") if result.outline else None,
                "attempts": [a.model_dump(mode="json") for a in result.attempts],
                "issues": [i.model_dump(mode="json") for i in result.issues],
                "input_tokens": result.input_tokens,
                "output_tokens": result.output_tokens,
            },
            evaluation_data=evaluation.model_dump(mode="json"),
            score=evaluation.score,
            error_message=result.error_code,
            started_at=started_at,
            completed_at=completed_at,
            created_at=completed_at,
            updated_at=completed_at,
        )
        await self._repo.create(session, run)
        return ContentHarnessRunDetail.model_validate(run)

    async def run_v3_draft(
        self,
        session: AsyncSession,
        *,
        actor: AuthenticatedUser,
        input_data: V3DraftHarnessInput,
    ) -> ContentHarnessRunDetail:
        """Evaluate the production V3 draft contract on a real ContentCard.

        Same bundle builder, draft input (approved outline, current claims, stored
        pages), prompt, generator and validation as the Content Hub. The result is
        scored and stored as a Harness run; the card is never modified.
        """
        from app.domains.content_cards.workflow_service import CardWorkflowService

        await set_actor_context(session, actor.user_id)
        project = await self._projects.get_model(
            session,
            actor=actor,
            project_id=input_data.project_id,
            permission=PermissionCode.AI_USE,
        )
        card = await ContentCardRepository(session).get_scoped(
            project.organization_id, project.id, input_data.card_id
        )
        if card is None:
            raise ResourceNotFound("content_card")
        bundle = await ContentAgentContextBuilder(project_service=self._projects).build_card_bundle(
            session, card=card
        )
        source = await CardWorkflowService(session, provider=self._provider).draft_input(
            card, bundle
        )
        started_at = datetime.now(UTC)
        result = await DraftGenerator(self._provider).generate(
            source, model=input_data.model, temperature=input_data.temperature
        )
        evaluation = evaluate_v3_draft(result, source)
        completed_at = datetime.now(UTC)
        run = ContentHarnessRun(
            id=uuid4(),
            organization_id=project.organization_id,
            project_id=project.id,
            created_by_id=actor.user_id,
            name=input_data.name,
            status=HarnessRunStatus.COMPLETED.value if result.ok else HarnessRunStatus.FAILED.value,
            prompt_version=V3_DRAFT_PROMPT_VERSION,
            model=result.model,
            provider=result.provider,
            input_data={"mode": "v3_draft", **input_data.model_dump(mode="json")},
            context_data={
                "bundle_hash": bundle_hash(bundle),
                "bundle": bundle.model_dump(mode="json"),
                "outline": source.outline.model_dump(mode="json"),
                "claim_ids": sorted(str(c.id) for c in source.claims),
            },
            prompt_data={
                "prompt_version": V3_DRAFT_PROMPT_VERSION,
                "messages": [m.model_dump() for m in build_draft_messages(source)],
            },
            output_data={
                "draft": result.draft.model_dump(mode="json") if result.draft else None,
                "attempts": [a.model_dump(mode="json") for a in result.attempts],
                "issues": [i.model_dump(mode="json") for i in result.issues],
                "input_tokens": result.input_tokens,
                "output_tokens": result.output_tokens,
            },
            evaluation_data=evaluation.model_dump(mode="json"),
            score=evaluation.score,
            error_message=result.error_code,
            started_at=started_at,
            completed_at=completed_at,
            created_at=completed_at,
            updated_at=completed_at,
        )
        await self._repo.create(session, run)
        return ContentHarnessRunDetail.model_validate(run)

    async def get_run(
        self,
        session: AsyncSession,
        *,
        actor: AuthenticatedUser,
        project_id: UUID,
        run_id: UUID,
    ) -> ContentHarnessRunDetail:
        """Retrieves a single harness run ensuring tenant isolation."""
        project = await self._projects.get_model(
            session,
            actor=actor,
            project_id=project_id,
            permission=PermissionCode.CONTENT_READ,
        )
        run = await self._repo.get_by_id(
            session,
            run_id=run_id,
            organization_id=project.organization_id,
            project_id=project.id,
        )
        if not run:
            raise ResourceNotFound(f"Content harness run {run_id} not found.")
        return ContentHarnessRunDetail.model_validate(run)

    async def list_runs(
        self,
        session: AsyncSession,
        *,
        actor: AuthenticatedUser,
        project_id: UUID,
        limit: int = 50,
        offset: int = 0,
    ) -> list[ContentHarnessRunListItem]:
        """Lists historical harness runs for a project."""
        project = await self._projects.get_model(
            session,
            actor=actor,
            project_id=project_id,
            permission=PermissionCode.CONTENT_READ,
        )
        runs = await self._repo.list_by_project(
            session,
            organization_id=project.organization_id,
            project_id=project.id,
            limit=limit,
            offset=offset,
        )
        return [ContentHarnessRunListItem.model_validate(r) for r in runs]

    async def compare_runs(
        self,
        session: AsyncSession,
        *,
        actor: AuthenticatedUser,
        project_id: UUID,
        run_id_a: UUID,
        run_id_b: UUID,
    ) -> ContentHarnessComparison:
        """Compares two harness runs side-by-side."""
        run_a_detail = await self.get_run(
            session,
            actor=actor,
            project_id=project_id,
            run_id=run_id_a,
        )
        run_b_detail = await self.get_run(
            session,
            actor=actor,
            project_id=project_id,
            run_id=run_id_b,
        )

        eval_a = run_a_detail.evaluation_data
        eval_b = run_b_detail.evaluation_data

        score_diffs: dict[str, float] = {
            "overall": round(
                float(eval_b.get("overall_score", 0.0)) - float(eval_a.get("overall_score", 0.0)), 1
            ),
            "seo": round(
                float(eval_b.get("seo_score", 0.0)) - float(eval_a.get("seo_score", 0.0)), 1
            ),
            "content": round(
                float(eval_b.get("content_score", 0.0)) - float(eval_a.get("content_score", 0.0)), 1
            ),
            "brand": round(
                float(eval_b.get("brand_score", 0.0)) - float(eval_a.get("brand_score", 0.0)), 1
            ),
            "linking": round(
                float(eval_b.get("linking_score", 0.0)) - float(eval_a.get("linking_score", 0.0)), 1
            ),
        }

        # Analyze findings improvements and regressions
        findings_a: dict[str, str] = {
            f.get("rule", ""): f.get("status", "")
            for f in eval_a.get("findings", [])
            if isinstance(f, dict) and f.get("rule")
        }
        findings_b: dict[str, str] = {
            f.get("rule", ""): f.get("status", "")
            for f in eval_b.get("findings", [])
            if isinstance(f, dict) and f.get("rule")
        }

        improvements: list[str] = []
        regressions: list[str] = []

        all_rules = set(findings_a.keys()) | set(findings_b.keys())
        for rule in all_rules:
            st_a = findings_a.get(rule, "UNKNOWN")
            st_b = findings_b.get(rule, "UNKNOWN")
            if st_b == FindingStatus.PASS.value and st_a in (
                FindingStatus.FAIL.value,
                FindingStatus.WARN.value,
            ):
                improvements.append(f"Rule '{rule}' improved from {st_a} to PASS in Run B.")
            elif (
                st_b in (FindingStatus.FAIL.value, FindingStatus.WARN.value)
                and st_a == FindingStatus.PASS.value
            ):
                regressions.append(f"Rule '{rule}' degraded from PASS to {st_b} in Run B.")

        summary = (
            f"Run B vs Run A: Overall score change is {score_diffs['overall']:+0.1f} points "
            f"({eval_a.get('overall_score')} -> {eval_b.get('overall_score')}). "
            f"{len(improvements)} improvements and {len(regressions)} regressions identified."
        )

        return ContentHarnessComparison(
            run_a=run_a_detail,
            run_b=run_b_detail,
            score_diffs=score_diffs,
            improvements=improvements,
            regressions=regressions,
            summary=summary,
        )

    async def evaluate_content_direct(
        self,
        session: AsyncSession,
        *,
        actor: AuthenticatedUser,
        payload: EvaluateContentRequest,
    ) -> HarnessScorecard:
        """Standalone evaluation of existing content without invoking AI generation."""
        await self._projects.get_model(
            session,
            actor=actor,
            project_id=payload.project_id,
            permission=PermissionCode.CONTENT_READ,
        )
        return evaluate_content(payload.content, payload.input_data)

    def list_golden_cases(self) -> list[dict[str, Any]]:
        """Returns the list of standardized golden test cases."""
        cases: list[dict[str, Any]] = []
        for case_id, case_input in GOLDEN_TEST_CASES.items():
            cases.append(
                {
                    "case_id": case_id,
                    "name": case_input.name,
                    "primary_keyword": case_input.primary_keyword,
                    "secondary_keywords": case_input.secondary_keywords,
                    "target_audience": case_input.target_audience,
                    "target_word_count": case_input.target_word_count,
                    "prompt_version": case_input.prompt_version,
                    "brand_tone": case_input.brand_rules.tone,
                    "forbidden_words": case_input.brand_rules.words_to_avoid,
                    "internal_links_count": len(case_input.internal_link_targets),
                }
            )
        return cases

    async def run_golden_case(
        self,
        session: AsyncSession,
        *,
        actor: AuthenticatedUser,
        project_id: UUID,
        case_id: str,
    ) -> ContentHarnessRunDetail:
        """Executes a pre-defined golden test case for the given project."""
        if case_id not in GOLDEN_TEST_CASES:
            raise ResourceNotFound(f"Golden test case '{case_id}' not found.")

        base_case = GOLDEN_TEST_CASES[case_id]
        case_input = base_case.model_copy(deep=True)
        case_input.project_id = project_id

        return await self.run_harness(
            session,
            actor=actor,
            input_data=case_input,
        )
