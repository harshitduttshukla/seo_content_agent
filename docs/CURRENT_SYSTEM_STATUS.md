# Current System Status Report: Content Intelligence OS

**Date:** September 11, 2026  
**Audited By:** Antigravity AI Engineering  
**Scope:** Verification of Phase 1 through Phase 6 implementations across Backend, Database, Frontend, and AI layers.

---

## 1. PROJECT OVERVIEW

### What this application does
This application is an **AI-Governed SEO Content Operating System**. Instead of generating generic AI blog posts, it turns a company's real business strategy, website crawl data, and keyword intelligence into a structured content roadmap. It guides writers with comprehensive briefs, optimizes drafts with deterministic SEO rules, and uses AI to assist with edits while keeping a human in complete control.

### Who uses it
- **Head of SEO / SEO Managers:** To audit site structure, cluster keywords, detect orphan pages, and set linking strategies.
- **Content Strategists & Editors:** To plan content maps, build detailed writing briefs, and review AI proposed changes.
- **Writers & Copywriters:** To draft articles in a structured block editor with live SEO and keyword scoring.

### What problem it solves
Generic AI content tools create ungrounded, unoptimized articles that can harm search rankings and violate brand voice. Spreadsheets and fragmented tools make it difficult to maintain internal link equity or avoid keyword cannibalization. This application solves both by using a PostgreSQL database as the single source of truth, where every AI proposal is strictly bounded by real SEO data and requires human sign-off.

### What the user can currently do
A user can log in, connect and verify a website, run an automated web crawler, formulate an SEO strategy, import and cluster keywords, visually explore their site's content architecture on an interactive graph, generate content briefs, draft articles in a block editor, chat with an AI assistant that uses specialized SEO tools, review side-by-side visual diffs of AI proposals, and approve or restore document versions.

---

## 2. COMPLETE USER FLOW

Here is the exact journey a user takes through the working application today:

```
User opens application
  ↓
Login / Authentication
  ↓
Organization Selection / Creation
  ↓
Project Selection / Creation
  ↓
Website Registration & Ownership Verification
  ↓
Website Crawling & Content Indexing
  ↓
SEO Strategy Definition
  ↓
Keyword Import & Intent Clustering
  ↓
Content Architecture & Topic Mapping
  ↓
Visual Content Map Exploration & Validation
  ↓
Internal Linking Opportunities Review
  ↓
Planned Page Creation
  ↓
Content Brief & SEO Guide Generation
  ↓
Structured Block Document Editing
  ↓
AI Chat & Multi-Step Orchestrator Task Execution
  ↓
Visual Diff Review & Human Approval / Rejection
  ↓
Version Bump, Verification & Rollback
```

### Step-by-Step Breakdown:

1. **User opens application**
   - *What the user does:* Navigates to `http://localhost:3000`.
   - *What the system does:* Displays the landing page explaining the system capabilities and checks for an active session cookie.
   - *What the user gets:* Clear entry point to sign in or open existing workspaces.

2. **Login / Authentication**
   - *What the user does:* Clicks "Continue with SSO" or selects a local development identity (`Admin User` or `SEO Manager`).
   - *What the system does:* Validates the OIDC JWT token (or local development credentials), provisions the user in PostgreSQL, assigns role-based permissions, and sets secure HTTP-only cookies.
   - *What the user gets:* Authenticated session redirected to the Organizations workspace.

3. **Organization Selection / Creation**
   - *What the user does:* Selects an existing organization card or enters a name to create a new one (e.g., "Acme Studio").
   - *What the system does:* Enforces multi-tenant data boundaries so data is never shared across organizations.
   - *What the user gets:* Tenant-scoped workspace and access to that organization's projects.

4. **Project Selection / Creation**
   - *What the user does:* Selects or creates a specific project (e.g., "Main Blog & Resource Center").
   - *What the system does:* Loads the project dashboard and scopes all subsequent content, crawler jobs, and keywords to this project.
   - *What the user gets:* Central command center with navigation to all 7 core modules.

5. **Website Registration & Verification**
   - *What the user does:* Enters website URL (e.g., `https://example.com`) and clicks "Verify".
   - *What the system does:* Generates a unique verification token and HTML meta tag snippet. When requested, the system performs a secure HTTP request to the domain to verify ownership and prevent unauthorized scanning.
   - *What the user gets:* Verified website status enabling crawling.

