# Phase 6 — AI Orchestrator + Tool/Action Layer

## Overview

Phase 6 introduces a fully governed **AI Orchestrator and Tool/Action Layer** on top of the established SaaS foundation (Phase 1), crawling/intelligence (Phase 2), strategy/keywords (Phase 3), content architecture/linking (Phase 4), and briefs/editor (Phase 5).

### Core Principle: LLM as Reasoning Engine, Not Database or Mutation Agent
1. **Zero Direct DB Access**: The LLM never issues SQL queries or interacts directly with the database.
2. **Zero Autonomous Writes**: The LLM cannot silently modify documents, publish content, or delete entities.
3. **Zero Autonomous Rule Changes**: AI proposals never automatically update active SEO or brand rules.
4. **Governed Tool Registry**: All capabilities are exposed as typed, validated, authorized Python tool functions with explicit risk classification (`READ`, `SUGGEST`, `WRITE`, `DESTRUCTIVE`).
5. **Mandatory Human Approval Gate**: Any tool that alters user documents (`WRITE`/`DESTRUCTIVE`) automatically halts the workflow in state `WAITING_FOR_APPROVAL`, generates an `AIEditProposal`, and waits for explicit user confirmation.
6. **Post-Action Verification**: After human approval, a deterministic verifier validates that the patch engine advanced the document version and applied the change faithfully.
7. **Complete Audit Trail**: Every tool call, duration, token usage, parameter set, and human decision is persisted to `ai_workflow_steps`, `tool_execution_records`, and `audit_events`.

---

## Domain Architecture & Implementation

### 1. Database Schema & Migration (`apps/api/alembic/versions/20260901_0006_phase6_orchestrator_workflows.py`)
Three new PostgreSQL relational tables:
- **`ai_workflows`**:
  - Primary key `id` (UUID)
  - `organization_id`, `project_id`, `document_id`, `brief_id`, `created_by_id`
  - `intent`: Workflow intent classification string
  - `status`: Enum (`PENDING`, `PLANNING`, `RUNNING`, `WAITING_FOR_APPROVAL`, `COMPLETED`, `FAILED`, `CANCELLED`)
  - `current_step`: Integer index tracking execution progress
  - `plan`: JSONB structured array of planned steps with tool names, rationales, and input arguments
  - `result`: JSONB outcome summary
  - `token_usage`: JSONB model usage telemetry
- **`ai_workflow_steps`**:
  - Primary key `id` (UUID), foreign key `workflow_id`
  - `step_index`: Ordering within the workflow
  - `tool_name`: Name of the registered tool
  - `status`: Enum (`PENDING`, `RUNNING`, `WAITING_FOR_APPROVAL`, `COMPLETED`, `FAILED`, `SKIPPED`)
  - `input`: JSONB validated tool inputs
  - `output`: JSONB tool execution results
  - `error_message`: Failure diagnostic text
  - `retry_count`: Tracked execution attempts
- **`tool_execution_records`**:
  - Primary key `id` (UUID), optional `workflow_step_id`
  - `organization_id`, `project_id`, `user_id`
  - `tool_name`, `status`, `risk_level`, `requires_approval`
  - `started_at`, `completed_at`, `duration_ms`
  - `input_arguments`, `output_data`, `error_message`

### 2. Tool Registry (`apps/api/app/domains/orchestrator/tool_registry.py`)
Registers 14 strongly-typed domain tools by reusing existing Phase 1–5 services without duplicating business logic:

