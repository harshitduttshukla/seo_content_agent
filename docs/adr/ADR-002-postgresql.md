# ADR-002: Use PostgreSQL as the source of truth

- Status: Accepted
- Date: 2026-08-31

## Context

The product combines multi-tenant transactional entities, immutable versions, flexible structured documents/rules, hierarchical and directed relationships, audit/jobs, analytics facts, full-text search, and embeddings. Consistency between strategy, target pages, links, approvals, and publications is more important than independent datastore specialization at MVP scale.

## Decision

Use PostgreSQL for canonical product state with normalized relational entities, foreign keys/constraints, JSONB for validated variable documents, recursive CTEs for bounded graph traversal, full-text search, and pgvector. Redis is cache/broker only; object storage holds private binaries with PostgreSQL metadata.

## Reason

PostgreSQL supplies transactions, mature indexing/query tools, JSONB, row-level security, recursive queries, partitioning, full-text, and extension support in one operational/tenant boundary. This avoids dual-write consistency and operational overhead for a two-developer team.

## Alternatives

- MySQL: capable relational store, but PostgreSQL has stronger fit for JSONB, RLS, recursive/extension/vector ecosystem.
- Document database: flexible JSON but weaker relationship/transaction/constraint model for targeting, versions, approvals, and tenant integrity.
- Separate graph/vector/search databases: specialized scale, but introduce replication, consistency, security, backup, and operational cost before measured need.

## Tradeoffs

One database can become a contention/failure domain. JSONB and recursive/vector queries can be misused. RLS adds operational/testing complexity. We mitigate with normalized ownership, measured indexes/query plans, queues/read projections, connection limits, backups/PITR, and strict JSON policy.

## Consequences

Every durable entity has explicit tenant ownership and constraints; application queries use scoped repositories and production adds RLS defense in depth. Schema changes use Alembic and expand-contract rollout. Vector/graph extraction requires evidence and a new ADR. Tests use real PostgreSQL, including RLS, JSONB, locks, recursive queries, and pgvector.