6. **Website Crawling & Content Indexing**
   - *What the user does:* Configures crawl parameters (max pages, max depth, crawl delay, respect robots.txt) and clicks "Start Crawl".
   - *What the system does:* Fetches robots.txt, parses sitemaps, queues URLs in a crawl frontier, fetches HTML, extracts headings (H1-H6), meta tags, word counts, and outgoing links, and stores everything in PostgreSQL (`content_pages` and `page_links`).
   - *What the user gets:* Real-time crawl progress counters and a searchable table of all indexed site pages.

7. **SEO Strategy Formulation**
   - *What the user does:* Navigates to Strategy, fills in business profile (target market, customer personas, tone of voice, offerings, SEO goals), and saves.
   - *What the system does:* Updates the active strategy, logs an audit event, and creates an immutable version snapshot (`seo_strategy_versions`).
   - *What the user gets:* Active brand and strategic constraints that will automatically govern future AI prompts.

8. **Keyword Import & Intent Clustering**
   - *What the user does:* Uploads a CSV of target search keywords with search volumes and difficulty scores.
   - *What the system does:* Deduplicates keywords, assigns deterministic search intents (Informational, Commercial, Navigational, Transactional), calculates priority scores, and runs a semantic clustering engine to group related terms around a primary keyword.
   - *What the user gets:* Interactive keyword dashboard and organized keyword clusters.

9. **Content Architecture & Topic Mapping**
   - *What the user does:* Creates Content Pillars (e.g., "Technical SEO") and Topics (e.g., "Site Speed Optimization"). Maps live crawled pages or planned articles to these topics.
   - *What the system does:* Persists the hierarchy and identifies unmapped keywords as new "Content Opportunities".
   - *What the user gets:* Structured hierarchy connecting business themes to actual web pages.

10. **Visual Content Map Exploration & Validation**
    - *What the user does:* Opens the visual Content Map canvas, zooms, pans, filters by status, or switches to tree view.
    - *What the system does:* Projects Pillars, Topics, Clusters, and Pages into a connected visual graph. Runs real-time integrity checks to detect orphan pages (pages with 0 incoming links) and keyword cannibalization risks.
    - *What the user gets:* Bird's-eye view of site architecture with instant warnings for architectural SEO defects.

11. **Internal Linking Opportunities**
    - *What the user does:* Navigates to Internal Linking to view system-recommended links.
    - *What the system does:* Analyzes crawled hyperlink graphs and topical relationships to propose specific links between relevant pages with recommended anchor text.
    - *What the user gets:* Approval pipeline where links can be approved, rejected, or queued for insertion into drafts.

12. **Planned Page & Brief Generation**
    - *What the user does:* Creates a Planned Content Page from a cluster or opportunity, selecting content type (e.g., Guide, Article).
    - *What the system does:* Generates a structured `ContentBrief` and an `SEOGuide` containing target word count, required headings, search intent, and secondary keyword density requirements.
    - *What the user gets:* Complete editorial brief ready for drafting.

13. **Structured Document Editing**
    - *What the user does:* Opens the page editor. Types or reorganizes content blocks (Headings, Paragraphs, FAQs, Callouts, Lists).
    - *What the system does:* Stores content in structured block format (`content_documents`) with automatic word counting and real-time SEO scoring.
    - *What the user gets:* Clean, distraction-free block editor with live SEO checklist feedback.

14. **AI Assistant & Workflow Orchestration**
    - *What the user does:* Opens the AI chat sidebar, selects a block, and asks the AI to perform an action (e.g., "Rewrite section to be more authoritative", "Add FAQ block", "Insert internal link to our speed guide", or "Analyze SEO quality").
    - *What the system does:* The AI Orchestrator classifies intent, formulates a multi-step plan, calls read tools safely (`read_document`, `seo_quality_check`, `find_link_opportunities`), and when preparing a write mutation (`rewrite_section`, `insert_internal_link`), pauses the workflow at a **Human Approval Gate**.
    - *What the user gets:* A visual workflow progress timeline and a clear proposal card.

15. **Visual Diff Review & Approval**
    - *What the user does:* Reviews the side-by-side diff showing exact text additions and deletions along with the AI's strategic rationale. Clicks "Approve" or "Reject".
    - *What the system does:* If approved, atomically applies the patch to the document blocks, increments the document version number, saves an immutable version snapshot (`content_document_versions`), runs an automated verification check, and records an audit log. If rejected, marks the proposal rejected with no changes to the draft.
    - *What the user gets:* Immediate update to the document with complete version history and 1-click rollback capability.

---

## 3. PHASE-BY-PHASE STATUS

### Phase 1: SaaS Platform Foundation

