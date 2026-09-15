"""AI Provider implementations and Content AI application service."""

import json
from collections.abc import AsyncIterator, Mapping, Sequence
from typing import Any
from uuid import uuid4

from app.ai.provider import (
    AIMessage,
    AIProvider,
    EmbeddingResult,
    GenerationRequest,
    GenerationResult,
    Usage,
)
from app.domains.content.document_schemas import (
    AIEditResponse,
    AIOperation,
    BlockType,
    ContentBlock,
    OperationType,
)
from pydantic import ValidationError


class MockAIProvider(AIProvider):
    """Deterministic AI provider for development, testing, and runtime fallback."""

    async def generate(self, request: GenerationRequest) -> GenerationResult:
        # Check if this is an SEO strategy generation request
        is_strategy_request = False
        strategy_context = ""
        for m in request.messages:
            if "<STRATEGY_CONTEXT>" in m.content or "INITIAL SEO STRATEGY" in m.content:
                is_strategy_request = True
                strategy_context += "\n" + m.content

        if is_strategy_request:
            biz_name = "Acme Intelligence"
            if "Project Name: " in strategy_context:
                import contextlib

                with contextlib.suppress(Exception):
                    biz_name = (
                        strategy_context.split("Project Name: ")[1].split("\n")[0].strip()
                        or biz_name
                    )

            strategy_json = json.dumps(
                {
                    "business_context": {
                        "business_name": biz_name,
                        "description": (
                            f"{biz_name} provides comprehensive solutions "
                            "and services tailored to industry standards."
                        ),
                        "industry": "Software & Technology Services",
                        "locations": ["Global"],
                    },
                    "audience": {
                        "segments": ["Enterprise Decision Makers", "Technical Practitioners"],
                        "personas": [
                            {
                                "name": "Technical Leader",
                                "description": (
                                    "Evaluates scalability, reliability, and security "
                                    "of modern digital solutions."
                                ),
                                "problems": ["Complex toolchains", "Lack of clear metrics"],
                                "goals": [
                                    "Improve operational efficiency",
                                    "Achieve high organic visibility",
                                ],
                                "funnel_stage": "MOFU",
                            }
                        ],
                        "needs": [
                            "Automated insights",
                            "Reliable execution",
                            "Clear return on investment",
                        ],
                        "buying_stages": ["Awareness", "Evaluation", "Decision"],
                    },
                    "products": [
                        {
                            "name": f"{biz_name} Core Platform",
                            "description": (
                                "Unified platform for managing and optimizing strategic "
                                "digital operations."
                            ),
                            "category": "Core Product",
                            "url": None,
                            "priority": 1,
                        }
                    ],
                    "services": [],
                    "markets": [
                        {"name": "United States", "code": "US", "is_primary": True},
                        {"name": "Europe", "code": "EU", "is_primary": False},
                    ],
                    "goals": [
                        {
                            "type": "LEAD_GENERATION",
                            "description": (
                                "Increase qualified organic inbound inquiries by 35% "
                                "year-over-year."
                            ),
                            "priority": 1,
                        }
                    ],
                    "competitors": [
                        {
                            "name": "Legacy Competitor",
                            "domain": "competitor.example.com",
                            "strengths": ["Brand awareness", "Large customer base"],
                        }
                    ],
                    "seo_objectives": [
                        "Establish topical authority in core market category",
                        "Rank on page 1 for high-intent product queries",
                    ],
                    "content_objectives": [
                        "Produce high-value architectural guides and solutions documentation",
                        "Build structured topic clusters covering essential buyer problems",
                    ],
                    "priority_topics": [
                        "Solution Architecture",
                        "Platform Migration",
                        "Best Practices & Guides",
                    ],
                },
                indent=2,
            )
            return GenerationResult(
                text=strategy_json,
                provider="mock",
                model="mock-strategy-v1",
                usage=Usage(input_tokens=150, output_tokens=350),
                finish_reason="stop",
            )

        # Check if this is an AI qualitative evaluation request
        if any("### ARTICLE TO EVALUATE:" in m.content for m in request.messages):
            eval_json = json.dumps(
                {
                    "ai_score": 88,
                    "factual_accuracy": "HIGH",
                    "hallucination_detected": False,
                    "strengths": [
                        "Direct search intent alignment",
                        "Grounded in verified operational principles",
                        "Consistent professional tone",
                    ],
                    "weaknesses": ["Could provide deeper technical edge-case diagnostics"],
                    "qualitative_summary": (
                        "The generated article successfully delivers authoritative, "
                        "search-optimized content aligned with audience requirements."
                    ),
                },
                indent=2,
            )
            return GenerationResult(
                text=eval_json,
                provider="mock",
                model="mock-evaluator-v1",
                usage=Usage(input_tokens=200, output_tokens=120),
                finish_reason="stop",
            )

        # Check if this is a Content Harness generation request
        is_harness_request = False
        harness_context = ""
        for m in request.messages:
            if "<CONTENT_HARNESS_REQUEST>" in m.content:
                is_harness_request = True
                harness_context += "\n" + m.content

        if is_harness_request:
            # Check for simulated invalid output test case
            if (
                "case 6: malformed output" in harness_context.lower()
                or "telematics hardware failure" in harness_context.lower()
            ):
                return GenerationResult(
                    text="<<<MALFORMED_JSON_OUTPUT_FOR_TESTING>>> {title: missing quotes}",
                    provider="mock",
                    model="mock-harness-v1",
                    usage=Usage(input_tokens=100, output_tokens=30),
                    finish_reason="stop",
                    provider_request_id=f"mock_harness_err_{uuid4().hex[:8]}",
                )

            # Parse specifications from harness context
            kw = "fleet vehicle tracking"
            if "- Primary Keyword: " in harness_context:
                kw = harness_context.split("- Primary Keyword: ")[1].split("\n")[0].strip() or kw

            sec_kws: list[str] = []
            if "- Secondary Keywords: " in harness_context:
                try:
                    raw_sec = (
                        harness_context.split("- Secondary Keywords: ")[1].split("\n")[0].strip()
                    )
                    sec_kws = json.loads(raw_sec)
                except Exception:
                    pass

            target_links: list[dict[str, str]] = []
            if "### APPROVED INTERNAL LINK TARGETS:" in harness_context:
                try:
                    raw_links = (
                        harness_context.split("### APPROVED INTERNAL LINK TARGETS:")[1]
                        .split("###")[0]
                        .strip()
                    )
                    parsed_targets = json.loads(raw_links)
                    if isinstance(parsed_targets, list):
                        target_links = [
                            {"url": t.get("url", ""), "anchor_text": t.get("anchor_text", "")}
                            for t in parsed_targets
                            if isinstance(t, dict) and t.get("url")
                        ]
                except Exception:
                    pass

            title = f"Complete Guide to {kw.title()}"
            meta_desc = (
                f"Discover how {kw} optimizes vehicle operations, reduces overhead costs, "
                "and enhances fleet visibility."
            )

            link_html_or_md = ""
            if target_links:
                first_link = target_links[0]
                link_html_or_md = (
                    f" Learn more through our [{first_link['anchor_text']}]({first_link['url']})."
                )

            sec_kw_mention = (
                f" Modern telematics architectures seamlessly integrate {', '.join(sec_kws)} "
                "to provide end-to-end fleet diagnostics and operational optimization."
                if sec_kws
                else ""
            )

            sec1_content = (
                f"Implementing {kw} gives modern logistics managers real-time visibility "
                "into vehicle locations, engine metrics, and transit performance. "
                "In today's fast-moving distribution environment, "
                f"{kw} is essential for ensuring vehicle health and schedule adherence."
                f"{link_html_or_md} "
                "By collecting diagnostic data from onboard vehicle sensors, operations teams gain "
                "actionable insights into fuel usage, driver behaviors, and scheduled route "
                f"efficiency.{sec_kw_mention}"
            )

            sec2_heading = f"Core Benefits of {kw.title()}"
            sec2_content = (
                f"A primary advantage of {kw} is substantial operational efficiency. "
                "Automated route tracking and dispatch integration reduce unnecessary idling, "
                "minimize deadhead miles, and alert technicians to preventative maintenance "
                "needs before critical failure. "
                f"Deploying {kw} also improves accountability and safety compliance across "
                "all operating depots."
            )

            sec3_heading = "Best Practices for Implementation"
            sec3_content = (
                f"When rolling out {kw}, organizations should configure automated alerts, "
                "train drivers on telematics expectations, and integrate telemetry logs into "
                "existing maintenance management tools. "
                "Consistent measurement of key metrics ensures continuous improvement and "
                "long-term cost containment."
            )

            all_sections = [
                {"heading": f"Understanding {kw.title()}", "level": 2, "content": sec1_content},
                {"heading": sec2_heading, "level": 2, "content": sec2_content},
                {"heading": sec3_heading, "level": 2, "content": sec3_content},
            ]

            # Add extra links if present
            if len(target_links) > 1:
                sec2_content += (
                    f" Integrate with our [{target_links[1]['anchor_text']}]"
                    f"({target_links[1]['url']}) for deeper synergy."
                )
                all_sections[1]["content"] = sec2_content

            content_body = (
                f"# {title}\n\n{sec1_content}\n\n"
                f"## {sec2_heading}\n\n{sec2_content}\n\n"
                f"## {sec3_heading}\n\n{sec3_content}"
            )
            words = content_body.split()

            # If target word count is higher, repeat informative blocks to hit realistic word counts
            if len(words) < 900:
                padding_block = (
                    f"\n\n## Advanced Telematics and Operational Analytics\n\n"
                    f"Modern telemetry expands the capabilities of {kw} by synchronizing engine "
                    "diagnostics with route scheduling algorithms. Logistics teams analyze fuel "
                    "consumption patterns, monitor driver brake applications, and benchmark depot "
                    "performance across operating regions. Structured data capture ensures audit "
                    "compliance with federal transportation regulations."
                )
                content_body += padding_block * 3
                all_sections.append(
                    {
                        "heading": "Advanced Telematics and Operational Analytics",
                        "level": 2,
                        "content": padding_block.strip(),
                    }
                )

            words_count = len(content_body.split())

            harness_output = {
                "title": title,
                "meta_description": meta_desc,
                "content": content_body,
                "sections": all_sections,
                "used_keywords": [kw, *sec_kws],
                "internal_links": target_links,
                "word_count": words_count,
            }

            return GenerationResult(
                text=json.dumps(harness_output, indent=2),
                provider="mock",
                model="mock-harness-v1",
                usage=Usage(input_tokens=350, output_tokens=650),
                finish_reason="stop",
                provider_request_id=f"mock_harness_{uuid4().hex[:8]}",
            )

        # Check if this is an Agent Loop request
        is_agent_request = any("<AVAILABLE_TOOLS>" in m.content for m in request.messages) or any(
            "You are the Content Agent" in m.content for m in request.messages
        )
        if is_agent_request:
            user_msg = ""
            obs_content = ""
            plan_content = ""
            for m in request.messages:
                if "<USER_REQUEST>" in m.content:
                    user_msg = (
                        m.content.split("<USER_REQUEST>")[1].split("</USER_REQUEST>")[0].strip()
                    )
                if "<TOOL_OBSERVATIONS>" in m.content:
                    obs_content = (
                        m.content.split("<TOOL_OBSERVATIONS>")[1]
                        .split("</TOOL_OBSERVATIONS>")[0]
                        .strip()
                    )
                if "<INITIAL_PLAN>" in m.content:
                    plan_content = (
                        m.content.split("<INITIAL_PLAN>")[1].split("</INITIAL_PLAN>")[0].strip()
                    )

            user_lower = user_msg.lower()
            has_obs = "Tool: " in obs_content

            # Check if there is an initial plan to follow
            plan_tools: list[str] = []
            if plan_content:
                for line in plan_content.splitlines():
                    line = line.strip()
                    if line and line[0].isdigit() and ". " in line:
                        part = line.split(". ", 1)[1]
                        t_name = part.split(" ")[0].strip()
                        if t_name:
                            plan_tools.append(t_name)

            if plan_tools:
                executed_count = obs_content.count("Tool: ")
                if executed_count < len(plan_tools):
                    next_tool = plan_tools[executed_count]
                    t_input: dict[str, Any] = {}
                    if next_tool in ("rewrite_section", "expand_section", "shorten_section"):
                        t_input = {
                            "block_id": "b1",
                            "instruction": "Rewrite section for optimal SEO",
                        }
                    elif next_tool == "insert_internal_link":
                        t_input = {
                            "block_id": "b1",
                            "url": "/test-link",
                            "anchor_text": "test anchor",
                        }
                    decision_data = {
                        "type": "TOOL_CALL",
                        "tool_name": next_tool,
                        "tool_input": t_input,
                        "reasoning_summary": f"Executing planned step: {next_tool}",
                    }
                else:
                    decision_data = {
                        "type": "FINAL",
                        "final_response": "All planned workflow steps executed successfully.",
                        "reasoning_summary": "Workflow plan steps completed.",
                    }
            elif has_obs:
                if (
                    "rewrite" in user_lower
                    or "improve" in user_lower
                    or "edit" in user_lower
                    or "optimize" in user_lower
                ):
                    if "rewrite_section" in obs_content:
                        decision_data = {
                            "type": "FINAL",
                            "final_response": (
                                "I have analyzed the article and proposed SEO improvements "
                                "for your review."
                            ),
                            "reasoning_summary": (
                                "All required SEO optimizations and proposals have been formulated."
                            ),
                        }
                    else:
                        decision_data = {
                            "type": "TOOL_CALL",
                            "tool_name": "rewrite_section",
                            "tool_input": {
                                "block_id": "block_001",
                                "instruction": (
                                    "Incorporate primary keyword into opening section and "
                                    "optimize clarity."
                                ),
                            },
                            "reasoning_summary": (
                                "SEO audit revealed missing keyword in introductory section; "
                                "proposing rewrite."
                            ),
                        }
                else:
                    decision_data = {
                        "type": "FINAL",
                        "final_response": (
                            "Analysis complete based on gathered evidence. "
                            "Quality rules and linking opportunities evaluated."
                        ),
                        "reasoning_summary": "Completed inspection and analysis.",
                    }
            else:
                # First iteration - select initial inspection tool
                if "link" in user_lower:
                    tool = "find_link_opportunities"
                elif "outline" in user_lower:
                    tool = "generate_outline"
                elif "keyword" in user_lower:
                    tool = "keyword_check"
                elif "read" in user_lower:
                    tool = "read_document"
                else:
                    tool = "seo_quality_check"

                decision_data = {
                    "type": "TOOL_CALL",
                    "tool_name": tool,
                    "tool_input": {},
                    "reasoning_summary": f"Starting task by inspecting with {tool}.",
                }

            return GenerationResult(
                text=json.dumps(decision_data),
                provider="mock",
                model="mock-agent-v1",
                usage=Usage(input_tokens=250, output_tokens=100),
                finish_reason="stop",
                provider_request_id=f"mock_agent_{uuid4().hex[:8]}",
            )

        user_text = ""
        context_text = ""
        for m in request.messages:
            if m.role == "user":
                if "<USER_QUERY>" in m.content:
                    user_text = m.content.split("<USER_QUERY>")[1].split("</USER_QUERY>")[0].strip()
                elif "<DOCUMENT_CONTEXT>" in m.content:
                    context_text = m.content

        user_lower = user_text.lower()

        # Parse selected block ID from context if present
        target_block_id = "block_001"
        target_content = ""
        if "--- FOCUSED BLOCK (" in context_text:
            try:
                hdr_split = context_text.split("--- FOCUSED BLOCK (")[1]
                target_block_id = hdr_split.split(") ---")[0].strip()
                if "Content: " in hdr_split:
                    target_content = hdr_split.split("Content: ")[1].split("\n")[0].strip()
            except Exception:
                pass

        operations: list[AIOperation] = []
        message = ""
        reason = ""
        diff_summary: dict[str, object] = {}

        if any(k in user_lower for k in ["shorten", "concise", "tighten", "brief"]):
            summary_default = (
                f"In summary, {target_content or 'this technical approach'} delivers impact."
            )
            new_text = (
                f"{target_content[:140]}..." if len(target_content) > 140 else summary_default
            )
            operations.append(
                AIOperation(
                    operation=OperationType.REPLACE_BLOCK,
                    block_id=target_block_id,
                    old_content=target_content,
                    new_content=new_text,
                    reason="Enhanced conciseness and removed redundant phrasing.",
                )
            )
            message = f"I have shortened block {target_block_id} to focus on high-impact value."
            reason = "Eliminated filler words while maintaining core semantic keywords."
            diff_summary = {"old": target_content, "new": new_text}

        elif any(k in user_lower for k in ["expand", "elaborate", "more detail"]):
            new_text = (
                f"{target_content} Specifically, integrating structured data and strict "
                "internal linking standards ensures search engines index and rank core pages."
            )
            operations.append(
                AIOperation(
                    operation=OperationType.REPLACE_BLOCK,
                    block_id=target_block_id,
                    old_content=target_content,
                    new_content=new_text,
                    reason="Expanded with technical depth and practical implementation details.",
                )
            )
            message = f"I have expanded block {target_block_id} with supporting technical context."
            reason = "Added execution details and search engine indexing specifics."
            diff_summary = {"old": target_content, "new": new_text}

        elif any(k in user_lower for k in ["faq", "question"]):
            faq_id = f"b_faq_{uuid4().hex[:6]}"
            faq_block = ContentBlock(
                id=faq_id,
                type=BlockType.FAQ,
                text="Frequently Asked Questions",
                data={
                    "question": "What is the primary benefit of this strategy?",
                    "answer": (
                        "It aligns search intent with structured content architecture "
                        "for sustained organic growth."
                    ),
                },
            )
            operations.append(
                AIOperation(
                    operation=OperationType.INSERT_BLOCK,
                    target_block_id=target_block_id,
                    position="after",
                    block=faq_block,
                    reason="Added strategic FAQ block addressing critical user queries.",
                )
            )
            message = "I have proposed an FAQ section to capture SERP snippet opportunities."
            reason = "Directly addresses core questions outlined in the approved Content Brief."
            diff_summary = {"inserted_block": faq_id, "type": "FAQ"}

        elif any(k in user_lower for k in ["link", "internal link"]):
            operations.append(
                AIOperation(
                    operation=OperationType.INSERT_LINK,
                    block_id=target_block_id,
                    url="/technical-seo-guide",
                    anchor_text="technical SEO guide",
                    reason="Connected supporting pillar page from internal linking suggestions.",
                )
            )
            message = f"I proposed an internal link in {target_block_id} to technical SEO guide."
            reason = "Increases internal link equity and topical authority between cluster pages."
            diff_summary = {"target_url": "/technical-seo-guide", "anchor": "technical SEO guide"}

        else:
            # Default rewrite / optimize
            fallback_text = (
                "Technical SEO ensures search engines discover, crawl, and index your content."
            )
            new_text = f"Optimized: {target_content or fallback_text}"
            operations.append(
                AIOperation(
                    operation=OperationType.REPLACE_BLOCK,
                    block_id=target_block_id,
                    old_content=target_content,
                    new_content=new_text,
                    reason="Polished phrasing according to active brand guidelines and SEO rules.",
                )
            )
            message = f"I have reviewed and optimized block {target_block_id} for readability."
            reason = "Aligns tone with brand voice and reinforces primary keyword prominence."
            diff_summary = {"old": target_content, "new": new_text}

        response = AIEditResponse(
            message=message,
            operations=operations,
            reason=reason,
            diff_summary=diff_summary,
        )

        return GenerationResult(
            text=json.dumps(response.model_dump()),
            provider="mock",
            model="mock-v1",
            usage=Usage(input_tokens=250, output_tokens=150),
            finish_reason="stop",
            provider_request_id=f"mock_req_{uuid4().hex[:8]}",
        )

    async def stream(self, request: GenerationRequest) -> AsyncIterator[str]:
        res = await self.generate(request)
        yield res.text

    async def embed(
        self,
        texts: Sequence[str],
        *,
        metadata: Mapping[str, str] | None = None,
    ) -> EmbeddingResult:
        # Mock 1536-dim normalized vector
        vector = [0.0] * 1536
        if vector:
            vector[0] = 1.0
        return EmbeddingResult(
            vectors=[vector for _ in texts],
            provider="mock",
            model="mock-embed-v1",
            usage=Usage(input_tokens=len(texts) * 10, output_tokens=0),
        )


