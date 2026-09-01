# ADR-007: Build a domain-oriented modular monolith

- Status: Accepted
- Date: 2026-08-31

## Context

The product has many named capabilities but begins with two developers, evolving requirements, and strong transactions across strategy, keywords, content, rules, approvals, and audit. Twenty services would multiply deployment, contracts, data consistency, security, observability, and on-call work before load/team boundaries are known.

## Decision

Build one deployable FastAPI codebase/database as a modular monolith, with separate API and Celery worker processes from the same version. Organize by domain ownership with service/repository/API layers and explicit public service/event boundaries. Use one PostgreSQL source of truth and a transactional outbox for asynchronous projections.

## Reason

This provides fast in-repository refactoring, simple deployment, and atomic invariants while teaching us real workload/team boundaries. Domain organization prevents a single giant application module and keeps future extraction possible.

## Alternatives

- Microservices from start: independent scaling/release but high operational/distributed transaction/contract cost and unclear boundaries.
- Layer-only monolith (`models/services/routes` globally): simple initially but domain ownership and change locality degrade.
- Serverless functions per route: scaling convenience but poor fit for transactions, long workflows, workers, and local contracts.

## Tradeoffs

Process/database failure domain is broad; modules can couple through imports/tables; deployments scale together. We enforce import/ownership rules, cross-domain public services/events, query/queue metrics, and bounded workers. Shared database access is not permission to query another domain's private tables.

## Consequences

All domain modules live under `app/domains`; routers/tasks are adapters. Services own transactions. Likely extraction candidates are crawling/ingestion or AI job execution after evidence. Extraction requires at least two sustained signals (independent scale, availability/security, release/team, contention/compliance), an API/event/data consistency plan, SLO/cost, migration, and superseding ADR. Architecture tests and code review monitor boundary violations.