- **IMPLEMENTED:**
  - Multi-tenant Organization management with complete tenant data isolation (`organization_id` on all entities).
  - Project management (workspace containers within organizations).
  - User identity provisioning and profile tracking (`users` table).
  - Comprehensive Role-Based Access Control (RBAC): 6 roles (`admin`, `seo_manager`, `content_manager`, `writer`, `editor`, `viewer`) and 22 permission codes (`PermissionCode`).
  - OIDC JWT verification via JWKS (`oidc.py`) with support for local development logins (`dev-admin`, `dev-seo_lead`).
  - Next.js Web BFF with secure httpOnly cookie session management and reverse proxy (`/api/backend/[...path]`).
  - PostgreSQL database with 50 relational tables, UUID primary keys, UTC timestamps, and Row-Level Security (RLS) policies.
  - Audit logging (`audit_logs` table) and Idempotency key tracking (`idempotency_records` table).
  - RESTful FastAPI v1 endpoints with uniform `{ data, meta, errors }` envelope.
  - Project dashboard and organization workspace UI.
- **PARTIAL:**
  - Team member invitation UI: Backend endpoints for managing members exist, but the frontend currently focuses on organization and project workspace switching without an interactive team invite modal.
- **MISSING:**
  - Native username/password registration with password reset flows (by design: outsourced to standard OIDC SSO providers).

---

### Phase 2: Website Crawling & Content Intelligence

- **IMPLEMENTED:**
  - Website registration with URL normalization and host extraction.
  - Domain ownership verification via meta tag (`<meta name="antigravity-verification">`), custom HTTP header, or verification file.
  - robots.txt discovery and path-rule parsing (`RobotsParser`).
  - sitemap.xml discovery and hierarchical index parsing (`SitemapParser`).
  - Crawl frontier management with depth tracking, URL normalization, and path filtering (`CrawlFrontier`).
  - HTTP fetching with custom user-agent, timeouts, and configurable polite crawl delays (`HttpFetcher`).
  - HTML extraction: page title, meta description, canonical URL, H1-H6 heading hierarchy, clean body text, word count, internal/external link discovery, and nofollow detection (`HtmlContentExtractor`).
  - Relational storage of crawled pages and links: `content_pages`, `page_links`, `crawl_jobs`, `crawl_urls`, and `crawl_events`.
  - Real-time crawl progress reporting, cancellation controls, failure summaries, and retry tracking.
  - SSRF protection: private IP and loopback restrictions during fetching and domain verification.
  - Crawl UI panel (`crawl-panel.tsx`) with real-time stats, page inventory table, and verification modal.
- **PARTIAL:**
  - Worker execution model: Crawling executes as an asynchronous in-process Python task (`asyncio.create_task`) rather than dispatching to an external Celery worker process.
- **MISSING:**
  - JavaScript-rendered crawling (Headless Chromium / Playwright). The crawler currently processes static server-rendered HTML.
  - S3 / Cloudflare R2 raw HTML archiving: The `ObjectStorage` interface exists, but HTML is currently parsed and stored directly in PostgreSQL.

---

### Phase 3: SEO Strategy & Keyword Intelligence

- **IMPLEMENTED:**
  - SEO Strategy domain model: target market, ideal customer profile (ICP), brand tone, product offerings, competitors, and strategic SEO goals.
  - Immutable strategy version snapshots (`seo_strategy_versions`) and audit logging.
  - CSV Keyword import with parsing, deduplication, and volume/difficulty/CPC validation (`KeywordImporter`).
  - Deterministic search intent classifier identifying Informational, Commercial, Navigational, and Transactional queries (`intent.py`).
  - Business priority and value scoring algorithms combining volume, intent weighting, and difficulty.
  - Semantic keyword clustering engine (`clustering.py`) grouping keywords by lexical token similarity and search intent compatibility.
  - Content Pillars (`content_pillars`) and Topics (`topics`) hierarchy models.
  - Keyword-to-page mappings (`keyword_page_mappings`) and discovered keyword associations (`page_keywords`).
  - Content opportunity detection identifying high-value unmapped keyword clusters.
  - Web UI: Strategy manager (`strategy-manager.tsx`), Keywords dashboard (`keywords-dashboard.tsx`) with clustering modal and intent filtering, and Architecture dashboard (`architecture-dashboard.tsx`).
- **PARTIAL:**
  - External SEO data provider APIs: Keyword metrics are currently imported via CSV spreadsheets rather than live querying third-party APIs (e.g. Semrush, Ahrefs).
- **MISSING:**
  - Google Search Console (GSC) OAuth integration for live organic search traffic data.

---

### Phase 4: Content Map, SEO Guide & Internal Linking

