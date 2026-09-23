# V3 Migration Decision

Hard cutover — legacy briefs/keywords/content-map are being removed now, not run in parallel. V3 is the only path going forward for these areas.

## Domain Classifications

| Domain | Bucket | Reason |
|---|---|---|
| `organizations` | KEEP AS-IS | Auth/tenant layer, V3 uses the same tenants. |
| `users` | KEEP AS-IS | Auth/tenant layer. |
| `crawling` | KEEP AS-IS | V3 site import reuses this directly. |
| `content` | KEEP AS-IS (Mostly) | Document storage/versioning needed for V3 Production. *Note: `content_briefs` API and services were removed from here.* |
| `orchestrator` | KEEP AS-IS | AgentLoop/ToolExecutor engine; V3 Production reuses this. |
| `auth` | KEEP AS-IS | Core authentication. |
| `projects` | KEEP AS-IS | Core tenant scope. |
| `websites` | KEEP AS-IS | Core tenant scope. |
| `ai` | KEEP AS-IS | Core AI provider integrations. Legacy ContextBuilder logic stripped. |
| `audit` | KEEP AS-IS | Core audit trails. |
| `brand` | KEEP AS-IS | Standard tenant configuration. |
| `canvas` | KEEP AS-IS | V3 Foundation. |
| `content_cards` | KEEP AS-IS | V3 Foundation. |
| `demand` | KEEP AS-IS | V3 Foundation. |
| `job_runs` | KEEP AS-IS | V3 Foundation. |
| `keywords` | REMOVE | Superseded by DemandNode. |
| `content_map` | REMOVE | Superseded by ContentCard + Kanban board. |
| `seo` | REMOVE | Contains legacy `SEOGuide` and quality checks superseded by V3 deterministic QA. |
| `analytics` | UNCERTAIN | Existing external data syncs, unclear if V3 replaces or keeps. |
| `content_harness` | UNCERTAIN | Evaluation tools for Phase 6 LLM flows. |
| `internal_linking` | UNCERTAIN | Contains legacy link opportunity generators. |
| `knowledge` | UNCERTAIN | RAG/pgvector infrastructure. |
| `learning` | UNCERTAIN | Phase 6 learning modules. |
| `publishing` | UNCERTAIN | External CMS sync. |
| `strategy` | UNCERTAIN | Contains legacy `SEOStrategy` (superseded by Canvas?). |

## Strict Rules for Future Development

**No new frontend or backend work touches `content_briefs`, `keywords`, or `content_map`/`planned_content_pages` endpoints from this commit forward. All new work is V3-only or touches KEEP-bucket infrastructure (crawling, orchestrator, content documents, auth).**

## Deferred Work
What's explicitly NOT happening yet in this step:
- BundleBuilder
- Deterministic QA
- Content Hub board
- Production writer UI

These are later steps and not part of the initial mechanical cleanup.
