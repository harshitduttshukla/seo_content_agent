"""PostgreSQL integration tests verifying Problem #3 — Write Tool Governance.

Verifies:
1. Every write tool executes through ToolExecutor (creating ToolExecutionRecord).
2. Write tools produce AIEditProposal in PROPOSED status and pause at approval gate.
3. Canonical ContentDocument is strictly NEVER mutated before human approval.
4. Human approval via WorkflowService.approve_step applies the proposal, bumps version,
   creates ContentDocumentVersion snapshot, and verifies consistency.
5. Invalid write inputs (missing block_id, unauthorized external URLs) fail safely
   through ToolExecutor and never create proposals or corrupt documents.
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
from app.domains.content.editor_models import (
    AIEditProposal,
    ContentDocument,
    ContentDocumentVersion,
    ProposalStatus,
)
from app.domains.content.models import PlannedContentPage
from app.domains.orchestrator.agent_loop import AgentLoop
from app.domains.orchestrator.models import (
    AIWorkflow,
    AIWorkflowStep,
    StepStatus,
    ToolExecutionRecord,
    ToolExecutionStatus,
    WorkflowIntent,
    WorkflowStatus,
)
from app.domains.orchestrator.tool_executor import ToolExecutor
from app.domains.orchestrator.tool_registry import ToolRegistry
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


class DeterministicSequenceAIProvider(AIProvider):
    """Deterministic AI provider returning scripted tool calls."""

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
                    "final_response": "Execution completed",
                    "reasoning_summary": "No more responses",
                }
            )

        return GenerationResult(
            text=content,
            provider="test",
            model="deterministic-write-governance-v1",
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
    """Seeds baseline organization, project, website, user, and content document in PostgreSQL."""
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
        display_name="Write Governance Tester",
    )

    async with session_factory() as session:
        org = Organization(id=org_id, name="Governance Org", slug=f"gov-org-{org_id.hex[:8]}")
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
            name="Governance Project",
            slug=f"gov-proj-{proj_id.hex[:8]}",
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
            title="Zero Trust Guide",
            slug="zero-trust-guide",
            url="/zero-trust-guide",
            page_type="PLANNED",
            content_type="BLOG_POST",
            status="PLANNED",
            intent="INFORMATIONAL",
            primary_keyword="zero trust",
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
            title="Zero Trust Architecture Guide",
            slug="zero-trust-architecture-guide",
            status="DRAFT",
            current_version=1,
            lock_version=1,
            word_count=250,
            content_blocks=[
                {"id": "b1", "type": "HEADING", "text": "Zero Trust Architecture Overview"},
                {"id": "b2", "type": "PARAGRAPH", "text": "Original introductory paragraph."},
            ],
            plain_text="Zero Trust Architecture Overview\nOriginal introductory paragraph.",
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
            text("DELETE FROM content_document_versions WHERE document_id = :did"),
            {"did": doc_id},
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
            text("DELETE FROM websites WHERE id = :sid"),
            {"sid": site_id},
        )
        await session.execute(
            text("DELETE FROM projects WHERE id = :pid"),
            {"pid": proj_id},
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
# TEST 1: Full Lifecycle of Governed Write Tool (ToolExecutor -> Proposal -> Approval -> Mutation)
# =========================================================================
@pytest.mark.asyncio
async def test_governed_write_tool_full_lifecycle(
    session_factory: async_sessionmaker[AsyncSession],
    seed_data: dict[str, Any],
) -> None:
    """Verifies write tool execution via ToolExecutor, records in PostgreSQL,
    creates AIEditProposal without mutating document, and applies upon approval.
    """
    wf_id = uuid4()
    doc_id = seed_data["doc_id"]
    actor = seed_data["actor"]

    # 1. Setup workflow in PostgreSQL
    async with session_factory() as setup_session:
        wf = AIWorkflow(
            id=wf_id,
            organization_id=seed_data["org_id"],
            project_id=seed_data["proj_id"],
            document_id=doc_id,
            created_by_id=actor.user_id,
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

    # 2. AI provider selects rewrite_section
    new_text = "Updated introductory paragraph with clear zero trust principles."
    provider = DeterministicSequenceAIProvider(
        [
            {
                "type": "TOOL_CALL",
                "tool_name": "rewrite_section",
                "tool_input": {
                    "block_id": "b2",
                    "instruction": "Make punchier and emphasize principles",
                    "new_content": new_text,
                },
                "reasoning_summary": "Update block b2 for clarity",
            }
        ]
    )

    registry = ToolRegistry()
    executor = ToolExecutor(registry=registry)
    loop = AgentLoop(provider=provider, registry=registry, executor=executor)

    # 3. Run agent turn outside explicit caller transaction
    from unittest.mock import patch

    with patch("app.domains.projects.service.ProjectService.get_model", return_value=None):
        async with session_factory() as session1:
            wf_to_run = await session1.get(AIWorkflow, wf_id)
            assert wf_to_run is not None
            await loop.run(
                session1,
                actor=actor,
                workflow=wf_to_run,
                user_message="Improve intro paragraph",
            )

    # 4. Verify post-run state in fresh database session
    async with session_factory() as session2:
        # A. Tool Execution was recorded in PostgreSQL via ToolExecutor
        exec_stmt = (
            select(ToolExecutionRecord)
            .where(ToolExecutionRecord.workflow_id == wf_id)
            .order_by(ToolExecutionRecord.started_at.desc())
        )
        exec_res = await session2.execute(exec_stmt)
        records = exec_res.scalars().all()
        assert len(records) >= 1, "ToolExecutionRecord must be inserted by ToolExecutor"
        rewrite_record = next(r for r in records if r.tool_name == "rewrite_section")
        assert rewrite_record.status == ToolExecutionStatus.SUCCESS.value
        assert rewrite_record.output.get("block_id") == "b2"
        assert rewrite_record.output.get("new_content") == new_text

        # B. Workflow paused at approval gate
        wf_persisted = await session2.get(AIWorkflow, wf_id)
        assert wf_persisted is not None
        assert wf_persisted.status == WorkflowStatus.WAITING_FOR_APPROVAL.value

        # C. Step transitioned to WAITING_FOR_APPROVAL with proposal reference
        step_stmt = select(AIWorkflowStep).where(AIWorkflowStep.workflow_id == wf_id)
        step_res = await session2.execute(step_stmt)
        steps = step_res.scalars().all()
        assert len(steps) >= 1
        waiting_step = steps[-1]
        assert waiting_step.status == StepStatus.WAITING_FOR_APPROVAL.value
        proposal_id_str = waiting_step.output.get("proposal_id")
        assert proposal_id_str is not None

        # D. AIEditProposal exists in PostgreSQL with PROPOSED status
        proposal_id = UUID(proposal_id_str)
        proposal = await session2.get(AIEditProposal, proposal_id)
        assert proposal is not None
        assert proposal.status == ProposalStatus.PROPOSED.value
        assert proposal.document_id == doc_id
        assert proposal.target_block_ids == ["b2"]

        # E. CRITICAL INVARIANT: Canonical document is NOT yet mutated!
        doc_persisted = await session2.get(ContentDocument, doc_id)
        assert doc_persisted is not None
        assert doc_persisted.current_version == 1
        assert doc_persisted.content_blocks[1]["text"] == "Original introductory paragraph."

    # 5. Human Approval Gate: Call WorkflowService.approve_step
    workflow_service = WorkflowService()
    with patch("app.domains.projects.service.ProjectService.get_model", return_value=None):
        async with session_factory() as session3:
            await workflow_service.approve_step(
                session3,
                actor=actor,
                workflow_id=wf_id,
                step_id=waiting_step.id,
            )

    # 6. Verify state after human approval in fresh database session
    async with session_factory() as session4:
        # A. AIEditProposal transitioned to APPLIED
        proposal_after = await session4.get(AIEditProposal, proposal_id)
        assert proposal_after is not None
        assert proposal_after.status == ProposalStatus.APPLIED.value

        # B. Canonical ContentDocument is NOW safely updated!
        doc_after = await session4.get(ContentDocument, doc_id)
        assert doc_after is not None
        assert doc_after.current_version == 2
        assert doc_after.content_blocks[1]["text"] == new_text

        # C. ContentDocumentVersion snapshot was created
        ver_stmt = select(ContentDocumentVersion).where(
            ContentDocumentVersion.document_id == doc_id,
            ContentDocumentVersion.version == 2,
        )
        ver_res = await session4.execute(ver_stmt)
        version_snap = ver_res.scalars().first()
        assert version_snap is not None
        assert version_snap.content_blocks[1]["text"] == new_text


# =========================================================================
# TEST 2: Governed Insert Link Full Lifecycle
# =========================================================================
@pytest.mark.asyncio
async def test_governed_insert_link_full_lifecycle(
    session_factory: async_sessionmaker[AsyncSession],
    seed_data: dict[str, Any],
) -> None:
    """Verifies that insert_internal_link executes through ToolExecutor and pauses for approval."""
    wf_id = uuid4()
    doc_id = seed_data["doc_id"]
    actor = seed_data["actor"]

    async with session_factory() as setup_session:
        wf = AIWorkflow(
            id=wf_id,
            organization_id=seed_data["org_id"],
            project_id=seed_data["proj_id"],
            document_id=doc_id,
            created_by_id=actor.user_id,
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

    # Valid internal link (relative path)
    provider = DeterministicSequenceAIProvider(
        [
            {
                "type": "TOOL_CALL",
                "tool_name": "insert_internal_link",
                "tool_input": {
                    "block_id": "b2",
                    "url": "/security/zero-trust-guide",
                    "anchor_text": "zero trust principles",
                },
                "reasoning_summary": "Link to zero trust guide",
            }
        ]
    )

    registry = ToolRegistry()
    executor = ToolExecutor(registry=registry)
    loop = AgentLoop(provider=provider, registry=registry, executor=executor)

    from unittest.mock import patch

    with patch("app.domains.projects.service.ProjectService.get_model", return_value=None):
        async with session_factory() as session1:
            wf_to_run = await session1.get(AIWorkflow, wf_id)
            assert wf_to_run is not None
            await loop.run(
                session1,
                actor=actor,
                workflow=wf_to_run,
                user_message="Add internal link",
            )

    async with session_factory() as session2:
        # Verify ToolExecutionRecord was created
        exec_stmt = select(ToolExecutionRecord).where(
            ToolExecutionRecord.workflow_id == wf_id,
            ToolExecutionRecord.tool_name == "insert_internal_link",
        )
        exec_res = await session2.execute(exec_stmt)
        record = exec_res.scalars().first()
        assert record is not None
        assert record.status == ToolExecutionStatus.SUCCESS.value
        assert record.output.get("url") == "/security/zero-trust-guide"

        # Verify proposal created
        step_stmt = select(AIWorkflowStep).where(AIWorkflowStep.workflow_id == wf_id)
        step_res = await session2.execute(step_stmt)
        step = step_res.scalars().first()
        assert step is not None
        assert step.status == StepStatus.WAITING_FOR_APPROVAL.value

        proposal_id_str = step.output.get("proposal_id")
        assert proposal_id_str is not None
        proposal = await session2.get(AIEditProposal, UUID(proposal_id_str))
        assert proposal is not None
        assert proposal.status == ProposalStatus.PROPOSED.value
        assert proposal.operation_type == "insert_link"

        # Canonical document unchanged
        doc = await session2.get(ContentDocument, doc_id)
        assert doc is not None
        assert doc.current_version == 1


# =========================================================================
# TEST 3: Invalid Block ID Fails Safely in ToolExecutor
# =========================================================================
@pytest.mark.asyncio
async def test_write_tool_fails_safely_on_invalid_block(
    session_factory: async_sessionmaker[AsyncSession],
    seed_data: dict[str, Any],
) -> None:
    """Verifies that an invalid block_id fails inside ToolExecutor
    and does NOT create a proposal.
    """
    wf_id = uuid4()
    doc_id = seed_data["doc_id"]
    actor = seed_data["actor"]

    async with session_factory() as setup_session:
        wf = AIWorkflow(
            id=wf_id,
            organization_id=seed_data["org_id"],
            project_id=seed_data["proj_id"],
            document_id=doc_id,
            created_by_id=actor.user_id,
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

    # Step 1: tool call with non-existent block
    # Step 2: model stops after observing failure
    provider = DeterministicSequenceAIProvider(
        [
            {
                "type": "TOOL_CALL",
                "tool_name": "rewrite_section",
                "tool_input": {
                    "block_id": "non_existent_block_999",
                    "instruction": "Fix block",
                    "new_content": "Some text",
                },
                "reasoning_summary": "Attempt rewrite on bad block",
            },
            {
                "type": "FINAL",
                "final_response": "Could not find block, aborted gracefully.",
                "reasoning_summary": "Block not found, stopping",
            },
        ]
    )

    registry = ToolRegistry()
    executor = ToolExecutor(registry=registry)
    loop = AgentLoop(provider=provider, registry=registry, executor=executor, max_iterations=3)

    from unittest.mock import patch

    with patch("app.domains.projects.service.ProjectService.get_model", return_value=None):
        async with session_factory() as session1:
            wf_to_run = await session1.get(AIWorkflow, wf_id)
            assert wf_to_run is not None
            await loop.run(
                session1,
                actor=actor,
                workflow=wf_to_run,
                user_message="Update invalid block",
            )

    async with session_factory() as session2:
        # ToolExecutionRecord was marked FAILED
        exec_stmt = select(ToolExecutionRecord).where(
            ToolExecutionRecord.workflow_id == wf_id,
            ToolExecutionRecord.tool_name == "rewrite_section",
        )
        exec_res = await session2.execute(exec_stmt)
        record = exec_res.scalars().first()
        assert record is not None
        assert record.status == ToolExecutionStatus.FAILED.value
        assert "not found in document" in str(record.error)

        # No AIEditProposal was created
        prop_stmt = select(AIEditProposal).where(AIEditProposal.document_id == doc_id)
        prop_res = await session2.execute(prop_stmt)
        proposals = prop_res.scalars().all()
        assert len(proposals) == 0

        # Canonical document untouched
        doc = await session2.get(ContentDocument, doc_id)
        assert doc is not None
        assert doc.current_version == 1


# =========================================================================
# TEST 4: Unauthorized External Link Fails Safely in ToolExecutor
# =========================================================================
@pytest.mark.asyncio
async def test_governed_insert_link_rejects_external_url(
    session_factory: async_sessionmaker[AsyncSession],
    seed_data: dict[str, Any],
) -> None:
    """Verifies that an external destination URL fails inside ToolExecutor
    and creates no proposal.
    """
    wf_id = uuid4()
    doc_id = seed_data["doc_id"]
    actor = seed_data["actor"]

    async with session_factory() as setup_session:
        wf = AIWorkflow(
            id=wf_id,
            organization_id=seed_data["org_id"],
            project_id=seed_data["proj_id"],
            document_id=doc_id,
            created_by_id=actor.user_id,
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

    # Model calls insert_internal_link with external attacker URL
    provider = DeterministicSequenceAIProvider(
        [
            {
                "type": "TOOL_CALL",
                "tool_name": "insert_internal_link",
                "tool_input": {
                    "block_id": "b2",
                    "url": "https://malicious-external-host.com/phishing",
                    "anchor_text": "click here",
                },
                "reasoning_summary": "Attempt insertion of external link",
            },
            {
                "type": "FINAL",
                "final_response": "Link rejected as external, aborted gracefully.",
                "reasoning_summary": "Domain rejected, stopping",
            },
        ]
    )

    registry = ToolRegistry()
    executor = ToolExecutor(registry=registry)
    loop = AgentLoop(provider=provider, registry=registry, executor=executor, max_iterations=3)

    from unittest.mock import patch

    with patch("app.domains.projects.service.ProjectService.get_model", return_value=None):
        async with session_factory() as session1:
            wf_to_run = await session1.get(AIWorkflow, wf_id)
            assert wf_to_run is not None
            await loop.run(
                session1,
                actor=actor,
                workflow=wf_to_run,
                user_message="Add external link",
            )

    async with session_factory() as session2:
        # ToolExecutionRecord was marked FAILED
        exec_stmt = select(ToolExecutionRecord).where(
            ToolExecutionRecord.workflow_id == wf_id,
            ToolExecutionRecord.tool_name == "insert_internal_link",
        )
        exec_res = await session2.execute(exec_stmt)
        record = exec_res.scalars().first()
        assert record is not None
        assert record.status == ToolExecutionStatus.FAILED.value
        assert "does not belong to project domain" in str(record.error)

        # No AIEditProposal was created
        prop_stmt = select(AIEditProposal).where(AIEditProposal.document_id == doc_id)
        prop_res = await session2.execute(prop_stmt)
        proposals = prop_res.scalars().all()
        assert len(proposals) == 0

        # Canonical document untouched
        doc = await session2.get(ContentDocument, doc_id)
        assert doc is not None
        assert doc.current_version == 1