- **IMPLEMENTED:**
  - Interactive visual Content Map canvas (`content-map-view.tsx`) with zoom, pan, search, node filtering, and toggleable tree view.
  - Relational content graph connecting Pillars -> Topics -> Clusters -> Pages (both existing crawled pages and planned pages).
  - Content architecture version snapshots (`content_architecture_versions`) with rollback capability.
  - Graph integrity validator detecting orphan pages (0 incoming links) and keyword cannibalization risks.
  - Governed Page Relationships (`page_relationships` table modeling parent, child, sibling, supporting, and canonical links).
  - Internal Linking intelligence service (`InternalLinkingService`): scans page content and link graph, generates recommended links with target URLs and anchor text.
  - Link opportunity review workflow (`link_opportunities` table: proposed, approved, rejected, applied).
  - Internal Linking dashboard (`internal-linking-dashboard.tsx`) showing link equity distribution, orphan pages, and approval actions.
  - SEO Guides (`seo_guides`, `seo_guide_versions`): automated guide generator producing target keywords, structural requirements, heading outlines, and quality thresholds.
  - SEO Guide viewer (`seo-guide-view.tsx`).
- **PARTIAL:**
  - Live CMS link insertion: Approved internal links can be inserted into draft documents inside the app, but there is no direct connector pushing changes to an external live CMS (e.g., WordPress).
- **MISSING:**
  - Third-party external backlink monitoring.

---

### Phase 5: Content Brief + AI Content Editor

- **IMPLEMENTED:**
  - Content Brief generation and management (`content_briefs`, `content_brief_versions`): target audience, primary/secondary keywords, intent, word count target, section outline, reference links.
  - Structured block-based document model (`content_documents`, `content_document_versions`) with typed blocks (`HEADING`, `PARAGRAPH`, `CALLOUT`, `FAQ`, `LIST`, `CODE`).
  - Block-based visual Content Editor (`content-editor.tsx`) with block selection, adding, editing, reordering, and deleting.
  - Production Google Gemini integration (`GeminiAIProvider` using `gemini-flash-latest` and `gemini-embedding-001` via direct HTTP REST) and deterministic test fallback (`MockAIProvider`).
  - AI Context Builder (`context.py`): compiles tenant-isolated prompts containing business strategy, SEO guide, keywords, brief outline, and internal link suggestions.
  - Conversational AI chat sidebar (`editor-sidebar.tsx`) tied to document sessions (`content_chat_sessions`, `content_chat_messages`).
  - Structured AI patch engine (`patch_service.py`): AI produces typed operations (`REPLACE_BLOCK`, `INSERT_BLOCK`, `DELETE_BLOCK`, `INSERT_LINK`).
  - Proposal management (`ai_edit_proposals`): side-by-side diff previews with rationale and provenance.
  - Human approval gate: user explicitly reviews diff and clicks "Apply" or "Reject".
  - Immutable document versioning: applying a proposal increments document version, stores an immutable version snapshot (`content_document_versions`), and allows 1-click restore.
  - Internal link insertion tool: AI detects insertion spots and injects target URL and anchor text into block metadata.
  - SEO quality scoring engine (`quality_service.py`): real-time checks for word count, keyword inclusion, heading structure, and meta tags.
- **PARTIAL:**
  - TipTap rich text integration: the editor currently renders and edits structured blocks directly using React state and Tailwind components rather than a full headless TipTap instance (structured blocks are implemented and functional).
- **MISSING:**
  - Real-time collaborative multi-user editing (e.g., WebSocket-based simultaneous typing).

---

### Phase 6: AI Orchestrator + Tool/Action Layer

- **IMPLEMENTED:**
  - Intent Classifier (`intent_classifier.py`): categorizes user requests into structured intents (`MULTI_STEP_CONTENT_TASK`, `ANALYZE_SEO`, `INSPECT_KEYWORDS`, `INTERNAL_LINKING_TASK`, `SECTION_EDIT`, `OUTLINE_GENERATION`, `GENERAL_INQUIRY`).
  - Workflow Planner (`planner.py`): generates an ordered, bounded sequence of tool steps based on intent and document context.
  - Tool Registry (`tool_registry.py`): 14 registered tools across 4 categories (Content, SEO, Internal Linking, Content Map) with Pydantic v2 input/output schemas, risk levels (`READ`, `SUGGEST`, `WRITE`), cost declarations, and RBAC permissions.
  - Tool Executor (`tool_executor.py`): executes tools with schema validation, permission checks, execution bounds, and audit records in `tool_executions`.
  - Orchestration state machine (`workflow_service.py`): manages workflow lifecycle (`PENDING`, `RUNNING`, `WAITING_FOR_APPROVAL`, `COMPLETED`, `FAILED`, `CANCELLED`, `PAUSED`).
  - Human Approval Gates: any write mutation tool automatically halts the workflow loop, generates an `AIEditProposal`, sets step to `WAITING_FOR_APPROVAL`, and notifies the user.
  - Human Actions: endpoints for `/workflows/{id}/steps/{step_id}/approve` and `/reject`.
  - Workflow Control: `/workflows/{id}/resume` and `/workflows/{id}/cancel`.
  - Mutation Verification (`verification_service.py`): validates that approved patches actually updated document blocks and bumped version numbers.
  - Workflow Activity UI (`workflow-activity.tsx`): visual timeline showing workflow progress, tool badges, risk levels, parameter inspectors, approval cards, and cancellation controls.
  - Bounded retry and error handling: handles transient errors with retry limits and records failures.
