# ADR-001: Use FastAPI for the backend HTTP API

- Status: Accepted
- Date: 2026-08-31

## Context

The product needs a typed Python API for tenant-scoped CRUD, versioned workflows, async AI/integration calls, job submission, streaming, and a frontend contract. Two developers need fast iteration and reliable TypeScript contract generation. Business logic must stay outside routes.

## Decision

Use FastAPI on Python 3.12+ with Pydantic v2 request/response schemas. Public routes live under `/api/v1`; dependency injection supplies authentication, authorization, sessions, and services. Use async route/service boundaries and generate OpenAPI as the frontend contract.

## Reason

FastAPI aligns directly with Pydantic, produces usable OpenAPI, supports async HTTP/streaming, has a mature ecosystem, and keeps transport code small. It reduces hand-maintained schema drift between the Python backend and Next.js.

## Alternatives

- Django + DRF: strong batteries/admin/ORM but duplicates the chosen SQLAlchemy architecture and adds framework conventions not needed initially.
- Flask: simple but would require assembling validation, OpenAPI, dependency, and async patterns ourselves.
- Litestar: technically capable but has a smaller team/ecosystem familiarity surface for this project.
- GraphQL: flexible client queries, but authorization/caching/version/idempotency complexity is not justified by current resource workflows.

## Tradeoffs

FastAPI does not enforce layered architecture; careless routes can accumulate business logic. OpenAPI generation can become unstable without schema discipline. Async debugging and dependency lifecycles require tests. We accept these costs and enforce thin routers, service/repository ownership, deterministic operation IDs, and contract snapshots.

## Consequences

All external schemas are Pydantic and ORM objects are mapped explicitly. API errors, envelopes, pagination, preconditions, and idempotency are centralized. CI generates/diffs OpenAPI and TypeScript types. Framework replacement would affect only the transport layer if domain services remain clean. API, authorization, and streaming behavior require HTTPX/ASGI tests.

