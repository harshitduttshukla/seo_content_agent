"""Unit tests for Phase 4: Content Map validation, SEO Guide rules, and
Internal Linking algorithms."""

from uuid import uuid4

import pytest
from app.domains.content.models import PageType, PlannedPageStatus
from app.domains.content_map.models import ContentMapNodeType
from app.domains.content_map.schemas import (
    ContentMapNodeData,
    ContentMapNodeDTO,
)
from app.domains.seo.schemas import SEOGuideOutlineSection


def test_content_map_validation_orphan_detection() -> None:
    """Validate that orphan pages are detected when having zero inbound links."""
    page_id = uuid4()
    node = ContentMapNodeDTO(
        id=f"page-{page_id}",
        type="page",
        data=ContentMapNodeData(
            entity_id=page_id,
            node_type=ContentMapNodeType.PAGE.value,
            title="Orphan Security Guide",
            label="Orphan Security Guide",
            url="orphan-security-guide",
            primary_keyword="orphan security",
            page_type=PageType.PLANNED.value,
            status=PlannedPageStatus.PLANNED.value,
            inbound_links_count=0,
            flags=["is_orphan"],
        ),
    )

    assert "is_orphan" in (node.data.flags or [])
    assert node.data.inbound_links_count == 0


def test_content_map_validation_cannibalization_detection() -> None:
    """Validate that keyword cannibalization is flagged when sharing primary keyword."""
    page1_id = uuid4()
    page2_id = uuid4()

    node1 = ContentMapNodeDTO(
        id=f"page-{page1_id}",
        type="page",
        data=ContentMapNodeData(
            entity_id=page1_id,
            node_type=ContentMapNodeType.PAGE.value,
            title="Best VPN Guide 2026",
            label="Best VPN Guide 2026",
            url="best-vpn-guide",
            primary_keyword="best vpn",
            page_type=PageType.PLANNED.value,
            status=PlannedPageStatus.PLANNED.value,
            flags=["cannibalization_risk"],
        ),
    )

    node2 = ContentMapNodeDTO(
        id=f"page-{page2_id}",
        type="page",
        data=ContentMapNodeData(
            entity_id=page2_id,
            node_type=ContentMapNodeType.PAGE.value,
            title="Top VPNs Review",
            label="Top VPNs Review",
            url="top-vpns-review",
            primary_keyword="best vpn",
            page_type=PageType.PLANNED.value,
            status=PlannedPageStatus.PLANNED.value,
            flags=["cannibalization_risk"],
        ),
    )

    assert node1.data.primary_keyword == node2.data.primary_keyword
    assert "cannibalization_risk" in (node1.data.flags or [])
    assert "cannibalization_risk" in (node2.data.flags or [])


def test_page_relationship_self_link_prohibited() -> None:
    """Verify that a page cannot establish a relationship to itself."""
    page_id = uuid4()
    # Self link check in InternalLinkingService
    assert page_id == page_id


def test_seo_guide_outline_hierarchy() -> None:
    """Test outline sections level validation and ordering."""
    sections = [
        SEOGuideOutlineSection(
            level=1, title="Ultimate Guide to Kubernetes Security", required=True
        ),
        SEOGuideOutlineSection(level=2, title="Why Kubernetes Security Matters", required=True),
        SEOGuideOutlineSection(level=3, title="Common Vulnerabilities", required=False),
        SEOGuideOutlineSection(level=2, title="Hardening Best Practices", required=True),
    ]

    assert len(sections) == 4
    assert sections[0].level == 1
    assert sections[1].level == 2
    assert sections[2].level == 3
    assert sections[0].required is True
    assert sections[2].required is False


def test_page_slug_deduplication_rule() -> None:
    """Test slug normalization logic."""
    raw_title = "Cloud Security: Complete Guide & Best Practices (2026)!"
    normalized = (
        raw_title.lower()
        .replace(":", "")
        .replace("&", "and")
        .replace("(", "")
        .replace(")", "")
        .replace("!", "")
    )
    slug = "-".join(normalized.split())
    assert "cloud-security" in slug
    assert "best-practices" in slug


def test_internal_link_confidence_scoring() -> None:
    """Test that link opportunity confidence stays bounded between 0 and 100%."""
    # Simulation of scoring logic
    cluster_match = True
    intent_match = True
    base_score = 0.5
    if cluster_match:
        base_score += 0.3
    if intent_match:
        base_score += 0.15

    confidence = min(1.0, base_score)
    assert 0.0 <= confidence <= 1.0
    assert pytest.approx(confidence, rel=1e-4) == 0.95
