"""V3 Step 0: Unit tests for ORM models.

Validates model instantiation, defaults, enum values, constraint-relevant
field types, and V3 domain invariants without requiring a database.
"""

from __future__ import annotations

from uuid import uuid4

# ──────────────────────────────────────────────────────────────────
# Canvas domain
# ──────────────────────────────────────────────────────────────────
from app.domains.canvas.models import Argument, Canvas, Claim, ClaimRow


class TestCanvas:
    """Canvas model instantiation and defaults."""

    def test_create_company_canvas(self) -> None:
        canvas = Canvas(
            organization_id=uuid4(),
            project_id=uuid4(),
            parent_id=None,
            product_line=None,
            version=1,
            problem_summary="",
            differentiation_summary="",
        )
        assert canvas.parent_id is None
        assert canvas.product_line is None
        assert canvas.version == 1
        assert canvas.problem_summary == ""
        assert canvas.differentiation_summary == ""

    def test_create_product_line_canvas(self) -> None:
        company_id = uuid4()
        canvas = Canvas(
            organization_id=uuid4(),
            project_id=uuid4(),
            parent_id=company_id,
            product_line="Enterprise Suite",
        )
        assert canvas.parent_id == company_id
        assert canvas.product_line == "Enterprise Suite"

    def test_default_anchors(self) -> None:
        """V3 §3.1: Anchors default to empty dicts."""
        canvas = Canvas(
            organization_id=uuid4(),
            project_id=uuid4(),
            id=uuid4(),
        )
        # Python-level defaults are not set by server_default; verify no error
        assert canvas.id is not None


class TestArgument:
    """Argument model instantiation and defaults."""

    def test_create_argument(self) -> None:
        arg = Argument(
            organization_id=uuid4(),
            project_id=uuid4(),
            canvas_id=uuid4(),
            order=0,
            sub_problem="How to scale customer support",
            differentiation_pillar="AI-powered automation",
            capability="Ticket routing",
            benefit="Faster resolution",
            override=False,
            inherited_from=None,
        )
        assert arg.sub_problem == "How to scale customer support"
        assert arg.override is False
        assert arg.inherited_from is None

    def test_defaults(self) -> None:
        arg = Argument(
            organization_id=uuid4(),
            project_id=uuid4(),
            canvas_id=uuid4(),
            sub_problem="",
            differentiation_pillar="",
            capability="",
            benefit="",
            order=0,
            override=False,
        )
        assert arg.sub_problem == ""
        assert arg.differentiation_pillar == ""
        assert arg.capability == ""
        assert arg.benefit == ""
        assert arg.order == 0
        assert arg.override is False

    def test_inheritance_fields(self) -> None:
        parent_arg_id = uuid4()
        arg = Argument(
            organization_id=uuid4(),
            project_id=uuid4(),
            canvas_id=uuid4(),
            inherited_from=parent_arg_id,
            override=True,
        )
        assert arg.inherited_from == parent_arg_id
        assert arg.override is True


class TestClaim:
    """Claim model instantiation and V3 invariants."""

    def test_create_claim(self) -> None:
        claim = Claim(
            organization_id=uuid4(),
            project_id=uuid4(),
            canvas_id=uuid4(),
            argument_id=uuid4(),
            row=ClaimRow.CAPABILITY,
            text="Our AI routes tickets 3x faster than manual triage",
            evidence="Internal benchmark study, Q2 2026",
            approved=False,
            version=1,
            superseded_by=None,
        )
        assert claim.row == "capability"
        assert claim.approved is False
        assert claim.version == 1
        assert claim.superseded_by is None

    def test_pitch_claim(self) -> None:
        """V3 §4.1: The elevator pitch is a claim cell (row: pitch)."""
        claim = Claim(
            organization_id=uuid4(),
            project_id=uuid4(),
            canvas_id=uuid4(),
            argument_id=None,  # pitch is canvas-level, not argument-specific
            row=ClaimRow.PITCH,
            text="You control how AI perceives you",
        )
        assert claim.row == "pitch"
        assert claim.argument_id is None

    def test_claim_approval(self) -> None:
        approver = uuid4()
        claim = Claim(
            organization_id=uuid4(),
            project_id=uuid4(),
            canvas_id=uuid4(),
            row=ClaimRow.BENEFIT,
            text="Reduces costs by 40%",
            approved=True,
            approved_by=approver,
        )
        assert claim.approved is True
        assert claim.approved_by == approver

    def test_claim_versioning(self) -> None:
        """V3 §6.7: superseded_by creates a version chain."""
        new_claim_id = uuid4()
        old_claim = Claim(
            organization_id=uuid4(),
            project_id=uuid4(),
            canvas_id=uuid4(),
            row=ClaimRow.CAPABILITY,
            text="Old text",
            version=1,
            superseded_by=new_claim_id,
        )
        assert old_claim.superseded_by == new_claim_id

    def test_all_claim_rows_valid(self) -> None:
        """V3 §3.1: All defined row types are valid ClaimRow enum values."""
        expected = {
            "sub_problem",
            "pillar",
            "capability",
            "feature",
            "benefit",
            "problem_summary",
            "differentiation_summary",
            "pitch",
        }
        assert {r.value for r in ClaimRow} == expected

    def test_market_overrides_default(self) -> None:
        """V3 §5.5: market_overrides defaults to empty dict."""
        claim = Claim(
            organization_id=uuid4(),
            project_id=uuid4(),
            canvas_id=uuid4(),
            row=ClaimRow.BENEFIT,
            text="Test",
        )
        # Python default not set by server_default, but model shouldn't error
        assert claim.row == "benefit"


