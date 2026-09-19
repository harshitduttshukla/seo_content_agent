"""End-to-End integration test for Phase 6 AI Orchestrator flow."""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from app.domains.content.editor_models import (
    AIEditProposal,
    ContentDocument,
    ProposalStatus,
)
from app.domains.content.patch_service import DocumentPatchService
from app.domains.orchestrator.intent_classifier import IntentClassifier
from app.domains.orchestrator.models import (
    AIWorkflow,
    AIWorkflowStep,
    StepStatus,
    WorkflowIntent,
    WorkflowStatus,
)
from app.domains.orchestrator.planner import WorkflowPlanner
from app.domains.orchestrator.tool_executor import ToolExecutor
from app.domains.orchestrator.tool_registry import ToolRegistry
from app.domains.orchestrator.verification_service import VerificationService
from app.domains.orchestrator.workflow_service import WorkflowService
from app.domains.projects.models import Project
from app.security.principal import AuthenticatedUser


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
    session.add = MagicMock()
    return session


@pytest.fixture
def test_actor() -> AuthenticatedUser:
    return AuthenticatedUser(
        user_id=uuid4(),
        issuer="https://identity.example.com",
        subject="test-user-sub",
        email="e2e@example.com",
        display_name="E2E Tester",
    )


@pytest.mark.asyncio
async def test_orchestrator_e2e_flow(test_actor: AuthenticatedUser) -> None:
    session = make_mock_session()
    doc_id = uuid4()
    org_id = uuid4()
    proj_id = uuid4()
    page_id = uuid4()

    mock_project = Project(
        id=proj_id,
        organization_id=org_id,
        name="Security Architecture Project",
        slug="security-architecture",
    )

    mock_doc = ContentDocument(
        id=doc_id,
        organization_id=org_id,
        project_id=proj_id,
        page_id=page_id,
        title="Zero Trust Network Architecture",
        slug="zero-trust-architecture",
        status="DRAFT",
        current_version=1,
        lock_version=1,
        word_count=500,
        plain_text="Zero Trust Network Architecture Overview",
        content_blocks=[
            {
                "id": "b1",
                "type": "DOCUMENT_TITLE",
                "level": 1,
                "text": "Zero Trust Network Architecture",
            },
            {
                "id": "b2",
                "type": "PARAGRAPH",
                "text": "Zero trust architecture requires strict identity verification.",
            },
        ],
    )

    classifier = IntentClassifier()
    registry = ToolRegistry()
    planner = WorkflowPlanner(registry=registry)
    executor = ToolExecutor(registry=registry)
    patch_service = DocumentPatchService()
    verifier = VerificationService()
    workflow_service = WorkflowService(
        tool_executor=executor,
        tool_registry=registry,
        patch_service=patch_service,
        verification_service=verifier,
    )
    user_query = "Optimize this article and add relevant internal links."

    # 1. Test Intent Classification
    intent_res = classifier.classify(user_query, document_id=doc_id)
    assert intent_res.intent == WorkflowIntent.MULTI_STEP_CONTENT_TASK

    # 2. Test Planning
    plan = planner.create_plan(
        intent_result=intent_res,
        user_message=user_query,
        document_id=doc_id,
    )
    assert len(plan) >= 4
    assert plan[0].tool_name == "read_document"
    assert plan[-1].requires_approval is True

    # 3. Create and Initiate Workflow
    wf = AIWorkflow(
        id=uuid4(),
        organization_id=org_id,
        project_id=proj_id,
        document_id=doc_id,
        created_by_id=test_actor.user_id,
        intent=WorkflowIntent.MULTI_STEP_CONTENT_TASK.value,
        status=WorkflowStatus.PENDING.value,
        current_step=0,
        plan=[s.model_dump() for s in plan],
        result={},
        token_usage={},
    )

    steps = [
        AIWorkflowStep(
            id=uuid4(),
            workflow_id=wf.id,
            step_index=s.step_index,
            tool_name=s.tool_name,
            status=StepStatus.PENDING.value,
            input=s.input_arguments,
        )
        for s in plan
    ]

    proposal_id = uuid4()
    mock_proposal = AIEditProposal(
        id=proposal_id,
        document_id=doc_id,
        status=ProposalStatus.PROPOSED.value,
        operation_type="replace_block",
        target_block_ids=["b2"],
        proposed_content={"text": "Enhanced Zero Trust block with technical depth."},
        reason="Expanded with technical depth",
    )

    # Set up mock execute queries
    def mock_execute(statement, *args, **kwargs):
        stmt_str = str(statement).lower()
        mock_res = MagicMock()
        if "ai_workflows" in stmt_str:
            mock_res.scalars().first.return_value = wf
        elif "ai_workflow_steps" in stmt_str:
            mock_res.scalars().all.return_value = steps
            mock_res.scalars().first.return_value = steps[-1]
        elif "content_documents" in stmt_str:
            mock_res.scalars().first.return_value = mock_doc
        elif "ai_edit_proposals" in stmt_str:
            mock_res.scalars().first.return_value = mock_proposal
        else:
            mock_res.scalars().first.return_value = None
            mock_res.scalars().all.return_value = []
        return mock_res

    session.execute.side_effect = mock_execute

    with (
        patch("app.domains.projects.service.ProjectService.get_model", return_value=mock_project),
        patch("app.domains.audit.repository.AuditWriter.log_event", AsyncMock()) as mock_audit,
    ):
        # 4. Run workflow until approval gate
        wf_after_run = await workflow_service.run_workflow(
            session, actor=test_actor, workflow_id=wf.id
        )

        assert wf_after_run.status == WorkflowStatus.WAITING_FOR_APPROVAL.value
        # Check audit called
        assert mock_audit.called

        # 5. User Approves Step
        last_step = steps[-1]
        last_step.status = StepStatus.WAITING_FOR_APPROVAL.value
        last_step.output = {"proposal_id": str(proposal_id)}

        async def fake_apply(*args, **kwargs):
            mock_doc.current_version += 1
            mock_doc.content_blocks[1]["text"] = "Enhanced Zero Trust block with technical depth."

        with patch(
            "app.domains.content.patch_service.DocumentPatchService.apply_proposal",
            side_effect=fake_apply,
        ):
            approved_wf = await workflow_service.approve_step(
                session,
                actor=test_actor,
                workflow_id=wf.id,
                step_id=last_step.id,
            )

        # 6. Workflow Completed and Changes Verified
        assert approved_wf.status == WorkflowStatus.COMPLETED.value
        assert approved_wf.completed_at is not None
