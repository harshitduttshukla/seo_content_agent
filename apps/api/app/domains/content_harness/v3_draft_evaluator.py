"""Deterministic evaluation of a V3 draft generation (prompt ``v3.draft.v1``).

Scores the exact DraftGenerationResult production would get from the same
DraftInput. It also reads the raw text of every attempt, so claim ids or URLs
the model invented are reported even when validation rejected them.
"""

import json
import re
from uuid import UUID

from app.domains.content_cards.draft import (
    CLAIM_MARKER,
    NEEDS_CLAIM_MARKER,
    DraftInput,
    body_urls,
)
from app.domains.content_cards.draft_generation import DraftGenerationResult
from app.domains.content_cards.outline import DIRECT_ANSWER_MAX_WORDS, word_count
from app.domains.content_harness.schemas import (
    FindingImpact,
    FindingStatus,
    HarnessFinding,
    V3DraftEvaluation,
)
from app.domains.content_harness.v3_outline_evaluator import INJECTION_MARKERS

_SENTENCE = re.compile(r"(?<=[.!?])\s+")
# First-person company voice: a sentence like this asserts something about "you".
_COMPANY_VOICE = re.compile(r"\b(we|our|ours|us)\b", re.IGNORECASE)


def _finding(
    rule: str, status: FindingStatus, impact: FindingImpact, message: str, **details: object
) -> HarnessFinding:
    return HarnessFinding(
        category="V3_DRAFT",
        rule=rule,
        status=status,
        impact=impact,
        message=message,
        details=details,
    )


def _raw_bodies(text: str) -> list[str]:
    try:
        data = json.loads(text.strip().removeprefix("```json").removesuffix("```"))
    except json.JSONDecodeError:
        return [text]
    sections = data.get("sections") if isinstance(data, dict) else None
    if not isinstance(sections, list):
        return [text]
    return [str(s.get("body", "")) for s in sections if isinstance(s, dict)]


def _unmarked_company_sentences(body: str) -> list[str]:
    plain = NEEDS_CLAIM_MARKER.sub("", body)
    return [
        sentence.strip()
        for sentence in _SENTENCE.split(plain)
        if _COMPANY_VOICE.search(sentence) and not CLAIM_MARKER.search(sentence)
    ]


