"""PostgreSQL integration tests verifying transaction ownership, boundaries,
and durable persistence for the Content Agent / AI Orchestrator (Problem #1).
"""

import asyncio
import json
import os
from collections.abc import AsyncIterator, Sequence
from datetime import UTC, datetime
from typing import Any
from unittest.mock import patch
from uuid import UUID, uuid4

import app.models  # noqa: F401
import pytest
import pytest_asyncio
from app.ai.provider import AIProvider, EmbeddingResult, GenerationRequest, GenerationResult, Usage
from app.db.session import transactional_session
from app.domains.content.editor_models import AIEditProposal, ContentDocument, ProposalStatus
from app.domains.content.models import PlannedContentPage
from app.domains.orchestrator.agent_loop import AgentLoop
from app.domains.orchestrator.intent_classifier import IntentClassifier
from app.domains.orchestrator.models import (
    AIWorkflow,
    AIWorkflowStep,
    StepStatus,
    ToolExecutionRecord,
    ToolExecutionStatus,
    WorkflowIntent,
    WorkflowStatus,
)
from app.domains.orchestrator.orchestrator_service import OrchestratorService
from app.domains.orchestrator.planner import WorkflowPlanner
from app.domains.orchestrator.policies import ToolRiskLevel
from app.domains.orchestrator.schemas import (
    WorkflowPlanStep,
)
from app.domains.orchestrator.tool_executor import ToolExecutor
from app.domains.orchestrator.tool_registry import ToolRegistry
from app.domains.orchestrator.workflow_service import WorkflowService
from app.domains.organizations.models import Organization
from app.domains.projects.models import Project
from app.domains.users.models import User
from app.security.principal import AuthenticatedUser
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@localhost:5432/seo_content",
)


class DeterministicSequenceAIProvider(AIProvider):
    """Deterministic AI provider for testing state transitions and boundary safety."""

    def __init__(
        self,
        responses: list[dict[str, Any] | str],
        *,
        on_generate_hook: Any | None = None,
    ) -> None:
        self._responses = list(responses)
        self._on_generate_hook = on_generate_hook
        self.call_count = 0
        self.last_request: GenerationRequest | None = None

    async def generate(self, request: GenerationRequest) -> GenerationResult:
        self.call_count += 1
        self.last_request = request

        if self._on_generate_hook:
            await self._on_generate_hook(self.call_count, request)

        if self._responses:
            item = self._responses.pop(0)
            content = json.dumps(item) if isinstance(item, dict) else str(item)
        else:
            content = json.dumps(
                {
                    "type": "FINAL",
                    "final_response": "Default completion",
                    "reasoning_summary": "No more responses",
                }
            )

        return GenerationResult(
            text=content,
            provider="test",
            model="deterministic-test-v1",
            usage=Usage(input_tokens=10, output_tokens=10),
            finish_reason="stop",
        )

    async def embed(self, texts: Sequence[str]) -> EmbeddingResult:
        return EmbeddingResult(
            vectors=[[0.1] * 768 for _ in texts],
            provider="test",
            model="embedding-test",
            usage=Usage(input_tokens=len(texts), output_tokens=0),
        )