| Tool Name | Risk Level | Requires Approval | Backing Service / Capability |
| :--- | :--- | :--- | :--- |
| `read_document` | `READ` | No | `DocumentService.get_document` |
| `read_seo_guide` | `READ` | No | `SEOGuideService` / DB query |
| `read_brief` | `READ` | No | `BriefService.get_brief` |
| `search_keywords` | `READ` | No | `KeywordService` database filtering |
| `search_pages` | `READ` | No | `ContentArchitectureService` / Planned pages |
| `retrieve_context` | `READ` | No | `ContextBuilderService.build_context` |
| `analyze_content_quality` | `READ` | No | `SEOQualityService.evaluate_document` |
| `check_cannibalization` | `READ` | No | `CannibalizationService.detect_cannibalization` |
| `find_internal_link_opportunities`| `READ` | No | `InternalLinkingService.find_opportunities` |
| `generate_link_suggestions` | `SUGGEST` | No | `InternalLinkingService` / candidate scoring |
| `generate_content_brief` | `SUGGEST` | No | `BriefService.create_brief` |
| `propose_edit` | `WRITE` | **Yes** | `DocumentPatchService.create_proposal` |
| `propose_links` | `WRITE` | **Yes** | `DocumentPatchService.create_proposal` |
| `delete_block` | `DESTRUCTIVE`| **Yes** | `DocumentPatchService.create_proposal` |

### 3. Intent Classification & Deterministic Workflow Planner
- **`IntentClassifier`** (`intent_classifier.py`):
  Categorizes user prompts into 8 distinct intents:
  - `SINGLE_STEP_READ`, `SINGLE_STEP_SUGGEST`, `SINGLE_STEP_EDIT`
  - `MULTI_STEP_CONTENT_TASK`, `OPTIMIZE_EXISTING_CONTENT`
  - `EXPAND_CONTENT_SECTION`, `INTERNAL_LINKING_TASK`, `AUDIT_CONTENT_TASK`
  - Multi-intent detection recognizes compound requests (e.g. "optimize quality and add internal links").
- **`WorkflowPlanner`** (`planner.py`):
  Constructs a bounded, sequential execution DAG ($N \le 6$ steps):
  - Every plan begins with observation steps (`read_document`, `read_seo_guide`, `analyze_content_quality`).
  - Proceeds through synthesis steps (`find_internal_link_opportunities`, `generate_link_suggestions`).
  - Caps mutating actions with `propose_edit` marked with `requires_approval=True`.

### 4. Governed Execution Pipeline (`tool_executor.py`)
For every tool invocation:
1. **Schema Validation**: Inputs validated against the tool's Pydantic schema.
2. **Authorization & RBAC**: Verifies tenant ownership and user permissions.
3. **Execution Record**: Creates a `tool_execution_records` row with timestamp.
4. **Bounded Timeout**: Strict `asyncio.wait_for` enforcement (defaults to 30s).
5. **Failure Handlers**: Captures domain and system exceptions; records duration and telemetry.
6. **Audit Integration**: Dispatches an immutable `AuditEvent` via `AuditWriter`.

### 5. State Machine & Approval Gates (`workflow_service.py`)
- **Execution Loop**: Executes read/suggest steps sequentially.
- **Approval Interruption**: When encountering a step requiring approval:
  - Calls `propose_edit` to create an `AIEditProposal` with status `PROPOSED`.
  - Transitions step to `WAITING_FOR_APPROVAL` and workflow to `WAITING_FOR_APPROVAL`.
  - Halts execution and notifies the caller.
- **Human Decision Endpoints**:
  - `approve_step`: Invokes `DocumentPatchService.apply_proposal`, runs `VerificationService`, advances workflow, and runs any remaining steps.
  - `reject_step`: Rejects the proposal, marks step `CANCELLED`, and stops the workflow.
- **Resilience**:
  - `retry_step`: Supports retrying transient failures up to `MAX_STEP_RETRIES` (3).
  - `cancel_workflow`: Cleanly aborts running or pending workflows.

### 6. Post-Action Verification (`verification_service.py`)
Guarantees integrity following an approved patch:
1. **Version Advance Check**: Confirms `document.current_version >= expected_version`.
2. **Block Verification**: Checks that replaced/inserted block text actually matches the approved payload.
3. **Deletion Verification**: Ensures target block ID no longer exists in `document.content_blocks`.
4. **Anchor & Link Verification**: Validates that newly added links point to approved targets and maintain valid URL syntax.

