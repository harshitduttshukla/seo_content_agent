"""Unit tests for Problem #3 — Write Tool Governance.

Verifies:
1. Pydantic ConfigDict(extra="forbid") on input schemas rejects unknown fields.
2. Input validation for SectionProposalInput and InsertInternalLinkInput.
3. Tool handlers reject invalid block_ids and unauthorized external hosts.
4. ToolExecutor enforces RBAC (CONTENT_WRITE required for write tools).
5. ToolExecutor strips spoofed scope keys and injects authoritative scope.
6. AgentLoop routes write tools through ToolExecutor and pauses for approval.
7. Canonical documents are never mutated by AgentLoop or ToolExecutor.
"""

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from app.ai.provider import AIProvider, GenerationRequest, GenerationResult, Usage
from app.core.errors import BadRequestError, PermissionDenied
from app.domains.content.editor_models import ContentDocument
from app.domains.orchestrator.agent_loop import AgentLoop
from app.domains.orchestrator.exceptions import ToolPermissionDeniedError
from app.domains.orchestrator.models import (
    AIWorkflow,
    ToolExecutionStatus,
    WorkflowIntent,
    WorkflowStatus,
)
from app.domains.orchestrator.tool_executor import ToolExecutor
from app.domains.orchestrator.tool_registry import (
    InsertInternalLinkInput,
    ReadDocumentInput,
    SectionProposalInput,
    ToolExecutionContext,
    ToolRegistry,
    _handle_insert_internal_link,
    _handle_rewrite_section,
)
from app.security.principal import AuthenticatedUser
from pydantic import ValidationError

# ---------------------------------------------------------------------------
# Test Helpers & Stubs
# ---------------------------------------------------------------------------


class MockAIProvider(AIProvider):
    def __init__(self, responses: list[dict[str, Any]]):
        self.responses = list(responses)

    async def generate(self, request: GenerationRequest) -> GenerationResult:
        import json

        if self.responses:
            data = self.responses.pop(0)
        else:
            data = {"action": "FINAL", "final_response": "Done"}
        return GenerationResult(
            text=json.dumps(data),
            provider="test",
            model="mock-v1",
            usage=Usage(input_tokens=10, output_tokens=10),
            finish_reason="stop",
        )

    async def embed(self, texts: list[str]):
        raise NotImplementedError


def make_mock_session(
    base_doc: ContentDocument | None = None,
    workflow: AIWorkflow | None = None,
    websites: list[str] | None = None,
) -> MagicMock:
    session = MagicMock()
    context_manager = MagicMock()
    context_manager.__aenter__ = AsyncMock(return_value=session)
    context_manager.__aexit__ = AsyncMock(return_value=None)
    session.begin.return_value = context_manager
    session.in_transaction.return_value = False
    session.refresh = AsyncMock()
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.scalar = AsyncMock(return_value=None)
    session.add = MagicMock()

    def default_execute_side_effect(statement, *args, **kwargs):
        stmt_str = str(statement).lower()
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        if "content_documents" in stmt_str:
            mock_scalars.first.return_value = base_doc
            mock_scalars.all.return_value = [base_doc] if base_doc else []
        elif "ai_workflows" in stmt_str:
            mock_scalars.first.return_value = workflow
            mock_scalars.all.return_value = [workflow] if workflow else []
        elif "ai_workflow_steps" in stmt_str:
            mock_scalars.first.return_value = None
            mock_scalars.all.return_value = []
        elif "websites" in stmt_str:
            mock_sites = [
                MagicMock(normalized_host=w) for w in (websites or ["allowed-domain.com"])
            ]
            mock_result.fetchall.return_value = [(w,) for w in (websites or ["allowed-domain.com"])]
            mock_scalars.all.return_value = mock_sites
        else:
            mock_scalars.first.return_value = None
            mock_scalars.all.return_value = []
        mock_result.scalars.return_value = mock_scalars
        return mock_result

    session.execute = AsyncMock(side_effect=default_execute_side_effect)
    return session


# ---------------------------------------------------------------------------
# 1. Schema Validation & Extra="Forbid" Tests
# ---------------------------------------------------------------------------


def test_section_proposal_input_extra_forbid():
    """Verify SectionProposalInput rejects unknown fields."""
    with pytest.raises(ValidationError) as exc_info:
        SectionProposalInput(
            document_id=uuid4(),
            block_id="b1",
            instruction="Make clearer",
            new_content="Updated text",
            unknown_injection="malicious_payload",
        )
    assert "extra_forbidden" in str(exc_info.value)


