# Phase 1 — SaaS Platform Foundation Report

This document specifies the completed **Phase 1 SaaS Platform Foundation** for the AI-powered SEO/AEO Content Intelligence and Content Operating System.

---

## 1. Architecture Implemented

The platform is designed and delivered as a **Modular Monolith** adhering strictly to domain-driven design principles, asynchronous I/O, typed contracts, and strict multi-tenant boundaries.

```
                    NEXT.JS (App Router)
                            │
                            │ (HTTPS + Bearer Token / Session Cookie)
                            ▼
                     FASTAPI API (/api/v1)
                            │
               ┌────────────┴────────────┐
               ▼                         ▼
      REQUEST MIDDLEWARE          SECURITY & RBAC
      (X-Request-ID, CORS)     (OIDC + Authorization)
               │                         │
               └────────────┬────────────┘
                            │
                    APPLICATION LAYER
                            │
        ┌───────────────────┼───────────────────┐
        ▼                   ▼                   ▼
  ORGANIZATIONS         PROJECTS             WEBSITES
        │                   │                   │
        └───────────────────┼───────────────────┘
                            │
                     DOMAIN SERVICES
             (Transaction Boundaries, Audit)
                            │
                            ▼
                    DOMAIN REPOSITORIES
                            │
                            ▼
                  POSTGRESQL 17 + RLS
```

---

## 2. Backend Modules Created

All backend domain modules live under `apps/api/app/`:

| Module | Purpose | Public Interface / Artifacts |
|---|---|---|
| `app/config/settings.py` | Pydantic Settings configuration with runtime environment safety checks. | `Settings`, `get_settings()` |
| `app/core/` | Cross-cutting primitives: errors, cursor encoding/decoding, model mixins (`TimestampMixin`, `RevisionMixin`, `UUIDPrimaryKeyMixin`), validators. | `AppError`, `ConflictError`, `ResourceNotFound`, `PermissionDenied` |
| `app/db/` | Base SQLAlchemy metadata with naming conventions, async engine, session factory, transaction-scoped actor context. | `Base`, `build_engine`, `set_actor_context` |
| `app/security/` | OIDC JWT verification, authenticated identity claims, RBAC permissions, and resource-scoped authorization policy. | `OIDCTokenVerifier`, `AuthorizationService`, `RoleCode`, `PermissionCode` |
| `app/domains/auth/` | Roles, permissions, role-permissions matrix, organization memberships, and project assignments. | `Role`, `Permission`, `OrganizationMember`, `ProjectMember` |
| `app/domains/organizations/` | Top-level tenant boundary entity, validation schemas, repository, and service. | `OrganizationService`, `Organization` |
| `app/domains/users/` | User identity entity, profile provisioning, and current-user query. | `UserService`, `User` |
| `app/domains/projects/` | Project aggregate root entity, lifecycle, default locale settings, and service. | `ProjectService`, `Project` |
| `app/domains/websites/` | Project-owned website properties, URL normalization, verification status, and service. | `WebsiteService`, `Website` |
| `app/domains/audit/` | Append-only audit logger, atomic idempotency claim repository, transactional outbox. | `AuditWriter`, `IdempotencyRepository`, `OutboxWriter` |
| `app/observability/` | Structured JSON logging with request context. | `configure_logging()` |
| `app/schemas/common.py` | Standard API response envelope `ApiResponse[T]`, `MetaEnvelope`, `ErrorItem`. | `ApiResponse`, `success`, `error_response` |

---

## 3. Database Tables Created

The database schema is managed through Alembic migration `20260901_0001_phase1_foundation.py` in PostgreSQL 17:

1. **`roles`**: Seeded with `admin`, `seo_manager`, `content_manager`, `writer`, `editor`, `viewer`.
2. **`permissions`**: Explicit capability definitions across organizations, projects, websites, strategy, keywords, content, SEO, AI, and publishing.
3. **`role_permissions`**: Composite PK `(role_id, permission_id)` mapping default system capabilities to roles.
4. **`organizations`**: Tenant root entity with `id (UUID PK)`, `name`, `slug`, `status` (`active`, `suspended`, `archived`), `settings (JSONB)`, `revision`, `created_at`, `updated_at`, `archived_at`.
5. **`users`**: Global identity entity with `identity_issuer`, `identity_subject`, `email`, `normalized_email`, `display_name`, `status`, `last_seen_at`.
6. **`organization_members`**: Organization membership joining `(organization_id, user_id, role_id, status, joined_at)`.
7. **`projects`**: Project aggregate entity with `organization_id (FK)`, `name`, `slug`, `description`, `status` (`active`, `archived`), `default_locale`, `default_country`, `revision`.
8. **`project_members`**: Composite tenant constraint `(organization_id, project_id, user_id, role_id)`.
9. **`websites`**: Project website property with `(organization_id, project_id)`, `name`, `base_url`, `normalized_host`, `status`, `locale`, `country`, `verification_status`.
10. **`audit_logs`**: Append-only log with `(actor_user_id, organization_id, project_id, action, resource_type, resource_id, outcome, request_id, metadata, occurred_at)`.
11. **`idempotency_records`**: Unique constraint `(actor_user_id, route, idempotency_key)` preventing duplicate mutations and race conditions.
12. **`outbox_events`**: Transactional outbox table for atomic event delivery.

