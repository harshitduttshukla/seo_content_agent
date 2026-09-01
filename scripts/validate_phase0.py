"""Dependency-free structural validation for the Phase 0 blueprint."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

REQUIRED_FILES = (
    "AGENTS.md",
    "README.md",
    ".env.example",
    "apps/api/pyproject.toml",
    "apps/api/alembic.ini",
    "apps/api/alembic/env.py",
    "apps/api/alembic/script.py.mako",
    "docs/PRD.md",
    "docs/ARCHITECTURE.md",
    "docs/DATABASE.md",
    "docs/API.md",
    "docs/AI-ORCHESTRATOR.md",
    "docs/SEO-RULES.md",
    "docs/INTERNAL-LINKING.md",
    "docs/CONTENT-MAP.md",
    "docs/SECURITY.md",
    "docs/TESTING.md",
    "docs/CODEX-WORKFLOW.md",
    "docs/ROADMAP.md",
    "docs/PHASE-0-REPORT.md",
)

ADR_SECTIONS = (
    "## Context",
    "## Decision",
    "## Reason",
    "## Alternatives",
    "## Tradeoffs",
    "## Consequences",
)

REPORT_SECTIONS = (
    "Executive Summary",
    "Product Architecture",
    "Python Backend Architecture",
    "Frontend Architecture",
    "Database Architecture",
    "AI Architecture",
    "Content Graph Architecture",
    "Internal Linking Architecture",
    "Security Architecture",
    "Repository Structure",
    "API Strategy",
    "Testing Strategy",
    "Codex Workflow",
    "Developer Split",
    "MVP Roadmap",
    "V1 Roadmap",
    "Risks",
    "Assumptions",
    "Open Questions",
    "Phase 1 Readiness Checklist",
)

MARKDOWN_LINK = re.compile(r"\[[^\]]+\]\(([^)]+)\)")


def validate_markdown_links(paths: list[Path]) -> list[str]:
    """Return broken local Markdown links while ignoring URLs and anchors."""

    broken: list[str] = []
    for path in paths:
        text = path.read_text(encoding="utf-8")
        for raw_target in MARKDOWN_LINK.findall(text):
            target = raw_target.strip("<>").split("#", maxsplit=1)[0]
            if not target or "://" in target or target.startswith("mailto:"):
                continue
            resolved = (path.parent / target).resolve()
            if not resolved.exists():
                broken.append(f"{path.relative_to(ROOT)} -> {raw_target}")
    return broken


def main() -> None:
    errors = [relative for relative in REQUIRED_FILES if not (ROOT / relative).is_file()]
    adrs = sorted((ROOT / "docs" / "adr").glob("ADR-*.md"))
    if len(adrs) != 10:
        errors.append(f"exactly 10 ADRs (found {len(adrs)})")
    for adr in adrs:
        contents = adr.read_text(encoding="utf-8")
        absent = [section for section in ADR_SECTIONS if section not in contents]
        if absent:
            errors.append(f"{adr.relative_to(ROOT)} missing {', '.join(absent)}")

    report = ROOT / "docs" / "PHASE-0-REPORT.md"
    if report.is_file():
        report_text = report.read_text(encoding="utf-8")
        for number, title in enumerate(REPORT_SECTIONS, start=1):
            if f"## {number}. {title}" not in report_text:
                errors.append(f"Phase 0 report missing section {number}: {title}")

    markdown_paths = sorted(ROOT.glob("*.md")) + sorted((ROOT / "docs").rglob("*.md"))
    errors.extend(validate_markdown_links(markdown_paths))
    forbidden_suffixes = (".env.local", ".env.production")
    leaked_env = [path for path in ROOT.rglob(".env*") if path.name.endswith(forbidden_suffixes)]
    if leaked_env:
        errors.extend(str(path.relative_to(ROOT)) for path in leaked_env)
    if errors:
        raise SystemExit("Phase 0 validation failed:\n- " + "\n- ".join(errors))
    print(
        "Phase 0 blueprint valid: "
        f"{len(REQUIRED_FILES)} required files, 10 complete ADRs, "
        f"{len(REPORT_SECTIONS)} report sections, and local Markdown links"
    )


if __name__ == "__main__":
    main()
