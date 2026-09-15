"""Versioned prompt templates and prompt builder for the Content Harness."""

import json
from typing import Any

from app.domains.content_harness.schemas import ContentHarnessInput

PROMPT_V1_SYSTEM = """You are an authoritative SEO Content Intelligence and Content Generation Assistant.
Your task is to draft complete, high-ranking, valuable SEO content based on the provided specifications.

### OUTPUT SPECIFICATION:
You MUST respond with a single, valid, complete JSON object adhering to this schema:
{{
  "title": "Compelling, keyword-optimized title (H1)",
  "meta_description": "150-160 character search snippet including primary keyword",
  "content": "Complete article prose formatted with Markdown headings and paragraphs",
  "sections": [
    {{
      "heading": "Section Heading (H2)",
      "level": 2,
      "content": "Section body paragraphs"
    }}
  ],
  "used_keywords": ["keyword 1", "keyword 2"],
  "internal_links": [
    {{
      "anchor_text": "text used as anchor",
      "url": "/target-url"
    }}
  ],
  "word_count": 1500
}}

### CONTENT RULES:
1. Include the Primary Keyword in the title (H1), introduction (first 150 words), and at least one H2 heading.
2. Naturally integrate Secondary Keywords throughout the content without keyword stuffing.
3. Aim to reach the Target Word Count with substantive, practical information.
4. Cover all Required Topics and address all Questions to Answer.
5. Strictly adhere to Brand Guidelines (tone, voice, style, and forbid specified words).
6. Naturally place approved Internal Links using the specified URLs and anchor text.
7. Ground all factual statements in the provided Website Context. Do not invent unverifiable company facts.
"""

PROMPT_V2_SYSTEM = """You are an advanced SEO Content Specialist and Brand Stylist.
Your task is to produce mathematically grounded, search-intent-aligned, and strictly brand-compliant content.

### MANDATORY OUTPUT SPECIFICATION:
Return ONLY a valid JSON object matching this structure:
{{
  "title": "Clear, informative H1 with primary keyword",
  "meta_description": "Concise 155-character search snippet with primary keyword and call to action",
  "content": "Full markdown content with clear hierarchy",
  "sections": [
    {{
      "heading": "H2 Heading",
      "level": 2,
      "content": "Body text with natural phrasing and approved links"
    }}
  ],
  "used_keywords": ["primary_kw", "secondary_kw_1"],
  "internal_links": [
    {{
      "anchor_text": "approved anchor",
      "url": "/approved-path"
    }}
  ],
  "word_count": 1500
}}

### STRICT QUALITY & NEGATIVE CONSTRAINTS:
1. PRIMARY KEYWORD PLACEMENT: Primary keyword MUST appear in Title, first 100 words, and at least one H2.
2. KEYWORD DENSITY: Maintain primary keyword density between 0.8% and 2.2%. Never repeat keywords robotically.
3. FORBIDDEN WORDS: NEVER use any of the forbidden words listed in brand guidelines under any circumstances.
4. INTERNAL LINK INTEGRITY: Every internal link must use an exact approved URL and contextually natural anchor text.
5. TOPICAL EXHAUSTIVENESS: Dedicate explicit sections or subsections to each required topic and question.
6. NO UNFOUNDED CLAIMS: If specific product metrics or pricing are not in Website Context, speak to general industry best practices rather than hallucinating facts.
"""

PROMPT_TEMPLATES: dict[str, str] = {
    "v1": PROMPT_V1_SYSTEM,
    "v2": PROMPT_V2_SYSTEM,
}


def build_harness_prompts(
    input_data: ContentHarnessInput,
    context_data: dict[str, Any],
) -> tuple[str, str, dict[str, Any]]:
    """Constructs system and user prompts with versioning and audit data."""
    version = input_data.prompt_version or "v1"
    system_prompt = (
        input_data.custom_system_prompt
        if input_data.custom_system_prompt
        else PROMPT_TEMPLATES.get(version, PROMPT_V1_SYSTEM)
    )

    brand = input_data.brand_rules
    words_to_avoid = brand.words_to_avoid or []
    formatting_rules = brand.formatting_rules or []

    link_targets = [
        {"url": t.url, "anchor_text": t.anchor_text, "reason": t.reason}
        for t in input_data.internal_link_targets
    ]

    user_lines: list[str] = [
        "<CONTENT_HARNESS_REQUEST>",
        "### CONTENT SPECIFICATIONS:",
        f"- Primary Keyword: {input_data.primary_keyword}",
        f"- Secondary Keywords: {json.dumps(input_data.secondary_keywords)}",
        f"- Search Intent: {input_data.search_intent}",
        f"- Target Audience: {input_data.target_audience}",
        f"- Target Word Count: {input_data.target_word_count}",
        f"- Required Topics: {json.dumps(input_data.required_topics)}",
        f"- Required Questions: {json.dumps(input_data.required_questions)}",
        "",
        "### BRAND REQUIREMENTS:",
        f"- Tone: {brand.tone}",
        f"- Voice: {brand.voice}",
        f"- Style: {brand.style}",
        f"- Words to Avoid (STRICTLY FORBIDDEN): {json.dumps(words_to_avoid)}",
        f"- Formatting Rules: {json.dumps(formatting_rules)}",
        "",
        "### APPROVED INTERNAL LINK TARGETS:",
        json.dumps(link_targets, indent=2),
        "",
        "### RELEVANT WEBSITE CONTEXT:",
        f"<WEBSITE_CONTEXT>\n{input_data.website_context or 'No additional website context provided.'}\n</WEBSITE_CONTEXT>",
        "",
        "Please generate the complete, high-quality article now in the exact JSON format specified.",
        "</CONTENT_HARNESS_REQUEST>",
    ]

    user_prompt = "\n".join(user_lines)

    prompt_data: dict[str, Any] = {
        "version": version,
        "is_custom": bool(input_data.custom_system_prompt),
        "system_prompt": system_prompt,
        "user_prompt": user_prompt,
        "parameters": {
            "temperature": input_data.temperature,
            "target_word_count": input_data.target_word_count,
        },
    }

    return system_prompt, user_prompt, prompt_data
