"""Structured Intent Classifier for AI Orchestration."""

from uuid import UUID

from app.domains.orchestrator.models import WorkflowIntent
from app.domains.orchestrator.schemas import IntentClassificationResult


class IntentClassifier:
    """Classifies user queries into structured workflow intents using deterministic

    patterns and semantic heuristics.
    """

    def classify(
        self,
        message: str,
        document_id: UUID | None = None,
        selected_block_ids: list[str] | None = None,
    ) -> IntentClassificationResult:
        query = message.lower().strip()
        selected_blocks = selected_block_ids or []

        # 1. Multi-step detection
        has_seo = any(k in query for k in ["seo", "quality", "audit", "score", "optimize"])
        has_linking = any(k in query for k in ["link", "internal link", "links", "anchor"])
        has_outline = any(k in query for k in ["outline", "structure", "headings"])
        has_rewrite = any(k in query for k in ["rewrite", "expand", "shorten", "improve", "polish"])

        matched_intents = sum(
            [bool(has_seo), bool(has_linking), bool(has_outline), bool(has_rewrite)]
        )
        if matched_intents >= 2 or ("and" in query and (has_seo and (has_linking or has_rewrite))):
            return IntentClassificationResult(
                intent=WorkflowIntent.MULTI_STEP_CONTENT_TASK,
                confidence=0.95,
                document_id=document_id,
                requires_tools=True,
                parameters={
                    "has_seo": has_seo,
                    "has_linking": has_linking,
                    "has_outline": has_outline,
                    "has_rewrite": has_rewrite,
                },
            )

        # 2. SEO Quality & Audit
        seo_terms = [
            "seo quality",
            "seo check",
            "seo audit",
            "quality check",
            "score",
            "seo report",
        ]
        if any(k in query for k in seo_terms):
            return IntentClassificationResult(
                intent=WorkflowIntent.ANALYZE_SEO,
                confidence=0.95,
                document_id=document_id,
                requires_tools=True,
            )

        # 3. Internal Linking
        link_terms = [
            "internal link",
            "link opportunities",
            "suggest links",
            "add links",
            "linking",
        ]
        if any(k in query for k in link_terms):
            return IntentClassificationResult(
                intent=WorkflowIntent.FIND_INTERNAL_LINKS,
                confidence=0.92,
                document_id=document_id,
                requires_tools=True,
            )

        # 4. Metadata Optimization
        meta_terms = [
            "meta title",
            "meta description",
            "metadata",
            "title tag",
            "meta tags",
        ]
        if any(k in query for k in meta_terms):
            return IntentClassificationResult(
                intent=WorkflowIntent.OPTIMIZE_METADATA,
                confidence=0.90,
                document_id=document_id,
                requires_tools=True,
            )

        # 5. Outline Generation
        outline_terms = [
            "generate outline",
            "create outline",
            "headings",
            "subheadings",
            "section outline",
        ]
        if any(k in query for k in outline_terms):
            return IntentClassificationResult(
                intent=WorkflowIntent.GENERATE_OUTLINE,
                confidence=0.90,
                document_id=document_id,
                requires_tools=True,
            )

        # 6. Topic Research
        topic_terms = [
            "research topic",
            "topic cluster",
            "entities",
            "subtopics",
            "keyword research",
        ]
        if any(k in query for k in topic_terms):
            return IntentClassificationResult(
                intent=WorkflowIntent.RESEARCH_TOPIC,
                confidence=0.85,
                document_id=document_id,
                requires_tools=True,
            )

        # 7. Content Analysis
        analysis_terms = [
            "word count",
            "content length",
            "keyword density",
            "keyword count",
            "analyze content",
        ]
        if any(k in query for k in analysis_terms):
            return IntentClassificationResult(
                intent=WorkflowIntent.ANALYZE_CONTENT,
                confidence=0.88,
                document_id=document_id,
                requires_tools=True,
            )

        # 8. Single Section / Document Edit
        return IntentClassificationResult(
            intent=WorkflowIntent.EDIT_DOCUMENT,
            confidence=0.80,
            document_id=document_id,
            requires_tools=True,
            parameters={"target_blocks": selected_blocks},
        )