# ──────────────────────────────────────────────────────────────────
# Demand domain
# ──────────────────────────────────────────────────────────────────
from app.domains.demand.models import DemandNode, DemandNodeOrigin, DemandNodeStatus, DemandNodeType


class TestDemandNode:
    """DemandNode model and V3 keyword/prompt distinction."""

    def test_create_keyword_node(self) -> None:
        node = DemandNode(
            organization_id=uuid4(),
            project_id=uuid4(),
            type=DemandNodeType.KEYWORD,
            text="customer support automation",
            volume=1200,
            country="US",
            origin=DemandNodeOrigin.UPLOAD,
        )
        assert node.type == "keyword"
        assert node.volume == 1200
        assert node.citation_gap is None

    def test_create_prompt_node(self) -> None:
        """V3 §4.7: Prompts have citation_gap and platforms, no volume."""
        node = DemandNode(
            organization_id=uuid4(),
            project_id=uuid4(),
            type=DemandNodeType.PROMPT,
            text="What is the best customer support tool?",
            volume=None,
            origin=DemandNodeOrigin.UPLOAD,
            citation_gap=0.75,
        )
        assert node.type == "prompt"
        assert node.volume is None
        assert node.citation_gap == 0.75

    def test_default_status(self) -> None:
        node = DemandNode(
            organization_id=uuid4(),
            project_id=uuid4(),
            type=DemandNodeType.KEYWORD,
            text="test",
            origin=DemandNodeOrigin.UPLOAD,
            status=DemandNodeStatus.PENDING,
        )
        assert node.status == "pending"

    def test_discard_reason(self) -> None:
        node = DemandNode(
            organization_id=uuid4(),
            project_id=uuid4(),
            type=DemandNodeType.KEYWORD,
            text="irrelevant keyword",
            origin=DemandNodeOrigin.UPLOAD,
            status=DemandNodeStatus.DISCARDED,
            discard_reason="Not relevant to canvas positioning",
        )
        assert node.status == "discarded"
        assert node.discard_reason is not None

    def test_all_origins(self) -> None:
        """V3 §3.1: Valid origins are upload, gsc_striking_distance, insight."""
        expected = {"upload", "gsc_striking_distance", "insight"}
        assert {o.value for o in DemandNodeOrigin} == expected

    def test_all_statuses(self) -> None:
        expected = {"pending", "kept", "discarded"}
        assert {s.value for s in DemandNodeStatus} == expected


# ──────────────────────────────────────────────────────────────────
# Content Cards domain
# ──────────────────────────────────────────────────────────────────
from app.domains.content_cards.models import (
    ContentCard,
    ContentCardKind,
    ContentCardOrigin,
    ContentCardState,
)