- **PARTIAL:**
  - Workflow durability across server crashes: workflow state is persisted in PostgreSQL, but active in-memory loops are synchronous/in-process rather than durable Celery workflow chains.
- **MISSING:**
  - Autonomous write actions without human gate (omitted intentionally: all write mutations require explicit human sign-off per architectural requirements).

---

## 4. WHAT CAN THE USER CURRENTLY DO?

Here is the exact list of actions a customer can perform **today** in the running application:

1. **Sign In:** Log in using corporate SSO or local development accounts (`admin@example.com` or `seo_lead@example.com`).
2. **Switch Organizations:** Select between isolated client or team workspaces.
3. **Create Projects:** Set up new project workspaces with dedicated settings.
4. **Connect Websites:** Register website URLs for tracking.
5. **Verify Ownership:** Confirm domain control using automated meta tag verification.
6. **Crawl Websites:** Run crawls to discover pages, follow sitemaps, and respect robots.txt.
7. **Inspect Crawled Pages:** View page titles, HTTP status codes, word counts, extracted headings, and internal links.
8. **Define SEO Strategy:** Input business description, target audience, tone of voice, products/services, and SEO targets.
9. **Import Keywords:** Upload CSV files containing keywords, search volumes, and difficulty metrics.
10. **Analyze Search Intent:** View automatic categorization of keywords into Informational, Commercial, Navigational, or Transactional.
11. **Cluster Keywords:** Run automated clustering to group similar keywords around a primary term.
12. **Build Content Hierarchy:** Create Content Pillars and Topics representing core business themes.
13. **Map Content to Strategy:** Assign keywords and existing pages to topics to identify content gaps.
14. **Navigate Visual Content Map:** Explore the interactive graph canvas with zoom, pan, and search controls.
15. **Detect SEO Defects:** Review automated warnings for orphan pages (no links) and keyword cannibalization.
16. **Save Content Architecture Versions:** Create and restore historical snapshots of the content graph.
17. **Review Internal Linking:** View algorithmically recommended links between pages with suggested anchor text.
18. **Approve / Reject Links:** Manage the internal link pipeline.
19. **Plan New Pages:** Schedule new planned content pages assigned to keyword clusters.
20. **Generate Content Briefs:** View auto-generated briefs detailing audience, keywords, intent, and outlines.
21. **Inspect SEO Guides:** Review target word counts, heading structures, and keyword density checklists.
22. **Write in Structured Block Editor:** Draft and organize content using block elements (Headings, Paragraphs, FAQs, Callouts, Lists).
23. **Chat with AI Assistant:** Converse with an AI that has access to project strategy, SEO rules, and internal link suggestions.
24. **Request AI Rewrites & Expansions:** Direct the AI to rewrite, expand, or summarize specific sections.
25. **Generate FAQ Sections:** Request the AI to generate FAQ blocks addressing user search queries.
26. **Run AI SEO Audits:** Trigger instant SEO checks evaluating keyword density and structure.
27. **Insert Internal Links with AI:** Have the AI find and insert internal links into draft blocks.
28. **Run Multi-Step Agent Tasks:** Launch AI workflows that execute multiple tools in sequence.
29. **Monitor Agent Execution:** Watch real-time execution steps and tool inputs/outputs in the workflow timeline.
30. **Review Visual Diffs:** Compare proposed changes side-by-side before accepting them.
31. **Approve or Reject AI Changes:** Approve patches to apply them to the draft or reject them to discard.
32. **Restore Previous Versions:** Revert drafts to any historical version with a single click.

---

## 5. WHAT DOES THE AI CURRENTLY DO?

- **What information does the AI receive?**  
  The AI receives carefully assembled, tenant-isolated context: the active document blocks, the approved Content Brief, the SEO Guide (target keywords, word counts, required headings), the project's business strategy (audience, tone of voice), and verified internal linking recommendations. It **never** receives direct or unrestricted database access.
