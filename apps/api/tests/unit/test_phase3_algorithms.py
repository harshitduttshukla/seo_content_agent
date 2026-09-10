"""Unit tests for Phase 3 algorithms: Normalization, Intent, Scoring, and Clustering."""

from uuid import uuid4

import pytest
from app.core.errors import DomainError
from app.domains.keywords.clustering import (
    KeywordClusteringInput,
    cluster_keywords,
    compute_keyword_similarity,
    tokenize_keyword,
)
from app.domains.keywords.importer import parse_csv_keywords
from app.domains.keywords.intent import (
    calculate_business_value,
    calculate_priority_score,
    classify_intent_and_funnel,
)
from app.domains.keywords.models import FunnelStage, SearchIntent
from app.domains.keywords.normalizer import normalize_keyword


def test_keyword_normalization() -> None:
    assert normalize_keyword("  Best   SEO   Tools  ") == "best seo tools"
    assert normalize_keyword("Enterprise \u2013 Software") == "enterprise software"
    assert normalize_keyword("What's   the   Cost???") == "whats the cost"
    assert normalize_keyword("B2B SaaS #1 Platform!") == "b2b saas 1 platform"


def test_intent_classification_signals() -> None:
    # Transactional
    res = classify_intent_and_funnel("buy enterprise seo software")
    assert res.intent == SearchIntent.TRANSACTIONAL
    assert res.funnel_stage == FunnelStage.BOFU
    assert res.confidence >= 0.90

    # Commercial
    res = classify_intent_and_funnel("best content intelligence platform vs competitors")
    assert res.intent == SearchIntent.COMMERCIAL
    assert res.funnel_stage == FunnelStage.MOFU

    # Navigational
    res = classify_intent_and_funnel("acme corp login portal")
    assert res.intent == SearchIntent.NAVIGATIONAL
    assert res.funnel_stage == FunnelStage.BOFU

    # Local
    res = classify_intent_and_funnel("seo agency in new york")
    assert res.intent == SearchIntent.LOCAL
    assert res.funnel_stage == FunnelStage.BOFU

    # Informational
    res = classify_intent_and_funnel("how to build a content architecture step by step")
    assert res.intent == SearchIntent.INFORMATIONAL
    assert res.funnel_stage == FunnelStage.TOFU


def test_business_value_and_priority_scores() -> None:
    # High intent + strategic term match + CPC
    bv = calculate_business_value(
        intent=SearchIntent.TRANSACTIONAL,
        cpc=12.50,
        keyword="buy enterprise content software",
        strategy_terms=["content software", "enterprise content"],
    )
    assert bv > 90.0

    # Informational without strategic term
    bv_info = calculate_business_value(
        intent=SearchIntent.INFORMATIONAL,
        cpc=0.0,
        keyword="what is seo",
        strategy_terms=[],
    )
    assert bv_info == 40.0

    # Priority score: High volume, low difficulty, high business value
    p_high = calculate_priority_score(
        search_volume=10000,
        keyword_difficulty=20.0,
        business_value_score=90.0,
        intent=SearchIntent.TRANSACTIONAL,
    )
    assert p_high >= 75.0

    # Priority score: Zero volume, high difficulty, low business value
    p_low = calculate_priority_score(
        search_volume=0,
        keyword_difficulty=95.0,
        business_value_score=20.0,
        intent=SearchIntent.NAVIGATIONAL,
    )
    assert p_low < 25.0


