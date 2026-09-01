# Testing and Quality Strategy

## 1. Quality model

Tests prove business invariants, tenant isolation, contract compatibility, deterministic behavior, approval safety, and recoverability. The pyramid favors pure unit tests, then real-boundary integration/API tests, then a small critical E2E suite. AI evaluation is a versioned product-quality layer, not a substitute for deterministic tests.

No default test contacts a paid AI, production CMS, or real customer source. Deterministic test doubles are explicitly named and live in test code.

## 2. Test layers

| Layer | Scope and tools | Required examples |
|---|---|---|
| Unit | Pytest; pure services/policies/value objects/evaluators/scoring | state transitions, permissions, link score, SEO boundaries, token packing, JSON upcasters |
| Repository/database | Pytest + disposable PostgreSQL with pgvector | tenant predicates/RLS, composite FKs, constraints, recursive queries, vector filters, transaction rollback, query plans |
| API | HTTPX/ASGI FastAPI client | schemas/envelopes/errors, JWT/membership, 404 vs 403, cursor, idempotency, ETag/conflicts, rate-limit mapping |
| Contract | OpenAPI snapshot/diff, JSON Schema fixtures, generated TypeScript compile | request/response compatibility, tool registry schemas, event versions, examples |
| Worker/integration | Celery eager/unit plus broker-backed integration; fake adapters | at-least-once duplicate, retry/backoff, heartbeat, cancellation, outbox, unknown provider result |
| Frontend component | Vitest + Testing Library (selected in Phase 1) | forms/errors, editor suggestions, graph commands, keyboard/accessibility, optimistic rollback |
| E2E | Playwright (selected with first vertical slice) | sign-in/project, keyword-map-brief-editor-review, approval/publish sandbox, tenant denial |
| Security | policy/property tests plus scanners/DAST in staging | injection, upload bomb, SSRF/redirect, approval replay, secrets/log redaction |
| Performance/resilience | load/query plans/fault injection at milestone gates | p95 list/graph, vector recall/latency, queue age, provider timeout, DB fail/recovery |
| AI evaluations | versioned datasets, rubric/reference labels, optional staging provider | tool selection, groundedness, brand/intent/link precision, refusal/approval gates |

## 3. Mandatory scenario matrix

Every tenant-owned resource test covers admin/allowed role success, insufficient role denial, unassigned project denial, another organization using a real UUID, archived/inactive parent, and worker/tool path. A foreign resource usually returns 404 without revealing existence. Every mutation covers valid, invalid schema, stale revision/base, duplicate idempotency key same body, same key different body, transaction failure, and audit outcome.

Every versioned resource covers immutable history, correct parent/hash, concurrent edit conflict, approve exact version, changed input invalidates approval, restore-as-new, and old analysis/publication references remain stable.

## 4. Backend test organization

```text
apps/api/tests/
  unit/          mirrors domain/service modules
  integration/   repositories, Postgres/Redis/storage/provider adapters
  api/           endpoint behavior and middleware
  contract/      OpenAPI, tools, events, schema fixtures
```

Use factories/builders that require organization/project explicitly. Avoid fixture defaults that make cross-tenant tests accidentally pass. Freeze/inject clock and UUID generator where ordering/idempotency matters. Transactional test cleanup is acceptable for unit/integration isolation, but migration and RLS suites must exercise real commits/connections.

Repository tests run against PostgreSQL, not SQLite, because JSONB, pgvector, RLS, constraints, locking, and SQL semantics differ. Redis/S3/provider fakes are used for pure tests; at least one adapter integration suite uses compatible local services or a controlled sandbox.

## 5. Database and migration tests

- `alembic upgrade head` from empty with required extensions.
- Upgrade from supported previous schema snapshot and compare model metadata/schema drift.
- Downgrade for reversible revisions; destructive forward-only revisions explicitly document recovery.
- Expand/backfill/enforce tested with old/new application compatibility where rollout spans versions.
- Constraints tested through direct inserts in addition to service tests.
- RLS tested from the actual application role on separate pooled connections, including unset/spoofed tenant setting.
- Representative-volume `EXPLAIN (ANALYZE, BUFFERS)` for new critical list/graph/vector paths and regression budget.
- Backup/PITR restoration exercise before production and periodically thereafter.