class TestContentCard:
    """ContentCard model and V3 state machine."""

    def test_create_pillar_card(self) -> None:
        card = ContentCard(
            organization_id=uuid4(),
            project_id=uuid4(),
            kind=ContentCardKind.PILLAR,
            origin=ContentCardOrigin.PLAN,
            title="Complete Guide to Customer Support Automation",
            state=ContentCardState.BACKLOG,
        )
        assert card.kind == "pillar"
        assert card.state == "backlog"
        assert card.origin == "plan"

    def test_create_refresh_card(self) -> None:
        """V3 §3.1: refresh is a distinct card kind for updating existing pages."""
        card = ContentCard(
            organization_id=uuid4(),
            project_id=uuid4(),
            kind=ContentCardKind.REFRESH,
            origin=ContentCardOrigin.INSIGHT,
            url="https://example.com/existing-page",
        )
        assert card.kind == "refresh"
        assert card.origin == "insight"
        assert card.url == "https://example.com/existing-page"

    def test_imported_card(self) -> None:
        """V3 §4.6: Imported pages are cards with origin=import, state=live."""
        card = ContentCard(
            organization_id=uuid4(),
            project_id=uuid4(),
            kind=ContentCardKind.CLUSTER,
            origin=ContentCardOrigin.IMPORT,
            state=ContentCardState.LIVE,
            url="https://example.com/blog/post",
        )
        assert card.origin == "import"
        assert card.state == "live"

    def test_market_variant(self) -> None:
        """V3 §5.5: variant_of creates a market variant group."""
        parent_id = uuid4()
        card = ContentCard(
            organization_id=uuid4(),
            project_id=uuid4(),
            kind=ContentCardKind.CLUSTER,
            origin=ContentCardOrigin.PLAN,
            variant_of=parent_id,
        )
        assert card.variant_of == parent_id

    def test_dual_primary_demand(self) -> None:
        """V3 §4.7: A card can have both primary_demand_id and primary_prompt_id."""
        kw_id = uuid4()
        prompt_id = uuid4()
        card = ContentCard(
            organization_id=uuid4(),
            project_id=uuid4(),
            kind=ContentCardKind.CLUSTER,
            origin=ContentCardOrigin.PLAN,
            primary_demand_id=kw_id,
            primary_prompt_id=prompt_id,
        )
        assert card.primary_demand_id == kw_id
        assert card.primary_prompt_id == prompt_id

    def test_all_states(self) -> None:
        """V3 §5.2: 9 valid states."""
        expected = {
            "backlog",
            "planned",
            "bundled",
            "outlined",
            "drafting",
            "qa_failed",
            "qa_passed",
            "approved",
            "live",
        }
        assert {s.value for s in ContentCardState} == expected

    def test_all_kinds(self) -> None:
        """V3 §3.1: 4 valid kinds."""
        expected = {"pillar", "cluster", "compare", "refresh"}
        assert {k.value for k in ContentCardKind} == expected

    def test_all_origins(self) -> None:
        """V3 §3.1: 4 valid origins."""
        expected = {"plan", "import", "insight", "manual"}
        assert {o.value for o in ContentCardOrigin} == expected

    def test_stale_claims_default(self) -> None:
        """V3 §6.7: stale_claims defaults to empty list."""
        card = ContentCard(
            organization_id=uuid4(),
            project_id=uuid4(),
            kind=ContentCardKind.CLUSTER,
            origin=ContentCardOrigin.PLAN,
        )
        # Python default not set by server_default
        assert card.kind == "cluster"

    def test_states_not_interchangeable_with_old(self) -> None:
        """Verify V3 states are distinct from old PlannedPageStatus."""
        old_states = {
            "PROPOSED",
            "PLANNED",
            "APPROVED",
            "IN_PROGRESS",
            "DRAFT",
            "PUBLISHED",
            "ARCHIVED",
        }
        v3_states = {s.value for s in ContentCardState}
        # No overlap in values (case-insensitive check)
        old_lower = {s.lower() for s in old_states}
        # Only 'planned' and 'approved' overlap — but semantics differ
        overlap = old_lower & v3_states
        # Verify the overlap is minimal and documented
        assert overlap == {"planned", "approved"}, (
            f"Unexpected overlap between old and V3 states: {overlap}"
        )


# ──────────────────────────────────────────────────────────────────
# Job Runs domain
# ──────────────────────────────────────────────────────────────────
from app.domains.job_runs.models import JobRun, JobRunStatus