def test_section_proposal_input_normalization():
    """Verify SectionProposalInput accepts either new_content or text."""
    # new_content provided
    inp1 = SectionProposalInput(
        document_id=uuid4(),
        block_id="b1",
        instruction="Make clearer",
        new_content="Updated text",
    )
    assert inp1.new_content == "Updated text"

    # text provided instead of new_content
    inp2 = SectionProposalInput(
        document_id=uuid4(),
        block_id="b1",
        instruction="Make clearer",
        text="Text field content",
    )
    assert inp2.new_content == "Text field content"

    # instruction only provided (handler will generate replacement)
    inp3 = SectionProposalInput(
        document_id=uuid4(),
        block_id="b1",
        instruction="Make clearer",
    )
    assert inp3.new_content is None
    assert inp3.instruction == "Make clearer"


def test_insert_internal_link_input_extra_forbid():
    """Verify InsertInternalLinkInput rejects unknown fields."""
    with pytest.raises(ValidationError) as exc_info:
        InsertInternalLinkInput(
            document_id=uuid4(),
            block_id="b1",
            url="/pricing",
            anchor_text="Pricing",
            spoofed_field="attack",
        )
    assert "extra_forbidden" in str(exc_info.value)


def test_insert_internal_link_input_validation():
    """Verify InsertInternalLinkInput validates URLs and anchor text."""
    doc_id = uuid4()

    # Valid relative path
    inp_rel = InsertInternalLinkInput(
        document_id=doc_id,
        block_id="b1",
        url="/solutions/enterprise",
        anchor_text="enterprise solutions",
    )
    assert inp_rel.url == "/solutions/enterprise"

    # Valid https URL
    inp_https = InsertInternalLinkInput(
        document_id=doc_id,
        block_id="b1",
        url="https://example.com/solutions/enterprise",
        anchor_text="enterprise solutions",
    )
    assert inp_https.url == "https://example.com/solutions/enterprise"

    # Dangerous javascript scheme
    with pytest.raises(ValidationError) as exc:
        InsertInternalLinkInput(
            document_id=doc_id,
            block_id="b1",
            url="javascript:alert(document.cookie)",
            anchor_text="click here",
        )
    assert "Unsafe URL scheme detected" in str(exc.value)

    # Dangerous data scheme
    with pytest.raises(ValidationError) as exc:
        InsertInternalLinkInput(
            document_id=doc_id,
            block_id="b1",
            url="data:text/html,<script>alert(1)</script>",
            anchor_text="click here",
        )
    assert "Unsafe URL scheme detected" in str(exc.value)

    # Protocol-relative scheme
    with pytest.raises(ValidationError) as exc:
        InsertInternalLinkInput(
            document_id=doc_id,
            block_id="b1",
            url="//attacker.com/exploit",
            anchor_text="click here",
        )
    assert "Protocol-relative URLs are not allowed" in str(exc.value)

    # Empty anchor text
    with pytest.raises(ValidationError):
        InsertInternalLinkInput(
            document_id=doc_id,
            block_id="b1",
            url="/pricing",
            anchor_text="   ",
        )


def test_read_document_input_extra_forbid():
    """Verify ReadDocumentInput rejects unknown fields."""
    with pytest.raises(ValidationError) as exc_info:
        ReadDocumentInput(
            document_id=uuid4(),
            project_id=uuid4(),  # ReadDocumentInput only defines document_id
        )
    assert "extra_forbidden" in str(exc_info.value)


# ---------------------------------------------------------------------------
# 2. Tool Handlers Validation Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_rewrite_section_rejects_missing_block():
    """Verify _handle_rewrite_section rejects non-existent block_id."""
    org_id = uuid4()
    proj_id = uuid4()
    doc_id = uuid4()

    actor = AuthenticatedUser(
        user_id=uuid4(),
        issuer="https://auth.example.com",
        subject="user-123",
        email="editor@example.com",
        display_name="Editor",
    )

    mock_doc = ContentDocument(
        id=doc_id,
        organization_id=org_id,
        project_id=proj_id,
        title="Test Doc",
        content_blocks=[
            {"id": "b1", "type": "paragraph", "text": "Existing paragraph"},
        ],
    )

    mock_session = make_mock_session(base_doc=mock_doc)

    ctx = ToolExecutionContext(
        session=mock_session,
        actor=actor,
        workflow_id=uuid4(),
        step_id=uuid4(),
        organization_id=org_id,
        project_id=proj_id,
        document_id=doc_id,
    )

    with pytest.raises(BadRequestError) as exc_info:
        await _handle_rewrite_section(
            ctx,
            {
                "block_id": "non_existent_block",
                "instruction": "Rewrite this",
                "new_content": "Brand new text",
            },
        )
    assert "not found in document" in str(exc_info.value)


