# V3 Crawling and Content Agent Harness Migration

## Scope and decision

This migration preserves the existing crawling and Harness domain implementations and exposes them in the V3 product shell. PostgreSQL tables, domain services, provider interfaces, production generators, claim contracts, and V1 compatibility routes are retained. No schema or data migration is required.

The V3 endpoints are compatibility facades over the same services, not a second crawler or agent. Authorization remains in `WebsiteService`, `ProjectService`, and scoped repositories. The V1 routes remain temporarily because external consumers have not been inventoried; removing them without that evidence would violate the migration's no-regression requirement.

## Website crawling flow

`V3 shell -> Website Intelligence -> /api/v3/websites/{website_id} -> CrawlService -> CrawlRepository/ContentService -> PostgreSQL`

The website lookup authorizes the actor and establishes organization/project scope before a crawl is created. Crawl jobs store all three ownership keys. The crawler retains normalized URL discovery, robots rules, sitemap indexes, bounded fetching, redirect SSRF checks, canonical and metadata extraction, headings, images, links, status/failure counters, cancellation, limits, and persisted page versions. Results feed stored website evidence used by content bundles and internal-link intelligence.

Individual page failures are recorded and do not abort the whole crawl. Unhandled job errors produce a failed terminal state. Crawl concurrency is limited to one active run per website. V3 currently reuses the existing in-process background runner; migration to the documented durable Celery/outbox worker remains separate operational hardening work.

## Content Agent Harness flow

`V3 shell -> Content Agent Harness -> /api/v3/content-harness -> ContentHarnessService -> production bundle/generator/QA contracts -> AIProvider -> content_harness_runs`

The V3 screen selects a real Content Card and runs one of the outline, draft, QA, or repair validation modes. These modes use `ContentAgentContextBuilder`, the production outline/draft generators, production deterministic QA, repair logic, structured validators, and provider abstraction. Runs do not mutate cards. Context snapshots, bundle hashes, prompt versions, provider/model metadata, outputs, errors, evaluation findings, scores, and timestamps are persisted for history and inspection.

Approved claim context and the `[CLM:<id>]` and `[NEEDS-CLAIM: ...]` rules remain owned by the production draft contracts and their shared Harness evaluators. The generic legacy Harness remains available only through its compatibility page/API while consumers are assessed.

## Migration map

| Area | Classification | Decision |
|---|---|---|
| `domains/crawling`, crawl/content tables and extractors | REUSE | One implementation serves V1 and V3. |
| V1 crawling and page routers | KEEP / DELETE LATER | Compatibility surface; do not remove until consumers are verified. |
| V3 crawling/page router mounts | MOVE/ADAPT | V3 facade over existing services. |
| legacy Website workspace UI | REUSE | Parameterized API prefix and rendered inside V3 shell. |
| `/projects/.../website` | DELETE LATER | Compatibility route retained pending external-link audit. |
| `ContentAgentContextBuilder` and production generators/QA | KEEP | Canonical production infrastructure used by V3 Harness. |
| V3 Harness service modes/evaluators | KEEP | Already share production contracts. |
| generic `run_harness`, prompts, golden-case surface | UNKNOWN | Retained for manual review; it is independent of production contracts. |
| `content_harness_runs` | REUSE | Existing scoped history supports both compatibility and V3 runs. |
| legacy Harness page | DELETE LATER | Retained pending consumer and saved-link audit. |
| V3 Harness page | MOVE/ADAPT | Production-pipeline validation UI in V3 shell. |

## Boundaries and non-goals

No authentication, RBAC, organization/project/website models, Production state transitions, G1/G2 gates, claim model, GSC, or Iteration Lab behavior is changed. No legacy table or code is deleted in this step because repository-only evidence cannot prove that deployed clients no longer use compatibility URLs.