def get_ai_provider() -> AIProvider:
    """Returns the configured AI provider based on process settings."""
    import os

    from app.config.settings import get_settings
    from app.integrations.gemini import GeminiAIProvider

    # Always use deterministic test double during test runs
    if os.environ.get("PYTEST_CURRENT_TEST") or os.environ.get("APP_ENV") in ("test", "testing"):
        return MockAIProvider()

    settings = get_settings()
    if settings.APP_ENV in ("test", "testing"):
        return MockAIProvider()

    provider_name = (settings.AI_PROVIDER or "").lower().strip()
    if provider_name in ("gemini", "gemini_api_key", "google") and settings.AI_API_KEY:
        return GeminiAIProvider(
            api_key=settings.AI_API_KEY,
            model=settings.AI_MODEL or "gemini-flash-latest",
            embedding_model=settings.AI_EMBEDDING_MODEL or "gemini-embedding-001",
            base_url=settings.AI_BASE_URL,
        )

    return MockAIProvider()


class ContentAIService:
    """Application AI service orchestrating provider calls, parsing, and validation."""

    def __init__(self, provider: AIProvider | None = None) -> None:
        self._provider = provider or get_ai_provider()

    async def generate_edit_proposal(
        self,
        messages: list[AIMessage],
    ) -> AIEditResponse:
        req = GenerationRequest(
            messages=messages,
            temperature=0.1,
            max_output_tokens=8192,
        )
        res = await self._provider.generate(req)
        clean_text = res.text.strip()
        # Strip markdown code blocks if present (e.g. ```json ... ```)
        if clean_text.startswith("```"):
            lines = clean_text.splitlines()
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            clean_text = "\n".join(lines).strip()

        try:
            data = json.loads(clean_text)
        except json.JSONDecodeError:
            # Providers may return a normal conversational response instead of JSON. A
            # JSON-looking result is an incomplete/invalid proposal and must never be
            # displayed as prose or persisted as an applicable edit.
            if clean_text.startswith(("{", "[")):
                limit_note = (
                    " because the provider reached its output limit"
                    if res.finish_reason.upper() in {"MAX_TOKENS", "LENGTH"}
                    else ""
                )
                return AIEditResponse(
                    message=(
                        "The AI generated an incomplete structured proposal"
                        f"{limit_note}. No document changes were created. Please retry the request."
                    ),
                    operations=[],
                    reason="Rejected incomplete structured AI output.",
                    provider=res.provider,
                    model=res.model,
                )
            return AIEditResponse(
                message=res.text,
                operations=[],
                reason="Conversational response without document modifications.",
                provider=res.provider,
                model=res.model,
            )

        try:
            resp = AIEditResponse.model_validate(data)
        except ValidationError:
            # Never leak a structured provider envelope into the chat bubble. If the
            # envelope has a usable message but unsafe/invalid operations, preserve
            # only the conversational part and discard the proposed mutations.
            if isinstance(data, dict) and isinstance(data.get("message"), str):
                reason = data.get("reason")
                return AIEditResponse(
                    message=data["message"],
                    operations=[],
                    reason=(
                        reason
                        if isinstance(reason, str)
                        else "Conversational response without valid document modifications."
                    ),
                    provider=res.provider,
                    model=res.model,
                )
            return AIEditResponse(
                message=res.text,
                operations=[],
                reason="Conversational response without document modifications.",
                provider=res.provider,
                model=res.model,
            )

        resp.provider = res.provider
        resp.model = res.model
        return resp