---

## 4. API Endpoints Created

All API endpoints live under `/api/v1` and return the standard JSON envelope:

```json
{
  "data": { ... },
  "meta": { "request_id": "req_...", "next_cursor": null, "has_more": null },
  "errors": []
}
```

| Method | Path | Required Permission | Description |
|---|---|---|---|
| `GET` | `/health/live` | None | Process liveness check |
| `GET` | `/health/ready` | None | Database connectivity readiness check |
| `GET` | `/api/v1/users/me` | Authenticated | Current user identity and status |
| `POST` | `/api/v1/organizations` | Authenticated | Create a new organization (assigns caller as Admin) |
| `GET` | `/api/v1/organizations` | Authenticated | List organizations accessible to caller (cursor paginated) |
| `GET` | `/api/v1/organizations/{id}` | `organization.read` | Get organization details |
| `PUT` | `/api/v1/organizations/{id}` | `organization.update` | Update organization details & status (optimistic concurrency) |
| `GET` | `/api/v1/organizations/{id}/members` | `members.read` | List organization team members |
| `POST` | `/api/v1/organizations/{id}/members` | `members.manage` | Add a new organization member with role |
| `PATCH` | `/api/v1/organizations/{id}/members/{user_id}` | `members.manage` | Update member role or status |
| `POST` | `/api/v1/projects` | `project.create` | Create a new project within organization |
| `GET` | `/api/v1/projects` | `project.read` | List projects in organization (cursor paginated) |
| `GET` | `/api/v1/projects/{id}` | `project.read` | Get project details |
| `PUT` | `/api/v1/projects/{id}` | `project.update` | Update project metadata (optimistic concurrency) |
| `DELETE` | `/api/v1/projects/{id}` | `project.delete` | Archive project |
| `POST` | `/api/v1/projects/{project_id}/websites` | `website.create` | Connect a website to project |
| `GET` | `/api/v1/projects/{project_id}/websites` | `website.read` | List websites connected to project |
| `GET` | `/api/v1/websites/{id}` | `website.read` | Get website details |
| `PUT` | `/api/v1/websites/{id}` | `website.update` | Update website metadata |
| `DELETE` | `/api/v1/websites/{id}` | `website.delete` | Archive website |

---

## 5. Authentication & Authorization

### Authentication
- Uses standard OpenID Connect (OIDC) JWT token verification with JWKS public key caching and skew tolerance (`OIDCTokenVerifier`).
- Frontend sessions are maintained through HTTP-only, secure, `SameSite=Lax` cookies with automatic token refresh in Next.js App Router route handler (`/api/backend/[...path]`).
- Password storage is avoided in accordance with Phase 0 security decisions.

### Authorization (RBAC)
- Organization-level and Project-level access policies are strictly enforced server-side.
- Hierarchical role evaluation:
  - `admin`: Superuser across organization.
  - `seo_manager`: Strategy, keywords, SEO rules, websites.
  - `content_manager`: Content briefs, topics, cluster assignments.
  - `writer`: Brief writing, drafting.
  - `editor`: Publishing, reviewing, approving.
  - `viewer`: Read-only.

---

## 6. Multi-Tenancy Implementation

- **Tenant Isolation**: Every database query joins through organization/project membership or applies PostgreSQL Row-Level Security (RLS) policies scoped to the transaction's `app.user_id`.
- **Zero Client Trust**: API endpoints never trust an unverified `organization_id` in headers or bodies; resource ownership is verified against caller access.
- **Non-Disclosing 404s**: Unauthorized access attempts to cross-tenant resources return `404 Not Found` (or `403 Forbidden` if tenant exists but action is unauthorized) to prevent resource enumeration.

---

## 7. Frontend Application Screens

Built with Next.js 16 (App Router), React 19, TypeScript, and Tailwind CSS:

1. **Login Screen (`/login`)**: OIDC authentication initiation and development mock credentials.
2. **Organizations Workspace (`/organizations`)**: Organization grid and new tenant creation modal.
3. **Organization Settings & Team (`/organizations/[organizationId]/settings`)**: Tenant metadata form, member list, role assignment dropdowns, member invitations, and role explanations.
4. **Projects Workspace (`/projects?organization_id=...`)**: Project card grid with status badges and creation form.
5. **Project Dashboard (`/projects/[projectId]`)**: High-level overview displaying connected website, locale configuration, and disabled placeholder cards for future platform modules (Strategy, Keywords, Content, SEO, AI).
6. **Website Management (`/projects/[projectId]/website`)**: Website list, connection modal, locale/country settings, and removal/archive confirmation.
7. **Project Settings (`/projects/[projectId]/settings`)**: Project name, slug, description, locale settings, and danger zone archive flow.