@pytest_asyncio.fixture
async def db_engine():
    engine = create_async_engine(DATABASE_URL, echo=False, pool_pre_ping=True)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def session_factory(db_engine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(db_engine, expire_on_commit=False)


@pytest_asyncio.fixture
async def seed_data(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[dict[str, Any]]:
    """Seeds baseline organization, project, user, and content document rows in PostgreSQL."""
    org_id = uuid4()
    user_id = uuid4()
    proj_id = uuid4()
    page_id = uuid4()
    doc_id = uuid4()

    actor = AuthenticatedUser(
        user_id=user_id,
        issuer="https://test.identity.example",
        subject=f"sub-{user_id.hex[:8]}",
        email=f"tester-{user_id.hex[:8]}@example.com",
        display_name="Persistence Tester",
    )

    async with session_factory() as session:
        org = Organization(id=org_id, name="Test Org", slug=f"test-org-{org_id.hex[:8]}")
        user = User(
            id=user_id,
            email=actor.email,
            normalized_email=actor.email,
            identity_issuer=actor.issuer,
            identity_subject=actor.subject,
            display_name=actor.display_name,
        )
        session.add_all([org, user])
        await session.flush()

        proj = Project(
            id=proj_id,
            organization_id=org_id,
            name="Test Project",
            slug=f"test-proj-{proj_id.hex[:8]}",
        )
        session.add(proj)
        await session.flush()

        page = PlannedContentPage(
            id=page_id,
            organization_id=org_id,
            project_id=proj_id,
            title="Test Page",
            slug="test-page",
            url="/test-page",
            page_type="PLANNED",
            content_type="BLOG_POST",
            status="PLANNED",
            intent="INFORMATIONAL",
            primary_keyword="test keyword",
            priority=1,
            business_value=1.0,
            revision=1,
        )
        session.add(page)
        await session.flush()

        doc = ContentDocument(
            id=doc_id,
            organization_id=org_id,
            project_id=proj_id,
            page_id=page_id,
            title="Zero Trust Architecture",
            slug="zero-trust-architecture",
            status="DRAFT",
            current_version=1,
            lock_version=1,
            word_count=200,
            content_blocks=[
                {"id": "b1", "type": "h1", "text": "Zero Trust Architecture Overview"},
                {"id": "b2", "type": "paragraph", "text": "Never trust, always verify."},
            ],
            plain_text="Zero Trust Architecture Overview\nNever trust, always verify.",
            revision=1,
        )
        session.add(doc)
        await session.commit()

    context = {
        "org_id": org_id,
        "user_id": user_id,
        "proj_id": proj_id,
        "page_id": page_id,
        "doc_id": doc_id,
        "actor": actor,
    }

    yield context

    # Clean up test rows in proper dependency order
    async with session_factory() as session:
        await session.execute(
            text("DELETE FROM audit_logs WHERE organization_id = :oid"),
            {"oid": org_id},
        )
        await session.execute(
            text(
                "DELETE FROM tool_executions WHERE workflow_id IN "
                "(SELECT id FROM ai_workflows WHERE organization_id = :oid)"
            ),
            {"oid": org_id},
        )
        await session.execute(
            text(
                "DELETE FROM ai_workflow_steps WHERE workflow_id IN "
                "(SELECT id FROM ai_workflows WHERE organization_id = :oid)"
            ),
            {"oid": org_id},
        )
        await session.execute(
            text("DELETE FROM ai_workflows WHERE organization_id = :oid"),
            {"oid": org_id},
        )
        await session.execute(
            text("DELETE FROM ai_edit_proposals WHERE document_id = :did"),
            {"did": doc_id},
        )
        await session.execute(
            text("DELETE FROM content_documents WHERE id = :did"),
            {"did": doc_id},
        )
        await session.execute(
            text("DELETE FROM planned_content_pages WHERE id = :pid"),
            {"pid": page_id},
        )
        await session.execute(
            text("DELETE FROM projects WHERE id = :pjid"),
            {"pjid": proj_id},
        )
        await session.execute(
            text("DELETE FROM users WHERE id = :uid"),
            {"uid": user_id},
        )
        await session.execute(
            text("DELETE FROM organizations WHERE id = :oid"),
            {"oid": org_id},
        )
        await session.commit()


# =========================================================================
# TEST 1: Workflow Creation Persistence
# =========================================================================
@pytest.mark.asyncio
async def test_workflow_creation_persistence(
    session_factory: async_sessionmaker[AsyncSession],
    seed_data: dict[str, Any],
) -> None:
    """TEST 1: Workflow and steps created in session 1 durably persist in PostgreSQL

    after session 1 closes, verified by querying in a new independent session 2.
    """
    service = WorkflowService()
    plan_steps = [
        WorkflowPlanStep(
            step_index=0,
            tool_name="read_document",
            input_arguments={"document_id": str(seed_data["doc_id"])},
            description="Inspect active document",
            risk_level=ToolRiskLevel.READ,
        ),
    ]

    with patch("app.domains.projects.service.ProjectService.get_model", return_value=None):
        async with session_factory() as session1:
            wf = await service.create_workflow(
                session1,
                actor=seed_data["actor"],
                organization_id=seed_data["org_id"],
                project_id=seed_data["proj_id"],
                document_id=seed_data["doc_id"],
                intent=WorkflowIntent.EDIT_DOCUMENT,
                plan_steps=plan_steps,
                user_message="Improve readability",
            )
            wf_id = wf.id

    async with session_factory() as session2:
        persisted_wf = await session2.get(AIWorkflow, wf_id)
        assert persisted_wf is not None
        assert persisted_wf.id == wf_id
        assert persisted_wf.status == WorkflowStatus.PENDING.value
        assert persisted_wf.intent == WorkflowIntent.EDIT_DOCUMENT.value
        assert persisted_wf.created_by_id == seed_data["actor"].user_id
        assert persisted_wf.result.get("user_message") == "Improve readability"

        stmt = (
            select(AIWorkflowStep)
            .where(AIWorkflowStep.workflow_id == wf_id)
            .order_by(AIWorkflowStep.step_index.asc())
        )
        res = await session2.execute(stmt)
        steps = res.scalars().all()
        assert len(steps) == 1
        assert steps[0].tool_name == "read_document"
        assert steps[0].status == StepStatus.PENDING.value
        assert steps[0].input == {"document_id": str(seed_data["doc_id"])}


# =========================================================================
# TEST 2: RUNNING Status Persistence
# =========================================================================
@pytest.mark.asyncio
async def test_workflow_running_status_persistence(
    session_factory: async_sessionmaker[AsyncSession],
    seed_data: dict[str, Any],
) -> None:
    """TEST 2: Workflow status is committed as RUNNING before the LLM provider call,

    verified by inspecting PostgreSQL from an independent session while the LLM call runs.
    """
    wf_id = uuid4()
    async with session_factory() as setup_session:
        wf = AIWorkflow(
            id=wf_id,
            organization_id=seed_data["org_id"],
            project_id=seed_data["proj_id"],
            document_id=seed_data["doc_id"],
            created_by_id=seed_data["actor"].user_id,
            intent=WorkflowIntent.EDIT_DOCUMENT.value,
            status=WorkflowStatus.PENDING.value,
            current_step=0,
            plan=[],
            result={},
            token_usage={"total_tokens": 0},
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        setup_session.add(wf)
        await setup_session.commit()

    observed_status_in_parallel_session: str | None = None

    async def check_status_during_provider_call(call_num: int, request: GenerationRequest) -> None:
        nonlocal observed_status_in_parallel_session
        async with session_factory() as parallel_session:
            w = await parallel_session.get(AIWorkflow, wf_id)
            assert w is not None
            observed_status_in_parallel_session = w.status

    provider = DeterministicSequenceAIProvider(
        [
            {
                "type": "FINAL",
                "final_response": "Done",
                "reasoning_summary": "Finished initial inspection",
            }
        ],
        on_generate_hook=check_status_during_provider_call,
    )

    loop = AgentLoop(provider=provider)
    with patch("app.domains.projects.service.ProjectService.get_model", return_value=None):
        async with session_factory() as run_session:
            wf_to_run = await run_session.get(AIWorkflow, wf_id)
            assert wf_to_run is not None
            await loop.run(
                run_session,
                actor=seed_data["actor"],
                workflow=wf_to_run,
                user_message="Start execution",
            )

    assert observed_status_in_parallel_session == WorkflowStatus.RUNNING.value


# =========================================================================
# TEST 3: Tool Execution Record & Step Persistence (Real Safe Read Tool)
# =========================================================================
@pytest.mark.asyncio
async def test_tool_execution_record_and_step_persistence(
    session_factory: async_sessionmaker[AsyncSession],
    seed_data: dict[str, Any],
) -> None:
    """TEST 3: When a safe read tool executes, the ToolExecutionRecord and updated

    AIWorkflowStep are committed and durably present in PostgreSQL after session close.
    """
    wf_id = uuid4()
    async with session_factory() as setup_session:
        wf = AIWorkflow(
            id=wf_id,
            organization_id=seed_data["org_id"],
            project_id=seed_data["proj_id"],
            document_id=seed_data["doc_id"],
            created_by_id=seed_data["actor"].user_id,
            intent=WorkflowIntent.EDIT_DOCUMENT.value,
            status=WorkflowStatus.PENDING.value,
            current_step=0,
            plan=[],
            result={},
            token_usage={"total_tokens": 0},
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        setup_session.add(wf)
        await setup_session.commit()

    provider = DeterministicSequenceAIProvider(
        [
            {
                "type": "TOOL_CALL",
                "tool_name": "read_document",
                "tool_input": {"document_id": str(seed_data["doc_id"])},
                "reasoning_summary": "Read active document",
            },
            {
                "type": "FINAL",
                "final_response": "Document content verified",
                "reasoning_summary": "Document successfully read",
            },
        ]
    )

    registry = ToolRegistry()
    executor = ToolExecutor(registry=registry)
    loop = AgentLoop(provider=provider, registry=registry, executor=executor)

    with patch("app.domains.projects.service.ProjectService.get_model", return_value=None):
        async with session_factory() as session1:
            wf_to_run = await session1.get(AIWorkflow, wf_id)
            assert wf_to_run is not None
            await loop.run(
                session1,
                actor=seed_data["actor"],
                workflow=wf_to_run,
                user_message="Inspect document",
            )

    async with session_factory() as session2:
        step_stmt = select(AIWorkflowStep).where(AIWorkflowStep.workflow_id == wf_id)
        step_res = await session2.execute(step_stmt)
        steps = step_res.scalars().all()
        assert len(steps) >= 1
        read_step = next(s for s in steps if s.tool_name == "read_document")
        assert read_step.status == StepStatus.COMPLETED.value
        assert "content_blocks" in read_step.output or "plain_text" in read_step.output

        exec_stmt = select(ToolExecutionRecord).where(ToolExecutionRecord.workflow_id == wf_id)
        exec_res = await session2.execute(exec_stmt)
        exec_records = exec_res.scalars().all()
        assert len(exec_records) >= 1
        read_exec = next(e for e in exec_records if e.tool_name == "read_document")
        assert read_exec.status == ToolExecutionStatus.SUCCESS.value
        assert read_exec.step_id == read_step.id


# =========================================================================
# TEST 4: Observation-Driven Second Iteration Persistence
# =========================================================================
@pytest.mark.asyncio
async def test_observation_driven_second_iteration_persistence(
    session_factory: async_sessionmaker[AsyncSession],
    seed_data: dict[str, Any],
) -> None:
    """TEST 4: Tool observation from iteration 1 is passed to iteration 2 prompt,

    and the resulting COMPLETED state and execution trail are durably committed.
    """
    wf_id = uuid4()
    async with session_factory() as setup_session:
        wf = AIWorkflow(
            id=wf_id,
            organization_id=seed_data["org_id"],
            project_id=seed_data["proj_id"],
            document_id=seed_data["doc_id"],
            created_by_id=seed_data["actor"].user_id,
            intent=WorkflowIntent.EDIT_DOCUMENT.value,
            status=WorkflowStatus.PENDING.value,
            current_step=0,
            plan=[],
            result={},
            token_usage={"total_tokens": 0},
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        setup_session.add(wf)
        await setup_session.commit()

    recorded_requests: list[GenerationRequest] = []

    async def record_req(call_num: int, req: GenerationRequest) -> None:
        recorded_requests.append(req)

    provider = DeterministicSequenceAIProvider(
        [
            {
                "type": "TOOL_CALL",
                "tool_name": "read_document",
                "tool_input": {"document_id": str(seed_data["doc_id"])},
                "reasoning_summary": "Read doc content",
            },
            {
                "type": "FINAL",
                "final_response": "Observation validated successfully",
                "reasoning_summary": "All observations checked",
            },
        ],
        on_generate_hook=record_req,
    )

    registry = ToolRegistry()
    executor = ToolExecutor(registry=registry)
    loop = AgentLoop(provider=provider, registry=registry, executor=executor)

    with patch("app.domains.projects.service.ProjectService.get_model", return_value=None):
        async with session_factory() as session1:
            wf_to_run = await session1.get(AIWorkflow, wf_id)
            assert wf_to_run is not None
            await loop.run(
                session1,
                actor=seed_data["actor"],
                workflow=wf_to_run,
                user_message="Examine and finalize",
            )

    assert len(recorded_requests) == 2
    prompt2 = recorded_requests[1].messages[-1].content
    assert "read_document" in prompt2
    assert "SUCCESS" in prompt2

    async with session_factory() as session2:
        wf_persisted = await session2.get(AIWorkflow, wf_id)
        assert wf_persisted is not None
        assert wf_persisted.status == WorkflowStatus.COMPLETED.value
        assert wf_persisted.completed_at is not None
        assert wf_persisted.result.get("summary") == "Observation validated successfully"


# =========================================================================
# TEST 5: Proposal Persistence (WAITING_FOR_APPROVAL & Proposal Row)
# =========================================================================
@pytest.mark.asyncio
async def test_proposal_and_approval_gate_persistence(
    session_factory: async_sessionmaker[AsyncSession],
    seed_data: dict[str, Any],
) -> None:
    """TEST 5: Write tool triggers proposal creation, transitions workflow and step

    to WAITING_FOR_APPROVAL, and all entities are committed durably in PostgreSQL.
    """
    wf_id = uuid4()
    async with session_factory() as setup_session:
        wf = AIWorkflow(
            id=wf_id,
            organization_id=seed_data["org_id"],
            project_id=seed_data["proj_id"],
            document_id=seed_data["doc_id"],
            created_by_id=seed_data["actor"].user_id,
            intent=WorkflowIntent.EDIT_DOCUMENT.value,
            status=WorkflowStatus.PENDING.value,
            current_step=0,
            plan=[],
            result={},
            token_usage={"total_tokens": 0},
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        setup_session.add(wf)
        await setup_session.commit()

    provider = DeterministicSequenceAIProvider(
        [
            {
                "type": "TOOL_CALL",
                "tool_name": "rewrite_section",
                "tool_input": {
                    "block_id": "b1",
                    "text": "Enhanced Zero Trust Overview",
                },
                "reasoning_summary": "Propose section update",
            }
        ]
    )

    registry = ToolRegistry()
    executor = ToolExecutor(registry=registry)
    loop = AgentLoop(provider=provider, registry=registry, executor=executor)

    with patch("app.domains.projects.service.ProjectService.get_model", return_value=None):
        async with session_factory() as session1:
            wf_to_run = await session1.get(AIWorkflow, wf_id)
            assert wf_to_run is not None
            await loop.run(
                session1,
                actor=seed_data["actor"],
                workflow=wf_to_run,
                user_message="Propose section update",
            )

    async with session_factory() as session2:
        wf_persisted = await session2.get(AIWorkflow, wf_id)
        assert wf_persisted is not None
        assert wf_persisted.status == WorkflowStatus.WAITING_FOR_APPROVAL.value

        step_stmt = select(AIWorkflowStep).where(AIWorkflowStep.workflow_id == wf_id)
        step_res = await session2.execute(step_stmt)
        steps = step_res.scalars().all()
        assert len(steps) == 1
        step = steps[0]
        assert step.status == StepStatus.WAITING_FOR_APPROVAL.value
        proposal_id_str = step.output.get("proposal_id")
        assert proposal_id_str is not None

        proposal = await session2.get(AIEditProposal, UUID(proposal_id_str))
        assert proposal is not None
        assert proposal.status == ProposalStatus.PROPOSED.value
        assert proposal.document_id == seed_data["doc_id"]
        assert proposal.target_block_ids == ["b1"]
        assert proposal.operation_type == "replace_block"


# =========================================================================
# TEST 6: Rollback Atomicity on Checkpoint Failure
# =========================================================================
@pytest.mark.asyncio
async def test_rollback_atomicity_on_checkpoint_failure(
    session_factory: async_sessionmaker[AsyncSession],
    seed_data: dict[str, Any],
) -> None:
    """TEST 6: A failure within a checkpoint rolls back that checkpoint's partial writes

    while preserving previously committed checkpoints in PostgreSQL.
    """
    wf_id = uuid4()
    async with session_factory() as setup_session:
        wf = AIWorkflow(
            id=wf_id,
            organization_id=seed_data["org_id"],
            project_id=seed_data["proj_id"],
            document_id=seed_data["doc_id"],
            created_by_id=seed_data["actor"].user_id,
            intent=WorkflowIntent.EDIT_DOCUMENT.value,
            status=WorkflowStatus.PENDING.value,
            current_step=0,
            plan=[],
            result={"checkpoint_0": "seed"},
            token_usage={"total_tokens": 0},
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        setup_session.add(wf)
        await setup_session.commit()

    class CrashingAIProvider(AIProvider):
        async def generate(self, request: GenerationRequest) -> GenerationResult:
            raise RuntimeError("Intentional AI outage simulation")

        async def embed(self, texts: Sequence[str]) -> EmbeddingResult:
            return EmbeddingResult(
                vectors=[],
                provider="test",
                model="test",
                usage=Usage(input_tokens=0, output_tokens=0),
            )

    loop = AgentLoop(provider=CrashingAIProvider())
    with patch("app.domains.projects.service.ProjectService.get_model", return_value=None):
        async with session_factory() as session1:
            wf_to_run = await session1.get(AIWorkflow, wf_id)
            assert wf_to_run is not None
            res = await loop.run(
                session1,
                actor=seed_data["actor"],
                workflow=wf_to_run,
                user_message="Trigger crash",
            )
            assert res.status == WorkflowStatus.FAILED

    async with session_factory() as session2:
        wf_persisted = await session2.get(AIWorkflow, wf_id)
        assert wf_persisted is not None
        assert wf_persisted.status == WorkflowStatus.FAILED.value
        assert "Intentional AI outage simulation" in str(wf_persisted.error)

        step_stmt = select(AIWorkflowStep).where(AIWorkflowStep.workflow_id == wf_id)
        steps = (await session2.execute(step_stmt)).scalars().all()
        assert len(steps) == 0


# =========================================================================
# TEST 7: Provider Boundary Has NO Open Write Transaction
# =========================================================================
@pytest.mark.asyncio
async def test_provider_boundary_has_no_open_write_transaction(
    session_factory: async_sessionmaker[AsyncSession],
    seed_data: dict[str, Any],
) -> None:
    """TEST 7: Asserts that session.in_transaction() is FALSE during AIProvider.generate(),

    guaranteeing that no database write transaction or row lock is held across LLM calls.
    """
    wf_id = uuid4()
    async with session_factory() as setup_session:
        wf = AIWorkflow(
            id=wf_id,
            organization_id=seed_data["org_id"],
            project_id=seed_data["proj_id"],
            document_id=seed_data["doc_id"],
            created_by_id=seed_data["actor"].user_id,
            intent=WorkflowIntent.EDIT_DOCUMENT.value,
            status=WorkflowStatus.PENDING.value,
            current_step=0,
            plan=[],
            result={},
            token_usage={"total_tokens": 0},
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        setup_session.add(wf)
        await setup_session.commit()

    active_session_ref: AsyncSession | None = None
    transaction_status_during_generate: bool | None = None

    async def verify_tx_status_during_generate(call_num: int, req: GenerationRequest) -> None:
        nonlocal transaction_status_during_generate, active_session_ref
        assert active_session_ref is not None
        transaction_status_during_generate = active_session_ref.in_transaction()

    provider = DeterministicSequenceAIProvider(
        [
            {
                "type": "FINAL",
                "final_response": "Checked",
                "reasoning_summary": "Boundary verified",
            }
        ],
        on_generate_hook=verify_tx_status_during_generate,
    )

    loop = AgentLoop(provider=provider)
    with patch("app.domains.projects.service.ProjectService.get_model", return_value=None):
        async with session_factory() as session1:
            active_session_ref = session1
            wf_to_run = await session1.get(AIWorkflow, wf_id)
            assert wf_to_run is not None
            await loop.run(
                session1,
                actor=seed_data["actor"],
                workflow=wf_to_run,
                user_message="Verify boundary",
            )

    assert transaction_status_during_generate is False


# =========================================================================
# TEST 8: No Nested Transaction Regression on Service-Backed Tools
# =========================================================================
@pytest.mark.asyncio
async def test_no_nested_transaction_regression_service_backed_tools(
    session_factory: async_sessionmaker[AsyncSession],
    seed_data: dict[str, Any],
) -> None:
    """TEST 8: Executes seo_quality_check (a service-backed tool that uses its own

    transactional_session boundary) through ToolExecutor, verifying that the depth-tracking
    session model handles nested boundaries cleanly without InvalidRequestError.
    """
    wf_id = uuid4()
    step_id = uuid4()
    async with session_factory() as setup_session:
        wf = AIWorkflow(
            id=wf_id,
            organization_id=seed_data["org_id"],
            project_id=seed_data["proj_id"],
            document_id=seed_data["doc_id"],
            created_by_id=seed_data["actor"].user_id,
            intent=WorkflowIntent.ANALYZE_SEO.value,
            status=WorkflowStatus.RUNNING.value,
            current_step=0,
            plan=[],
            result={},
            token_usage={"total_tokens": 0},
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        step = AIWorkflowStep(
            id=step_id,
            workflow_id=wf_id,
            step_index=0,
            step_type="tool_call",
            tool_name="seo_quality_check",
            status=StepStatus.RUNNING.value,
            input={"document_id": str(seed_data["doc_id"])},
            output={},
        )
        setup_session.add_all([wf, step])
        await setup_session.commit()

    registry = ToolRegistry()
    executor = ToolExecutor(registry=registry)

    with patch("app.domains.projects.service.ProjectService.get_model", return_value=None):
        async with session_factory() as session1:
            result = await executor.execute(
                session1,
                actor=seed_data["actor"],
                workflow_id=wf_id,
                step_id=step_id,
                tool_name="seo_quality_check",
                arguments={"document_id": str(seed_data["doc_id"])},
                organization_id=seed_data["org_id"],
                project_id=seed_data["proj_id"],
                document_id=seed_data["doc_id"],
            )

    assert result.status == ToolExecutionStatus.SUCCESS
    assert "score_percentage" in result.result
    assert "checks" in result.result

    async with session_factory() as session2:
        exec_stmt = select(ToolExecutionRecord).where(ToolExecutionRecord.step_id == step_id)
        exec_record = (await session2.execute(exec_stmt)).scalars().first()
        assert exec_record is not None
        assert exec_record.status == ToolExecutionStatus.SUCCESS.value
        output_val = exec_record.output
        if isinstance(output_val, str):
            import ast

            try:
                output_val = json.loads(output_val)
            except Exception:
                output_val = ast.literal_eval(output_val)
        assert output_val.get("score_percentage") is not None


# =========================================================================
# TEST 9: Completion Persistence
# =========================================================================
@pytest.mark.asyncio
async def test_workflow_completion_persistence(
    session_factory: async_sessionmaker[AsyncSession],
    seed_data: dict[str, Any],
) -> None:
    """TEST 9: Terminal COMPLETED state, completed_at, and final result are

    durably written and verified in PostgreSQL across session boundaries.
    """
    wf_id = uuid4()
    async with session_factory() as setup_session:
        wf = AIWorkflow(
            id=wf_id,
            organization_id=seed_data["org_id"],
            project_id=seed_data["proj_id"],
            document_id=seed_data["doc_id"],
            created_by_id=seed_data["actor"].user_id,
            intent=WorkflowIntent.EDIT_DOCUMENT.value,
            status=WorkflowStatus.PENDING.value,
            current_step=0,
            plan=[],
            result={},
            token_usage={"total_tokens": 0},
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        setup_session.add(wf)
        await setup_session.commit()

    provider = DeterministicSequenceAIProvider(
        [
            {
                "type": "FINAL",
                "final_response": "Comprehensive task completed successfully",
                "reasoning_summary": "Task complete",
            }
        ]
    )

    loop = AgentLoop(provider=provider)
    with patch("app.domains.projects.service.ProjectService.get_model", return_value=None):
        async with session_factory() as session1:
            wf_to_run = await session1.get(AIWorkflow, wf_id)
            assert wf_to_run is not None
            res = await loop.run(
                session1,
                actor=seed_data["actor"],
                workflow=wf_to_run,
                user_message="Wrap up",
            )
            assert res.status == WorkflowStatus.COMPLETED

    async with session_factory() as session2:
        wf_persisted = await session2.get(AIWorkflow, wf_id)
        assert wf_persisted is not None
        assert wf_persisted.status == WorkflowStatus.COMPLETED.value
        assert wf_persisted.completed_at is not None
        assert wf_persisted.result.get("summary") == "Comprehensive task completed successfully"
        assert wf_persisted.token_usage is not None


# =========================================================================
# TEST 10: Failure Persistence
# =========================================================================
@pytest.mark.asyncio
async def test_workflow_failure_persistence(
    session_factory: async_sessionmaker[AsyncSession],
    seed_data: dict[str, Any],
) -> None:
    """TEST 10: Terminal FAILED state and error payload are durably written

    and verified in PostgreSQL across session boundaries.
    """
    wf_id = uuid4()
    async with session_factory() as setup_session:
        wf = AIWorkflow(
            id=wf_id,
            organization_id=seed_data["org_id"],
            project_id=seed_data["proj_id"],
            document_id=seed_data["doc_id"],
            created_by_id=seed_data["actor"].user_id,
            intent=WorkflowIntent.EDIT_DOCUMENT.value,
            status=WorkflowStatus.PENDING.value,
            current_step=0,
            plan=[],
            result={},
            token_usage={"total_tokens": 0},
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        setup_session.add(wf)
        await setup_session.commit()

    class ErrorProvider(AIProvider):
        async def generate(self, request: GenerationRequest) -> GenerationResult:
            raise ValueError("Downstream model endpoint connection reset")

        async def embed(self, texts: Sequence[str]) -> EmbeddingResult:
            return EmbeddingResult(
                vectors=[],
                provider="test",
                model="test",
                usage=Usage(input_tokens=0, output_tokens=0),
            )

    loop = AgentLoop(provider=ErrorProvider())
    with patch("app.domains.projects.service.ProjectService.get_model", return_value=None):
        async with session_factory() as session1:
            wf_to_run = await session1.get(AIWorkflow, wf_id)
            assert wf_to_run is not None
            res = await loop.run(
                session1,
                actor=seed_data["actor"],
                workflow=wf_to_run,
                user_message="Run to error",
            )
            assert res.status == WorkflowStatus.FAILED

    async with session_factory() as session2:
        wf_persisted = await session2.get(AIWorkflow, wf_id)
        assert wf_persisted is not None
        assert wf_persisted.status == WorkflowStatus.FAILED.value
        assert wf_persisted.completed_at is not None
        assert wf_persisted.error is not None
        assert "Downstream model endpoint connection reset" in str(wf_persisted.error)


def _workflow_for_seed(seed_data: dict[str, Any], workflow_id: UUID) -> AIWorkflow:
    return AIWorkflow(
        id=workflow_id,
        organization_id=seed_data["org_id"],
        project_id=seed_data["proj_id"],
        document_id=seed_data["doc_id"],
        created_by_id=seed_data["actor"].user_id,
        intent=WorkflowIntent.EDIT_DOCUMENT.value,
        status=WorkflowStatus.PENDING.value,
        current_step=0,
        plan=[],
        result={"user_message": "Inspect this document"},
        token_usage={"total_tokens": 0},
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )


@pytest.mark.asyncio
async def test_planner_uuid_jsonb_persists_in_new_session(session_factory, seed_data) -> None:
    """The production planner's UUID arguments must be JSON-safe at both storage sites."""
    classifier = IntentClassifier()
    planner = WorkflowPlanner()
    intent = classifier.classify("Inspect this document", document_id=seed_data["doc_id"])
    plan = planner.create_plan(
        intent_result=intent,
        user_message="Inspect this document",
        document_id=seed_data["doc_id"],
    )
    assert isinstance(plan[0].input_arguments["document_id"], UUID)
    nested_id = uuid4()
    plan[0].input_arguments["nested"] = {
        "ids": [nested_id],
        "when": datetime.now(UTC),
        "state": WorkflowStatus.PENDING,
        "model": plan[0].model_copy(update={"input_arguments": {"document_id": nested_id}}),
    }
    with patch("app.domains.projects.service.ProjectService.get_model", return_value=None):
        async with session_factory() as session:
            workflow = await WorkflowService().create_workflow(
                session,
                actor=seed_data["actor"],
                organization_id=seed_data["org_id"],
                project_id=seed_data["proj_id"],
                document_id=seed_data["doc_id"],
                intent=intent.intent,
                plan_steps=plan,
            )
            workflow_id = workflow.id
    async with session_factory() as verify:
        workflow = await verify.get(AIWorkflow, workflow_id)
        assert workflow is not None
        assert workflow.plan[0]["input_arguments"]["document_id"] == str(seed_data["doc_id"])
        steps = (
            (
                await verify.execute(
                    select(AIWorkflowStep).where(AIWorkflowStep.workflow_id == workflow_id)
                )
            )
            .scalars()
            .all()
        )
        assert steps
        assert steps[0].input["document_id"] == str(seed_data["doc_id"])
        assert steps[0].input["nested"]["ids"] == [str(nested_id)]
        assert steps[0].input["nested"]["state"] == WorkflowStatus.PENDING.value
        assert isinstance(steps[0].input["nested"]["model"], dict)
        json.dumps(workflow.plan)
        json.dumps(steps[0].input)


@pytest.mark.asyncio
async def test_explicit_parent_transaction_is_not_committed(session_factory, seed_data) -> None:
    caller_id, helper_id = uuid4(), uuid4()
    async with session_factory() as session:
        with pytest.raises(RuntimeError, match="outer failed"):
            async with session.begin():
                session.add(_workflow_for_seed(seed_data, caller_id))
                async with transactional_session(session):
                    session.add(_workflow_for_seed(seed_data, helper_id))
                    await session.flush()
                raise RuntimeError("outer failed")
    async with session_factory() as verify:
        assert await verify.get(AIWorkflow, caller_id) is None
        assert await verify.get(AIWorkflow, helper_id) is None


@pytest.mark.asyncio
async def test_autobegin_read_then_helper_commit(session_factory, seed_data) -> None:
    workflow_id = uuid4()
    async with session_factory() as session:
        assert await session.get(ContentDocument, seed_data["doc_id"]) is not None
        assert session.in_transaction()
        async with transactional_session(session):
            session.add(_workflow_for_seed(seed_data, workflow_id))
            await session.flush()
    async with session_factory() as verify:
        assert await verify.get(AIWorkflow, workflow_id) is not None


@pytest.mark.asyncio
async def test_nested_helper_commits_once_and_rolls_back_together(
    session_factory, seed_data
) -> None:
    success_ids = (uuid4(), uuid4())
    failed_ids = (uuid4(), uuid4())
    async with session_factory() as session:
        async with transactional_session(session):
            session.add(_workflow_for_seed(seed_data, success_ids[0]))
            async with transactional_session(session):
                session.add(_workflow_for_seed(seed_data, success_ids[1]))
        with pytest.raises(RuntimeError, match="checkpoint failed"):
            async with transactional_session(session):
                session.add(_workflow_for_seed(seed_data, failed_ids[0]))
                async with transactional_session(session):
                    session.add(_workflow_for_seed(seed_data, failed_ids[1]))
                    await session.flush()
                raise RuntimeError("checkpoint failed")
    async with session_factory() as verify:
        for workflow_id in success_ids:
            assert await verify.get(AIWorkflow, workflow_id) is not None
        for workflow_id in failed_ids:
            assert await verify.get(AIWorkflow, workflow_id) is None


@pytest.mark.asyncio
async def test_real_resume_has_durable_running_boundary(session_factory, seed_data) -> None:
    workflow_id = uuid4()
    async with session_factory() as setup:
        setup.add(_workflow_for_seed(seed_data, workflow_id))
        await setup.commit()

    observed: list[tuple[bool, str]] = []
    run_session: AsyncSession | None = None

    async def at_generate(call_num: int, request: GenerationRequest) -> None:
        assert run_session is not None
        async with session_factory() as verify:
            persisted = await verify.get(AIWorkflow, workflow_id)
            assert persisted is not None
            observed.append((run_session.in_transaction(), persisted.status))

    provider = DeterministicSequenceAIProvider(
        [{"type": "FINAL", "final_response": "Finished", "reasoning_summary": "Done"}],
        on_generate_hook=at_generate,
    )
    service = OrchestratorService(ai_provider=provider)
    with patch("app.domains.projects.service.ProjectService.get_model", return_value=None):
        async with session_factory() as session:
            run_session = session
            detail = await service.resume_workflow(
                session, actor=seed_data["actor"], workflow_id=workflow_id
            )
            assert detail.status == WorkflowStatus.COMPLETED
    assert observed == [(False, WorkflowStatus.RUNNING.value)]
    async with session_factory() as verify:
        persisted = await verify.get(AIWorkflow, workflow_id)
        assert persisted is not None and persisted.status == WorkflowStatus.COMPLETED.value
        assert persisted.result["summary"] == "Finished"


@pytest.mark.asyncio
async def test_agent_rejects_explicit_parent_without_commit(session_factory, seed_data) -> None:
    workflow_id, caller_id = uuid4(), uuid4()
    async with session_factory() as setup:
        setup.add(_workflow_for_seed(seed_data, workflow_id))
        await setup.commit()
    provider = DeterministicSequenceAIProvider([{"type": "FINAL", "final_response": "No call"}])
    async with session_factory() as session:
        with pytest.raises(RuntimeError, match="caller transaction"):
            async with session.begin():
                session.add(_workflow_for_seed(seed_data, caller_id))
                workflow = await session.get(AIWorkflow, workflow_id)
                assert workflow is not None
                await AgentLoop(provider=provider).run(
                    session, actor=seed_data["actor"], workflow=workflow, user_message="Inspect"
                )
    assert provider.call_count == 0
    async with session_factory() as verify:
        assert await verify.get(AIWorkflow, caller_id) is None


@pytest.mark.asyncio
async def test_early_context_failure_persists_failed(session_factory, seed_data) -> None:
    workflow_id = uuid4()
    async with session_factory() as setup:
        setup.add(_workflow_for_seed(seed_data, workflow_id))
        await setup.commit()

    class BrokenContextBuilder:
        async def build_agent_context(self, *args, **kwargs):
            raise RuntimeError("context lookup failed")

    async with session_factory() as session:
        workflow = await session.get(AIWorkflow, workflow_id)
        assert workflow is not None
        result = await AgentLoop(context_builder=BrokenContextBuilder()).run(
            session, actor=seed_data["actor"], workflow=workflow, user_message="Inspect"
        )
        assert result.status == WorkflowStatus.FAILED
    async with session_factory() as verify:
        persisted = await verify.get(AIWorkflow, workflow_id)
        assert persisted is not None and persisted.status == WorkflowStatus.FAILED.value
        assert "context lookup failed" in str(persisted.error)


@pytest.mark.asyncio
async def test_cancelled_agent_rolls_back_and_persists_failed(session_factory, seed_data) -> None:
    workflow_id = uuid4()
    async with session_factory() as setup:
        setup.add(_workflow_for_seed(seed_data, workflow_id))
        await setup.commit()
    started = asyncio.Event()
    keep_waiting = asyncio.Event()

    async def at_generate(call_num: int, request: GenerationRequest) -> None:
        started.set()
        await keep_waiting.wait()

    provider = DeterministicSequenceAIProvider([], on_generate_hook=at_generate)
    async with session_factory() as session:
        workflow = await session.get(AIWorkflow, workflow_id)
        assert workflow is not None
        with patch("app.domains.projects.service.ProjectService.get_model", return_value=None):
            task = asyncio.create_task(
                AgentLoop(provider=provider).run(
                    session, actor=seed_data["actor"], workflow=workflow, user_message="Inspect"
                )
            )
            await asyncio.wait_for(started.wait(), timeout=5)
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
        assert session.info.get("_tx_depth", 0) == 0
        assert not session.in_transaction()
        assert await session.get(ContentDocument, seed_data["doc_id"]) is not None
    async with session_factory() as verify:
        persisted = await verify.get(AIWorkflow, workflow_id)
        assert persisted is not None and persisted.status == WorkflowStatus.FAILED.value


@pytest.mark.asyncio
async def test_database_checkpoint_failure_rolls_back_partial_writes(
    session_factory, seed_data
) -> None:
    workflow_id, step_id = uuid4(), uuid4()
    async with session_factory() as setup:
        setup.add(_workflow_for_seed(seed_data, workflow_id))
        await setup.commit()
    async with session_factory() as session:
        with pytest.raises(DBAPIError):
            async with transactional_session(session):
                first = AIWorkflowStep(
                    id=step_id,
                    workflow_id=workflow_id,
                    step_index=0,
                    step_type="tool_call",
                    tool_name="read_document",
                    status=StepStatus.RUNNING.value,
                    input={},
                    output={},
                )
                session.add(first)
                await session.flush()
                workflow = await session.get(AIWorkflow, workflow_id)
                assert workflow is not None
                workflow.current_step = 5
                await session.flush()
                await session.execute(text("SELECT 1 / 0"))
        assert session.info.get("_tx_depth", 0) == 0
    async with session_factory() as verify:
        workflow = await verify.get(AIWorkflow, workflow_id)
        assert workflow is not None and workflow.current_step == 0
        assert await verify.get(AIWorkflowStep, step_id) is None


@pytest.mark.asyncio
async def test_real_tool_failure_record_survives_failed_workflow(
    session_factory, seed_data
) -> None:
    """A real handler error leaves a durable failed execution and failed step."""
    workflow_id = uuid4()
    async with session_factory() as setup:
        setup.add(_workflow_for_seed(seed_data, workflow_id))
        await setup.commit()

    async def fail_after_tool(call_num: int, request: GenerationRequest) -> None:
        if call_num == 2:
            raise RuntimeError("provider failed after tool error")

    provider = DeterministicSequenceAIProvider(
        [
            {
                "type": "TOOL_CALL",
                "tool_name": "read_section",
                "tool_input": {"document_id": str(seed_data["doc_id"]), "block_id": "missing"},
                "reasoning_summary": "Read a missing section",
            }
        ],
        on_generate_hook=fail_after_tool,
    )
    registry = ToolRegistry()
    loop = AgentLoop(
        provider=provider,
        registry=registry,
        executor=ToolExecutor(registry=registry),
    )
    with patch("app.domains.projects.service.ProjectService.get_model", return_value=None):
        async with session_factory() as session:
            workflow = await session.get(AIWorkflow, workflow_id)
            assert workflow is not None
            result = await loop.run(
                session, actor=seed_data["actor"], workflow=workflow, user_message="Read section"
            )
            assert result.status == WorkflowStatus.FAILED

    async with session_factory() as verify:
        workflow = await verify.get(AIWorkflow, workflow_id)
        assert workflow is not None and workflow.status == WorkflowStatus.FAILED.value
        steps = (
            (
                await verify.execute(
                    select(AIWorkflowStep).where(AIWorkflowStep.workflow_id == workflow_id)
                )
            )
            .scalars()
            .all()
        )
        assert len(steps) == 1 and steps[0].status == StepStatus.FAILED.value
        executions = (
            (
                await verify.execute(
                    select(ToolExecutionRecord).where(
                        ToolExecutionRecord.workflow_id == workflow_id
                    )
                )
            )
            .scalars()
            .all()
        )
        assert len(executions) == 1
        assert executions[0].status == ToolExecutionStatus.FAILED.value
        assert "missing" in str(executions[0].error).lower()
