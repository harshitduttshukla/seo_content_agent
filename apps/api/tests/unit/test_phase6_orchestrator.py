"""Unit tests for Phase 6 AI Orchestrator, Tool Registry, Tool Executor,

Intent Classifier, Planner, and Verification Service.
"""

from dataclasses import replace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from app.core.errors import PermissionDenied, ResourceNotFound
from app.domains.content.editor_models import (
    AIEditProposal,
    ContentDocument,
    ProposalStatus,
)
from app.domains.orchestrator.exceptions import (
    ToolNotFoundError,
    ToolPermissionDeniedError,
    VerificationFailedError,
)
from app.domains.orchestrator.intent_classifier import IntentClassifier
from app.domains.orchestrator.models import (
    AIWorkflow,
    AIWorkflowStep,
    StepStatus,
    ToolExecutionStatus,
    WorkflowIntent,
    WorkflowStatus,
)
from app.domains.orchestrator.planner import WorkflowPlanner
from app.domains.orchestrator.policies import ToolAvailability, ToolRiskLevel
from app.domains.orchestrator.schemas import WorkflowPlanStep
from app.domains.orchestrator.tool_executor import ToolExecutor
from app.domains.orchestrator.tool_registry import (
    ToolRegistry,
)
from app.domains.orchestrator.verification_service import VerificationService
from app.domains.orchestrator.workflow_service import WorkflowService
from app.security.principal import AuthenticatedUser, PermissionCode


def make_mock_session() -> MagicMock:
    session = MagicMock()
    context_manager = MagicMock()
    context_manager.__aenter__ = AsyncMock(return_value=session)
    context_manager.__aexit__ = AsyncMock(return_value=None)
    session.begin.return_value = context_manager
    session.in_transaction.return_value = False
    session.refresh = AsyncMock()
    session.flush = AsyncMock()
    session.execute = AsyncMock()
    session.scalar = AsyncMock()
    session.add = MagicMock()
    return session


@pytest.fixture
def test_actor() -> AuthenticatedUser:
    return AuthenticatedUser(
        user_id=uuid4(),
        issuer="https://identity.example.com",
        subject="test-user-sub",
        email="orchestrator-tester@example.com",
        display_name="Orchestrator Tester",
    )


# ---------------------------------------------------------------------------
# 1. Intent Classifier Tests
# ---------------------------------------------------------------------------


def test_intent_classifier_multi_step() -> None:
    classifier = IntentClassifier()
    res = classifier.classify("Optimize this article and add internal links")
    assert res.intent == WorkflowIntent.MULTI_STEP_CONTENT_TASK
    assert res.confidence >= 0.90
    assert res.requires_tools is True
    assert res.parameters.get("has_seo") is True
    assert res.parameters.get("has_linking") is True


def test_intent_classifier_seo_check() -> None:
    classifier = IntentClassifier()
    res = classifier.classify("Run a complete SEO quality check and audit")
    assert res.intent == WorkflowIntent.ANALYZE_SEO
    assert res.confidence >= 0.90


def test_intent_classifier_internal_linking() -> None:
    classifier = IntentClassifier()
    res = classifier.classify("Find approved internal link opportunities for this page")
    assert res.intent == WorkflowIntent.FIND_INTERNAL_LINKS


def test_intent_classifier_outline() -> None:
    classifier = IntentClassifier()
    res = classifier.classify("Generate a section outline with headings")
    assert res.intent == WorkflowIntent.GENERATE_OUTLINE


def test_intent_classifier_metadata() -> None:
    classifier = IntentClassifier()
    res = classifier.classify("Audit the meta title and meta description")
    assert res.intent == WorkflowIntent.OPTIMIZE_METADATA


def test_intent_classifier_research_and_content() -> None:
    classifier = IntentClassifier()
    res_topic = classifier.classify("Research topic cluster entities and keywords")
    assert res_topic.intent == WorkflowIntent.RESEARCH_TOPIC

    res_content = classifier.classify("Check word count and keyword density")
    assert res_content.intent == WorkflowIntent.ANALYZE_CONTENT


def test_intent_classifier_default_edit() -> None:
    classifier = IntentClassifier()
    res = classifier.classify("Make this introduction more concise", selected_block_ids=["b_01"])
    assert res.intent == WorkflowIntent.EDIT_DOCUMENT
    assert res.parameters.get("target_blocks") == ["b_01"]


# ---------------------------------------------------------------------------
# 2. Tool Registry Tests
# ---------------------------------------------------------------------------


