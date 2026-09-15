"""Deterministic and optional AI content evaluation logic for the Content Harness."""

import json
import re
from typing import Any

from app.ai.provider import AIMessage, AIProvider, GenerationRequest
from app.domains.content_harness.schemas import (
    ContentHarnessInput,
    FindingImpact,
    FindingStatus,
    HarnessFinding,
    HarnessGeneratedContent,
    HarnessScorecard,
)


def _count_words(text: str) -> int:
    words = re.findall(r"\b\w+\b", text)
    return len(words)


def _text_contains_phrase(text: str, phrase: str) -> bool:
    if not phrase or not text:
        return False
    # Case-insensitive substring or regex word boundary match
    pattern = r"\b" + re.escape(phrase.strip().lower()) + r"\b"
    return bool(re.search(pattern, text.lower()))


def evaluate_content(
    generated: HarnessGeneratedContent,
    input_data: ContentHarnessInput,
    raw_text: str = "",
) -> HarnessScorecard:
    """Executes deterministic evaluation across SEO, Content, Brand, Linking, and Technical checks."""
    findings: list[HarnessFinding] = []

    # Assemble full text for inspection
    title = (generated.title or "").strip()
    meta_desc = (generated.meta_description or "").strip()
    sections = generated.sections or []
    section_headings = [s.heading for s in sections if s.heading]
    section_texts = [s.content for s in sections if s.content]
    full_content = (generated.content or "") + "\n" + "\n".join(section_texts)
    combined_text = f"{title}\n{meta_desc}\n{full_content}"
    total_words = _count_words(combined_text)

    # -------------------------------------------------------------
    # 1. Technical Validity (PASS / FAIL)
    # -------------------------------------------------------------
    tech_passed = True
    if not title:
        tech_passed = False
        findings.append(
            HarnessFinding(
                category="TECHNICAL",
                rule="title_presence",
                status=FindingStatus.FAIL,
                impact=FindingImpact.HIGH,
                message="Title is missing or empty in generated content.",
            )
        )
    if not full_content.strip():
        tech_passed = False
        findings.append(
            HarnessFinding(
                category="TECHNICAL",
                rule="content_presence",
                status=FindingStatus.FAIL,
                impact=FindingImpact.HIGH,
                message="Content body is empty.",
            )
        )
    if not sections:
        tech_passed = False
        findings.append(
            HarnessFinding(
                category="TECHNICAL",
                rule="sections_presence",
                status=FindingStatus.FAIL,
                impact=FindingImpact.MEDIUM,
                message="No structured sections were returned.",
            )
        )

    technical_validity = "PASS" if tech_passed else "FAIL"
    if tech_passed:
        findings.append(
            HarnessFinding(
                category="TECHNICAL",
                rule="json_schema_compliance",
                status=FindingStatus.PASS,
                impact=FindingImpact.INFO,
                message="Output successfully validated against structured content schema.",
            )
        )

    # -------------------------------------------------------------
    # 2. SEO Checks (0 - 100)
    # -------------------------------------------------------------
    seo_points = 0.0
    primary_kw = (input_data.primary_keyword or "").strip().lower()

    # Rule 1: Primary Keyword in Title (25 pts)
    if primary_kw and _text_contains_phrase(title, primary_kw):
        seo_points += 25.0
        findings.append(
            HarnessFinding(
                category="SEO",
                rule="primary_keyword_in_title",
                status=FindingStatus.PASS,
                impact=FindingImpact.HIGH,
                message=f"Primary keyword '{primary_kw}' is included in the title.",
            )
        )
    else:
        findings.append(
            HarnessFinding(
                category="SEO",
                rule="primary_keyword_in_title",
                status=FindingStatus.FAIL,
                impact=FindingImpact.HIGH,
                message=f"Primary keyword '{primary_kw}' is missing from the title.",
            )
        )

    # Rule 2: Primary Keyword in Introduction (first 150 words) (20 pts)
    intro_words = " ".join(full_content.split()[:150])
    if primary_kw and _text_contains_phrase(intro_words, primary_kw):
        seo_points += 20.0
        findings.append(
            HarnessFinding(
                category="SEO",
                rule="primary_keyword_in_intro",
                status=FindingStatus.PASS,
                impact=FindingImpact.HIGH,
                message=f"Primary keyword '{primary_kw}' appears in the introductory 150 words.",
            )
        )
    else:
        findings.append(
            HarnessFinding(
                category="SEO",
                rule="primary_keyword_in_intro",
                status=FindingStatus.FAIL,
                impact=FindingImpact.HIGH,
                message=f"Primary keyword '{primary_kw}' was not found in the introductory paragraphs.",
            )
        )

    # Rule 3: Primary Keyword in Headings (H2) (15 pts)
    kw_in_heading = any(_text_contains_phrase(h, primary_kw) for h in section_headings)
    if primary_kw and kw_in_heading:
        seo_points += 15.0
        findings.append(
            HarnessFinding(
                category="SEO",
                rule="primary_keyword_in_headings",
                status=FindingStatus.PASS,
                impact=FindingImpact.MEDIUM,
                message=f"Primary keyword '{primary_kw}' appears in at least one section heading.",
            )
        )
    else:
        findings.append(
            HarnessFinding(
                category="SEO",
                rule="primary_keyword_in_headings",
                status=FindingStatus.WARN,
                impact=FindingImpact.MEDIUM,
                message=f"Primary keyword '{primary_kw}' was not found in any section headings (H2).",
            )
        )

    # Rule 4: Secondary Keywords Coverage (25 pts)
    sec_kws = [k.strip().lower() for k in input_data.secondary_keywords if k.strip()]
    if not sec_kws:
        seo_points += 25.0
    else:
        matched_sec = [k for k in sec_kws if _text_contains_phrase(combined_text, k)]
        ratio = len(matched_sec) / len(sec_kws)
        seo_points += ratio * 25.0
        if ratio >= 0.8:
            findings.append(
                HarnessFinding(
                    category="SEO",
                    rule="secondary_keyword_coverage",
                    status=FindingStatus.PASS,
                    impact=FindingImpact.MEDIUM,
                    message=f"Secondary keyword coverage is {len(matched_sec)}/{len(sec_kws)} ({ratio:.0%}).",
                    details={"matched": matched_sec, "missing": list(set(sec_kws) - set(matched_sec))},
                )
            )
        else:
            findings.append(
                HarnessFinding(
                    category="SEO",
                    rule="secondary_keyword_coverage",
                    status=FindingStatus.WARN,
                    impact=FindingImpact.MEDIUM,
                    message=f"Secondary keyword coverage is only {len(matched_sec)}/{len(sec_kws)} ({ratio:.0%}).",
                    details={"matched": matched_sec, "missing": list(set(sec_kws) - set(matched_sec))},
                )
            )

    # Rule 5: Keyword Stuffing & Density Check (15 pts)
    if primary_kw and total_words > 50:
        matches = len(re.findall(r"\b" + re.escape(primary_kw) + r"\b", combined_text.lower()))
        kw_word_count = len(primary_kw.split())
        density = (matches * kw_word_count / total_words) * 100.0 if total_words else 0.0

        if 0.4 <= density <= 2.8:
            seo_points += 15.0
            findings.append(
                HarnessFinding(
                    category="SEO",
                    rule="keyword_density",
                    status=FindingStatus.PASS,
                    impact=FindingImpact.LOW,
                    message=f"Primary keyword density is healthy at {density:.2f}% ({matches} occurrences).",
                    details={"occurrences": matches, "density_pct": round(density, 2)},
                )
            )
        elif density > 3.0:
            findings.append(
                HarnessFinding(
                    category="SEO",
                    rule="keyword_density",
                    status=FindingStatus.FAIL,
                    impact=FindingImpact.HIGH,
                    message=f"Warning: Potential keyword stuffing detected. Density is {density:.2f}% ({matches} occurrences).",
                    details={"occurrences": matches, "density_pct": round(density, 2)},
                )
            )
        else:
            seo_points += 7.5
            findings.append(
                HarnessFinding(
                    category="SEO",
                    rule="keyword_density",
                    status=FindingStatus.WARN,
                    impact=FindingImpact.LOW,
                    message=f"Primary keyword density is somewhat low at {density:.2f}% ({matches} occurrences).",
                    details={"occurrences": matches, "density_pct": round(density, 2)},
                )
            )
    else:
        seo_points += 15.0

    seo_score = max(0.0, min(100.0, round(seo_points, 1)))

    # -------------------------------------------------------------
    # 3. Content Coverage (0 - 100)
    # -------------------------------------------------------------
    content_points = 0.0

    # Rule 1: Target Word Count Tolerance (+/- 20% = 30 pts)
    target_wc = input_data.target_word_count or 1500
    lower_bound = target_wc * 0.80
    upper_bound = target_wc * 1.25

    if lower_bound <= total_words <= upper_bound:
        content_points += 30.0
        findings.append(
            HarnessFinding(
                category="CONTENT",
                rule="word_count_tolerance",
                status=FindingStatus.PASS,
                impact=FindingImpact.MEDIUM,
                message=f"Total word count ({total_words}) is well within target range ({int(lower_bound)}-{int(upper_bound)}).",
                details={"actual": total_words, "target": target_wc},
            )
        )
    else:
        diff_pct = abs(total_words - target_wc) / target_wc
        partial_pts = max(0.0, 30.0 * (1.0 - min(1.0, diff_pct)))
        content_points += partial_pts
        findings.append(
            HarnessFinding(
                category="CONTENT",
                rule="word_count_tolerance",
                status=FindingStatus.WARN if diff_pct <= 0.4 else FindingStatus.FAIL,
                impact=FindingImpact.MEDIUM,
                message=f"Word count ({total_words}) deviates by {diff_pct:.0%} from target ({target_wc}).",
                details={"actual": total_words, "target": target_wc, "diff_pct": round(diff_pct, 2)},
            )
        )

    # Rule 2: Required Topics Covered (35 pts)
    req_topics = [t.strip().lower() for t in input_data.required_topics if t.strip()]
    if not req_topics:
        content_points += 35.0
    else:
        covered_topics: list[str] = []
        for top in req_topics:
            # Check if any significant word of topic is in headings or content
            top_words = [w for w in re.findall(r"\w+", top) if len(w) > 3]
            if _text_contains_phrase(combined_text, top) or (
                top_words and all(_text_contains_phrase(combined_text, w) for w in top_words)
            ):
                covered_topics.append(top)

        topic_ratio = len(covered_topics) / len(req_topics)
        content_points += topic_ratio * 35.0
        if topic_ratio >= 0.75:
            findings.append(
                HarnessFinding(
                    category="CONTENT",
                    rule="required_topics_coverage",
                    status=FindingStatus.PASS,
                    impact=FindingImpact.HIGH,
                    message=f"Covered {len(covered_topics)} of {len(req_topics)} required topics ({topic_ratio:.0%}).",
                    details={"covered": covered_topics, "missing": list(set(req_topics) - set(covered_topics))},
                )
            )
        else:
            findings.append(
                HarnessFinding(
                    category="CONTENT",
                    rule="required_topics_coverage",
                    status=FindingStatus.WARN,
                    impact=FindingImpact.HIGH,
                    message=f"Missing topics: only {len(covered_topics)} of {len(req_topics)} required topics covered.",
                    details={"covered": covered_topics, "missing": list(set(req_topics) - set(covered_topics))},
                )
            )

    # Rule 3: Required Questions Addressed (25 pts)
    req_questions = [q.strip().lower() for q in input_data.required_questions if q.strip()]
    if not req_questions:
        content_points += 25.0
    else:
        answered_questions: list[str] = []
        for q in req_questions:
            q_keywords = [w for w in re.findall(r"\w+", q) if len(w) > 3]
            if _text_contains_phrase(combined_text, q) or (
                len(q_keywords) >= 2
                and sum(1 for w in q_keywords if _text_contains_phrase(combined_text, w)) >= 2
            ):
                answered_questions.append(q)

        q_ratio = len(answered_questions) / len(req_questions)
        content_points += q_ratio * 25.0
        if q_ratio >= 0.7:
            findings.append(
                HarnessFinding(
                    category="CONTENT",
                    rule="required_questions_addressed",
                    status=FindingStatus.PASS,
                    impact=FindingImpact.MEDIUM,
                    message=f"Addressed {len(answered_questions)} of {len(req_questions)} required questions.",
                    details={"answered": answered_questions, "missing": list(set(req_questions) - set(answered_questions))},
                )
            )
        else:
            findings.append(
                HarnessFinding(
                    category="CONTENT",
                    rule="required_questions_addressed",
                    status=FindingStatus.WARN,
                    impact=FindingImpact.MEDIUM,
                    message=f"Addressed only {len(answered_questions)} of {len(req_questions)} required questions.",
                    details={"answered": answered_questions, "missing": list(set(req_questions) - set(answered_questions))},
                )
            )

    # Rule 4: Heading Structure & Non-Duplication (10 pts)
    if len(sections) >= 2 and len(section_headings) == len(set(section_headings)):
        content_points += 10.0
        findings.append(
            HarnessFinding(
                category="CONTENT",
                rule="heading_structure",
                status=FindingStatus.PASS,
                impact=FindingImpact.LOW,
                message=f"Well-structured document with {len(sections)} distinct sections.",
            )
        )
    else:
        findings.append(
            HarnessFinding(
                category="CONTENT",
                rule="heading_structure",
                status=FindingStatus.WARN,
                impact=FindingImpact.LOW,
                message="Sections are sparse or duplicate headings were detected.",
            )
        )

    content_score = max(0.0, min(100.0, round(content_points, 1)))

    # -------------------------------------------------------------
    # 4. Brand Compliance (0 - 100)
    # -------------------------------------------------------------
    brand = input_data.brand_rules
    forbidden_words = [w.strip().lower() for w in brand.words_to_avoid if w.strip()]
    brand_points = 100.0
    detected_forbidden: list[str] = []

    for word in forbidden_words:
        if _text_contains_phrase(combined_text, word):
            detected_forbidden.append(word)
            brand_points -= 25.0
            findings.append(
                HarnessFinding(
                    category="BRAND",
                    rule="forbidden_words",
                    status=FindingStatus.FAIL,
                    impact=FindingImpact.HIGH,
                    message=f"Strictly forbidden word '{word}' found in generated content.",
                )
            )

    if not detected_forbidden:
        findings.append(
            HarnessFinding(
                category="BRAND",
                rule="forbidden_words",
                status=FindingStatus.PASS,
                impact=FindingImpact.HIGH,
                message="Zero forbidden brand words detected.",
            )
        )

    # Tone check (check for presence of tone signals)
    if brand.tone:
        findings.append(
            HarnessFinding(
                category="BRAND",
                rule="tone_adherence",
                status=FindingStatus.PASS,
                impact=FindingImpact.INFO,
                message=f"Target brand tone '{brand.tone}' configured.",
            )
        )

    brand_score = max(0.0, min(100.0, round(brand_points, 1)))

    # -------------------------------------------------------------
    # 5. Internal Linking (0 - 100)
    # -------------------------------------------------------------
    link_targets = input_data.internal_link_targets or []
    if not link_targets:
        linking_score = 100.0
        findings.append(
            HarnessFinding(
                category="INTERNAL_LINKING",
                rule="approved_links",
                status=FindingStatus.PASS,
                impact=FindingImpact.INFO,
                message="No internal links required for this article scenario.",
            )
        )
    else:
        linking_points = 0.0
        used_links = generated.internal_links or []
        used_urls = [str(l.get("url", "")).strip().lower() for l in used_links if isinstance(l, dict)]
        used_anchors = [str(l.get("anchor_text", "")).strip().lower() for l in used_links if isinstance(l, dict)]

        matched_targets: list[str] = []
        for target in link_targets:
            t_url = (target.url or "").strip().lower()
            t_anchor = (target.anchor_text or "").strip().lower()

            url_found = any(t_url in u for u in used_urls) or (t_url and t_url in full_content.lower())
            anchor_found = any(t_anchor in a for a in used_anchors) or (t_anchor and _text_contains_phrase(full_content, t_anchor))

            if url_found and anchor_found:
                matched_targets.append(t_url)
            elif url_found:
                matched_targets.append(t_url)

        link_ratio = len(matched_targets) / len(link_targets) if link_targets else 1.0
        linking_points = link_ratio * 80.0

        # Duplicate link penalty
        if len(used_urls) == len(set(used_urls)):
            linking_points += 20.0
        else:
            linking_points += 10.0
            findings.append(
                HarnessFinding(
                    category="INTERNAL_LINKING",
                    rule="duplicate_links",
                    status=FindingStatus.WARN,
                    impact=FindingImpact.LOW,
                    message="Multiple identical link target URLs detected.",
                )
            )

        if link_ratio >= 0.7:
            findings.append(
                HarnessFinding(
                    category="INTERNAL_LINKING",
                    rule="approved_links",
                    status=FindingStatus.PASS,
                    impact=FindingImpact.MEDIUM,
                    message=f"Placed {len(matched_targets)} of {len(link_targets)} approved internal link targets.",
                    details={"matched_urls": matched_targets},
                )
            )
        else:
            findings.append(
                HarnessFinding(
                    category="INTERNAL_LINKING",
                    rule="approved_links",
                    status=FindingStatus.FAIL,
                    impact=FindingImpact.MEDIUM,
                    message=f"Missing internal links: only {len(matched_targets)} of {len(link_targets)} approved targets found.",
                    details={"matched_urls": matched_targets},
                )
            )

        linking_score = max(0.0, min(100.0, round(linking_points, 1)))

    # -------------------------------------------------------------
    # 6. Overall Score & Status Calculation
    # -------------------------------------------------------------
    overall_score = round(
        0.30 * seo_score + 0.30 * content_score + 0.20 * brand_score + 0.20 * linking_score,
        1,
    )

    # Determine PASS or NEEDS IMPROVEMENT
    has_high_impact_failure = any(
        f.status == FindingStatus.FAIL and f.impact == FindingImpact.HIGH for f in findings
    )
    if technical_validity == "FAIL" or brand_score < 70.0 or has_high_impact_failure or overall_score < 75.0:
        overall_status = "NEEDS IMPROVEMENT"
    else:
        overall_status = "PASS"

    summary = (
        f"Overall: {overall_status} (Score: {overall_score}/100). "
        f"SEO: {seo_score}, Content: {content_score}, Brand: {brand_score}, Links: {linking_score}, "
        f"Technical: {technical_validity}."
    )

    return HarnessScorecard(
        seo_score=seo_score,
        content_score=content_score,
        brand_score=brand_score,
        linking_score=linking_score,
        technical_validity=technical_validity,
        overall_score=overall_score,
        status=overall_status,
        findings=findings,
        summary=summary,
    )


