# SEO Content Intelligence & AI Content Operating System

This repository contains the Phase 0 product and technical foundation for a multi-tenant SEO content operating system. Phase 0 deliberately includes architecture, contracts, configuration, and development rules only. Keyword clustering, content generation, orchestration, publishing, learning, and other product behavior are not implemented.

## Start here

1. Read [AGENTS.md](AGENTS.md).
2. Read the [product requirements](docs/PRD.md) and [system architecture](docs/ARCHITECTURE.md).
3. Resolve the blocking choices in [the Phase 0 report](docs/PHASE-0-REPORT.md#19-open-questions) before implementation.
4. Start Phase 1 from the milestones in [ROADMAP.md](docs/ROADMAP.md).

## Repository map

```text
apps/web/                 Next.js application boundary (configuration only)
apps/api/                 FastAPI modular-monolith boundary and typed contracts
packages/ui/              Shared React UI package boundary
packages/shared-types/    Generated OpenAPI TypeScript output boundary
docs/                     Product, architecture, operations, and ADRs
scripts/                  Repository automation boundary
```

The database is the source of truth. Human-readable documents and editor views are projections over structured entities, rules, relationships, and versioned JSON.

## Phase 0 validation

No dependencies are installed by Phase 0. The scaffold can be checked with:

```bash
python3 -m compileall apps/api/app apps/api/tests
python3 scripts/validate_phase0.py
```

Once Phase 1 dependencies are installed, use `ruff check`, `mypy`, and `pytest` as defined in `apps/api/pyproject.toml`.