---

## REST API Endpoints (`apps/api/app/api/v1/orchestrator.py`)

All endpoints are mounted under `/api/v1/orchestrator` and enforce tenant authentication:
- `GET /api/v1/orchestrator/tools`: List all registered tools, risk levels, and parameter schemas.
- `POST /api/v1/orchestrator/execute`: Execute a prompt/goal. Automatically classifies intent, plans steps, runs read tools, and halts at approval gates.
- `GET /api/v1/orchestrator/workflows/{workflow_id}`: Fetch workflow details, step breakdown, and execution durations.
- `POST /api/v1/orchestrator/workflows/{workflow_id}/steps/{step_id}/approve`: Approve an edit proposal, verify document updates, and resume workflow.
- `POST /api/v1/orchestrator/workflows/{workflow_id}/steps/{step_id}/reject`: Reject an edit proposal and mark step cancelled.
- `POST /api/v1/orchestrator/workflows/{workflow_id}/retry`: Retry a failed step.
- `POST /api/v1/orchestrator/workflows/{workflow_id}/cancel`: Abort a pending or waiting workflow.

---

## Frontend Integration (`apps/web`)

### 1. `WorkflowActivity` Component (`apps/web/src/features/editor/workflow-activity.tsx`)
- **Visual Execution Timeline**: Displays each step with status icon, tool name, duration (ms), and risk badge (`READ`, `SUGGEST`, `WRITE`, `DESTRUCTIVE`).
- **Dynamic Progress Bar**: Visualizes completed steps vs. total steps ($X$ of $Y$ steps, percentage).
- **Human Approval Card**:
  - Highlighted amber callout with shield icon.
  - Target proposal ID and explanation.
  - One-click "Approve & Apply" button (triggers patch application and document update).
  - "Reject" button.
- **Workflow Controls**: "Retry Failed Step" and "Cancel Workflow" action buttons.

### 2. Editor Sidebar "Agent" Tab (`apps/web/src/features/editor/editor-sidebar.tsx`)
- Dedicated **Agent** tab with pulsing amber beacon when approval is pending.
- **Quick Agent Recipes**:
  - "Optimize Document" (Full content & SEO audit + enhancement proposal)
  - "Audit & Fix SEO" (Deterministic quality check + optimization)
  - "Inject Links" (Graph-based internal linking discovery + proposal)
  - "Expand Depth" (Technical elaboration + block insertion)
- **Interactive Prompt Box**: Allows users to issue arbitrary multi-step optimization commands.

---

## Verification & Test Results

### 1. Backend Verification
- `tests/unit/test_phase6_orchestrator.py`: **20/20 passed**
  - Tool registration and schema reflection
  - RBAC and unknown tool protection
  - Execution timeout and error capture
  - Intent classification and compound queries
  - Planner step bounding and approval tagging
  - Post-action verifier: version bump, block insertion, block deletion
  - State machine: approval transitions, retry limits, cancellation
- `tests/api/test_phase6_api.py`: **2/2 passed**
  - Tool catalog listing endpoint
  - Workflow execution endpoint
- `tests/api/test_phase6_e2e.py`: **1/1 passed**
  - Full end-to-end multi-step workflow with human approval and verification
- **Total Backend Suite**: **87 passed, 1 skipped (live postgres url required)** in 2.71s
- **Linter & Formatter**: `ruff check .` and `ruff format --check .` passed cleanly (169 files).

### 2. Frontend Verification
- `apps/web/src/__tests__/phase6-components.test.tsx`: **8/8 passed**
  - Empty and loading states
  - Status badges, progress calculation, and tool duration telemetry
  - Approval card actions (`onApproveStep`, `onRejectStep`)
  - Retry on failed workflow
  - Sidebar tab switching and recipe triggers
  - End-to-end client API execution and proposal application
- **Total Frontend Suite**: **42/42 passed** across 8 test suites.
- **TypeScript Check**: `tsc --noEmit` passed with 0 errors.