def test_tool_registry_contains_initial_tools() -> None:
    registry = ToolRegistry()
    tools = registry.list_tools()
    tool_names = {t.name for t in tools}

    expected_tools = {
        "read_document",
        "read_section",
        "rewrite_section",
        "expand_section",
        "shorten_section",
        "generate_outline",
        "seo_quality_check",
        "keyword_check",
        "metadata_check",
        "find_link_opportunities",
        "suggest_internal_links",
        "insert_internal_link",
        "get_page_relationships",
        "get_related_pages",
    }
    assert expected_tools.issubset(tool_names)


def test_tool_registry_risk_and_permission() -> None:
    registry = ToolRegistry()

    read_doc = registry.get("read_document")
    assert read_doc.risk_level == ToolRiskLevel.READ
    assert read_doc.required_permission == PermissionCode.CONTENT_READ

    insert_link = registry.get("insert_internal_link")
    assert insert_link.risk_level == ToolRiskLevel.WRITE
    assert insert_link.required_permission == PermissionCode.CONTENT_WRITE

    seo_tool = registry.get("seo_quality_check")
    assert seo_tool.risk_level == ToolRiskLevel.READ
    assert seo_tool.required_permission == PermissionCode.SEO_READ


def test_every_tool_has_complete_contract_metadata() -> None:
    tools = ToolRegistry().list_tools()

    assert len(tools) == 14
    for tool in tools:
        assert tool.name
        assert tool.description
        assert tool.input_schema.model_json_schema()["type"] == "object"
        assert tool.output_schema.model_json_schema()["type"] == "object"
        assert tool.authentication_requirements
        assert tool.permissions == (tool.required_permission,)
        assert tool.cost.estimated_usd_per_call >= 0
        assert tool.cost.billing_unit
        assert tool.rate_limits.max_calls_per_workflow > 0
        assert tool.rate_limits.max_concurrent_calls > 0
        assert tool.availability.value == "AVAILABLE"
        assert tool.version == "1.0.0"


def test_tool_registry_unknown_tool_raises() -> None:
    registry = ToolRegistry()
    with pytest.raises(ToolNotFoundError):
        registry.get("non_existent_tool_123")


def test_tool_registry_rejects_unavailable_tool() -> None:
    registry = ToolRegistry()
    unavailable = replace(
        registry.get("read_document"),
        name="unavailable_read_document",
        availability=ToolAvailability.UNAVAILABLE,
    )
    registry.register(unavailable)

    with pytest.raises(ToolNotFoundError):
        registry.get(unavailable.name)


# ---------------------------------------------------------------------------
# 3. Workflow Planner Tests
# ---------------------------------------------------------------------------


def test_planner_multi_step_workflow() -> None:
    planner = WorkflowPlanner()
    classifier = IntentClassifier()
    doc_id = uuid4()

    intent_res = classifier.classify("Optimize this article and add internal links")
    plan = planner.create_plan(
        intent_result=intent_res,
        user_message="Optimize this article and add internal links",
        document_id=doc_id,
        selected_block_ids=["block_10"],
    )

    assert len(plan) >= 4
    tool_sequence = [s.tool_name for s in plan]
    assert tool_sequence[0] == "read_document"
    assert "seo_quality_check" in tool_sequence
    assert "find_link_opportunities" in tool_sequence

    # The last write step must require approval
    write_step = plan[-1]
    assert write_step.requires_approval is True
    assert write_step.risk_level == ToolRiskLevel.WRITE


def test_planner_simple_edit_workflow() -> None:
    planner = WorkflowPlanner()
    classifier = IntentClassifier()
    doc_id = uuid4()

    intent_res = classifier.classify("Make this section shorter")
    plan = planner.create_plan(
        intent_result=intent_res,
        user_message="Make this section shorter",
        document_id=doc_id,
        selected_block_ids=["b_99"],
    )

    assert len(plan) == 2
    assert plan[0].tool_name == "read_document"
    assert plan[1].tool_name == "shorten_section"
    assert plan[1].requires_approval is True


# ---------------------------------------------------------------------------
# 4. Tool Executor Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_tool_executor_unknown_tool(test_actor: AuthenticatedUser) -> None:
    session = make_mock_session()
    executor = ToolExecutor()

    with pytest.raises(ToolNotFoundError):
        await executor.execute(
            session,
            tool_name="unregistered_tool",
            arguments={},
            actor=test_actor,
            workflow_id=uuid4(),
            step_id=uuid4(),
            organization_id=uuid4(),
            project_id=uuid4(),
            document_id=uuid4(),
        )


@pytest.mark.asyncio
async def test_tool_executor_permission_denied(test_actor: AuthenticatedUser) -> None:
    session = make_mock_session()
    executor = ToolExecutor()

    with (
        patch(
            "app.domains.projects.service.ProjectService.get_model",
            side_effect=PermissionDenied("Missing content.write"),
        ),
        pytest.raises(ToolPermissionDeniedError),
    ):
        await executor.execute(
            session,
            tool_name="rewrite_section",
            arguments={"block_id": "b1"},
            actor=test_actor,
            workflow_id=uuid4(),
            step_id=uuid4(),
            organization_id=uuid4(),
            project_id=uuid4(),
            document_id=uuid4(),
        )