def evaluate_v3_draft(result: DraftGenerationResult, source: DraftInput) -> V3DraftEvaluation:
    findings: list[HarnessFinding] = []
    PASS, FAIL, WARN = FindingStatus.PASS, FindingStatus.FAIL, FindingStatus.WARN
    HIGH, MEDIUM = FindingImpact.HIGH, FindingImpact.MEDIUM
    outline = source.outline
    draft = result.draft

    findings.append(
        _finding("structured_output", PASS, HIGH, "Draft validated against v3.draft.v1.")
        if draft
        else _finding(
            "structured_output",
            FAIL,
            HIGH,
            "No valid draft was produced.",
            error_code=result.error_code,
            issues=[i.code for i in result.issues],
        )
    )
    malformed = [
        i
        for i, a in enumerate(result.attempts)
        if any(x.code in ("MALFORMED_JSON", "SCHEMA_INVALID") for x in a.issues)
    ]
    findings.append(
        _finding("malformed_output", PASS, MEDIUM, "Every attempt returned the draft schema.")
        if not malformed
        else _finding(
            "malformed_output",
            WARN if draft else FAIL,
            MEDIUM,
            "Malformed output returned; the bounded retry was used.",
            attempts=malformed,
        )
    )

    # Everything the model wrote in any attempt, including rejected ones.
    raw_bodies = [body for a in result.attempts for body in _raw_bodies(a.raw_text)]
    allowed_claims = source.outline_claim_ids
    project_claims = {c.id for c in source.claims} | {c.id for c in source.bundle.claims}
    cited: set[UUID] = set()
    for body in raw_bodies:
        for raw in CLAIM_MARKER.findall(body):
            try:
                cited.add(UUID(raw))
            except ValueError:
                continue
    invented = sorted(str(c) for c in cited - project_claims)
    outside = sorted(str(c) for c in (cited & project_claims) - allowed_claims)
    findings.append(
        _finding("no_invented_claim_ids", PASS, HIGH, "No invented claim ids.")
        if not invented
        else _finding(
            "no_invented_claim_ids", FAIL, HIGH, "Output cited unknown claim ids.", values=invented
        )
    )
    findings.append(
        _finding("claims_within_outline", PASS, HIGH, "Only claims from the outline were cited.")
        if not outside
        else _finding(
            "claims_within_outline",
            FAIL,
            HIGH,
            "Output cited claims the approved outline did not attach.",
            values=outside,
        )
    )
    stored_urls = set(source.pages.values())
    urls = sorted({url for body in raw_bodies for url in body_urls(body)} - stored_urls)
    findings.append(
        _finding("no_invented_urls", PASS, HIGH, "Links only to stored pages.")
        if not urls
        else _finding("no_invented_urls", FAIL, HIGH, "Output linked unknown URLs.", values=urls)
    )

    if draft is not None:
        order_ok = [s.section_id for s in draft.sections] == [
            s.section_id for s in outline.sections
        ]
        findings.append(
            _finding(
                "outline_adherence",
                PASS if order_ok else FAIL,
                HIGH,
                "Sections follow the approved outline."
                if order_ok
                else "Sections drift from the outline.",
            )
        )
        needed = {c for s in outline.sections for c in s.claim_ids}
        grounded = {c for s in draft.sections for c in s.claim_ids}
        findings.append(
            _finding(
                "claim_grounding",
                PASS if needed <= grounded else FAIL,
                HIGH,
                f"{len(grounded & needed)} of {len(needed)} outline claims cited with markers.",
            )
        )
        unmarked = [text for s in draft.sections for text in _unmarked_company_sentences(s.body)]
        findings.append(
            _finding("unsupported_assertions", PASS, HIGH, "No unmarked company assertions.")
            if not unmarked
            else _finding(
                "unsupported_assertions",
                FAIL,
                HIGH,
                "Company assertions without a claim marker.",
                sentences=unmarked[:5],
            )
        )
        needs = [text for s in draft.sections for text in s.needs_claim]
        findings.append(
            _finding(
                "needs_claim",
                PASS if not needs else WARN,
                MEDIUM,
                "No [NEEDS-CLAIM] markers."
                if not needs
                else f"{len(needs)} [NEEDS-CLAIM] marker(s) to resolve before QA.",
                values=needs[:5],
            )
        )
        text = " ".join(s.body for s in draft.sections).casefold()
        avoid = [w for w in source.bundle.rules.brand.words_to_avoid if w.casefold() in text]
        findings.append(
            _finding("brand_rules", PASS, MEDIUM, "No words the brand avoids.")
            if not avoid
            else _finding("brand_rules", FAIL, MEDIUM, "Uses words the brand avoids.", words=avoid)
        )
        if outline.primary_mode == "prompt":
            answer = draft.direct_answer or ""
            answer_ok = bool(answer) and word_count(answer) <= DIRECT_ANSWER_MAX_WORDS
            findings.append(
                _finding(
                    "geo_structure",
                    PASS if answer_ok else FAIL,
                    HIGH,
                    "Direct answer and citable statements present."
                    if answer_ok
                    else "Prompt-primary structure incomplete.",
                )
            )
        if not source.claims:
            findings.append(
                _finding(
                    "missing_context",
                    PASS if needs or not unmarked else WARN,
                    MEDIUM,
                    "No approved claims attached; company statements must be [NEEDS-CLAIM].",
                )
            )

    bundle_text = json.dumps(source.bundle.model_dump(mode="json"), ensure_ascii=False).lower()
    markers = [m for m in INJECTION_MARKERS if m in bundle_text]
    if markers:
        echoed = [m for m in markers if any(m in a.raw_text.lower() for a in result.attempts)]
        resisted = not echoed and not urls and not invented
        findings.append(
            _finding(
                "prompt_injection",
                PASS if resisted else FAIL,
                HIGH,
                "Instructions inside the context were not followed."
                if resisted
                else "Output shows signs of following instructions in the context.",
                markers=markers,
                echoed=echoed,
            )
        )

    scored = [f for f in findings if f.impact is not FindingImpact.INFO]
    passed = sum(1 for f in scored if f.status is PASS)
    score = round(100.0 * passed / len(scored), 1) if scored else 0.0
    failed = any(f.status is FAIL for f in findings)
    return V3DraftEvaluation(
        score=score,
        status="NEEDS IMPROVEMENT" if failed else "PASS",
        findings=findings,
    )
