# Final Phase 0 Report

Status: Complete blueprint; no product features implemented  
Date: 2026-08-31

## 1. Executive Summary

Phase 0 establishes an implementation-ready foundation for a multi-tenant SEO Content Intelligence and AI Content Operating System. The solution is a Next.js frontend over a Python/FastAPI domain-oriented modular monolith, with PostgreSQL/JSONB/pgvector as source of truth, Redis/Celery for asynchronous work, S3-compatible object storage, and provider-neutral governed AI.

The central product rule is preserved end to end: business strategy, keywords, content architecture, SEO/brand/linking policy, editor content, AI context, approvals, and learning are structured/versioned data with human projections—not documents or prompts alone. AI may read or propose through typed, authorized, audited tools; publishing and other high-impact effects require exact human approval.

The repository contains configuration and typed boundary contracts only. There are intentionally no fake routes, domain services, database migrations, clustering, editor, graph UI, orchestrator, ingestion, publishing, or analytics implementations.

## 2. Product Architecture

The product flow is organization/project/site -> structured strategy -> keyword intent/clusters -> pillar/topic/page architecture -> content map/rules -> frozen brief -> structured editor/AI proposals -> human approval -> publishing -> performance -> approved learning. [PRD.md](PRD.md) specifies users, outcomes, all 28 capabilities with inputs/outputs/owners/dependencies/APIs/extensions, role matrix, lifecycle, MVP/V1, and product measures.

Important invariants include many keywords per intent-coherent cluster, one canonical target page per cluster/site/locale, explicit cannibalization conflicts, immutable versions, exact dependency manifests, and separate planned/recommended/approved/observed/published states.

## 3. Python Backend Architecture

The backend is a Python 3.12+ FastAPI modular monolith with Pydantic v2, SQLAlchemy 2.x async sessions, and Alembic. Thin routers validate/authenticate/authorize then call domain services; services own transactions/invariants; repositories own tenant-scoped data access; adapters own provider protocols. Celery tasks are adapters to the same services and remain idempotent through durable job/outbox records.

The scaffold includes validated settings, SQLAlchemy naming/session conventions, response/pagination schemas, AI provider/context contracts, governed tool contracts and all tool input/output models, object-storage interface, principal/roles, pyproject quality policy, and empty domain boundaries. Details are in [ARCHITECTURE.md](ARCHITECTURE.md).

## 4. Frontend Architecture

Next.js/React/TypeScript/Tailwind is organized by feature. The client consumes generated OpenAPI types through a reviewed HTTP layer; product data is server state, not duplicated as canonical client/global state. React Flow renders a bounded graph projection with explicit revisioned commands and separate layouts. TipTap edits pinned, versioned structured JSON; suggestions are attributed diffs. Both map and editor require keyboard/accessibility alternatives, conflict rollback, sanitized output, and tenant-aware cache keys.

The web package is intentionally dependency-light until the first feature chooses query/test libraries and installs React Flow/TipTap/Tailwind with actual use.

## 5. Database Architecture

PostgreSQL stores tenant/project entities, normalized relationships, immutable versions, jobs/outbox/audit, AI/tool/approval provenance, performance metrics, and pgvector embeddings. JSONB is reserved for validated versioned documents, rule parameters, snapshots, and manifests. UUIDv4, UTC `timestamptz`, named constraints, optimistic revisions, selective archive/retention, composite tenant foreign keys, scoped repositories, and production RLS are defined.

[DATABASE.md](DATABASE.md) catalogs every requested entity plus memberships, assignments/conflicts, suggestions/comments, approvals, publication destinations/runs, jobs/outbox/audit; for each it states purpose, fields, model/lifecycle, relationships, indexes/constraints, JSONB, and ownership. It includes an ERD, strategy Pydantic/version strategy, index review, and expand-contract migration policy.

## 6. AI Architecture

Application code depends on `AIProvider.generate/stream/embed`; vendor SDKs remain in adapters. The context manager classifies allowed context kinds, authorizes each source, performs tenant-filtered structured/hybrid retrieval, ranks/deduplicates, packs a configured token budget, and records source/version/hash manifests. The bounded orchestrator validates every tool input/output, re-authorizes execution, stops on limits/errors/approval, and records run/model/prompt/context/tool/usage/cost provenance.

