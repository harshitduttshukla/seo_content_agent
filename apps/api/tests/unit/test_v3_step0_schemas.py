"""V3 Step 0: Pydantic schema validation tests.

Tests the typed Pydantic schemas for workspace configuration, scoring,
market, canvas anchors, and score breakdowns.
"""

from __future__ import annotations

import pytest
from app.domains.canvas.schemas import (
    AutoApproveConfig,
    CanvasAnchor,
    ClaimMarketOverride,
    ClaimRow,
    DigestConfig,
    FunnelWeights,
    MarketConfig,
    ModelConfig,
    PromptScoringConfig,
    ScoringConfig,
    StrikingDistanceConfig,
    TechSEOScoreWeights,
    WordBudgets,
    WorkspaceConfig,
)
from app.domains.content_cards.schemas import (
    ContentCardKind,
    ContentCardOrigin,
    ContentCardState,
    Market,
)
from app.domains.demand.schemas import (
    DemandNodeFunnel,
    DemandNodeType,
    KeywordScoreBreakdown,
    PromptScoreBreakdown,
)
from app.domains.job_runs.schemas import JobRunStatus, JobType, TriggerSource
from pydantic import ValidationError


class TestWorkspaceConfig:
    """V3 §9.2: Workspace configuration validation."""

    def test_empty_config_valid(self) -> None:
        """An empty {} must be valid — all fields have defaults."""
        config = WorkspaceConfig()
        assert config.scoring.w_volume == 0.5
        assert config.scoring.w_gap == 0.3
        assert config.scoring.w_funnel == 0.2
        assert config.word_budgets.pillar == 2000
        assert config.experiment_window_days == 28
        assert config.dedupe_similarity_threshold == 0.86

    def test_full_config_from_v3(self) -> None:
        """V3 §9.2: Parse the exact config from the handoff."""
        config = WorkspaceConfig(
            domain="example.com",
            scoring=ScoringConfig(
                w_volume=0.5,
                w_gap=0.3,
                w_funnel=0.2,
                funnel_weight=FunnelWeights(bofu=1.0, mofu=0.7, tofu=0.4),
            ),
            prompt_scoring=PromptScoringConfig(platform_weight=1.0),
            funnel_definitions={"bofu": "...", "mofu": "...", "tofu": "..."},
            word_budgets=WordBudgets(
                pillar=2000,
                cluster=1000,
                compare=1000,
                refresh="inherit",
                tables_excluded=True,
            ),
            markets=[
                MarketConfig(lang="en", country="GB", spelling="en-GB", currency="GBP")
            ],
            demand_strings_exempt_from_spelling=True,
            banned_words=[],
            competitor_stances={},
            reviewers={"G1": [], "G2": []},
            auto_approve=AutoApproveConfig(),
            soft_warnings_require_dismissal=True,
            digest=DigestConfig(day="Monday", recipients=[]),
            experiment_window_days=28,
            striking_distance=StrikingDistanceConfig(
                position_min=4, position_max=15, impressions_floor=100
            ),
            dedupe_similarity_threshold=0.86,
            cluster_volume_floor=50,
            techseo_score_weights=TechSEOScoreWeights(severe=5, moderate=2, minor=1),
            classification_cache=True,
            models=ModelConfig(default="vendor/model"),
        )
        assert config.domain == "example.com"
        assert config.markets[0].country == "GB"
        assert config.scoring.funnel_weight.bofu == 1.0

    def test_scoring_weight_bounds(self) -> None:
        """Scoring weights must be between 0 and 1."""
        with pytest.raises(ValidationError):
            ScoringConfig(w_volume=1.5)
        with pytest.raises(ValidationError):
            ScoringConfig(w_gap=-0.1)

    def test_dedupe_threshold_bounds(self) -> None:
        with pytest.raises(ValidationError):
            WorkspaceConfig(dedupe_similarity_threshold=1.5)
        with pytest.raises(ValidationError):
            WorkspaceConfig(dedupe_similarity_threshold=-0.1)

    def test_experiment_window_minimum(self) -> None:
        with pytest.raises(ValidationError):
            WorkspaceConfig(experiment_window_days=0)

    def test_monthly_cost_cap(self) -> None:
        config = WorkspaceConfig(monthly_cost_cap_usd=500.0)
        assert config.monthly_cost_cap_usd == 500.0

    def test_monthly_cost_cap_none(self) -> None:
        config = WorkspaceConfig()
        assert config.monthly_cost_cap_usd is None

    def test_monthly_cost_cap_negative_invalid(self) -> None:
        with pytest.raises(ValidationError):
            WorkspaceConfig(monthly_cost_cap_usd=-10.0)


