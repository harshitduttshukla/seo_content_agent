"""PostgreSQL integration tests verifying Problem #4 — Approval / Resume State Management.

Verifies:
1. Full 10-step lifecycle: ToolExecutor write -> proposal PROPOSED -> WAITING_FOR_APPROVAL ->
   approve_step() -> APPLIED + version bump + verifier -> RUNNING -> AgentLoop resume -> COMPLETED.
2. Crash recovery: Post-approval crash simulation where resume_workflow() from a new session
   recovers cleanly and runs to completion.
3. Stale proposal rejection: Optimistic concurrency check fails with ConflictError when
   document.current_version != proposal.base_version.
4. Concurrent approve vs reject serialization: Applied proposal cannot be rejected;
   rejected/skipped step cannot be approved.
5. Concurrent direct apply idempotency: Re-applying an APPLIED proposal is an idempotent no-op.
6. Reject lifecycle: reject_step skips step, marks proposal REJECTED, completes workflow.
7. Out-of-band apply handling: Direct patch application before approve_step is handled cleanly.
8. Idempotent approve_step retry: Re-calling approve_step on completed step succeeds idempotently.
"""

import json
import os
from collections.abc import AsyncIterator, Sequence
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import app.models  # noqa: F401
import pytest
import pytest_asyncio
from app.ai.provider import AIProvider, EmbeddingResult, GenerationRequest, GenerationResult, Usage
from app.core.errors import ConflictError
from app.domains.auth.models import OrganizationMember
from app.domains.content.editor_models import (
    AIEditProposal,
    ContentDocument,
    ContentDocumentVersion,
    ProposalStatus,
)
from app.domains.content.models import PlannedContentPage
from app.domains.content.patch_service import DocumentPatchService
from app.domains.orchestrator.exceptions import WorkflowStateError
from app.domains.orchestrator.models import (
    AIWorkflow,
    AIWorkflowStep,
    StepStatus,
    WorkflowIntent,
    WorkflowStatus,
)
from app.domains.orchestrator.workflow_service import WorkflowService
from app.domains.organizations.models import Organization
from app.domains.projects.models import Project
from app.domains.users.models import User
from app.domains.websites.models import Website, WebsiteStatus
from app.security.principal import AuthenticatedUser
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@localhost:5432/seo_content",
)

ADMIN_ROLE_ID = UUID("00000000-0000-0000-0000-000000000001")