[AI-ORCHESTRATOR.md](AI-ORCHESTRATOR.md) defines all 24 future tools with Python models, effects, permissions, side effects, errors, and audits; approval protocol; knowledge pipeline; learning pipeline; injection defenses; and evaluation gates. The actual Pydantic tool models live in `apps/api/app/tools/models.py`; there are no executors.

## 7. Content Graph Architecture

Canonical nodes are pillar, topic, keyword cluster, and page. Canonical relations live in typed relational tables and project as parent/child/supports/targets/related/internal-link edges. Hierarchy is acyclic; page targeting enforces cannibalization rules; graph revision protects commands; layout is separate presentation state. Bounded filtered reads, lazy expansion, recursive CTEs, versioned projections, accessible tree/table, and extraction criteria are specified in [CONTENT-MAP.md](CONTENT-MAP.md).

## 8. Internal Linking Architecture

Linking separates guide rules, eligible targets, scored opportunities, human-approved edges, editor patches, published state, and crawl-observed evidence. The initial transparent ranking weights semantic relevance, graph proximity, intent complement, priority, orphan benefit, contextual span, and freshness with bounded risk penalties. AI may suggest wording but cannot bypass eligibility or apply/publish. Edge integrity, anchor policy, crawl reconciliation, evaluation metrics, and API ownership are in [INTERNAL-LINKING.md](INTERNAL-LINKING.md).

## 9. Security Architecture

OIDC identity maps to internal memberships/RBAC; organization roles are narrowed by project assignment. Every protected path enforces action, tenant, project, resource, status, and approval as needed. Composite FKs and PostgreSQL RLS provide database defense in depth. Knowledge/vector/context caches are tenant-scoped. Upload/parser quarantine, crawler SSRF controls, private S3 objects, secret-manager references, CSP/CORS/CSRF/rate limits, log redaction, append-only audit, detection, recovery, and production gate are defined in [SECURITY.md](SECURITY.md).

AI never receives database/shell/generic HTTP/secret access. Proposal-only tools cannot mutate canonical state. High-impact execution requires a current permission plus single-use exact approval digest and idempotency.

## 10. Repository Structure

```text
apps/
  api/                 FastAPI configuration, typed boundaries, tests, Alembic home
    app/domains/       future domain-owned implementations (intentionally empty)
    app/ai|tools/      provider/context/tool contracts
    app/security/      principal/policy boundary
  web/                 Next.js/React/TypeScript boundary
packages/
  ui/                  reusable presentation boundary
  shared-types/        generated OpenAPI TypeScript boundary
docs/
  adr/                 ten accepted decision records
scripts/               dependency-free structural validation
AGENTS.md               binding repository development rules
.env.example            secret-free environment contract
```

Root and package READMEs explain current scope. `apps/api/pyproject.toml` classifies core, Phase 1 optional, development, and deliberately future adapter dependencies. Alembic `versions/` is empty because creating a fictional schema migration would violate Phase 0.

## 11. API Strategy

`/api/v1` uses strict Pydantic request/response schemas, success/error envelope, centralized exception mapping, OIDC/RBAC dependencies, cursor pagination, allowlisted filters/sorts, ETags/base versions, idempotency keys, 202 durable jobs, rate/concurrency/usage limits, and stable machine error codes. [API.md](API.md) catalogs endpoints for every product group with purpose and permission. CI will snapshot OpenAPI, detect breaking changes, and regenerate TypeScript.

## 12. Testing Strategy

Testing combines Pytest unit, PostgreSQL/Redis/storage integration, HTTPX API, OpenAPI/tool/event contract, Celery/outbox, frontend component/accessibility, Playwright E2E, security, performance/resilience, and versioned AI evaluation. Cross-tenant negative tests and approval/proposal behavior are mandatory for every relevant resource/tool. PostgreSQL—not SQLite—validates JSONB, pgvector, RLS, locks, constraints, and recursive queries. Full matrices and CI/release gates are in [TESTING.md](TESTING.md).

## 13. Codex Workflow