- **What does the AI analyze?**  
  The AI analyzes user chat prompts, document structure, keyword inclusion, readability, heading hierarchy, and potential internal linking insertion points.
- **What decisions can the AI make?**  
  The AI can decide which tools to invoke based on user intent (e.g. choosing whether to run an SEO quality check, find link opportunities, or rewrite a section). However, **the AI cannot decide to modify or publish content on its own**.
- **What tools can the AI use?**  
  The AI has access to 14 registered tools across 4 categories:
  - *Reading tools:* `read_document`, `read_section`, `get_related_pages`, `get_page_relationships`
  - *SEO analysis tools:* `seo_quality_check`, `keyword_check`, `metadata_check`
  - *Internal linking tools:* `find_link_opportunities`, `suggest_internal_links`, `insert_internal_link`
  - *Content generation & writing tools:* `generate_outline`, `rewrite_section`, `expand_section`, `shorten_section`
- **Can the AI modify content?**  
  **Only as a proposal**. The AI creates an `AIEditProposal` (a structured patch) specifying the exact block ID, old text, and proposed new text. The live document remains unchanged until a human reviews it.
- **Does the user approve changes?**  
  **Yes, strictly**. Every write action (editing text, inserting an FAQ block, adding a link) triggers an approval gate. The workflow halts in state `WAITING_FOR_APPROVAL`. The user must review the diff and explicitly click "Approve" or "Reject".
- **Can the AI execute multiple steps?**  
  **Yes**. The Workflow Planner chains multiple read, analysis, and suggest tools in sequence (e.g. read document -> check SEO quality -> find link opportunities -> suggest links -> propose edit).
- **Can the AI verify its work?**  
  **Yes**. The system includes a `VerificationService` that runs after an approved patch is applied to verify that the target block was modified as expected and that the document version bumped correctly.

---

## 6. DATABASE SCHEMA

The PostgreSQL database contains **50 tables** (49 application tables + 1 migration tracking table). Here is what each major table stores:

1. `users` → Stores registered user accounts and their linked login identities.
2. `organizations` → Stores client companies and serves as the strict security boundary between customers.
3. `organization_members` → Stores which users belong to which organization and their administrative roles.
4. `projects` → Stores distinct website or brand workspaces within an organization.
5. `project_members` → Stores user assignments and access rights for individual projects.
6. `roles` → Stores system and custom security role definitions.
7. `permissions` → Stores granular action permission keys (e.g., `content.write`, `ai.use`).
8. `role_permissions` → Stores rules assigning permissions to roles.
9. `websites` → Stores tracked domain URLs, crawl settings, and ownership verification records.
10. `crawl_jobs` → Stores execution runs, progress counters, and status metrics of the website crawler.
11. `crawl_urls` → Stores every individual web address found, crawled, or skipped during a site scan.
12. `crawl_events` → Stores timestamped diagnostic and error logs recorded during crawling.
13. `seo_strategies` → Stores the active business profile, audience targets, and SEO strategy for a project.
14. `seo_strategy_versions` → Stores permanent historical snapshots of previous SEO strategies.
15. `keywords` → Stores target search queries along with search volume, difficulty, and intent data.
16. `keyword_imports` → Stores uploaded keyword spreadsheets and their processing status.
17. `keyword_import_rows` → Stores the individual raw rows parsed from uploaded keyword spreadsheets.
18. `keyword_clusters` → Stores related keyword groups organized around a primary search topic.
19. `keyword_cluster_members` → Stores the links between individual keywords and their parent cluster.
20. `clustering_runs` → Stores the history and settings of automated keyword grouping calculations.
21. `content_pillars` → Stores top-level strategic themes that organize website content.
22. `topics` → Stores focused sub-themes categorized under each content pillar.
23. `content_pages` → Stores crawled live website pages and their extracted SEO metadata.
24. `content_page_versions` → Stores revision history for indexed live web pages.
25. `planned_content_pages` → Stores upcoming articles and guide pages scheduled to be written.
26. `keyword_page_mappings` → Stores assignments linking specific keywords to live or planned pages.
27. `page_keywords` → Stores keywords detected on crawled web pages.
28. `page_links` → Stores hyperlinks discovered connecting website pages together.
29. `content_opportunities` → Stores discovered content gaps where new pages should be created.
30. `content_map_nodes` → Stores the visual nodes displayed on the interactive Content Map.
31. `content_map_edges` → Stores the connecting lines displayed on the interactive Content Map.
32. `content_architecture_versions` → Stores saved historical snapshots of the overall site content structure.
33. `seo_guides` → Stores rules, word counts, and heading requirements for specific target topics.
34. `seo_guide_versions` → Stores historical snapshots of SEO guidelines.
35. `page_relationships` → Stores approved hierarchical connections between parent, child, and related pages.
36. `link_opportunities` → Stores recommendations for adding internal hyperlinks between site pages.
37. `content_briefs` → Stores editorial guidelines, outlines, and target keywords for writing articles.
38. `content_brief_versions` → Stores historical revisions of content writing briefs.
39. `content_documents` → Stores block-based article drafts, their text, and block structures.
40. `content_document_versions` → Stores complete historical revisions and rollback checkpoints for drafts.
41. `content_chat_sessions` → Stores conversational AI chat threads held while editing an article.
42. `content_chat_messages` → Stores individual user and assistant messages within an editing session.
43. `ai_edit_proposals` → Stores suggested content modifications generated by AI awaiting human approval.
44. `ai_workflows` → Stores multi-step AI agent task plans and overall execution states.
45. `ai_workflow_steps` → Stores individual tool calls and execution records within an AI workflow.
46. `tool_executions` → Stores performance timings and audit records for every AI tool execution.
47. `audit_logs` → Stores an unalterable security log of all critical actions for compliance.
48. `idempotency_records` → Stores tracking tokens to prevent accidental duplicate actions when requests are retried.
49. `outbox_events` → Stores asynchronous domain events waiting to be dispatched reliably.
50. `alembic_version` → Stores the current database schema migration tracking version.