@pytest.mark.asyncio
async def test_tool_executor_cross_tenant_rejection(
    test_actor: AuthenticatedUser,
) -> None:
    session = make_mock_session()
    executor = ToolExecutor()
    proj_id = uuid4()
    org_id = uuid4()
    wrong_proj_id = uuid4()
    doc_id = uuid4()

    mock_doc = ContentDocument(
        id=doc_id,
        organization_id=org_id,
        project_id=wrong_proj_id,  # Mismatch
        page_id=uuid4(),
        title="Mismatch Doc",
    )
    mock_res = MagicMock()
    mock_res.scalars().first.return_value = mock_doc
    session.execute.return_value = mock_res

    with (
        patch("app.domains.projects.service.ProjectService.get_model", return_value=None),
        pytest.raises(ResourceNotFound),
    ):
        await executor.execute(
            session,
            tool_name="read_document",
            arguments={"document_id": doc_id},
            actor=test_actor,
            workflow_id=uuid4(),
            step_id=uuid4(),
            organization_id=org_id,
            project_id=proj_id,
            document_id=doc_id,
        )


@pytest.mark.asyncio
async def test_tool_executor_successful_read(test_actor: AuthenticatedUser) -> None:
    session = make_mock_session()
    executor = ToolExecutor()
    proj_id = uuid4()
    org_id = uuid4()
    doc_id = uuid4()

    mock_doc = ContentDocument(
        id=doc_id,
        organization_id=org_id,
        project_id=proj_id,
        page_id=uuid4(),
        title="Zero Trust Architecture",
        slug="zero-trust",
        word_count=500,
        current_version=1,
        content_blocks=[{"id": "b1", "type": "PARAGRAPH", "text": "Hello world"}],
    )
    mock_res = MagicMock()
    mock_res.scalars().first.return_value = mock_doc
    session.execute.return_value = mock_res

    with (
        patch("app.domains.projects.service.ProjectService.get_model", return_value=None),
        patch("app.domains.audit.repository.AuditWriter.log_event", AsyncMock()),
    ):
        result = await executor.execute(
            session,
            tool_name="read_document",
            arguments={"document_id": doc_id},
            actor=test_actor,
            workflow_id=uuid4(),
            step_id=uuid4(),
            organization_id=org_id,
            project_id=proj_id,
            document_id=doc_id,
        )

    assert result.status == ToolExecutionStatus.SUCCESS
    assert result.result["title"] == "Zero Trust Architecture"
    assert result.result["word_count"] == 500


# ---------------------------------------------------------------------------
# 5. Verification Service Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_verification_service_success() -> None:
    session = make_mock_session()
    verifier = VerificationService()
    doc_id = uuid4()

    proposal = AIEditProposal(
        id=uuid4(),
        document_id=doc_id,
        operation_type="replace_block",
        target_block_ids=["b1"],
        status=ProposalStatus.PROPOSED.value,
    )

    mock_doc = ContentDocument(
        id=doc_id,
        current_version=2,
        content_blocks=[{"id": "b1", "text": "Updated content"}],
    )
    mock_res = MagicMock()
    mock_res.scalars().first.return_value = mock_doc
    session.execute.return_value = mock_res

    verified = await verifier.verify_patch_applied(
        session,
        document_id=doc_id,
        proposal=proposal,
        expected_version=2,
    )
    assert verified is True


@pytest.mark.asyncio
async def test_verification_service_missing_block_raises() -> None:
    session = make_mock_session()
    verifier = VerificationService()
    doc_id = uuid4()

    proposal = AIEditProposal(
        id=uuid4(),
        document_id=doc_id,
        operation_type="replace_block",
        target_block_ids=["b_missing"],
        status=ProposalStatus.PROPOSED.value,
    )

    mock_doc = ContentDocument(
        id=doc_id,
        current_version=2,
        content_blocks=[{"id": "b1", "text": "Unrelated content"}],
    )
    mock_res = MagicMock()
    mock_res.scalars().first.return_value = mock_doc
    session.execute.return_value = mock_res

    with pytest.raises(VerificationFailedError):
        await verifier.verify_patch_applied(
            session,
            document_id=doc_id,
            proposal=proposal,
            expected_version=2,
        )