[AGENTS.md](../AGENTS.md) is the binding repository instruction. [CODEX-WORKFLOW.md](CODEX-WORKFLOW.md) defines understand -> plan -> implement -> test -> review/refactor -> handoff, a standard task brief, migration/API/AI rules, parallel coordination, and truthful blocker reporting. Codex must inspect current architecture/changes, stay in active phase, preserve unrelated work, run/report checks, never invent APIs or expose secrets, and update affected documentation/ADRs.

## 14. Developer Split

Developer 1 owns Python/backend, database/migrations/RLS, jobs/outbox, AI provider/context/tools/evaluations, algorithms, storage and external adapters. Developer 2 owns Next.js/React, generated API client, UI/accessibility, React Flow, TipTap, frontend tests/E2E. Shared review covers Pydantic/OpenAPI schemas, error/permission/version/idempotency contracts, graph/editor commands, fixtures, and integration E2E. Backend contracts/examples land early so frontend can work against mocks in parallel.

## 15. MVP Roadmap

Six vertical milestones in [ROADMAP.md](ROADMAP.md): secure project foundation; structured strategy/rules; keywords/intent/clustering; content architecture/map; briefs/editor/versions/validation; internal linking/basic AI assistant. Each includes backend/frontend/joint work and measurable exit. MVP ends with a tenant-safe, traceable path from strategy and keywords to an approved structured document with explainable AI/link/SEO proposals; production publishing may remain manual export.

## 16. V1 Roadmap

V1 adds secure knowledge and brand, bounded orchestrated workflows/collaboration, approval-bound CMS publishing, performance imports/intelligence, approved learning, privacy/retention/quotas, disaster recovery, and production hardening. It explicitly does not add autonomous publication or rule activation.

## 17. Risks

| Risk | Impact | Mitigation / trigger |
|---|---|---|
| Scope across 28 capabilities | shallow/inconsistent MVP | vertical milestones, active-phase gate, explicit deferred list |
| Two-developer bottleneck | contract/integration delays | OpenAPI-first parallel split, mocks, one integrated slice per milestone |
| Tenant leak | severe confidentiality incident | direct tenant keys, composite FKs, scoped repos, RLS, mandatory negative tests |
| AI hallucination/injection | wrong content/action/data leak | least context, provenance, typed allowlisted tools, proposals, exact approval, adversarial eval |
| AI/provider cost or churn | unstable economics/quality | provider abstraction, budgets/quotas/cost metrics, task policy, regression eval |
| Keyword/link algorithm quality | low trust/SEO harm | explainable components, human review, labeled datasets, precision/acceptance gates |
| Editor/schema complexity | lost/conflicting content | pinned schema, immutable versions, optimistic concurrency, upcasters/golden fixtures |
| Postgres mixed workload | OLTP/search contention | profiling/indexing, jobs/read models/replicas; extraction only on evidence |
| Celery at-least-once/external uncertainty | duplicate jobs/publication | durable run state, operation keys, idempotent services, reconciliation before retry |
| External source/upload threats | SSRF/parser compromise | scoped crawler, quarantine/scan/sandbox/resource limits/egress controls |
| Documentation drift | unsafe inconsistent implementation | ADR ownership, contract/structure validation, DoD requires docs |

Each milestone must turn relevant risks into owned tests/metrics; accepting residual high-severity risk requires explicit review.

## 18. Assumptions

- Initial scale fits one regional PostgreSQL primary plus normal replicas/backups and pgvector; actual corpus/QPS must be measured before vector/index choices.
- Organizations are the top isolation/billing boundary; a user may belong to several; projects do not share canonical private data by default.
- OIDC is available; custom password authentication is not required for MVP.
- English may be the first evaluation corpus, but locale/country are modeled from the start and rule/model quality is not assumed portable.
- One project may contain multiple sites/locales; canonical cluster target uniqueness is scoped appropriately.
- Users review AI content/link/strategy proposals and high-impact actions; fully autonomous mode is not an MVP requirement.
- CMS, keyword-metric, Search Console, and analytics vendors are not yet selected; adapters and secrets remain vendor-neutral.
- Celery/Redis and S3-compatible storage are operationally acceptable initially.
- Regulatory/data residency/retention requirements are not yet specified; production ingestion waits for policy decisions.
- The initial team can operate a modular monolith; service extraction follows measured need.

## 19. Open Questions