## 6. Deterministic SEO and graph tests

Each SEO evaluator has table-driven boundary cases, Unicode/locale cases, malformed normalized document, not-applicable behavior, stable evidence locations, and golden finding schema. Property tests cover heading tree invariants, URL/length normalization, and score bounds.

Content/link graph property tests generate random valid/invalid hierarchies and assert no cross-tenant edges, no hierarchy cycles, source != target, canonical target uniqueness, valid score range, and stable traversal/ranking for stable inputs. Cannibalization fixtures cover same keyword, semantic overlap, distinct intent, supporting page, redirect/merge, and reviewed exception.

## 7. AI tool and context tests

- Registry startup: unique name/version, strict Pydantic input/output, permission/effect/audit metadata, declared executor.
- Selection: canonical requests map to expected tool or no tool; ambiguous/high-impact requests pause for review.
- Authorization: every role; model-supplied foreign IDs; permission revoked between plan and execute; proposal tools cannot mutate canonical state.
- Approval: exact digest/version/destination, expiry, single use, replay, changed payload, actor loses role, idempotent unknown external result.
- Context: allowed kinds only, structured dependencies outrank semantic results, token reserve/truncation, source attribution/hash, membership/source invalidation, no cross-tenant chunks/caches.
- Injection: malicious websites/docs/comments ask to reveal prompts, call publish, use external URL, alter tenant, or ignore policy; expected result is data treatment/denial.
- Resilience: invalid structured output with bounded repair, repeated tool errors stop, timeout/cancel, provider rate limit, stream disconnect, cost cap.

## 8. AI evaluation datasets and gates

Create version-controlled, privacy-safe datasets by capability with input references, expected allowed tools, prohibited actions, source facts, reviewer label/rubric, locale/domain, adversarial tags, and dataset version. Where no single text is canonical, score factual support/citations, instruction following, harmful fabrication, rule rubric, proposal applicability, and human pairwise preference.

Release comparison reports model/prompt/retrieval/tool version, sample size, pass rate/confidence interval, cost, latency, regressions by slice, and reviewer disagreement. Initial thresholds are set during baseline creation, then may only tighten or be explicitly risk-accepted. Hard gates always include zero cross-tenant disclosure, zero unapproved high-impact execution, schema-valid tool calls, and deterministic rule consistency. Stochastic quality uses statistically meaningful regression thresholds, not one cherry-picked example.

## 9. Frontend and E2E tests

- Contract-generated types compile; fixtures match OpenAPI examples.
- Forms display field errors and request ID; auth/permission status is handled without leaking data.
- React Flow tests cover projection, filters, accessible tree/table, keyboard commands, layout vs structural change, large graph, and conflict rollback.
- TipTap tests cover schema validation, autosave debounce/idempotency, offline/network error, stale base, suggestion diff/accept/reject, comment anchor, sanitized render, and version history.
- Accessibility automation plus keyboard/screen-reader manual checks on map/editor/approval workflows; target WCAG 2.2 AA.
- E2E uses sandbox connectors and deterministic AI test adapter; it asserts database/audit outcome, not merely visible toast.

## 10. CI and release gates

Pull request checks run secret scan, formatting/lint, MyPy strict, unit tests/coverage report, PostgreSQL integration and RLS tests for affected domains, API/contract/OpenAPI diff, TypeScript typecheck/lint/component tests, migration upgrade/drift, dependency/license/container scan when images exist, and documentation link/Phase 0 validator where relevant.

Coverage is diagnostic; changed business/security code requires meaningful branch coverage, not a repository-wide number alone. No skips/xfailed security test without owner and expiry. Flaky tests are quarantined only with issue, owner, and deadline; a quarantined tenant/approval test blocks release.

Staging/release gates add E2E, live-provider evaluation within approved budget, migration rehearsal, performance smoke, DAST, publication sandbox, backup/rollback verification, and manual review of breaking contracts/migrations/security. Production deploy uses health/error/latency/queue/cost canaries and an explicit rollback/forward decision.

## 11. Definition of tested

A feature is tested when happy and failure paths, permissions/tenant isolation, concurrency/idempotency, persistence constraints, contract/examples, audit/metrics, worker retry, UI error/accessibility, and relevant AI/security regressions are covered; commands and results are reproducible in CI; and failures are reported rather than masked.