class TestCanvasAnchor:
    """V3 §3.1: Canvas anchor schema."""

    def test_default_anchor(self) -> None:
        anchor = CanvasAnchor()
        assert anchor.text == ""
        assert anchor.primary is False

    def test_primary_anchor(self) -> None:
        anchor = CanvasAnchor(text="Enterprise SaaS", primary=True)
        assert anchor.text == "Enterprise SaaS"
        assert anchor.primary is True


class TestClaimMarketOverride:
    """V3 §5.5: Per-market claim override."""

    def test_default(self) -> None:
        override = ClaimMarketOverride()
        assert override.text == ""
        assert override.evidence == ""
        assert override.excluded is False

    def test_exclude_market(self) -> None:
        override = ClaimMarketOverride(excluded=True)
        assert override.excluded is True


class TestMarket:
    """V3 §5.5: Market schema."""

    def test_default(self) -> None:
        m = Market()
        assert m.lang == "en"
        assert m.country == "US"

    def test_custom(self) -> None:
        m = Market(lang="de", country="DE")
        assert m.lang == "de"
        assert m.country == "DE"

    def test_country_length_validation(self) -> None:
        with pytest.raises(ValidationError):
            Market(country="USA")  # 3 chars, max is 2


class TestKeywordScoreBreakdown:
    """V3 §4.5: Keyword score breakdown."""

    def test_defaults(self) -> None:
        b = KeywordScoreBreakdown()
        assert b.volume_component == 0.0
        assert b.gap_component == 0.0
        assert b.funnel_component == 0.0

    def test_no_negative(self) -> None:
        with pytest.raises(ValidationError):
            KeywordScoreBreakdown(volume_component=-1.0)


class TestPromptScoreBreakdown:
    """V3 §4.7: Prompt score breakdown."""

    def test_defaults(self) -> None:
        b = PromptScoreBreakdown()
        assert b.citation_gap == 0.0
        assert b.platform_count == 0

    def test_citation_gap_bounds(self) -> None:
        with pytest.raises(ValidationError):
            PromptScoreBreakdown(citation_gap=1.5)


class TestClaimRowEnum:
    """V3 §3.1: All claim row types."""

    def test_count(self) -> None:
        assert len(ClaimRow) == 8

    def test_pitch_is_a_row(self) -> None:
        """V3 §4.1: The elevator pitch is a claim cell."""
        assert ClaimRow.PITCH.value == "pitch"


class TestDemandEnums:
    """V3 Demand domain enums."""

    def test_types(self) -> None:
        assert DemandNodeType.KEYWORD.value == "keyword"
        assert DemandNodeType.PROMPT.value == "prompt"

    def test_funnels(self) -> None:
        """V3 uses lowercase funnel names."""
        assert {f.value for f in DemandNodeFunnel} == {"tofu", "mofu", "bofu"}


class TestContentCardEnums:
    """V3 ContentCard domain enums."""

    def test_kinds_count(self) -> None:
        assert len(ContentCardKind) == 4

    def test_states_count(self) -> None:
        """V3 §5.2: 9 states."""
        assert len(ContentCardState) == 9

    def test_origins_count(self) -> None:
        assert len(ContentCardOrigin) == 4


class TestJobRunEnums:
    """V3 JobRun domain enums."""

    def test_statuses(self) -> None:
        assert len(JobRunStatus) == 5

    def test_job_types(self) -> None:
        """V3 §6.8: Five production model calls plus pipeline operations."""
        assert JobType.OUTLINE.value == "outline"
        assert JobType.DRAFT.value == "draft"
        assert JobType.QA_EXTRACTION.value == "qa_extraction"
        assert JobType.REPAIR.value == "repair"
        assert JobType.SECTION_REGENERATE.value == "section_regenerate"

    def test_trigger_sources(self) -> None:
        assert TriggerSource.AUTO_APPROVE.value == "auto_approve"
        assert TriggerSource.MCP.value == "mcp"
