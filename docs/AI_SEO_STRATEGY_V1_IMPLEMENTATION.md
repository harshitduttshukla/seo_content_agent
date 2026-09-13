# AI-Generated SEO Strategy V1 Implementation Report

## 1. Executive Summary & Objective

In accordance with the directive:
> "V1 should be AI built and then the user can improve from that point."

The SEO Strategy feature has been enhanced to empower users starting a new project to generate an initial Strategy Version 1 using AI. The generated strategy functions strictly as an uncommitted draft: the user reviews, inspects, and refines the AI-proposed strategy in the strategy editor before clicking **"Save as Version 1"**. Once saved, all subsequent edits increment to Version 2, Version 3, and beyond, preserving the version audit trail and historical integrity. Manual strategy entry without AI remains completely intact and supported.

Strict non-interference constraints were adhered to: no changes were made to authentication, organizations, projects, websites, website crawling, keyword import, keyword clustering, content map, content editor, publishing, or analytics.

---

## 2. Files Changed

### Backend
- `apps/api/app/domains/ai/service.py`:
  - Updated `MockAIProvider.generate()` to recognize SEO strategy generation requests and return high-fidelity, deterministic `StrategyDataSchema` JSON tailored to the project/website context.
- `apps/api/app/domains/strategy/service.py`:
  - Added `SEOStrategyService.generate_initial_strategy_draft(...)`:
    - Queries project context, up to 5 active websites, up to 30 recent crawled page titles/URLs, and up to 50 targeted keywords.
    - Uses XML anti-prompt-injection fencing (`<STRATEGY_CONTEXT>`) around untrusted input.
    - Enforces JSON validation via `StrategyDataSchema.model_validate_json(...)`.
    - Emits audit log event `strategy.ai_draft_generated`.
    - Returns strictly in-memory draft (does not persist to database).
  - Enhanced `SEOStrategyService.update_strategy(...)`:
    - Checks if the current version is an uncommitted initial draft (`version == 1` and `change_summary == "Initial strategy template initialized"`).
    - If so, updates this template in-place, sets status to `ACTIVE`, and records `strategy.created`.
    - For all subsequent edits on an active strategy, creates a new row via `create_version(...)` incrementing to Version 2+, sets status to `ACTIVE`, and records `strategy.updated`.
- `apps/api/app/api/v1/strategy.py`:
  - Added route `POST /projects/{project_id}/strategy/generate` returning `ApiResponse[StrategyDataSchema]`.
- `apps/api/tests/contract/test_openapi.py`:
  - Added endpoint check verifying `/api/v1/projects/{project_id}/strategy/generate` in the OpenAPI schema.
- `apps/api/tests/unit/test_strategy_ai_generation.py` (New):
  - 5 comprehensive tests covering AI draft generation, non-persistence guarantee, malformed AI output error handling, cross-tenant permission denial, and the Version 1 vs Version 2 lifecycle.

### Contracts & Shared Types
- `packages/shared-types/openapi.json`:
  - Regenerated via `scripts/export_openapi.py` with the new endpoint schema.
- `packages/shared-types/schema.d.ts`:
  - Regenerated TypeScript types via `npm run generate`.

### Frontend
- `apps/web/src/features/strategy/strategy-manager.tsx`:
  - Integrated AI Kickstart section displayed whenever the strategy is uncommitted (`status !== "active"` or empty data).
  - Added **"Generate Strategy with AI"** action button with loading states, error handling, and success banner.
  - Added comprehensive form controls for all `StrategyDataSchema` sections:
    - Business Context (Brand Name, Industry, Locations, Business Description)
    - Products & Services (dynamic item builder with name, category, priority, description)
    - Target Audience & Personas (audience segments, customer needs, persona name & problem builder)
    - Competitors (domain, competitor strengths)
    - SEO Goals & Priority Topics (primary goals, core objectives, priority topic lists)
  - Dynamic button text: **"Save as Version 1"** for initial draft commit, **"Save New Version"** once active.

---

## 3. Database Changes

- **None**. Existing schema and Alembic migrations already support `seo_strategies` and `seo_strategy_versions` with JSONB `strategy_data` and version tracking. No migrations were required or executed.

---

## 4. API Changes

### `POST /api/v1/projects/{project_id}/strategy/generate`
- **Authentication**: Bearer JWT (`AuthenticatedUser`).
- **Authorization**: Requires `PermissionCode.STRATEGY_WRITE` on the project. Cross-tenant access is rejected with `403 Forbidden`.
- **Request Body**: None (retrieves verified project context from DB).
- **Response**: `ApiResponse[StrategyDataSchema]`
- **Side Effects**: Emits `strategy.ai_draft_generated` audit log. Does not write or mutate any strategy table rows.

