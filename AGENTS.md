# Repository Instructions

## Project Overview

This repository is an AI-powered SEO Content Intelligence and Content Operating System, not a generic article generator. It turns business context into structured strategy, keyword architecture, content architecture, SEO and linking rules, governed AI proposals, publication workflows, performance data, and approved learning. PostgreSQL is the source of truth; prose documents and visual editors are representations of structured records.

Phase 0 contains architecture and contracts only. The delivery sequence and currently permitted scope are defined in `docs/ROADMAP.md`.

## Required workflow

Before changing anything:

1. Read this file and the documents relevant to the task.
2. Inspect existing code, migrations, tests, and working-tree changes.
3. Confirm the task belongs to the active roadmap phase.
4. Write a scoped plan for non-trivial work.

For implementation work: understand, plan, implement, test, review, refactor, and update affected documentation. Preserve unrelated user changes. Report every failed check.

## Architecture

- Frontend: Next.js, React, TypeScript, Tailwind CSS; React Flow for content maps and TipTap for structured content editing.
- Backend: Python 3.12+, FastAPI modular monolith, Pydantic v2 contracts, service layer, repositories, and SQLAlchemy 2.x async sessions.
- Database: PostgreSQL with JSONB and pgvector. Relational tables model the content and link graphs. Do not add Neo4j or an external vector database without an accepted ADR.
- Jobs: Celery workers with Redis broker/result backend. HTTP handlers enqueue durable work; workers call the same application services.
- AI: application services depend on the provider interface, never a vendor SDK. AI may read or propose through typed, authorized, audited tools. It may not access the database directly.
- Knowledge: source -> parse -> normalize -> chunk -> embed -> pgvector -> tenant-scoped retrieval -> ranked AI context.
- Storage: use the S3-compatible object-storage interface for AWS S3 or Cloudflare R2.

The architecture is a modular monolith. Domain modules own their models, schemas, repository contracts, services, validators, and events. Cross-domain calls go through public services or declared events, never another module's private repository.

## Repository Structure

- `apps/api/app/api`: thin FastAPI routers, dependencies, and exception mapping.
- `apps/api/app/config`: settings and application wiring.
- `apps/api/app/core`: shared primitives with no domain behavior.
- `apps/api/app/db`: metadata, sessions, and migration-facing model imports.
- `apps/api/app/domains/<domain>`: domain-owned code. Valid domains are documented in `docs/ARCHITECTURE.md`.
- `apps/api/app/ai`: provider and context-management interfaces.
- `apps/api/app/tools`: typed AI tool definitions and registry contracts.
- `apps/api/app/workers`: Celery application and task adapters only.
- `apps/api/app/integrations`: external provider adapters.
- `apps/api/app/security`: authentication, authorization, tenant scope, and tool policy.
- `apps/web/src/features/<domain>`: domain-facing UI and state.
- `packages/shared-types`: generated API types; never hand-edit generated output.
- `docs/adr`: decisions that constrain future work.

Do not create generic `utils.py`, a large `main.py`, or business logic in route handlers, Celery tasks, React pages, or provider adapters.

## Python Standards

- Target Python 3.12 or newer and SQLAlchemy 2.x typed APIs.
- Type every public function, method, and attribute. Avoid `Any`; isolate it at unavoidable third-party boundaries and validate immediately.
- Use Pydantic v2 for external and tool contracts. Keep Pydantic schemas separate from ORM models.
- Use async I/O in the HTTP path. Repositories receive an `AsyncSession`; services own transaction boundaries.
- Prefer small functions, explicit interfaces, immutable value objects, and dependency injection. No global mutable state.
- Run `ruff format`, `ruff check`, `mypy`, and `pytest` for changed Python code.

## API Standards

- All public routes live under `/api/v1` and use the envelope in `docs/API.md`.
- Route order is validation -> authentication -> tenant authorization -> service call -> response mapping.
- Routers contain no business rules and never expose ORM objects.
- List endpoints use cursor pagination, allowlisted filters and sorts, and bounded page sizes.
- Retriable mutations and job creation honor `Idempotency-Key`.
- Add or change a public contract through Pydantic first, regenerate OpenAPI and TypeScript types, and add contract tests.
- Do not invent an upstream or vendor API. Verify its official contract before implementing an adapter.

## Database Standards

