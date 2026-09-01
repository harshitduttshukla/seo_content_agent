# Codex Engineering Workflow

## 1. Purpose

Codex assists the two developers with scoped implementation, tests, migrations, components, API clients, refactoring, debugging, and documentation. It follows [AGENTS.md](../AGENTS.md) and the accepted architecture. It does not expand scope, invent provider APIs, present test doubles as product behavior, or silently change decisions.

## 2. Task workflow

### Understand

Read `AGENTS.md`, roadmap phase, relevant domain/API/database/ADR documents, existing models/migrations/tests, and working-tree status. Restate the intended outcome, non-goals, permissions/tenant impact, and acceptance criteria. Verify any external API against official documentation before coding.

### Plan

For non-trivial work, identify vertical slice, files/owners, contract/migration changes, authorization and transaction boundary, background/external behavior, tests, documentation, rollout and rollback. Surface an architecture change before implementation and create/update an ADR only with approval.

### Implement

Prefer the smallest complete vertical slice. Add Pydantic contract and domain policy, then model/migration/repository/service, then thin route/worker/adapter, then generated client/UI. Preserve unrelated changes. AI features begin with tool/context/approval contracts and test adapters, not a hard-coded provider call.

### Test

Run the narrow test during iteration, then affected Ruff, MyPy, Pytest, migration, OpenAPI/type generation, frontend checks, security/tenant tests, and documentation validation. Use PostgreSQL for database semantics. Never claim a check passed if it was not run; report command, result, and environment blocker.

### Review and refactor

Review diff for scope creep, missing tenant predicate/permission/audit, commit inside repository, external call inside DB transaction, unbounded query/context/job, secret/content logging, fake integration, duplicated domain rule, breaking contract, and stale docs. Refactor only within scope and rerun checks.

### Handoff

Lead with outcome. List material files/contracts/migrations, validation results, known limitations/risks, operational steps, and next safe roadmap item. Do not hide failures or leave ambiguous placeholders.

## 3. Standard task brief

```text
Outcome:
Active roadmap phase/milestone:
In scope:
Out of scope:
Affected domain owner:
API/tool/event contracts:
Roles and tenant rules:
Data/migration and transaction plan:
External/job/idempotency plan:
Acceptance cases:
Required checks:
Docs/ADR impact:
Rollout/rollback:
```

If a field is not relevant, say why. A task is too broad when it crosses several milestones, lacks a single demonstrable outcome, or cannot state its invariants.

## 4. Architecture and API changes

Codex may apply an existing decision but must not replace the modular monolith, database/vector/graph/editor/provider choices, tenancy model, approval model, or public contract strategy without explicit review. Proposed change includes current limitation with evidence, decision/options/tradeoffs, data/security/operations impact, migration/rollback, affected docs, and ADR. Update every affected document after acceptance.

Public schema changes start in Pydantic. Add OpenAPI examples and compatibility assessment, regenerate TypeScript, update fixtures/consumer, and include contract diff. Do not invent fields merely to satisfy a UI; confirm domain ownership and persistence.

## 5. Migration workflow

1. Confirm current head/model registry and inspect recent revisions.
2. Design expand/backfill/enforce/contract sequence and tenant/index/lock implications.
3. Generate/edit a descriptive Alembic revision; inspect SQL and downgrade safety.
4. Test empty upgrade, previous-snapshot upgrade, constraints/RLS, and downgrade or documented forward recovery.
5. Keep large backfills out of migration transactions; add resumable job and observability.
6. Report release ordering and rollback.

Codex never runs a manual production DDL/data fix, destructive migration, or production configuration change without explicit approval and runbook.

## 6. AI implementation workflow

Define purpose and evaluation dataset first. Add strict tool/context/output contracts and permissions; deterministic test provider; proposal/approval/audit path; adapter behind `AIProvider`; bounded context and budgets; adversarial/tenant tests; model/prompt/retrieval version; staging evaluation. No production tool gets generic database, network, shell, object-store, or secret access.

## 7. Parallel developer coordination

Backend developer publishes reviewed OpenAPI/schema examples and deterministic mock fixtures before frontend integration. Frontend developer can build against the snapshot/mock without waiting on internal Python. Changes to content-map/editor command semantics are jointly reviewed. Shared integration cadence: contract diff early, sandbox vertical slice mid-task, E2E before merge. Codex can prepare either side but must preserve domain ownership.

## 8. Failure and blocked-work reporting

When blocked, exhaust safe read-only inspection and in-scope alternatives. Report exact failed command/contract/dependency, concise error, what was verified, impact, and the smallest user/developer decision or external change needed. Do not bypass security/tests, fabricate output, substitute a materially different architecture, or leave fake success behavior.

## 9. Phase 0 usage

This repository currently permits only foundation/contract/documentation improvements. Feature code begins only when the team explicitly starts a milestone in [ROADMAP.md](ROADMAP.md). Empty domain directories are intentional; do not add placeholder services, routes that return dummy data, fake adapters, or migrations for imagined fields.