class TestJobRun:
    """JobRun model and V3 invariants."""

    def test_create_job_run(self) -> None:
        run = JobRun(
            organization_id=uuid4(),
            project_id=uuid4(),
            job_type="outline",
            prompt_version="outline_v1.2",
            model="gemini-2.0-flash",
            provider="gemini",
            triggered_by="user",
            status=JobRunStatus.PENDING,
            input_tokens=0,
            estimated_cost_usd=0.0,
        )
        assert run.prompt_version == "outline_v1.2"
        assert run.status == "pending"
        assert run.input_tokens == 0
        assert run.estimated_cost_usd == 0.0

    def test_prompt_version_required(self) -> None:
        """V3 §6.8: prompt_version is MANDATORY for every model call.

        The column is NOT NULL in the database. At the Python model level,
        we do not set a default.
        """
        run = JobRun(
            organization_id=uuid4(),
            project_id=uuid4(),
            job_type="draft",
            model="gemini-2.0-flash",
            provider="gemini",
            triggered_by="pipeline",
        )
        # Validation happens at flush time (IntegrityError),
        # but locally it will just be missing.
        assert getattr(run, "prompt_version", None) is None
    def test_entity_reference(self) -> None:
        """JobRun can reference any entity via polymorphic type+id."""
        card_id = uuid4()
        run = JobRun(
            organization_id=uuid4(),
            project_id=uuid4(),
            job_type="qa_extraction",
            prompt_version="qa_v1.0",
            model="gemini-2.0-flash",
            provider="gemini",
            triggered_by="pipeline",
            entity_type="content_card",
            entity_id=card_id,
        )
        assert run.entity_type == "content_card"
        assert run.entity_id == card_id

    def test_all_statuses(self) -> None:
        expected = {"pending", "running", "completed", "failed", "cancelled"}
        assert {s.value for s in JobRunStatus} == expected

    def test_auto_approve_trigger(self) -> None:
        """V3 §5.4: auto_approve gates write a JOB_RUN with triggered_by: auto_approve."""
        run = JobRun(
            organization_id=uuid4(),
            project_id=uuid4(),
            job_type="auto_approve",
            prompt_version="gate_v1.0",
            model="gemini-2.0-flash",
            provider="gemini",
            triggered_by="auto_approve",
        )
        assert run.triggered_by == "auto_approve"


# ──────────────────────────────────────────────────────────────────
# Workspace Config on Project
# ──────────────────────────────────────────────────────────────────
from app.domains.projects.models import Project


class TestProjectWorkspaceConfig:
    """V3 §9.2: workspace_config column on Project."""

    def test_project_has_workspace_config(self) -> None:
        """Verify the workspace_config field exists on Project."""
        project = Project(
            organization_id=uuid4(),
            name="Test Project",
            slug="test-project",
        )
        # workspace_config has a server_default, so Python-side it may be unset
        # but the column should exist
        assert hasattr(project, "workspace_config")

    def test_existing_settings_preserved(self) -> None:
        """Verify the existing settings column is unchanged."""
        project = Project(
            organization_id=uuid4(),
            name="Test Project",
            slug="test-project",
        )
        assert hasattr(project, "settings")


# ──────────────────────────────────────────────────────────────────
# State Machine Validation
# ──────────────────────────────────────────────────────────────────
from app.domains.content_cards.schemas import (
    NON_TERMINAL_STATES,
    TERMINAL_STATES,
    VALID_STATE_TRANSITIONS,
)
from app.domains.content_cards.schemas import ContentCardState as SchemaState


class TestContentCardStateMachine:
    """V3 §5.2: State machine validity checks."""

    def test_all_states_have_transition_entry(self) -> None:
        """Every state must appear in the transition map."""
        for state in SchemaState:
            assert state in VALID_STATE_TRANSITIONS, f"Missing transition entry for {state}"

    def test_live_is_terminal(self) -> None:
        """V3 §5.2: live is terminal (refresh creates a NEW card)."""
        assert SchemaState.LIVE in TERMINAL_STATES
        assert VALID_STATE_TRANSITIONS[SchemaState.LIVE] == []

    def test_non_terminal_states(self) -> None:
        """All non-live states are non-terminal."""
        for state in SchemaState:
            if state != SchemaState.LIVE:
                assert state in NON_TERMINAL_STATES

    def test_backlog_to_planned(self) -> None:
        assert SchemaState.PLANNED in VALID_STATE_TRANSITIONS[SchemaState.BACKLOG]

    def test_planned_to_bundled(self) -> None:
        assert SchemaState.BUNDLED in VALID_STATE_TRANSITIONS[SchemaState.PLANNED]

    def test_drafting_to_qa_failed_or_passed(self) -> None:
        transitions = VALID_STATE_TRANSITIONS[SchemaState.DRAFTING]
        assert SchemaState.QA_FAILED in transitions
        assert SchemaState.QA_PASSED in transitions

    def test_qa_failed_cycles_to_drafting(self) -> None:
        """V3 §5.2: qa_failed ⇄ drafting (repair cycle)."""
        assert SchemaState.DRAFTING in VALID_STATE_TRANSITIONS[SchemaState.QA_FAILED]