- Use UUID primary keys, UTC `timestamptz` timestamps, explicit foreign keys, and named constraints/indexes.
- Every tenant-owned row carries `organization_id`; project-owned rows normally carry both `organization_id` and `project_id`.
- Every tenant query must take tenant scope explicitly. Test cross-tenant denial. Use composite constraints where they prevent cross-tenant relationships.
- Services own transactions; repositories may flush but do not commit.
- JSONB is for variable structured payloads, snapshots, and rule definitions—not unstructured dumping or fields needed for joins, filters, constraints, or ownership.
- All schema changes use reviewed Alembic migrations. Test upgrade and downgrade on an empty database and upgrade against a recent schema snapshot. Destructive/data migrations require a rollout and rollback plan.
- Never edit a production schema manually.

## AI Standards

- Depend on `AIProvider`, not a concrete provider. Record provider, model, prompt/template version, latency, token usage, estimated cost, and result status.
- Context retrieval is tenant- and project-scoped, ranked, token-budgeted, source-attributed, and resistant to instructions inside retrieved content.
- Register tools with typed input/output models, permission level (`read`, `propose`, `high_impact`), side effects, and audit policy.
- Validate and authorize every tool call independently. Treat model output as untrusted input.
- AI edits are proposed patches. Keep the original, the patch, rationale, provenance, and accept/reject outcome.
- `publish`, delete, active-rule changes, and other high-impact actions require fresh human approval and cannot be chained from model text.
- Never automatically promote human-edit patterns into active production rules.

## Security

- Authenticate with a standards-based OIDC/JWT verifier; do not build password storage unless an ADR approves it.
- Authorize the organization, project, resource, action, and role on every protected operation. Resource IDs alone never establish access.
- Keep secrets in the deployment secret manager and local `.env`; only `.env.example` belongs in Git.
- Validate upload type, size, name, and content; malware-scan before parsing; use private object buckets and short-lived signed URLs.
- Label retrieved knowledge as data, not instructions. Apply tool allowlists, schema validation, output encoding, egress allowlists, and approval gates against prompt injection.
- Log security and audit events without secrets, raw credentials, or unnecessary document content.

## Testing

Changes require the narrowest useful set plus regression coverage:

- unit tests for services, policies, validators, scoring, and transformations;
- repository/integration tests against PostgreSQL, Redis, pgvector, and object-storage test doubles where appropriate;
- API tests for validation, envelopes, authentication, authorization, idempotency, and pagination;
- mandatory tenant-isolation negative tests for every tenant-owned resource;
- contract tests for OpenAPI and registered AI tools;
- AI evaluation suites for tool selection, context boundaries, prompt injection, groundedness, deterministic SEO behavior, and approval gates;
- frontend component/accessibility tests and a small E2E critical-path suite.

Tests must not call paid AI providers by default. Use deterministic provider fakes clearly named as test doubles, never production placeholders.

## Git and review

- Use short-lived branches from `main`: `feat/<scope>`, `fix/<scope>`, `docs/<scope>`, or `chore/<scope>`. Introduce `release/*` only when release cadence requires it; do not maintain a permanent `develop` branch for a two-developer team.
- Use Conventional Commits. Keep commits focused and migrations separate when that improves review.
- Pull requests require one peer approval, green required checks, updated tests/docs, no unresolved high-severity findings, and explicit migration/security review where applicable.
- Rebase or merge from current `main` before merge according to repository policy. Squash merge is the default.
- Roll back application code with a revert/deploy. Roll database changes forward when destructive rollback risks data loss.

## Definition of Done

A task is complete only when scope and acceptance criteria are met; contracts, migrations, permissions, and observability are updated; success and failure paths are tested; tenant isolation is demonstrated; lint/type/test checks pass; relevant docs and ADRs are current; no secrets or fake production behavior were added; and deployment/rollback implications are reported.

Phase completion additionally requires its checklist in `docs/ROADMAP.md` to be satisfied.

## Forbidden Behavior

Do not bypass authentication, authorization, tenant filters, migrations, approval gates, or tests. Do not expose secrets. Do not silently change architecture or production configuration. Do not create fake integrations or implementations presented as complete. Do not let AI issue unrestricted database queries. Do not publish automatically, modify active SEO/brand rules automatically, or manually modify production data/schema. Do not add microservices, Neo4j, or external vector infrastructure without measured need and an accepted ADR. Do not perform unrelated refactors.