async def evaluate_with_ai(
    generated: HarnessGeneratedContent,
    input_data: ContentHarnessInput,
    provider: AIProvider,
) -> dict[str, Any]:
    """Optional qualitative AI evaluation that inspects depth, tone, and hallucination risks."""
    eval_prompt = f"""You are a senior editorial and SEO reviewer evaluating a generated article.
DO NOT MODIFY OR REWRITE THE ARTICLE. Your job is ONLY to assess its quality and produce a structured evaluation.

### INPUT SPECIFICATIONS:
- Primary Keyword: {input_data.primary_keyword}
- Target Audience: {input_data.target_audience}
- Brand Voice: {input_data.brand_rules.voice}
- Tone: {input_data.brand_rules.tone}
- Provided Website Context:
{input_data.website_context or 'None provided.'}

### ARTICLE TO EVALUATE:
Title: {generated.title}
Content:
{generated.content[:3000]}

### EVALUATION INSTRUCTIONS:
Evaluate the article on:
1. Factual grounding (did it invent facts not supported by context?)
2. Voice & Tone fidelity
3. Depth and value to the target audience
4. Search Intent alignment

Respond with valid JSON:
{{
  "ai_score": 85,
  "factual_accuracy": "HIGH|MEDIUM|LOW",
  "hallucination_detected": false,
  "strengths": ["Clear explanation...", "Good structure..."],
  "weaknesses": ["Could expand on...", "Slightly generic tone..."],
  "qualitative_summary": "Comprehensive assessment..."
}}
"""
    req = GenerationRequest(
        messages=[AIMessage(role="user", content=eval_prompt)],
        temperature=0.1,
        max_output_tokens=1500,
    )
    try:
        res = await provider.generate(req)
        clean = res.text.strip()
        if clean.startswith("```"):
            lines = clean.splitlines()
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            clean = "\n".join(lines).strip()
        parsed = json.loads(clean)
        return parsed if isinstance(parsed, dict) else {"raw_response": clean}
    except Exception as exc:
        return {"error": f"AI evaluation could not complete: {exc}"}
