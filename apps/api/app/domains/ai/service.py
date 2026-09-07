"""AI Provider implementations and Content AI application service."""

import json
from collections.abc import AsyncIterator, Mapping, Sequence
from uuid import uuid4

from app.ai.provider import (
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


class MockAIProvider(AIProvider):
    """Deterministic AI provider for development, testing, and runtime fallback."""

    async def generate(self, request: GenerationRequest) -> GenerationResult:
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


class ContentAIService:
    """Application AI service orchestrating provider calls, parsing, and validation."""

    def __init__(self, provider: AIProvider | None = None) -> None:
        self._provider = provider or MockAIProvider()

    async def generate_edit_proposal(
        self,
        messages: list,
    ) -> AIEditResponse:
        req = GenerationRequest(
            messages=messages,
            temperature=0.1,
            max_output_tokens=2048,
        )
        res = await self._provider.generate(req)
        try:
            data = json.loads(res.text)
            return AIEditResponse.model_validate(data)
        except Exception:
            # Fallback if raw text returned
            return AIEditResponse(
                message=res.text,
                operations=[],
                reason="Conversational response without document modifications.",
            )
