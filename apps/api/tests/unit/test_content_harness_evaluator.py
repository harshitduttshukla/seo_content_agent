"""Unit tests for the deterministic Content Harness evaluator."""

import pytest
from app.domains.content.brief_schemas import BrandRequirements, InternalLinkTarget
from app.domains.content_harness.evaluator import evaluate_content
from app.domains.content_harness.schemas import (
    ContentHarnessInput,
    FindingStatus,
    HarnessGeneratedContent,
    HarnessSection,
)
from uuid import uuid4


@pytest.fixture
def base_input() -> ContentHarnessInput:
    return ContentHarnessInput(
        project_id=uuid4(),
        primary_keyword="fleet vehicle tracking",
        secondary_keywords=["gps tracking", "fleet diagnostics", "route optimization"],
        search_intent="INFORMATIONAL",
        target_audience="Fleet managers",
        target_word_count=500,
        required_topics=["Hardware and sensors", "Fuel reduction benefits"],
        required_questions=["How does fleet vehicle tracking work?"],
        brand_rules=BrandRequirements(
            tone="Professional, practical",
            voice="Expert",
            style="Clear",
            words_to_avoid=["cheap", "miracle", "guaranteed"],
        ),
        internal_link_targets=[
            InternalLinkTarget(
                url="/telematics-platform",
                anchor_text="telematics platform",
                reason="Connect core pillar",
            )
        ],
    )


def test_evaluator_perfect_content(base_input: ContentHarnessInput) -> None:
    content_text = (
        "Implementing fleet vehicle tracking gives logistics directors full visibility into operations. "
        "In this guide, we explore how fleet vehicle tracking works and how onboard hardware and sensors "
        "deliver real-time telemetry to reduce fuel consumption. Learn more via our [telematics platform](/telematics-platform). "
        "With gps tracking and route optimization, modern telematics reduces idle time. "
    )
    # Pad to ~500 words to satisfy target word count tolerance
    body = content_text + (" Fleet diagnostics ensure vehicle reliability across regional depots." * 55)

    generated = HarnessGeneratedContent(
        title="Complete Guide to Fleet Vehicle Tracking for Modern Fleets",
        meta_description="Learn how fleet vehicle tracking optimizes fuel, reduces wear, and automates maintenance.",
        content=body,
        sections=[
            HarnessSection(
                heading="How Fleet Vehicle Tracking Works",
                level=2,
                content="Hardware and sensors capture engine data continuously.",
            ),
            HarnessSection(
                heading="Fuel Reduction Benefits and ROI",
                level=2,
                content="Logistics fleets achieve measurable savings through route optimization.",
            ),
        ],
        used_keywords=["fleet vehicle tracking", "gps tracking", "fleet diagnostics", "route optimization"],
        internal_links=[{"url": "/telematics-platform", "anchor_text": "telematics platform"}],
        word_count=len(body.split()),
    )

    scorecard = evaluate_content(generated, base_input)

    assert scorecard.technical_validity == "PASS"
    assert scorecard.seo_score >= 80.0
    assert scorecard.content_score >= 80.0
    assert scorecard.brand_score == 100.0
    assert scorecard.linking_score == 100.0
    assert scorecard.overall_score >= 80.0
    assert scorecard.status == "PASS"

    # Confirm key pass findings
    rules_passed = {f.rule for f in scorecard.findings if f.status == FindingStatus.PASS}
    assert "primary_keyword_in_title" in rules_passed
    assert "primary_keyword_in_intro" in rules_passed
    assert "primary_keyword_in_headings" in rules_passed
    assert "forbidden_words" in rules_passed
    assert "approved_links" in rules_passed


def test_evaluator_forbidden_words_penalty(base_input: ContentHarnessInput) -> None:
    generated = HarnessGeneratedContent(
        title="Fleet Vehicle Tracking Guide",
        meta_description="Guide to fleet vehicle tracking.",
        content="This is a cheap miracle tool with guaranteed success for fleet vehicle tracking. How fleet vehicle tracking works is simple.",
        sections=[
            HarnessSection(heading="Overview of Fleet Vehicle Tracking", level=2, content="Hardware and sensors."),
        ],
        used_keywords=["fleet vehicle tracking"],
    )

    scorecard = evaluate_content(generated, base_input)

    # 3 forbidden words ("cheap", "miracle", "guaranteed") => 100 - (3 * 25) = 25
    assert scorecard.brand_score <= 30.0
    assert scorecard.status == "NEEDS IMPROVEMENT"

    forbidden_findings = [f for f in scorecard.findings if f.rule == "forbidden_words" and f.status == FindingStatus.FAIL]
    assert len(forbidden_findings) == 3


def test_evaluator_missing_keyword_and_malformed_output(base_input: ContentHarnessInput) -> None:
    # Missing title and body doesn't contain primary keyword
    generated = HarnessGeneratedContent(
        title="",
        content="Short content without the primary keyword.",
        sections=[],
    )

    scorecard = evaluate_content(generated, base_input)

    assert scorecard.technical_validity == "FAIL"
    assert scorecard.status == "NEEDS IMPROVEMENT"

    seo_findings = {f.rule: f.status for f in scorecard.findings}
    assert seo_findings.get("primary_keyword_in_title") == FindingStatus.FAIL
    assert seo_findings.get("primary_keyword_in_intro") == FindingStatus.FAIL


def test_evaluator_word_count_scaling(base_input: ContentHarnessInput) -> None:
    # Target is 500 words, provide only 150 words
    short_text = "fleet vehicle tracking " * 30
    generated = HarnessGeneratedContent(
        title="fleet vehicle tracking overview",
        content=short_text,
        sections=[
            HarnessSection(heading="fleet vehicle tracking section", level=2, content=short_text),
            HarnessSection(heading="fleet vehicle tracking second", level=2, content=short_text),
        ],
    )

    scorecard = evaluate_content(generated, base_input)

    # Word count tolerance should flag a warning or failure
    wc_finding = next(f for f in scorecard.findings if f.rule == "word_count_tolerance")
    assert wc_finding.status in (FindingStatus.WARN, FindingStatus.FAIL)
    assert scorecard.content_score < 100.0


def test_evaluator_internal_link_verification(base_input: ContentHarnessInput) -> None:
    generated = HarnessGeneratedContent(
        title="Complete fleet vehicle tracking",
        content="fleet vehicle tracking explanation with hardware and sensors and fuel reduction benefits.",
        sections=[
            HarnessSection(heading="fleet vehicle tracking basics", level=2, content="How fleet vehicle tracking works."),
            HarnessSection(heading="fleet vehicle tracking extra", level=2, content="Extra details."),
        ],
        internal_links=[],  # No links provided despite base_input requiring /telematics-platform
    )

    scorecard = evaluate_content(generated, base_input)

    link_finding = next(f for f in scorecard.findings if f.rule == "approved_links")
    assert link_finding.status == FindingStatus.FAIL
    assert scorecard.linking_score < 50.0
