# ADR-003: Use SQLAlchemy 2.x with async sessions

- Status: Accepted
- Date: 2026-08-31

## Context

The FastAPI backend needs typed relational mapping, explicit queries/transactions, PostgreSQL feature access, Alembic integration, and repository isolation. HTTP and provider operations are async; mixing sync/async database strategies would raise complexity.

## Decision

Use SQLAlchemy 2.x typed declarative models and `AsyncSession` with asyncpg for application access. Repositories receive a session and encapsulate tenant-scoped queries. Application services own transaction boundaries; repositories may flush but never commit. Alembic uses a controlled sync psycopg URL where appropriate.

## Reason

SQLAlchemy is mature, expressive enough for JSONB/vector/CTEs/locking, independent of FastAPI, and pairs with Alembic. Its unit-of-work and explicit query model fit a modular monolith while allowing optimized SQL where needed.

## Alternatives

- Django ORM: would couple the project to Django and conflicts with FastAPI choice.
- SQLModel: ergonomic but adds abstraction and can blur separation between persistence and public Pydantic schemas.
- Tortoise/other async ORM: smaller ecosystem and less control for advanced PostgreSQL/query/migration requirements.
- Raw SQL only: maximum control but more mapping/boilerplate and easier inconsistency across domains.

## Tradeoffs

SQLAlchemy has a learning curve, implicit loading can cause N+1/async errors, and ORM models can leak if discipline fails. Async sessions complicate tests and migrations. We use explicit loading, `lazy="raise"` where useful, typed repository methods, explicit mappers, query-plan tests, and separate Pydantic contracts.

## Consequences

No database access in routers, UI, provider adapters, or AI tools. Cross-domain data access goes through public services/read models. Sessions are request/job scoped; external network calls do not hold transactions. Integration tests run against PostgreSQL and verify rollback, concurrency, constraints, tenant predicates, and performance. Replacing SQLAlchemy remains possible behind repositories but migrations/models are a substantial investment.