---

## 7. IMPORTANT: CURRENT ERRORS & ISSUES

### 1. In-Process Background Crawling (Missing Dedicated Celery Worker)
- **ISSUE:** Crawling jobs and AI workflow execution loops run inside the main FastAPI application container using Python's in-memory `asyncio.create_task`. Although Redis is running and Celery dependencies are specified in `pyproject.toml`, no Celery worker container is running in `docker-compose.yml`, and `apps/api/app/workers` contains only an empty stub.
- **IMPACT:** If the API container restarts or crashes during a long crawl (e.g. 500 pages), the crawl process is killed immediately in memory and the database record remains stuck in `running` status. It also prevents distributing heavy crawls across separate machines.
- **CURRENT STATUS:** Functional for local testing and small sites, but architectural tech debt for production scale.

### 2. Missing Cloud Object Storage Implementation (Raw HTML Not Persisted)
- **ISSUE:** The repository defines an `ObjectStorage` interface protocol in `apps/api/app/integrations/object_storage.py`, but has no concrete S3 or Cloudflare R2 adapter. Extracted page content is saved in PostgreSQL, and raw HTML payloads are discarded after parsing.
- **IMPACT:** Raw HTML cannot be re-inspected later for debugging or re-extraction, and storing large text payloads in PostgreSQL will increase database storage costs over time.
- **CURRENT STATUS:** Deferred / not yet implemented.

### 3. No Live External SEO Data Provider Integration
- **ISSUE:** Keyword intelligence relies entirely on manual CSV uploads for search volume, difficulty, and CPC data.
- **IMPACT:** Users must manually export CSV files from tools like Semrush or Ahrefs before importing them, preventing live ranking updates or automated keyword discovery.
- **CURRENT STATUS:** By design for Phase 3 (CSV import met the Phase 3 roadmap criteria; live provider integrations belong to later phases).

### 4. Static HTML Crawler Without JavaScript Rendering
- **ISSUE:** The web crawler uses `httpx` and `BeautifulSoup`. It does not execute JavaScript using a headless browser (such as Chromium or Playwright).
- **IMPACT:** Single Page Applications (SPAs) built with React or Angular that render their content client-side cannot be properly crawled (the crawler will only see an empty HTML shell).
- **CURRENT STATUS:** Fully functional for standard server-rendered websites; JS rendering requires a dedicated headless browser service.

### 5. Future Domains Left as Empty Stubs
- **ISSUE:** The domain folders `publishing`, `analytics`, `learning`, `brand`, and `knowledge` contain only `.gitkeep` files.
- **IMPACT:** There is currently no 1-click publishing to WordPress/Webflow, no automated Google Analytics tracking, and no persistent vector embeddings knowledge base.
- **CURRENT STATUS:** Expected; these domains belong to Phase 7+ on the project roadmap.

---

## 8. SUGGESTIONS & IMPROVEMENTS