@pytest.mark.asyncio
async def test_insert_internal_link_rejects_external_host():
    """Verify _handle_insert_internal_link rejects absolute URLs not matching project websites."""
    org_id = uuid4()
    proj_id = uuid4()
    doc_id = uuid4()

    actor = AuthenticatedUser(
        user_id=uuid4(),
        issuer="https://auth.example.com",
        subject="user-123",
        email="editor@example.com",
        display_name="Editor",
    )

    mock_doc = ContentDocument(
        id=doc_id,
        organization_id=org_id,
        project_id=proj_id,
        title="Test Doc",
        content_blocks=[
            {"id": "b1", "type": "paragraph", "text": "Check out our product here."},
        ],
    )

    mock_session = make_mock_session(base_doc=mock_doc, websites=["allowed-domain.com"])

    ctx = ToolExecutionContext(
        session=mock_session,
        actor=actor,
        workflow_id=uuid4(),
        step_id=uuid4(),
        organization_id=org_id,
        project_id=proj_id,
        document_id=doc_id,
    )

    with pytest.raises(BadRequestError) as exc_info:
        await _handle_insert_internal_link(
            ctx,
            {
                "block_id": "b1",
                "url": "https://attacker-domain.com/phishing",
                "anchor_text": "product",
            },
        )
    assert "does not belong to project domain" in str(exc_info.value)


# ---------------------------------------------------------------------------
# 3. ToolExecutor Scope & RBAC Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_tool_executor_denies_write_without_permission():
    """Verify ToolExecutor raises ToolPermissionDeniedError if actor lacks CONTENT_WRITE."""
    registry = ToolRegistry()
    executor = ToolExecutor(registry=registry)

    # Mock ProjectService to simulate permission denial
    executor._projects = MagicMock()
    executor._projects.get_model = AsyncMock(
        side_effect=PermissionDenied("Actor lacks content.write permission")
    )
    executor._record_execution = AsyncMock()

    org_id = uuid4()
    proj_id = uuid4()
    doc_id = uuid4()
    wf_id = uuid4()
    step_id = uuid4()

    actor = AuthenticatedUser(
        user_id=uuid4(),
        issuer="https://auth.example.com",
        subject="user-123",
        email="viewer@example.com",
        display_name="Viewer",
    )

    mock_session = AsyncMock()

    with pytest.raises(ToolPermissionDeniedError) as exc_info:
        await executor.execute(
            mock_session,
            tool_name="rewrite_section",
            arguments={
                "block_id": "b1",
                "instruction": "Improve",
                "new_content": "New text",
            },
            actor=actor,
            workflow_id=wf_id,
            step_id=step_id,
            organization_id=org_id,
            project_id=proj_id,
            document_id=doc_id,
        )

    assert "content.write" in str(exc_info.value)
    # Ensure failure execution record was recorded
    executor._record_execution.assert_awaited_once()


@pytest.mark.asyncio
async def test_tool_executor_strips_spoofed_fields_and_injects_valid_scope():
    """Verify ToolExecutor strips untrusted keys and dynamically matches input schema."""
    registry = ToolRegistry()
    executor = ToolExecutor(registry=registry)

    org_id = uuid4()
    proj_id = uuid4()
    doc_id = uuid4()
    wf_id = uuid4()
    step_id = uuid4()

    actor = AuthenticatedUser(
        user_id=uuid4(),
        issuer="https://auth.example.com",
        subject="user-123",
        email="editor@example.com",
        display_name="Editor",
    )

    # Bypass RBAC check for this test
    executor._projects = MagicMock()
    executor._projects.get_model = AsyncMock()
    executor._record_execution = AsyncMock()

    mock_doc = ContentDocument(
        id=doc_id,
        organization_id=org_id,
        project_id=proj_id,
        title="Test",
        content_blocks=[{"id": "b1", "type": "paragraph", "text": "Original"}],
    )

    mock_session = make_mock_session(base_doc=mock_doc)

    # Pass spoofed organization_id and workflow_id in arguments
    raw_args = {
        "organization_id": str(uuid4()),
        "workflow_id": str(uuid4()),
        "document_id": str(uuid4()),  # Spoofed document_id
        "block_id": "b1",
        "instruction": "Refine",
        "new_content": "Refined content",
    }

    result = await executor.execute(
        mock_session,
        tool_name="rewrite_section",
        arguments=raw_args,
        actor=actor,
        workflow_id=wf_id,
        step_id=step_id,
        organization_id=org_id,
        project_id=proj_id,
        document_id=doc_id,  # Authoritative document_id
    )

    assert result.status == ToolExecutionStatus.SUCCESS
    # Result output should have used authoritative block_id and new_content
    assert result.result["block_id"] == "b1"
    assert result.result["new_content"] == "Refined content"


