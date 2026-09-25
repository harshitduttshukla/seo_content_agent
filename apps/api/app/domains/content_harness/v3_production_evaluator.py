"""Deterministic evaluation of V3 Production calls: QA (v3.qa.v1), repair (v3.repair.v1)
and section regeneration (v3.section.v1).

Scores exactly what production would get from the same card: the same deterministic
QA, the same QAExtractor and DraftReviser, the same validators. Repair and section
runs are re-checked with the deterministic QA layer to show what was really fixed.
"""

import json
from collections.abc import Callable

from app.domains.content_cards.draft import StoredDraft
from app.domains.content_cards.draft_revision import RevisionResult
from app.domains.content_cards.qa import ModelQAResult, QAFinding
from app.domains.content_harness.schemas import (
    FindingImpact,
    FindingStatus,
    HarnessFinding,
    V3DraftEvaluation,
)
from app.domains.content_harness.v3_outline_evaluator import INJECTION_MARKERS

PASS, FAIL, WARN = FindingStatus.PASS, FindingStatus.FAIL, FindingStatus.WARN
HIGH, MEDIUM = FindingImpact.HIGH, FindingImpact.MEDIUM


def _f(
    rule: str, status: FindingStatus, impact: FindingImpact, message: str, **details: object
) -> HarnessFinding:
    return HarnessFinding(
        category="V3_PRODUCTION",
        rule=rule,
        status=status,
        impact=impact,
        message=message,
        details=details,
    )


def _score(findings: list[HarnessFinding]) -> V3DraftEvaluation:
    scored = [f for f in findings if f.impact is not FindingImpact.INFO]
    passed = sum(1 for f in scored if f.status is PASS)
    return V3DraftEvaluation(
        score=round(100.0 * passed / len(scored), 1) if scored else 0.0,
        status="NEEDS IMPROVEMENT" if any(f.status is FAIL for f in findings) else "PASS",
        findings=findings,
    )


def _injection(raw_texts: list[str], context_text: str) -> HarnessFinding | None:
    markers = [m for m in INJECTION_MARKERS if m in context_text.lower()]
    if not markers:
        return None
    echoed = [m for m in markers if any(m in t.lower() for t in raw_texts)]
    return _f(
        "prompt_injection",
        PASS if not echoed else FAIL,
        HIGH,
        "Instructions inside the context were not followed."
        if not echoed
        else "Output echoes instructions from the context.",
        markers=markers,
        echoed=echoed,
    )


def evaluate_v3_qa(
    deterministic: list[QAFinding], model: ModelQAResult | None, context_text: str
) -> V3DraftEvaluation:
    errors = sorted({f.code for f in deterministic if f.severity == "error"})
    findings = [
        _f(
            "deterministic_layer",
            PASS,
            MEDIUM,
            f"{len(deterministic)} deterministic finding(s), {len(errors)} blocking code(s).",
            codes=sorted({f.code for f in deterministic}),
        )
    ]
    if model is None:
        findings.append(
            _f(
                "model_layer",
                PASS,
                MEDIUM,
                "Skipped: deterministic errors come first.",
                blocking=errors,
            )
        )
    else:
        findings.append(
            _f("structured_output", PASS, HIGH, "Model QA output validated.")
            if model.ok
            else _f(
                "structured_output",
                FAIL,
                HIGH,
                "Model QA output rejected.",
                error_code=model.error_code,
                issues=[i.code for i in model.issues],
            )
        )
        malformed = [i for i, a in enumerate(model.attempts) if a.issues]
        findings.append(
            _f(
                "malformed_output",
                PASS if not malformed else WARN if model.ok else FAIL,
                MEDIUM,
                "Every attempt was valid." if not malformed else "The bounded retry was used.",
                attempts=malformed,
            )
        )
        invalid_refs = [
            i.code
            for a in model.attempts
            for i in a.issues
            if i.code in ("UNKNOWN_SECTION", "EVIDENCE_NOT_FOUND", "UNKNOWN_CLAIM")
        ]
        findings.append(
            _f(
                "no_hallucinated_references",
                PASS if not invalid_refs else FAIL,
                HIGH,
                "Model findings referred only to real sections, quotes and claims."
                if not invalid_refs
                else "Model invented sections, quotes or claim ids.",
                codes=invalid_refs,
            )
        )
        if model.findings:
            findings.append(
                _f(
                    "model_findings",
                    PASS,
                    FindingImpact.INFO,
                    f"{len(model.findings)} model finding(s).",
                    codes=sorted({f.code for f in model.findings}),
                )
            )
        injection = _injection([a.raw_text for a in model.attempts], context_text)
        if injection:
            findings.append(injection)
    return _score(findings)


def evaluate_v3_revision(
    before: StoredDraft,
    result: RevisionResult,
    targets: list[str],
    targeted: list[QAFinding],
    recheck: Callable[[StoredDraft], list[QAFinding]],
    context_text: str,
) -> V3DraftEvaluation:
    findings = [
        _f("structured_output", PASS, HIGH, "Revision validated.")
        if result.ok
        else _f(
            "structured_output",
            FAIL,
            HIGH,
            "Revision rejected.",
            error_code=result.error_code,
            issues=[i.code for i in result.issues],
        )
    ]
    rejected = {i.code for a in result.attempts for i in a.issues}
    for rule, codes, label in (
        ("no_invented_claims", {"CLAIM_NOT_IN_OUTLINE", "MALFORMED_CLAIM_MARKER"}, "claim ids"),
        ("no_invented_urls", {"INVENTED_URL"}, "URLs"),
        (
            "preserves_outline",
            {"STRUCTURE_CHANGED", "OUT_OF_SCOPE", "SECTION_MISSING"},
            "structure",
        ),
        ("preserves_links", {"MISSING_PLANNED_LINK"}, "planned links"),
    ):
        hit = sorted(rejected & codes)
        findings.append(
            _f(
                rule,
                PASS if not hit else FAIL,
                HIGH,
                f"No attempt broke {label}."
                if not hit
                else f"An attempt broke {label} (rejected).",
                codes=hit,
            )
        )
    draft = result.draft
    if draft is not None:
        unchanged = [
            s.section_id
            for s, old in zip(draft.sections, before.draft.sections, strict=True)
            if s.section_id not in targets and s.body != old.body
        ]
        findings.append(
            _f(
                "unrelated_sections_unchanged",
                PASS if not unchanged else FAIL,
                HIGH,
                "Only target sections changed." if not unchanged else "Other sections changed.",
                sections=unchanged,
            )
        )
        after = recheck(before.model_copy(update={"draft": draft, "version": before.version + 1}))
        still = sorted({f.id for f in after} & {f.id for f in targeted})
        if targeted:
            findings.append(
                _f(
                    "fixes_intended_findings",
                    PASS if not still else FAIL,
                    HIGH,
                    f"{len(targeted) - len(still)} of {len(targeted)} targeted findings fixed.",
                    remaining=still,
                )
            )
        new_errors = sorted(
            {f.code for f in after if f.severity == "error" and f.section_id in targets}
        )
        findings.append(
            _f(
                "targets_clean",
                PASS if not new_errors else FAIL,
                HIGH,
                "Rewritten sections pass deterministic QA."
                if not new_errors
                else "Rewritten sections still have errors.",
                codes=new_errors,
            )
        )
    injection = _injection([a.raw_text for a in result.attempts], context_text)
    if injection:
        findings.append(injection)
    return _score(findings)


def context_text(*parts: object) -> str:
    return json.dumps(parts, default=str, ensure_ascii=False)