The architecture is not blocked, but these product/deployment choices must be resolved at the indicated milestone; defaults are recommendations, not hidden assumptions.

| Question | Recommended default | Decision deadline / consequence |
|---|---|---|
| Which OIDC provider and browser session pattern? | managed OIDC; server-managed secure session/BFF where practical | Before M1 auth implementation; affects token flow and local dev adapter |
| Is role scope organization-wide by default or explicit project assignment? | org role plus optional project allowlist; sensitive orgs default explicit | Before M1 membership schema/UI |
| Initial countries/locales/verticals and intent taxonomy? | choose one pilot locale/vertical but model locale/country | Before M2 rule defaults and M3 evaluation dataset |
| Keyword metric/import provider and file formats? | CSV import first with provenance; one verified provider adapter later | Before M3 import mappings/dependencies |
| MVP cluster quality labels and acceptance threshold? | SEO-manager labeled pilot dataset; report precision/cohesion/stability and override rate | Before selecting M3 algorithm |
| Required content types and TipTap nodes/marks? | article/landing page; minimal headings/paragraph/list/link/image/table/CTA schema | Before M5 schema freeze; affects migrations/editor plugins |
| Score policies and publish blockers? | show components; only deterministic project-approved blockers gate readiness | Before M2/M5 UX and evaluator config |
| First knowledge source limits/data classification? | private PDF/DOCX/web with conservative size/retention; no regulated data | Before V1.1 security/operations |
| First AI provider/models, data retention, budget, region? | evaluation-based choice behind adapter, no provider training, hard per-org budget | Before M6 staging integration |
| First CMS and what does “publish” mean (draft vs live)? | one sandboxable CMS; default AI tool action saves CMS draft, live publish separately approved | Before V1.3 adapter/approval UI |
| Search Console/analytics sources and metric definitions? | Search Console first; preserve raw dimension provenance | Before V1.4 schema/connector |
| Required privacy, residency, retention, audit, RTO/RPO/SLO? | define with pilot customer before production; conservative private retention | Before any production data, hard production gate |
| Collaboration requirement: optimistic versions or real-time CRDT? | optimistic autosave/version conflicts for MVP | Before M5; real-time needs separate provider/data/permission ADR |
| Commercial packaging/quotas? | usage recorded now, billing deferred | Before broad production rollout; affects org limits but not domain design |

## 20. Phase 1 Readiness Checklist

- [x] PRD and 28 module specifications exist.
- [x] Product flow Mermaid diagram exists.
- [x] System, Python backend, frontend, modular-monolith, job/cache/observability architecture exists.
- [x] Database entity catalog, conventions, tenancy model, ERD, JSONB/index/migration policy exist.
- [x] API endpoint catalog, auth/RBAC, schemas/envelopes/errors, pagination/filter/sort, idempotency/versioning/rate limits exist.
- [x] AI provider, context, tool registry, all 24 tool models/permissions/effects/errors/audits, approval, knowledge and learning architecture exist.
- [x] TipTap structured editor/autosave/version/diff/suggestion/comment architecture exists.
- [x] React Flow content graph nodes/edges/commands/layout/invariants architecture exists.
- [x] SEO deterministic/AI rule architecture and transparent scoring exists.
- [x] Internal-link graph, ranking formula, anchor/reconciliation/evaluation architecture exists.
- [x] Security threat/tenant/tool/upload/crawler/secret/audit/production gate exists.
- [x] Testing/AI evaluation/CI/release strategy exists.
- [x] Repository, configuration, typed boundary scaffold, `.env.example`, pyproject dependency phases, and Alembic home exist.
- [x] Root `AGENTS.md`, Codex workflow, Git/PR/DoD/forbidden behavior exist.
- [x] Ten accepted ADRs with context/decision/reason/alternatives/tradeoffs/consequences exist.
- [x] MVP/V1 milestones, dependencies, developer split, risks, assumptions, open questions, and extraction triggers exist.
- [x] No Phase 1 product features or fake implementations were added.
- [ ] Product/engineering/security owners acknowledge the recommended defaults and assign owners/dates to open questions.
- [ ] Team explicitly starts M1 and selects its first vertical-slice task.

Phase 1 can begin with M1 once the last two governance actions are complete. No major architectural ambiguity blocks M1 implementation.