### Must Fix (Before Production Launch)
1. **Activate Celery Background Workers:** Move `CrawlService` and `WorkflowService` execution loops from FastAPI in-memory tasks to durable Celery background workers backed by the existing Redis container.
2. **Implement Cloud Object Storage:** Create an S3 / Cloudflare R2 adapter using `aiobotocore` so that raw crawl HTML and media assets are stored safely in cloud object storage instead of burdening the database.
3. **Headless Browser Crawler Fallback:** Integrate Playwright or an external rendering proxy to support client-rendered JavaScript websites.

### Should Improve (High-Value Next Steps)
1. **Direct CMS Publishing (Phase 7):** Build connectors for WordPress (via REST API) and Webflow so that approved articles can be exported with 1 click directly from the document editor.
2. **Live Keyword API Integration:** Connect to a search data provider (e.g. DataForSEO or ValueSerp) so users can type a seed topic and automatically pull search volume and intent without manual CSV uploads.
3. **Full TipTap Rich Text Integration:** Replace the raw block list view with a rich-text WYSIWYG editor powered by TipTap for formatting (bold, italic, lists, quotes) while preserving the underlying structured block data.

### Later (Nice-to-Have Post-MVP)
1. **Google Search Console (GSC) Integration:** Connect GSC via OAuth to import actual click, impression, and average position data directly onto crawled pages.
2. **Real-Time Collaborative Editing:** Add WebSockets (e.g. Yjs) so multiple editors can work on the same article draft simultaneously.
3. **Automated Content Decay Alerts:** Periodically re-crawl indexed pages to detect outdated statistics, broken links, or declining search rankings.

---

## 9. WHAT IS THE NEXT STEP?

### What we should build next:
**Phase 7: CMS Publishing & Content Export (WordPress / Webflow / Headless CMS Integration)**.

### Why:
We have successfully built the entire end-to-end editorial pipeline:
1. Crawling real websites (Phase 2)
2. Structuring SEO strategy & keywords (Phase 3)
3. Visualizing architecture & linking rules (Phase 4)
4. Generating briefs & drafting articles (Phase 5)
5. Governing AI modifications with human approval gates (Phase 6)

The only missing piece of the primary customer value chain is **publishing**. Right now, an approved, perfectly optimized article remains inside our database. Users must manually copy and paste text into their content management system. Building Phase 7 completes the loop from research to published URL.

### User problem it solves:
Eliminates manual copy-paste friction, preserves heading and metadata formatting, and allows content teams to publish directly to their live staging or production websites with full audit records.

### Existing components it will use:
- The `content_documents` and `content_document_versions` tables from Phase 5.
- The `publish.execute` permission code already configured in the Phase 1 RBAC system.
- The Phase 6 `ToolRegistry`, where a new `publish_to_cms` tool can be registered with a mandatory human approval gate.

---

## 10. MANAGER SUMMARY

A high-level summary in simple business language:

### What we have built
1. **A Complete SEO Intelligence Hub:** We can scan existing client websites, extract all their pages, and analyze their headings and links.
2. **Keyword & Strategy Engine:** We can import search keywords, automatically group them into themes, and set brand guidelines.
3. **Visual Content Architecture:** An interactive visual map that connects business topics to website pages and warns us about unlinked or competing pages.
4. **Governed AI Article Editor:** A clean writing space where writers draft articles and an AI assistant helps write, rewrite, and optimize content.
5. **Human Approval Safeguards:** The AI cannot change or publish anything on its own. Every AI recommendation must be reviewed and approved by a human editor.

### What is working
1. **Live Website Crawling:** Successfully scanned real websites (including `github.blog` and `pajasaapartments.com`), storing over 380 pages with full structure and metadata.
2. **Interactive Visual Content Map:** Fully functioning visual graph with zoom, search, and real-time SEO defect warnings.
3. **AI Editor with Proposal Diffs:** AI chat is fully connected to Google Gemini, proposing precise block-by-block edits with visual diffs and instant version rollback.

### What needs fixing
1. **Background Job Reliability:** Crawls and AI tasks currently run inside the web server's memory rather than in a dedicated background worker queue, meaning long crawls could stop if the server restarts.
2. **JavaScript Site Support:** The crawler currently reads static code and cannot read websites that require JavaScript to display content.

### One important suggestion
**Connect to a Content Management System (like WordPress):** Allow writers to send approved articles straight to their website as drafts with a single click, eliminating tedious copy-pasting.

### What we should do next
1. **Build Phase 7 (Publishing):** Add 1-click publishing to WordPress and Webflow.
2. **Set up Dedicated Background Workers:** Move crawling and multi-step tasks to the background queue for industrial-grade stability.
3. **Connect a Live Keyword Data Provider:** Replace manual CSV spreadsheet uploads with live search volume lookups.