# ---------------------------------------------------------------------------
# 4. AgentLoop Write Tool Governance & Approval Transition Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_agent_loop_executes_write_tool_and_pauses_for_approval():
    """Verify AgentLoop executes write tools through ToolExecutor and pauses for approval."""
    org_id = uuid4()
    proj_id = uuid4()
    user_id = uuid4()
    doc_id = uuid4()
    wf_id = uuid4()

    actor = AuthenticatedUser(
        user_id=user_id,
        issuer="https://auth.example.com",
        subject="user-123",
        email="editor@example.com",
        display_name="Editor",
    )

    doc = ContentDocument(
        id=doc_id,
        organization_id=org_id,
        project_id=proj_id,
        title="Test Article",
        slug="test-article",
        current_version=1,
        content_blocks=[{"id": "b1", "type": "paragraph", "text": "Original paragraph text."}],
        plain_text="Original paragraph text.",
    )

    workflow = AIWorkflow(
        id=wf_id,
        organization_id=org_id,
        project_id=proj_id,
        created_by_id=user_id,
        document_id=doc_id,
        intent=WorkflowIntent.EDIT_DOCUMENT,
        status=WorkflowStatus.RUNNING,
        current_step=0,
        plan=[
            {
                "step_index": 0,
                "step_name": "rewrite",
                "description": "Rewrite block b1",
                "tool_call": "rewrite_section",
                "risk_level": "WRITE",
                "status": "PENDING",
            }
        ],
    )

    mock_session = make_mock_session(base_doc=doc, workflow=workflow)

    # AI decision chooses rewrite_section
    ai_provider = MockAIProvider(
        responses=[
            {
                "type": "TOOL_CALL",
                "tool_name": "rewrite_section",
                "tool_input": {
                    "block_id": "b1",
                    "instruction": "Make punchy",
                    "new_content": "Punchy paragraph text.",
                },
                "reasoning_summary": "Need punchier intro",
            }
        ]
    )

    registry = ToolRegistry()
    executor = ToolExecutor(registry=registry)
    executor._projects = MagicMock()
    executor._projects.get_model = AsyncMock()
    executor._record_execution = AsyncMock()

    loop = AgentLoop(
        provider=ai_provider,
        registry=registry,
        executor=executor,
        max_iterations=5,
    )

    mock_context = MagicMock()
    mock_context.website = None
    mock_context.current_document.title = "Test Article"
    mock_context.current_document.current_word_count = 100
    mock_context.current_document.current_version = 1
    mock_context.current_document.blocks = []
    mock_context.content_brief = None
    mock_context.seo_guide = None
    mock_context.resolved_intent = "Informational"
    mock_context.resolved_audience = "General"
    mock_context.brand_rules = None
    mock_context.selection = None
    mock_context.format_for_prompt.return_value = "Mock context prompt"

    with (
        patch.object(
            loop._context_builder,
            "build_agent_context",
            new_callable=AsyncMock,
            return_value=mock_context,
        ),
        patch("app.domains.orchestrator.agent_loop.set_actor_context", new_callable=AsyncMock),
    ):
        result = await loop.run(
            session=mock_session,
            actor=actor,
            workflow=workflow,
            user_message="Revise intro block",
        )

    # 1. Workflow should be paused at approval gate
    assert result.status == WorkflowStatus.WAITING_FOR_APPROVAL
    assert result.approval_required is True
    assert len(result.proposals_created) == 1

    # 2. Workflow state updated
    assert workflow.status == WorkflowStatus.WAITING_FOR_APPROVAL

    # 3. Canonical document NOT mutated
    assert doc.content_blocks[0]["text"] == "Original paragraph text."
    assert doc.current_version == 1