def test_tokenization_and_keyword_similarity() -> None:
    tokens = tokenize_keyword("how to do keyword research for seo")
    assert "keyword" in tokens
    assert "research" in tokens
    assert "seo" in tokens
    assert "how" not in tokens  # Stop word removed

    kw1 = KeywordClusteringInput(
        id=uuid4(),
        keyword="b2b seo strategy",
        normalized_keyword="b2b seo strategy",
        search_volume=1200,
        keyword_difficulty=45.0,
        cpc=5.0,
        intent="INFORMATIONAL",
        priority_score=70.0,
        business_value_score=60.0,
    )
    kw2 = KeywordClusteringInput(
        id=uuid4(),
        keyword="seo strategy for b2b",
        normalized_keyword="seo strategy for b2b",
        search_volume=800,
        keyword_difficulty=40.0,
        cpc=4.5,
        intent="INFORMATIONAL",
        priority_score=68.0,
        business_value_score=60.0,
    )
    kw3 = KeywordClusteringInput(
        id=uuid4(),
        keyword="buy running shoes",
        normalized_keyword="buy running shoes",
        search_volume=50000,
        keyword_difficulty=80.0,
        cpc=1.5,
        intent="TRANSACTIONAL",
        priority_score=50.0,
        business_value_score=80.0,
    )

    sim_related = compute_keyword_similarity(kw1, kw2)
    sim_unrelated = compute_keyword_similarity(kw1, kw3)

    assert sim_related >= 0.70
    assert sim_unrelated <= 0.10


def test_clustering_engine() -> None:
    kw1 = KeywordClusteringInput(
        id=uuid4(),
        keyword="seo audit guide",
        normalized_keyword="seo audit guide",
        search_volume=2400,
        keyword_difficulty=35.0,
        cpc=3.0,
        intent="INFORMATIONAL",
        priority_score=75.0,
        business_value_score=60.0,
    )
    kw2 = KeywordClusteringInput(
        id=uuid4(),
        keyword="how to do an seo audit",
        normalized_keyword="how to do an seo audit",
        search_volume=5400,
        keyword_difficulty=40.0,
        cpc=3.5,
        intent="INFORMATIONAL",
        priority_score=80.0,
        business_value_score=65.0,
    )
    kw3 = KeywordClusteringInput(
        id=uuid4(),
        keyword="technical seo audit checklist",
        normalized_keyword="technical seo audit checklist",
        search_volume=1800,
        keyword_difficulty=30.0,
        cpc=4.0,
        intent="INFORMATIONAL",
        priority_score=78.0,
        business_value_score=70.0,
    )
    kw4 = KeywordClusteringInput(
        id=uuid4(),
        keyword="buy email marketing software",
        normalized_keyword="buy email marketing software",
        search_volume=1000,
        keyword_difficulty=60.0,
        cpc=15.0,
        intent="TRANSACTIONAL",
        priority_score=72.0,
        business_value_score=90.0,
    )

    clusters = cluster_keywords([kw1, kw2, kw3, kw4], similarity_threshold=0.45)
    assert len(clusters) == 2  # SEO Audit cluster + Email Marketing cluster

    audit_cluster = next(c for c in clusters if "Audit" in c.cluster_name)
    assert len(audit_cluster.member_keyword_ids) == 3
    assert audit_cluster.primary_keyword_id == kw2.id  # Highest search volume & priority


def test_csv_importer() -> None:
    csv_data = b"""Keyword,Search Volume,Difficulty,CPC,Intent
b2b seo tools,2400,45.5,5.20,COMMERCIAL
how to index pages fast,1200,30,1.50,INFORMATIONAL
pricing for content intelligence,500,25,12.00,TRANSACTIONAL
"""
    rows = parse_csv_keywords(csv_data)
    assert len(rows) == 3
    assert rows[0]["keyword"] == "b2b seo tools"
    assert rows[0]["volume"] == 2400
    assert rows[0]["difficulty"] == 45.5
    assert rows[0]["cpc"] == 5.20
    assert rows[0]["intent"] == "COMMERCIAL"

    # Test error handling on missing keyword header
    bad_csv = b"""Title,Volume\nPage 1,100"""
    with pytest.raises(DomainError) as exc_info:
        parse_csv_keywords(bad_csv)
    assert exc_info.value.code == "MISSING_KEYWORD_COLUMN"
