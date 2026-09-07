"""Workflow Planner for transforming user requests and intents into structured execution plans."""

from uuid import UUID

from app.domains.orchestrator.models import WorkflowIntent
from app.domains.orchestrator.policies import (
    ABSOLUTE_MAX_WORKFLOW_STEPS,
    DEFAULT_MAX_WORKFLOW_STEPS,
    requires_human_approval,
)
from app.domains.orchestrator.schemas import IntentClassificationResult, WorkflowPlanStep
from app.domains.orchestrator.tool_registry import ToolRegistry


class WorkflowPlanner:
    def __init__(self, registry: ToolRegistry | None = None) -> None:
        self._registry = registry or ToolRegistry()

    def create_plan(
        self,
        *,
        intent_result: IntentClassificationResult,
        user_message: str,
        document_id: UUID,
        selected_block_ids: list[str] | None = None,
        max_steps: int = DEFAULT_MAX_WORKFLOW_STEPS,
    ) -> list[WorkflowPlanStep]:
        """Translates intent and context into an ordered list of WorkflowPlanSteps."""
        steps: list[WorkflowPlanStep] = []
        bounded_limit = min(max_steps, ABSOLUTE_MAX_WORKFLOW_STEPS)
        target_block = selected_block_ids[0] if selected_block_ids else "block_001"
        query_lower = user_message.lower()

        intent = intent_result.intent

        if intent == WorkflowIntent.MULTI_STEP_CONTENT_TASK:
            # 1. Read document
            self._add_step(
                steps,
                tool_name="read_document",
                description="Read current document structure and blocks",
                arguments={"document_id": document_id},
            )
            # 2. SEO Quality Check
            self._add_step(
                steps,
                tool_name="seo_quality_check",
                description="Evaluate deterministic SEO quality rules",
                arguments={"document_id": document_id},
            )
            # 3. Find Link Opportunities
            self._add_step(
                steps,
                tool_name="find_link_opportunities",
                description="Retrieve approved link opportunities for the project",
                arguments={"document_id": document_id},
            )
            # 4. Suggest Internal Links
            self._add_step(
                steps,
                tool_name="suggest_internal_links",
                description="Identify relevant blocks and anchor matches",
                arguments={"document_id": document_id, "limit": 3},
            )
            # 5. Formulate Patch (WRITE / Human Approval Gate)
            if "expand" in query_lower:
                write_tool = "expand_section"
            elif "shorten" in query_lower or "concise" in query_lower:
                write_tool = "shorten_section"
            elif "link" in query_lower:
                write_tool = "insert_internal_link"
            else:
                write_tool = "rewrite_section"

            self._add_step(
                steps,
                tool_name=write_tool,
                description=f"Propose structured patch using {write_tool} (requires approval)",
                arguments={
                    "document_id": document_id,
                    "block_id": target_block,
                    "instruction": user_message,
                    "url": "/technical-seo-guide",
                    "anchor_text": "technical SEO guide",
                },
            )

        elif intent == WorkflowIntent.ANALYZE_SEO:
            self._add_step(
                steps,
                tool_name="read_document",
                description="Read document content for SEO evaluation",
                arguments={"document_id": document_id},
            )
            self._add_step(
                steps,
                tool_name="seo_quality_check",
                description="Evaluate deterministic SEO checks (headings, word count, topics)",
                arguments={"document_id": document_id},
            )
            self._add_step(
                steps,
                tool_name="keyword_check",
                description="Verify primary and secondary keyword density",
                arguments={"document_id": document_id},
            )
            self._add_step(
                steps,
                tool_name="metadata_check",
                description="Validate H1 and meta tags consistency",
                arguments={"document_id": document_id},
            )

        elif intent == WorkflowIntent.FIND_INTERNAL_LINKS:
            self._add_step(
                steps,
                tool_name="read_document",
                description="Read current document blocks",
                arguments={"document_id": document_id},
            )
            self._add_step(
                steps,
                tool_name="find_link_opportunities",
                description="Retrieve active linking opportunities",
                arguments={"document_id": document_id},
            )
            self._add_step(
                steps,
                tool_name="suggest_internal_links",
                description="Match candidate anchors with document text",
                arguments={"document_id": document_id, "limit": 5},
            )
            self._add_step(
                steps,
                tool_name="insert_internal_link",
                description="Propose internal link insertion (requires approval)",
                arguments={
                    "document_id": document_id,
                    "block_id": target_block,
                    "url": "/internal-linking-guide",
                    "anchor_text": "internal linking guide",
                },
            )

        elif intent == WorkflowIntent.GENERATE_OUTLINE:
            self._add_step(
                steps,
                tool_name="read_document",
                description="Read current document context",
                arguments={"document_id": document_id},
            )
            self._add_step(
                steps,
                tool_name="generate_outline",
                description="Extract outline headings from brief and SEO guide",
                arguments={"document_id": document_id},
            )

        elif intent == WorkflowIntent.OPTIMIZE_METADATA:
            self._add_step(
                steps,
                tool_name="read_document",
                description="Read current document title and headings",
                arguments={"document_id": document_id},
            )
            self._add_step(
                steps,
                tool_name="metadata_check",
                description="Audit meta title and description against search guidelines",
                arguments={"document_id": document_id},
            )

        elif intent == WorkflowIntent.ANALYZE_CONTENT:
            self._add_step(
                steps,
                tool_name="read_document",
                description="Read document blocks and word counts",
                arguments={"document_id": document_id},
            )
            self._add_step(
                steps,
                tool_name="keyword_check",
                description="Analyze keyword frequencies and density",
                arguments={"document_id": document_id},
            )

        else:
            # Default: EDIT_DOCUMENT
            self._add_step(
                steps,
                tool_name="read_document",
                description="Read targeted document section",
                arguments={"document_id": document_id},
            )
            if any(k in query_lower for k in ["expand", "elaborate", "longer", "detail"]):
                tool_choice = "expand_section"
            elif any(k in query_lower for k in ["short", "shorter", "shorten", "concise", "brief"]):
                tool_choice = "shorten_section"
            else:
                tool_choice = "rewrite_section"
            self._add_step(
                steps,
                tool_name=tool_choice,
                description=f"Propose content patch via {tool_choice} (requires approval)",
                arguments={
                    "document_id": document_id,
                    "block_id": target_block,
                    "instruction": user_message,
                },
            )

        return steps[:bounded_limit]

    def _add_step(
        self,
        steps: list[WorkflowPlanStep],
        tool_name: str,
        description: str,
        arguments: dict[str, object],
    ) -> None:
        tool = self._registry.get(tool_name)
        step_idx = len(steps)
        steps.append(
            WorkflowPlanStep(
                step_index=step_idx,
                tool_name=tool.name,
                description=description,
                risk_level=tool.risk_level,
                requires_approval=requires_human_approval(tool.risk_level),
                input_arguments=arguments,
            )
        )
