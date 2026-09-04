"""Deterministic keyword clustering engine using lexical, entity, and intent similarity."""

import re
from typing import NamedTuple
from uuid import UUID

STOP_WORDS = {
    "a",
    "an",
    "the",
    "in",
    "on",
    "at",
    "for",
    "to",
    "of",
    "and",
    "or",
    "with",
    "by",
    "is",
    "are",
    "was",
    "were",
    "be",
    "been",
    "from",
    "as",
    "it",
    "this",
    "that",
    "how",
    "what",
    "why",
    "when",
    "where",
    "who",
    "your",
    "my",
    "our",
    "do",
    "does",
    "did",
    "doing",
    "can",
    "could",
    "will",
    "would",
    "should",
    "about",
    "into",
    "over",
    "after",
}


class KeywordClusteringInput(NamedTuple):
    id: UUID
    keyword: str
    normalized_keyword: str
    search_volume: int
    keyword_difficulty: float
    cpc: float
    intent: str
    priority_score: float
    business_value_score: float


class ClusterCandidate(NamedTuple):
    cluster_name: str
    primary_keyword_id: UUID
    primary_keyword: str
    intent: str
    cluster_score: float
    rationale: str
    member_keyword_ids: list[UUID]
    similarities: dict[UUID, float]


def tokenize_keyword(text: str) -> set[str]:
    """Tokenize and filter stop words from keyword string."""
    tokens = re.findall(r"\b[a-z0-9]+\b", text.lower())
    filtered = {t for t in tokens if t not in STOP_WORDS and len(t) > 1}
    return filtered or set(tokens)


def compute_keyword_similarity(
    kw1: KeywordClusteringInput,
    kw2: KeywordClusteringInput,
) -> float:
    """Compute semantic/lexical similarity between two keywords (0.0 to 1.0)."""
    if kw1.normalized_keyword == kw2.normalized_keyword:
        return 1.0

    tokens1 = tokenize_keyword(kw1.keyword)
    tokens2 = tokenize_keyword(kw2.keyword)

    if not tokens1 or not tokens2:
        return 0.0

    intersection = tokens1.intersection(tokens2)
    union = tokens1.union(tokens2)
    jaccard = len(intersection) / len(union) if union else 0.0

    # Strong partial overlap bonus when main root tokens match (e.g. "seo", "audit")
    overlap_ratio = len(intersection) / min(len(tokens1), len(tokens2))
    overlap_bonus = 0.20 if overlap_ratio >= 0.66 else 0.0

    phrase_score = 0.0
    if (
        kw1.normalized_keyword in kw2.normalized_keyword
        or kw2.normalized_keyword in kw1.normalized_keyword
    ):
        phrase_score = 0.25

    intent_match = 0.15 if kw1.intent == kw2.intent else 0.0
    total_sim = (jaccard * 0.50) + overlap_bonus + phrase_score + intent_match
    return min(1.0, round(total_sim, 3))


def cluster_keywords(
    keywords: list[KeywordClusteringInput],
    similarity_threshold: float = 0.45,
) -> list[ClusterCandidate]:
    """Cluster keywords deterministically using token similarity and intent grouping."""
    if not keywords:
        return []

    sorted_kws = sorted(
        keywords,
        key=lambda k: (k.priority_score, k.search_volume),
        reverse=True,
    )

    assigned: set[UUID] = set()
    clusters: list[ClusterCandidate] = []

    for leader in sorted_kws:
        if leader.id in assigned:
            continue

        cluster_members: list[KeywordClusteringInput] = [leader]
        similarities: dict[UUID, float] = {leader.id: 1.0}
        assigned.add(leader.id)

        for candidate in sorted_kws:
            if candidate.id in assigned:
                continue

            sim = compute_keyword_similarity(leader, candidate)
            if sim >= similarity_threshold:
                cluster_members.append(candidate)
                similarities[candidate.id] = sim
                assigned.add(candidate.id)

        primary = max(
            cluster_members,
            key=lambda k: (k.search_volume, k.priority_score),
        )

        avg_priority = sum(m.priority_score for m in cluster_members) / len(cluster_members)
        cluster_score = round(min(100.0, avg_priority + (len(cluster_members) * 1.5)), 1)

        all_tokens: list[str] = []
        for m in cluster_members:
            all_tokens.extend(list(tokenize_keyword(m.keyword)))
        token_freq: dict[str, int] = {}
        for t in all_tokens:
            token_freq[t] = token_freq.get(t, 0) + 1
        threshold_count = max(1, len(cluster_members) // 2)
        common_tokens = [t for t, count in token_freq.items() if count >= threshold_count]
        themes = ", ".join(common_tokens[:4]) or primary.keyword

        rationale = (
            f"Clustered {len(cluster_members)} keywords around primary term '{primary.keyword}'. "
            f"Key overlapping themes: {themes} with {leader.intent} intent."
        )

        clusters.append(
            ClusterCandidate(
                cluster_name=primary.keyword.title(),
                primary_keyword_id=primary.id,
                primary_keyword=primary.keyword,
                intent=primary.intent,
                cluster_score=cluster_score,
                rationale=rationale,
                member_keyword_ids=[m.id for m in cluster_members],
                similarities=similarities,
            )
        )

    return clusters
