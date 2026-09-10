# Phase 5 — Content Brief & Chat-Native AI Content Editor

## Overview

Phase 5 turns the Content Map, SEO Guides, Keywords, Page Architecture, Internal Linking, and Brand Guidelines into production-ready content through two core components:
1. **Governed, Versioned Content Briefs**: Strategic, frozen specifications that bridge SEO strategy to drafting.
2. **Chat-Native AI Content Editor**: A block-based, structured editor where AI proposes surgical patches under strict human review, anti-injection prompt fencing, optimistic locking, and deterministic SEO quality scoring.

### Core Architecture Invariant: The User Document is Authoritative
Phase 5 is **not** an autonomous agent that dumps unstructured text or silently modifies files. The PostgreSQL `content_documents.content_blocks` records are the sole source of truth. The AI only proposes typed operations (`AIEditProposal`), which require explicit human approval via the Patch Engine before altering the document state.

---

## Implemented Domain Services & Architecture

### 1. Content Brief Domain (`apps/api/app/domains/content/brief_service.py`)
- **`ContentBrief`**: Governed entity containing:
  - Strategic target audience & business goals
  - Primary & secondary target keywords
  - Recommended H1 title & URL slug
  - Google SERP Meta Title & Meta Description limits
  - Target word count
  - Required topics checklist & semantic entities
  - Approved internal link targets
  - Brand voice, tone, and prohibited claims
- **`ContentBriefVersion`**: Immutable version snapshots created on manual updates and formal human approval.
- **Approval Workflow**: Transitions from `DRAFT` or `REVIEW` to `APPROVED` with version increment and audit logging.

### 2. Structured Block Document Engine (`apps/api/app/domains/content/document_service.py`)
- **`ContentDocument`**: Block-based content document with stable block IDs (e.g. `block_001`, `block_002`):
  - Block Types: `DOCUMENT_TITLE` (H1), `HEADING` (H2-H4), `PARAGRAPH`, `BULLET_LIST`, `NUMBERED_LIST`, `QUOTE`, `IMAGE`, `LINK`, `TABLE`, `FAQ`.
  - Stored as structured JSONB in PostgreSQL.
  - Automatically initializes outline blocks from SEO Guide and Content Brief upon creation.
- **Optimistic Locking**: Enforced via `lock_version`. Concurrent updates return HTTP 409 Conflict without overwriting newer edits.
- **Autosave & Version Snapshots**: Background debounced autosave preserves drafts, while explicit checkpoints create immutable `ContentDocumentVersion` records.
- **Non-Destructive Restoration**: Rolling back to historical version $v_k$ copies its content blocks to a new version $v_{N+1}$, leaving past history completely intact.

### 3. ContextBuilder & Anti-Injection Data Isolation (`apps/api/app/domains/ai/context_builder.py`)
Assembles a 10-layer prioritized context bundle within a strict token budget:
1. System instructions & operational policies
2. Strategic brand guidelines (tone, voice, forbidden phrases)
3. Primary & secondary target keywords
4. SEO rules & target word count
5. Required topics checklist
6. Approved internal link targets & anchor text
7. Focused block selection & surrounding context blocks
8. Full document outline
9. Recent conversational chat history
10. Anti-injection fencing: Untrusted user text and retrieved context data are fenced inside `<DOCUMENT_CONTEXT>` and `<USER_QUERY>` delimiters with explicit directives treating data as data, never as system instructions.

### 4. AI Patch & Human Approval Engine (`apps/api/app/domains/content/patch_service.py`)
- **Typed Operations**:
  - `replace_block`: Safely replaces target block text
  - `insert_block`: Inserts a block before or after a target block ID
  - `delete_block`: Deletes a targeted block ID
  - `move_block`: Reorders blocks
  - `update_title`: Updates the H1 title
  - `insert_link`: Embeds internal links with approved anchor text
  - `batch_operations`: Multiple coordinated atomic edits
- **Review & Diff Preview**:
  - AI proposals are persisted with status `PROPOSED`.
  - Frontend renders Old vs. New diff cards (inline strikethrough vs. green addition).
  - Explicit human action (`apply` or `reject`) via dedicated POST endpoints.
  - Applying a proposal atomically updates the document, creates a new `ContentDocumentVersion`, and marks the proposal `APPLIED`.

### 5. Deterministic SEO Quality Evaluator (`apps/api/app/domains/seo/quality_service.py`)
Deterministic rules evaluated on document change:
1. **H1 Heading Presence**: Validates exactly one primary H1 exists.
2. **Primary Keyword in H1**: Ensures primary keyword appears naturally in the title.
3. **Word Count Target Progress**: Compares actual word count against the brief's target.
4. **Primary Keyword in Introduction**: Checks keyword presence in opening 100 words.
5. **Required Topics Checklist**: Scans document text for coverage of required brief topics.
6. **Empty Blocks Check**: Detects unwritten or blank blocks.
7. **Deterministic SEO Score**: Computes percentage score (0-100%) and generates actionable recommendations.

---

## Frontend Workspace & Components

- **Route**: `/projects/[projectId]/content/[pageId]`
- **Entry points**: Planned-page rows expose **Brief & Editor** and Content Map page-node inspectors expose **Open Brief & Editor**.
- **Authenticated browser API**: All brief, editor, chat, quality, history, restore, and proposal actions use the Next.js `/api/backend` proxy through the shared `clientApi` helper.
- **`ContentPageWorkspace` (`apps/web/src/features/content/content-page-workspace.tsx`)**:
  - Header with breadcrumbs, page slug, status badges, and word count target.
  - Tab switcher: **Content Brief** vs. **AI Document Editor**.
- **`ContentBriefView` (`apps/web/src/features/briefs/content-brief-view.tsx`)**:
  - Form editing for SEO titles, meta descriptions, audience, goals, and keywords.
  - Interactive required topics and internal link targets.
  - Approve Brief button with versioning.
- **`ContentEditor` (`apps/web/src/features/editor/content-editor.tsx`)**:
  - Structured block canvas with stable block IDs.
  - Hover toolbar for block reordering, insertion, and deletion.
  - Inline diff preview banner when an AI proposal targets a block.
  - Autosave status indicator (`Saved`, `Saving...`, `Conflict`).
- **`EditorSidebar` (`apps/web/src/features/editor/editor-sidebar.tsx`)**:
  - **AI Chat Tab**: Prompt input, persistent message history, quick action chips, message copy/edit controls, and proposal review cards with 1-click **Apply** and **Reject**. Explicit full-page requests receive complete-document context and may produce a larger reviewed batch instead of the normal 1–3 focused operations.
  - **Outline Tab**: Dynamic H1/H2/H3 tree with jump-to-block highlighting.
  - **SEO Tab**: Quality score badge, word count progress bar, and check criteria list.
  - **History Tab**: Immutable version history list with 1-click non-destructive **Restore**.

---

## Verification & Test Results

### 1. Backend Verification (`apps/api`)
- **Unit Tests**: `apps/api/tests/unit/test_phase5_services.py` (8 test suites)
- **API Tests**: `apps/api/tests/api/test_phase5_api.py` (2 comprehensive integration flows)
- **Total Backend Tests**: **64 passed**, 1 skipped (real Postgres required), 0 failed.
- **Linter**: `ruff check apps/api` passes with **0 warnings / 0 errors**.

### 2. Frontend Verification (`apps/web`)
- **Component Tests**: `apps/web/src/__tests__/phase5-components.test.tsx` (5 test suites)
- **Total Frontend Tests**: **34 passed across 7 test files**, 0 failed.
- **TypeScript**: `tsc --noEmit` passes with **0 type errors**.