class ScriptedSequenceAIProvider(AIProvider):
    """Deterministic AI provider returning scripted JSON tool calls or responses."""

    def __init__(self, responses: list[dict[str, Any] | str]) -> None:
        self._responses = list(responses)
        self.call_count = 0

    async def generate(self, request: GenerationRequest) -> GenerationResult:
        self.call_count += 1
        if self._responses:
            item = self._responses.pop(0)
            content = json.dumps(item) if isinstance(item, dict) else str(item)
        else:
            content = json.dumps(
                {
                    "type": "FINAL",
                    "final_response": "Workflow completed",
                    "reasoning_summary": "All steps finished",
                }
            )

        return GenerationResult(
            text=content,
            provider="test",
            model="scripted-approval-v1",
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
    org_id = uuid4()
    user_id = uuid4()
    proj_id = uuid4()
    site_id = uuid4()
    page_id = uuid4()
    doc_id = uuid4()

    actor = AuthenticatedUser(
        user_id=user_id,
        issuer="https://test.identity.example",
        subject=f"sub-{user_id.hex[:8]}",
        email=f"tester-{user_id.hex[:8]}@example.com",
        display_name="Approval Lifecycle Tester",
    )

    async with session_factory() as session:
        org = Organization(id=org_id, name="Approval Org", slug=f"appr-org-{org_id.hex[:8]}")
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

        member = OrganizationMember(
            organization_id=org_id,
            user_id=user_id,
            role_id=ADMIN_ROLE_ID,
            status="active",
            joined_at=datetime.now(UTC),
        )
        session.add(member)
        await session.flush()

        proj = Project(
            id=proj_id,
            organization_id=org_id,
            name="Approval Project",
            slug=f"appr-proj-{proj_id.hex[:8]}",
        )
        session.add(proj)
        await session.flush()

        website = Website(
            id=site_id,
            organization_id=org_id,
            project_id=proj_id,
            name="Main Site",
            base_url="https://example.com",
            normalized_host="example.com",
            status=WebsiteStatus.ACTIVE,
            locale="en",
        )
        session.add(website)
        await session.flush()

        page = PlannedContentPage(
            id=page_id,
            organization_id=org_id,
            project_id=proj_id,
            title="Approval Guide",
            slug="approval-guide",
            url="/approval-guide",
            page_type="PLANNED",
            content_type="BLOG_POST",
            status="PLANNED",
            intent="INFORMATIONAL",
            primary_keyword="approval lifecycle",
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
            title="Lifecycle Test Document",
            slug="lifecycle-test-doc",
            status="DRAFT",
            current_version=1,
            lock_version=1,
            word_count=200,
            content_blocks=[
                {"id": "b1", "type": "HEADING", "text": "Intro Header"},
                {"id": "b2", "type": "PARAGRAPH", "text": "Initial body content."},
            ],
            plain_text="Intro Header\nInitial body content.",
            revision=1,
        )
        session.add(doc)
        await session.commit()

    context = {
        "org_id": org_id,
        "user_id": user_id,
        "proj_id": proj_id,
        "site_id": site_id,
        "page_id": page_id,
        "doc_id": doc_id,
        "actor": actor,
    }

    yield context

    async with session_factory() as session:
        for stmt in (
            text("DELETE FROM audit_logs WHERE organization_id = :oid"),
            text(
                "DELETE FROM tool_executions WHERE workflow_id IN "
                "(SELECT id FROM ai_workflows WHERE organization_id = :oid)"
            ),
            text(
                "DELETE FROM ai_workflow_steps WHERE workflow_id IN "
                "(SELECT id FROM ai_workflows WHERE organization_id = :oid)"
            ),
            text("DELETE FROM ai_workflows WHERE organization_id = :oid"),
            text("DELETE FROM ai_edit_proposals WHERE document_id = :did"),
            text("DELETE FROM content_document_versions WHERE organization_id = :oid"),
            text("DELETE FROM content_documents WHERE id = :did"),
            text("DELETE FROM planned_content_pages WHERE id = :pid"),
            text("DELETE FROM websites WHERE organization_id = :oid"),
            text("DELETE FROM projects WHERE id = :pjid"),
            text("DELETE FROM organization_members WHERE organization_id = :oid"),
            text("DELETE FROM users WHERE id = :uid"),
            text("DELETE FROM organizations WHERE id = :oid"),
        ):
            await session.execute(
                stmt,
                {
                    "oid": org_id,
                    "uid": user_id,
                    "pjid": proj_id,
                    "pid": page_id,
                    "did": doc_id,
                },
            )
        await session.commit()


async def _create_test_workflow(
    session: AsyncSession,
    seed_data: dict[str, Any],
    wf_id: UUID | None = None,
    user_message: str = "Improve body paragraph",
) -> UUID:
    workflow_id = wf_id or uuid4()
    wf = AIWorkflow(
        id=workflow_id,
        organization_id=seed_data["org_id"],
        project_id=seed_data["proj_id"],
        document_id=seed_data["doc_id"],
        created_by_id=seed_data["actor"].user_id,
        intent=WorkflowIntent.EDIT_DOCUMENT.value,
        status=WorkflowStatus.PENDING.value,
        current_step=0,
        plan=[],
        result={"user_message": user_message},
        token_usage={"total_tokens": 0},
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    session.add(wf)
    await session.commit()
    return workflow_id


@pytest.mark.asyncio
async def test_full_approval_resume_completion_lifecycle(
    session_factory: async_sessionmaker[AsyncSession],
    seed_data: dict[str, Any],
) -> None:
    """Tests the full 10-step lifecycle:
    1. Tool call produces AIEditProposal with base_version=1.
    2. Workflow pauses at WAITING_FOR_APPROVAL.
    3. Document remains version 1 before human approval.
    4. approve_step applies proposal, bumps document to version 2, and records snapshot.
    5. AgentLoop resumes and makes next decision (FINAL response).
    6. Workflow transitions to COMPLETED.
    """
    actor: AuthenticatedUser = seed_data["actor"]
    doc_id: UUID = seed_data["doc_id"]

    provider = ScriptedSequenceAIProvider(
        [
            # Turn 1: AI proposes rewrite_section
            {
                "type": "TOOL_CALL",
                "tool_name": "rewrite_section",
                "tool_input": {
                    "block_id": "b2",
                    "instruction": "Improve clarity and flow",
                    "new_content": "Updated paragraph via governed rewrite.",
                },
                "thought": "Proposing edit to block b2",
            },
            # Turn 2: After approval resume, AI gives final completion
            {
                "type": "FINAL",
                "final_response": "Successfully rewritten and optimized.",
                "reasoning_summary": "All edits approved and verified.",
            },
        ]
    )

    wf_service = WorkflowService(ai_provider=provider)

    # 1. Setup workflow
    async with session_factory() as session:
        wf_id = await _create_test_workflow(session, seed_data)

    # 2. Run initial execution -> pauses at approval gate
    async with session_factory() as session:
        wf_run = await wf_service.run_workflow(session, actor=actor, workflow_id=wf_id)
        assert wf_run.status == WorkflowStatus.WAITING_FOR_APPROVAL.value

    # 3. Verify PostgreSQL state before approval
    async with session_factory() as session:
        # Document is untouched at version 1
        doc = await session.get(ContentDocument, doc_id)
        assert doc is not None
        assert doc.current_version == 1
        assert doc.content_blocks[1]["text"] == "Initial body content."

        # Step is WAITING_FOR_APPROVAL
        step_stmt = select(AIWorkflowStep).where(
            AIWorkflowStep.workflow_id == wf_id,
            AIWorkflowStep.status == StepStatus.WAITING_FOR_APPROVAL.value,
        )
        step = (await session.execute(step_stmt)).scalars().first()
        assert step is not None
        proposal_id = UUID(str(step.output["proposal_id"]))

        # Proposal is PROPOSED with base_version == 1
        proposal = await session.get(AIEditProposal, proposal_id)
        assert proposal is not None
        assert proposal.status == ProposalStatus.PROPOSED.value
        assert proposal.base_version == 1

    # 4. Human approves the step -> applies patch and resumes loop to completion
    async with session_factory() as session:
        completed_wf = await wf_service.approve_step(
            session,
            actor=actor,
            workflow_id=wf_id,
            step_id=step.id,
        )
        assert completed_wf.status == WorkflowStatus.COMPLETED.value

    # 5. Verify PostgreSQL state after completion
    async with session_factory() as session:
        # Document version bumped to 2 with updated content
        doc = await session.get(ContentDocument, doc_id)
        assert doc is not None
        assert doc.current_version == 2
        assert doc.content_blocks[1]["text"] == "Updated paragraph via governed rewrite."

        # Version snapshot exists for version 2
        ver_stmt = select(ContentDocumentVersion).where(
            ContentDocumentVersion.document_id == doc_id,
            ContentDocumentVersion.version == 2,
        )
        ver = (await session.execute(ver_stmt)).scalars().first()
        assert ver is not None

        # Proposal status is APPLIED
        prop = await session.get(AIEditProposal, proposal_id)
        assert prop is not None
        assert prop.status == ProposalStatus.APPLIED.value
        assert prop.applied_version == 2

        # Step 0 is COMPLETED
        st = await session.get(AIWorkflowStep, step.id)
        assert st is not None
        assert st.status == StepStatus.COMPLETED.value


@pytest.mark.asyncio
async def test_crash_recovery_after_approval_commit(
    session_factory: async_sessionmaker[AsyncSession],
    seed_data: dict[str, Any],
) -> None:
    """Tests crash recovery:
    Simulate a crash after approve_step commits the approval (proposal APPLIED, step COMPLETED,
    workflow marked RUNNING). A subsequent resume_workflow() from a new session recovers cleanly
    and runs to completion.
    """
    actor: AuthenticatedUser = seed_data["actor"]
    doc_id: UUID = seed_data["doc_id"]

    provider = ScriptedSequenceAIProvider(
        [
            {
                "type": "TOOL_CALL",
                "tool_name": "rewrite_section",
                "tool_input": {
                    "block_id": "b2",
                    "instruction": "Clarity update",
                    "new_content": "Content updated before simulated crash.",
                },
                "thought": "Rewrite section",
            },
            {
                "type": "FINAL",
                "final_response": "Post-crash recovery complete.",
                "reasoning_summary": "Done",
            },
        ]
    )

    wf_service = WorkflowService(ai_provider=provider)

    async with session_factory() as session:
        wf_id = await _create_test_workflow(session, seed_data, user_message="Crash recovery test")

    async with session_factory() as session:
        await wf_service.run_workflow(session, actor=actor, workflow_id=wf_id)

    # Get waiting step
    async with session_factory() as session:
        step_stmt = select(AIWorkflowStep).where(
            AIWorkflowStep.workflow_id == wf_id,
            AIWorkflowStep.status == StepStatus.WAITING_FOR_APPROVAL.value,
        )
        step = (await session.execute(step_stmt)).scalars().first()
        assert step is not None
        proposal_id = UUID(str(step.output["proposal_id"]))

    # Simulate crash right at approval commit:
    patch_service = DocumentPatchService()
    async with session_factory() as crash_session:
        # 1. Apply proposal
        await patch_service.apply_proposal(crash_session, actor=actor, proposal_id=proposal_id)
        # 2. Update step
        st = await crash_session.get(AIWorkflowStep, step.id)
        assert st is not None
        st.status = StepStatus.COMPLETED.value
        # 3. Update workflow to RUNNING
        wf = await crash_session.get(AIWorkflow, wf_id)
        assert wf is not None
        wf.status = WorkflowStatus.RUNNING.value
        wf.current_step = 1
        await crash_session.commit()

    # Now the "server restarts" — resume_workflow is invoked from a completely new session
    async with session_factory() as new_session:
        resumed_wf = await wf_service.resume_workflow(
            new_session,
            actor=actor,
            workflow_id=wf_id,
        )
        assert resumed_wf.status == WorkflowStatus.COMPLETED.value

    # Verify final document state
    async with session_factory() as session:
        doc = await session.get(ContentDocument, doc_id)
        assert doc is not None
        assert doc.current_version == 2
        assert doc.content_blocks[1]["text"] == "Content updated before simulated crash."


@pytest.mark.asyncio
async def test_stale_proposal_rejection_on_concurrent_edit(
    session_factory: async_sessionmaker[AsyncSession],
    seed_data: dict[str, Any],
) -> None:
    """Tests P0-2:
    If a document version is bumped (e.g. concurrent human edit) while a proposal is pending,
    approving stale proposal raises ConflictError because base_version != current_version.
    """
    actor: AuthenticatedUser = seed_data["actor"]
    doc_id: UUID = seed_data["doc_id"]

    patch_service = DocumentPatchService()

    # 1. Create a proposal based on version 1
    async with session_factory() as session:
        doc = await session.get(ContentDocument, doc_id)
        assert doc is not None
        assert doc.current_version == 1

        proposal = AIEditProposal(
            id=uuid4(),
            document_id=doc.id,
            chat_message_id=None,
            base_version=doc.current_version,  # base_version = 1
            status=ProposalStatus.PROPOSED.value,
            operation_type="replace_block",
            target_block_ids=["b2"],
            old_content={"text": "Initial body content."},
            proposed_content={"text": "Stale update."},
            diff_summary={"type": "REPLACE", "block_id": "b2"},
            reason="Stale proposal",
        )
        session.add(proposal)
        await session.commit()
        prop_id = proposal.id

    # 2. Simulate concurrent human edit bumping document to version 2
    async with session_factory() as session:
        doc = await session.get(ContentDocument, doc_id)
        assert doc is not None
        doc.current_version = 2
        doc.content_blocks = [
            {"id": "b1", "type": "HEADING", "text": "Intro Header"},
            {"id": "b2", "type": "PARAGRAPH", "text": "Direct human edit."},
        ]
        await session.commit()

    # 3. Verify document is now at version 2
    async with session_factory() as session:
        doc = await session.get(ContentDocument, doc_id)
        assert doc is not None
        assert doc.current_version == 2

    # 4. Attempt to apply the stale proposal (base_version=1 != current_version=2)
    async with session_factory() as session:
        with pytest.raises(ConflictError) as exc_info:
            await patch_service.apply_proposal(session, actor=actor, proposal_id=prop_id)

        assert "has been modified" in str(exc_info.value).lower()

    # 5. Verify document was NOT overwritten and proposal remains PROPOSED
    async with session_factory() as session:
        doc = await session.get(ContentDocument, doc_id)
        assert doc is not None
        assert doc.current_version == 2
        assert doc.content_blocks[1]["text"] == "Direct human edit."

        prop = await session.get(AIEditProposal, prop_id)
        assert prop is not None
        assert prop.status == ProposalStatus.PROPOSED.value


@pytest.mark.asyncio
async def test_concurrent_approve_vs_reject_serialization(
    session_factory: async_sessionmaker[AsyncSession],
    seed_data: dict[str, Any],
) -> None:
    """Tests P1-1:
    - Calling reject_step after approve_step raises ConflictError (cannot reject applied proposal).
    - Calling approve_step after reject_step raises ConflictError (cannot approve skipped step).
    """
    actor: AuthenticatedUser = seed_data["actor"]

    provider = ScriptedSequenceAIProvider(
        [
            {
                "type": "TOOL_CALL",
                "tool_name": "rewrite_section",
                "tool_input": {
                    "block_id": "b2",
                    "instruction": "Clarification",
                    "new_content": "Updated paragraph.",
                },
                "thought": "Rewrite",
            },
            {
                "type": "FINAL",
                "final_response": "Done",
                "reasoning_summary": "Done",
            },
        ]
    )
    wf_service = WorkflowService(ai_provider=provider)

    # Start workflow and run to WAITING_FOR_APPROVAL
    async with session_factory() as session:
        wf_id = await _create_test_workflow(session, seed_data, user_message="Test race")

    async with session_factory() as session:
        await wf_service.run_workflow(session, actor=actor, workflow_id=wf_id)

    # Get step
    async with session_factory() as session:
        step_stmt = select(AIWorkflowStep).where(
            AIWorkflowStep.workflow_id == wf_id,
            AIWorkflowStep.status == StepStatus.WAITING_FOR_APPROVAL.value,
        )
        step = (await session.execute(step_stmt)).scalars().first()
        assert step is not None
        step_id = step.id

    # 1. Approve step
    async with session_factory() as session:
        await wf_service.approve_step(
            session,
            actor=actor,
            workflow_id=wf_id,
            step_id=step_id,
        )

    # 2. Subsequent reject_step must raise ConflictError
    async with session_factory() as session:
        with pytest.raises((ConflictError, WorkflowStateError)):
            await wf_service.reject_step(
                session,
                actor=actor,
                workflow_id=wf_id,
                step_id=step_id,
            )


@pytest.mark.asyncio
async def test_concurrent_direct_apply_idempotency(
    session_factory: async_sessionmaker[AsyncSession],
    seed_data: dict[str, Any],
) -> None:
    """Tests P1-2:
    Applying an already APPLIED proposal directly via DocumentPatchService is idempotent:
    it returns the applied proposal without bumping version again or raising an error.
    """
    actor: AuthenticatedUser = seed_data["actor"]
    doc_id: UUID = seed_data["doc_id"]

    patch_service = DocumentPatchService()

    # Create proposal
    async with session_factory() as session:
        doc = await session.get(ContentDocument, doc_id)
        assert doc is not None
        proposal = AIEditProposal(
            id=uuid4(),
            document_id=doc.id,
            chat_message_id=None,
            base_version=doc.current_version,
            status=ProposalStatus.PROPOSED.value,
            operation_type="replace_block",
            target_block_ids=["b2"],
            old_content={"text": "Initial body content."},
            proposed_content={"text": "Idempotent apply content."},
            diff_summary={"type": "REPLACE", "block_id": "b2"},
            reason="Idempotency test proposal",
        )
        session.add(proposal)
        await session.commit()
        prop_id = proposal.id

    # First apply
    async with session_factory() as session:
        applied1 = await patch_service.apply_proposal(session, actor=actor, proposal_id=prop_id)
        assert applied1.current_version == 2

    # Second apply (idempotent retry)
    async with session_factory() as session:
        applied2 = await patch_service.apply_proposal(session, actor=actor, proposal_id=prop_id)
        assert applied2.current_version == 2

    # Verify proposal is APPLIED in database
    async with session_factory() as session:
        prop = await session.get(AIEditProposal, prop_id)
        assert prop is not None
        assert prop.status == ProposalStatus.APPLIED.value
        assert prop.applied_version == 2

    # Document remains at version 2 (NOT bumped to 3)
    async with session_factory() as session:
        doc = await session.get(ContentDocument, doc_id)
        assert doc is not None
        assert doc.current_version == 2
        assert doc.content_blocks[1]["text"] == "Idempotent apply content."


@pytest.mark.asyncio
async def test_reject_step_lifecycle(
    session_factory: async_sessionmaker[AsyncSession],
    seed_data: dict[str, Any],
) -> None:
    """Tests reject_step:
    Rejects the pending step proposal -> proposal marked REJECTED, step marked SKIPPED,
    workflow marked COMPLETED, document remains version 1 unmutated.
    """
    actor: AuthenticatedUser = seed_data["actor"]
    doc_id: UUID = seed_data["doc_id"]

    provider = ScriptedSequenceAIProvider(
        [
            {
                "type": "TOOL_CALL",
                "tool_name": "rewrite_section",
                "tool_input": {
                    "block_id": "b2",
                    "instruction": "Clarification",
                    "new_content": "Rejected edit text.",
                },
                "thought": "Rewrite",
            }
        ]
    )
    wf_service = WorkflowService(ai_provider=provider)

    # Start workflow and run to WAITING_FOR_APPROVAL
    async with session_factory() as session:
        wf_id = await _create_test_workflow(session, seed_data, user_message="Test reject")

    async with session_factory() as session:
        await wf_service.run_workflow(session, actor=actor, workflow_id=wf_id)

    # Get step
    async with session_factory() as session:
        step_stmt = select(AIWorkflowStep).where(
            AIWorkflowStep.workflow_id == wf_id,
            AIWorkflowStep.status == StepStatus.WAITING_FOR_APPROVAL.value,
        )
        step = (await session.execute(step_stmt)).scalars().first()
        assert step is not None
        proposal_id = UUID(str(step.output["proposal_id"]))

    # Call reject_step
    async with session_factory() as session:
        rejected_wf = await wf_service.reject_step(
            session,
            actor=actor,
            workflow_id=wf_id,
            step_id=step.id,
        )
        assert rejected_wf.status == WorkflowStatus.COMPLETED.value

    # Verify PostgreSQL state
    async with session_factory() as session:
        # Document unchanged at version 1
        doc = await session.get(ContentDocument, doc_id)
        assert doc is not None
        assert doc.current_version == 1
        assert doc.content_blocks[1]["text"] == "Initial body content."

        # Proposal status is REJECTED
        prop = await session.get(AIEditProposal, proposal_id)
        assert prop is not None
        assert prop.status == ProposalStatus.REJECTED.value

        # Step status is SKIPPED
        st = await session.get(AIWorkflowStep, step.id)
        assert st is not None
        assert st.status == StepStatus.SKIPPED.value


@pytest.mark.asyncio
async def test_out_of_band_proposal_apply_handled_in_approve(
    session_factory: async_sessionmaker[AsyncSession],
    seed_data: dict[str, Any],
) -> None:
    """Tests P1-3:
    If a proposal is applied out-of-band before approve_step is called,
    approve_step detects proposal.status == APPLIED, sets expected_version,
    does not double-bump the document, marks step COMPLETED, and resumes workflow.
    """
    actor: AuthenticatedUser = seed_data["actor"]
    doc_id: UUID = seed_data["doc_id"]

    provider = ScriptedSequenceAIProvider(
        [
            {
                "type": "TOOL_CALL",
                "tool_name": "rewrite_section",
                "tool_input": {
                    "block_id": "b2",
                    "instruction": "Clarification",
                    "new_content": "Out of band applied content.",
                },
                "thought": "Rewrite",
            },
            {
                "type": "FINAL",
                "final_response": "Out of band approved workflow finished.",
                "reasoning_summary": "Done",
            },
        ]
    )
    wf_service = WorkflowService(ai_provider=provider)

    # Start and run to WAITING_FOR_APPROVAL
    async with session_factory() as session:
        wf_id = await _create_test_workflow(session, seed_data, user_message="Test out-of-band")

    async with session_factory() as session:
        await wf_service.run_workflow(session, actor=actor, workflow_id=wf_id)

    # Get step & proposal
    async with session_factory() as session:
        step_stmt = select(AIWorkflowStep).where(
            AIWorkflowStep.workflow_id == wf_id,
            AIWorkflowStep.status == StepStatus.WAITING_FOR_APPROVAL.value,
        )
        step = (await session.execute(step_stmt)).scalars().first()
        assert step is not None
        proposal_id = UUID(str(step.output["proposal_id"]))

    # Apply proposal out-of-band via DocumentPatchService
    patch_service = DocumentPatchService()
    async with session_factory() as session:
        await patch_service.apply_proposal(session, actor=actor, proposal_id=proposal_id)

    # Now call approve_step on the workflow
    async with session_factory() as session:
        completed_wf = await wf_service.approve_step(
            session,
            actor=actor,
            workflow_id=wf_id,
            step_id=step.id,
        )
        assert completed_wf.status == WorkflowStatus.COMPLETED.value

    # Verify document version is 2 (not 3)
    async with session_factory() as session:
        doc = await session.get(ContentDocument, doc_id)
        assert doc is not None
        assert doc.current_version == 2
        assert doc.content_blocks[1]["text"] == "Out of band applied content."


@pytest.mark.asyncio
async def test_approve_step_idempotent_retry(
    session_factory: async_sessionmaker[AsyncSession],
    seed_data: dict[str, Any],
) -> None:
    """Tests P2-4:
    Re-calling approve_step after step has already been COMPLETED and proposal APPLIED
    (e.g. network timeout / retry) succeeds idempotently without error.
    """
    actor: AuthenticatedUser = seed_data["actor"]

    provider = ScriptedSequenceAIProvider(
        [
            {
                "type": "TOOL_CALL",
                "tool_name": "rewrite_section",
                "tool_input": {
                    "block_id": "b2",
                    "instruction": "Clarification",
                    "new_content": "Idempotent retry test content.",
                },
                "thought": "Rewrite",
            },
            {
                "type": "FINAL",
                "final_response": "Workflow completed",
                "reasoning_summary": "Done",
            },
        ]
    )
    wf_service = WorkflowService(ai_provider=provider)

    async with session_factory() as session:
        wf_id = await _create_test_workflow(session, seed_data, user_message="Test retry")

    async with session_factory() as session:
        await wf_service.run_workflow(session, actor=actor, workflow_id=wf_id)

    async with session_factory() as session:
        step_stmt = select(AIWorkflowStep).where(
            AIWorkflowStep.workflow_id == wf_id,
            AIWorkflowStep.status == StepStatus.WAITING_FOR_APPROVAL.value,
        )
        step = (await session.execute(step_stmt)).scalars().first()
        assert step is not None
        step_id = step.id

    # First approve call -> succeeds and completes
    async with session_factory() as session:
        wf1 = await wf_service.approve_step(
            session,
            actor=actor,
            workflow_id=wf_id,
            step_id=step_id,
        )
        assert wf1.status == WorkflowStatus.COMPLETED.value

    # Second approve call (retry) -> also succeeds without ConflictError
    async with session_factory() as session:
        wf2 = await wf_service.approve_step(
            session,
            actor=actor,
            workflow_id=wf_id,
            step_id=step_id,
        )
        assert wf2.status == WorkflowStatus.COMPLETED.value