# ---------------------------------------------------------------------------
# 6. Workflow Service Tests (State Machine & Approval Gate)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_workflow_halts_at_approval_gate(test_actor: AuthenticatedUser) -> None:
    session = make_mock_session()
    workflow_service = WorkflowService()
    doc_id = uuid4()
    org_id = uuid4()
    proj_id = uuid4()

    plan_steps = [
        WorkflowPlanStep(
            step_index=0,
            tool_name="read_document",
            description="Read document",
            risk_level=ToolRiskLevel.READ,
            requires_approval=False,
            input_arguments={"document_id": doc_id},
        ),
        WorkflowPlanStep(
            step_index=1,
            tool_name="rewrite_section",
            description="Rewrite section (requires approval)",
            risk_level=ToolRiskLevel.WRITE,
            requires_approval=True,
            input_arguments={"document_id": doc_id, "block_id": "b1"},
        ),
    ]

    with (
        patch("app.domains.projects.service.ProjectService.get_model", return_value=None),
        patch("app.domains.audit.repository.AuditWriter.log_event", AsyncMock()),
    ):
        wf = await workflow_service.create_workflow(
            session,
            actor=test_actor,
            organization_id=org_id,
            project_id=proj_id,
            document_id=doc_id,
            intent=WorkflowIntent.EDIT_DOCUMENT,
            plan_steps=plan_steps,
        )

    assert wf.status == WorkflowStatus.PENDING.value
    assert wf.current_step == 0

    # Mock execute for step 0 (read_document)
    mock_doc = ContentDocument(
        id=doc_id,
        organization_id=org_id,
        project_id=proj_id,
        page_id=uuid4(),
        title="Test Doc",
        content_blocks=[{"id": "b1", "text": "Original text"}],
    )
    mock_doc_res = MagicMock()
    mock_doc_res.scalars().first.return_value = mock_doc

    mock_wf_res = MagicMock()
    mock_wf_res.scalars().first.return_value = wf

    step0 = AIWorkflowStep(
        workflow_id=wf.id,
        step_index=0,
        tool_name="read_document",
        status=StepStatus.PENDING.value,
        input={"document_id": doc_id},
    )
    step1 = AIWorkflowStep(
        workflow_id=wf.id,
        step_index=1,
        tool_name="rewrite_section",
        status=StepStatus.PENDING.value,
        input={"document_id": doc_id, "block_id": "b1"},
    )
    mock_steps_res = MagicMock()
    mock_steps_res.scalars().all.return_value = [step0, step1]

    def mock_execute_side_effect(statement, *args, **kwargs):
        stmt_str = str(statement).lower()
        mock_result = MagicMock()
        if "ai_workflows" in stmt_str:
            mock_result.scalars().first.return_value = wf
        elif "ai_workflow_steps" in stmt_str:
            mock_result.scalars().all.return_value = [step0, step1]
        elif "content_documents" in stmt_str:
            mock_result.scalars().first.return_value = mock_doc
        else:
            mock_result.scalars().first.return_value = None
            mock_result.scalars().all.return_value = []
        return mock_result

    session.execute.side_effect = mock_execute_side_effect

    with (
        patch("app.domains.projects.service.ProjectService.get_model", return_value=None),
        patch("app.domains.audit.repository.AuditWriter.log_event", AsyncMock()),
    ):
        updated_wf = await workflow_service.run_workflow(
            session,
            actor=test_actor,
            workflow_id=wf.id,
        )

    # Workflow must have stopped at approval gate
    assert updated_wf.status == WorkflowStatus.WAITING_FOR_APPROVAL.value
    assert updated_wf.current_step == 1
    assert step0.status == StepStatus.COMPLETED.value
    assert step1.status == StepStatus.WAITING_FOR_APPROVAL.value
    assert "proposal_id" in (step1.output or {})


@pytest.mark.asyncio
async def test_workflow_cancellation(test_actor: AuthenticatedUser) -> None:
    session = make_mock_session()
    workflow_service = WorkflowService()
    wf_id = uuid4()

    mock_wf = AIWorkflow(
        id=wf_id,
        organization_id=uuid4(),
        project_id=uuid4(),
        document_id=uuid4(),
        status=WorkflowStatus.WAITING_FOR_APPROVAL.value,
        current_step=1,
        plan=[],
        result={},
        token_usage={},
    )
    mock_res = MagicMock()
    mock_res.scalars().first.return_value = mock_wf

    mock_steps = MagicMock()
    mock_steps.scalars().all.return_value = []
    session.execute.side_effect = [mock_res, mock_steps]

    with (
        patch("app.domains.projects.service.ProjectService.get_model", return_value=None),
        patch("app.domains.audit.repository.AuditWriter.log_event", AsyncMock()),
    ):
        cancelled = await workflow_service.cancel_workflow(
            session,
            actor=test_actor,
            workflow_id=wf_id,
            reason="Change of plan",
        )

    assert cancelled.status == WorkflowStatus.CANCELLED.value
    assert cancelled.error == {"cancellation_reason": "Change of plan"}