---

## 5. AI Generation Flow

```
┌────────────────────────────────────────────────────────┐
│ User navigates to SEO Strategy for New Project        │
└───────────────────────────┬────────────────────────────┘
                            │
                            ▼
┌────────────────────────────────────────────────────────┐
│ Clicks "Generate Strategy with AI"                     │
└───────────────────────────┬────────────────────────────┘
                            │
                            ▼
┌────────────────────────────────────────────────────────┐
│ Backend assembles verified project context:            │
│ - Project Name, Locale, Country, Description           │
│ - Up to 5 Active Websites                              │
│ - Up to 30 Crawled URL paths & page titles             │
│ - Up to 50 Targeted Keywords & clusters                │
└───────────────────────────┬────────────────────────────┘
                            │
                            ▼
┌────────────────────────────────────────────────────────┐
│ Prompt Fencing with <STRATEGY_CONTEXT> (anti-injection)│
│ Calls AIProvider.generate(...)                         │
└───────────────────────────┬────────────────────────────┘
                            │
                            ▼
┌────────────────────────────────────────────────────────┐
│ Pydantic Validation: StrategyDataSchema                │
│ Audit Log: strategy.ai_draft_generated                 │
│ Returns JSON to Frontend (Database remains untouched)  │
└───────────────────────────┬────────────────────────────┘
                            │
                            ▼
┌────────────────────────────────────────────────────────┐
│ Frontend populates form fields                         │
│ User reviews, edits, and inspects AI draft             │
└────────────────────────────────────────────────────────┘
```

---

## 6. Version 1 vs Version 2 Lifecycle Flow

1. **Initial Uncommitted State**:
   - `strategy.current_version = 1`, `status = "draft"`, `change_summary = "Initial strategy template initialized"`.
   - The user can click "Generate Strategy with AI" or type manually.
2. **Commit Version 1**:
   - User clicks **"Save as Version 1"**.
   - `update_strategy` identifies `is_first_save = True`.
   - The version 1 template record is updated in-place with user-reviewed data.
   - Status transitions to `ACTIVE`.
   - Audit event `strategy.created` is emitted.
3. **Subsequent Edits (Version 2+)**:
   - User updates fields and clicks **"Save New Version"**.
   - `update_strategy` identifies `is_first_save = False`.
   - Creates a new version record (`version = 2`), increments `strategy.current_version = 2`.
   - Preserves version 1 intact in `seo_strategy_versions`.
   - Audit event `strategy.updated` is emitted.

---

## 7. Security & RBAC

- **Tenant Isolation**: Every database query explicitly checks `organization_id == actor.organization_id`. Negative cross-tenant tests verify unauthorized access is denied.
- **Prompt Injection Defense**: All untrusted database text (scraped titles, keyword names, project descriptions) is isolated inside `<STRATEGY_CONTEXT>` XML fencing blocks and explicitly marked as data, not instructions.
- **Auditing**: Every generation invocation (`strategy.ai_draft_generated`) and every version creation/update (`strategy.created`, `strategy.updated`) is written to the audit log table.
- **No Autonomous Side Effects**: AI output is never saved to the database without explicit user action ("Save as Version 1").

---

## 8. Test Coverage

- `apps/api/tests/unit/test_strategy_ai_generation.py`:
  - `test_generate_initial_strategy_draft_success`: Verifies AI generates structured `StrategyDataSchema` from project context.
  - `test_generate_initial_strategy_draft_does_not_mutate_db`: Verifies DB is not modified by generation.
  - `test_generate_initial_strategy_draft_malformed_json`: Verifies graceful failure when AI output is invalid JSON.
  - `test_generate_initial_strategy_draft_cross_tenant_denied`: Verifies tenant isolation on unauthorized project.
  - `test_version_1_and_version_2_lifecycle`: Verifies Version 1 commit and Version 2 versioning behavior.
- `apps/api/tests/contract/test_openapi.py`:
  - Verifies `/api/v1/projects/{project_id}/strategy/generate` endpoint exists in OpenAPI specification.
- `apps/web`:
  - Vitest test suite: 54 tests passing.
  - TypeScript strict typecheck: 0 errors.

---

## 9. Status Report

```
FEATURE STATUS: COMPLETE
REGRESSION: NONE
EXISTING FEATURES: UNCHANGED
TESTS: PASS (5/5 unit tests, 1/1 contract test, 54/54 web tests)
```