---

## 8. Test Suites & Quality Metrics

### Backend Quality
- **Unit & Service Tests**: `apps/api/tests/unit/` testing concurrency revision conflicts, authorization rules, cursor encoding/decoding, and settings validation.
- **API Contract Tests**: `apps/api/tests/api/` testing health check envelopes, unauthorized route responses, validation errors, and `/users/me`.
- **Contract Schema Tests**: `apps/api/tests/contract/test_openapi.py` verifying that only Phase 1 foundation endpoints are exposed.
- **Tenant Isolation Integration Tests**: `apps/api/tests/integration/test_tenant_isolation_api.py` testing cross-tenant boundaries between User A (Organization A) and User B (Organization B).

### Frontend Quality
- **Unit & Component Tests**: `apps/web/src/__tests__/components.test.tsx` testing core UI components (`Button`, `Input`, `Dropdown`, `Card`, `Table`, `Toast`, `States`, `Header`).
- **Client API Tests**: `apps/web/src/__tests__/client-api.test.ts` testing API envelope parsing, error raising, and idempotency key generation.

### Quality Status
- `pytest`: **16 passed, 1 integration skipped (needs live DB)**
- `mypy`: **Success: 0 issues in 72 source files**
- `ruff check` & `ruff format`: **Clean / All formatted**
- `vitest`: **12 passed across 2 test suites**
- `next build`: **Compiled successfully with all static & dynamic routes**

---

## 9. Local Development & Commands

### Prerequisites
- Docker & Docker Compose
- Node.js 20+
- Python 3.12+

### Running the System
```bash
# 1. Start PostgreSQL and migrate schema
docker compose up -d postgres
docker compose up migrate

# 2. Run Backend API
cd apps/api
python3 -m uvicorn app.main:app --reload --port 8000

# 3. Run Frontend Web Application
cd apps/web
npm run dev
```

### Running Test Suites
```bash
# Backend tests and lints
cd apps/api
ruff check .
mypy app tests
pytest

# Frontend tests and typecheck
cd apps/web
npm run typecheck
npm test
npm run build
```

---

## 10. Environment Variables

Documented in `.env.example`:

```bash
# Application
APP_ENV=local
ALLOW_LOCAL_AUTH=true
APP_NAME=seo-content-agent
DEBUG=true
LOG_LEVEL=INFO

# Database
DATABASE_URL=postgresql+asyncpg://seo_content_app:seo_content_app@localhost:5432/seo_content
DATABASE_MIGRATION_URL=postgresql+psycopg://postgres:postgres@localhost:5432/seo_content

# OIDC Identity
AUTH_ISSUER=https://identity.example.com/
AUTH_AUDIENCE=seo-content-api
AUTH_JWKS_URL=https://identity.example.com/.well-known/jwks.json

# Web Frontend
API_INTERNAL_URL=http://localhost:8000
NEXT_PUBLIC_APP_URL=http://localhost:3000
```

The Docker Compose development stack enables local authentication by default. When both
`APP_ENV=local` and `ALLOW_LOCAL_AUTH=true`, `/login` displays the allowlisted Admin User and
SEO Manager shortcuts. Development tokens are rejected in staging and production, and production
configuration validation forbids enabling local authentication.

For a temporary direct-IP HTTP deployment, set `NEXT_PUBLIC_APP_URL` and `CORS_ORIGINS` to the
browser-visible origin (for example, `http://35.173.128.192:3000`). Keep `APP_ENV=local` and
`ALLOW_LOCAL_AUTH=true` only for this controlled test. The web session cookie is allowed over HTTP
in this mode; production still requires a secure cookie and must use HTTPS with local auth disabled.

---

## 11. Deferred Features & Phase 2 Transition

The following features were intentionally **deferred** to subsequent milestones:

1. **Phase 2 (M2 — Strategy & Rules)**: Strategy aggregate root, immutable strategy versions, and deterministic SEO engine.
2. **Phase 3 (M3 — Keywords & Clustering)**: Keyword taxonomy, Semrush/Ahrefs import mapping, and clustering algorithms.
3. **Phase 4 (M4 — Content Architecture & Content Map)**: Pillars, topics, pages, and React Flow visual graph.
4. **Phase 5 (M5 — Editor & Briefs)**: TipTap structured JSON editor, brief freezing, and versioned autosave.
5. **Phase 6 (M6 — Internal Linking & AI Orchestrator)**: Link relationship scoring, AI context assembly, and tool registry.
6. **Infrastructure**: Celery workers, Redis queue/caching, and pgvector extension (to be activated when vector embeddings are implemented in V1).
