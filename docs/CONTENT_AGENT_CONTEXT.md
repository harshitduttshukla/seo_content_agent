# Content Agent Context System

## 1. Purpose

The Content Agent Context System is the single authoritative working context pipeline for AI-driven SEO content operations. It replaces ad-hoc prompt formatting with a structured, tenant-authorized, prioritized, token-budgeted, and provenance-tracked data bundle: `ContentAgentContext`.

The Context Builder:
- **Does NOT** call LLMs or AI providers.
- **Does NOT** execute tools.
- **Does NOT** mutate documents or database records.
- **Strictly** collects authorized project and content intelligence, enforces tenant isolation, normalizes schemas, tracks provenance, budgets tokens, and produces pure structured data.

```text
SEO Strategy
     \
Keywords
      \
Content Map
       \
SEO Guide
        \
Content Brief ---- Brand Rules
          \
       Internal Links
            \
Website/Crawl
             \
Existing Pages
              \
Current Document
                ↓
       ContentAgentContext
                ↓
       Prompt Builder
                ↓
          AI / Agent
```

---

## 2. Context Sources

The system integrates data across domain models using the strongest existing relational ownership:

| Context Area | Underlying Database Models | Scoping Predicates |
|---|---|---|
| **Request** | Caller arguments (`document_id`, `user_message`, `selected_block_id`, `selected_text`) | `document.id`, `document.project_id`, `document.organization_id` |
| **Project** | `Project` via `ProjectService` | `projects.id`, `projects.organization_id` |
| **Website** | `Website` | `websites.id`, `websites.organization_id`, `websites.project_id` |
| **SEO Strategy** | `SEOStrategy`, `SEOStrategyVersion` | `strategy.organization_id`, `strategy.project_id`, matching `current_version` |
| **Keywords** | `Keyword`, `KeywordCluster`, `KeywordClusterMember` | `keywords.organization_id`, `keywords.project_id`, normalized keyword match |
| **Content Map** | `PlannedContentPage`, `ContentPillar`, `Topic`, `ContentMapNode`, `ContentMapEdge` | `organization_id`, `project_id`, `page_id == document.page_id` |
| **SEO Guide** | `SEOGuide` | `seo_guides.organization_id`, `seo_guides.project_id`, `page_id == document.page_id` |
| **Content Brief** | `ContentBrief` | `content_briefs.organization_id`, `content_briefs.project_id`, `brief_id` / `page_id` |
| **Brand Rules** | `ContentBrief.brand_requirements` | Extracted directly from brief JSON |
| **Internal Linking** | `LinkOpportunity`, `PageRelationship`, `ContentBrief.internal_link_targets` | `organization_id`, `project_id`, `source_page_id` / `target_page_id == document.page_id` |
| **Website / Crawl** | `ContentPage` (indexed pages) | `content_pages.organization_id`, `content_pages.project_id`, bounded evidence |
| **Existing Pages** | `PlannedContentPage.existing_page_id` -> `ContentPage` | `content_pages.organization_id`, `content_pages.project_id` |
| **Current Document** | `ContentDocument` | `content_documents.id`, `organization_id`, `project_id` |
| **Conversation** | `ContentChatMessage` | `content_chat_messages.document_id`, latest 6 turns |

---

## 3. Context Structure

`ContentAgentContext` is defined in `apps/api/app/domains/ai/context.py` with 18 distinct sections:

```text
ContentAgentContext
├── request                     (task type, user prompt, selection, full_doc flag, timestamp)
├── project                     (project ID, organization ID, metadata)
├── website                     (website ID, base URL, normalized host, locale, settings)
├── seo_strategy                (business name/desc, industry, audience, products, services, markets, goals, competitors, priority topics)
├── keyword_context             (primary keyword metrics, secondary keywords metrics, cluster info, member keywords)
├── content_map                 (current planned page, pillar, topic, cluster, sibling pages, graph nodes/edges)
├── seo_guide                   (primary/secondary keywords, intent, audience, title/meta/URL guidance, target word count, outline, seo_rules)
├── content_brief               (complete brief parameters, required topics, key entities, questions, link targets, source requirements)
├── brand_rules                 (tone, voice, style, words to avoid, formatting rules)
├── internal_linking            (approved targets, link opportunities with anchors/reasons, page relationships)
├── website_context             (website identity, bounded crawled page snippets/headings)
├── existing_pages              (related existing page evidence)
├── current_document            (document ID, title, slug, word count, versions, structured blocks, truncation flags)
├── selection                   (selected block ID, selected text, focused block, surrounding context blocks)
├── conversation                (structured chat history with roles and timestamps)
├── resolved_intent             (deterministic intent + resolved_intent_source)
├── resolved_audience           (deterministic audience + resolved_audience_source)
├── entities                    (deduplicated key entities across Brief & Guide)
├── questions                   (questions to answer from Brief)
├── content_requirements        (deduplicated requirements across Brief & Guide)
├── source_requirements         (external source requirements from Brief)
├── competitors                 (competitors from active SEO strategy)
├── provenance                  (exact database IDs, version numbers, and sources)
└── budget                      (max_token_budget, estimated_tokens, truncated, truncated_sections)
```

---

## 4. Source Precedence

Factual fields that can appear across multiple entities are resolved using explicit deterministic precedence:

### Search Intent Precedence
1. `ContentBrief.search_intent` (if not empty and != `"UNKNOWN"`)
2. `SEOGuide.search_intent` (if not empty and != `"UNKNOWN"`)
3. `PlannedContentPage.intent` (if not empty and != `"UNKNOWN"`)
4. Primary `Keyword.intent` (if not empty and != `"UNKNOWN"`)
5. If missing everywhere: **`None`** (never invented).

### Target Audience Precedence
1. `ContentBrief.target_audience` (if not empty)
2. `SEOGuide.target_audience` (if not empty)
3. `SEOStrategy.strategy_data.audience` (formatted summary of segments and personas)
4. If missing everywhere: **`None`** (never invented).

### Keywords Precedence
1. Primary keyword candidate: `ContentBrief.primary_keyword` > `SEOGuide.primary_keyword` > `PlannedContentPage.primary_keyword`.
2. Normalized query lookup against `Keyword` table to fetch verified volume, difficulty, CPC, and intent confidence.
3. If not in DB: keyword string preserved with `None` for metrics. Never fabricate metrics.

---

## 5. Authorization Boundaries

- **Tenant Isolation:** Every context query explicitly enforces `organization_id == document.organization_id` and `project_id == document.project_id`.
- **Actor RBAC:** When an `AuthenticatedUser` is passed, `ProjectService.get_model(session, actor, project_id, PermissionCode.CONTENT_READ)` is checked before any domain query executes.
- **Relational Integrity:** Child and join tables without direct organization/project columns (such as `KeywordClusterMember` or `PageKeyword`) are strictly joined to parent tables carrying tenant scoping predicates.

---

## 6. Token Budget & Pruning Order

`ContentAgentContextBuilder` enforces `max_token_budget` using deterministic token estimation (~4 characters per token).

When `estimated_tokens > max_token_budget`, context is pruned in strict priority order:

### Priority Tier 3: Supporting Context (Pruned First)
1. Crawled website snippets and raw headings (`website_context.crawled_pages`)
2. Content map graph edges and non-essential nodes (`content_map.graph_edges`, `content_map.graph_nodes`)
3. Competitors list (`competitors`, `seo_strategy.competitors`)
4. Older conversation history (trims older turns, retaining the newest 1-2 messages)
5. Related existing pages (`existing_pages.pages`)
6. Detailed strategy matrices (products, services, markets, goals)

### Priority Tier 2: High Priority Context (Pruned Only if Still Over Budget)
7. Sibling pages beyond top 2
8. Link opportunities beyond top 2
9. Secondary keywords beyond top 3
10. Required topics beyond top 5
11. SEO Guide outline sections beyond top 3

### Priority Tier 1: Required Context (NEVER Pruned)
- User task / request
- Selected text and focused block (`selection.selected_text`, `selection.selected_block`)
- Core document essential blocks
- Content Brief essentials
- Primary keyword
- Resolved search intent
- Resolved target audience
- Brand rules

---

## 7. Truncation Observability

Truncation is never silent:
- `budget.truncated`: boolean flag indicating whether any section was pruned.
- `budget.truncated_sections`: explicit list of pruned section names (e.g. `["website_crawl_evidence", "competitors", "older_conversation_history"]`).
- `budget.estimated_tokens`: final token estimation.
- `current_document.truncated`: boolean flag indicating whether document blocks were capped for outline mode.

---

## 8. Provenance

All source entities are recorded in `provenance`:
- `strategy_id`, `strategy_version`, `strategy_source`
- `brief_id`, `brief_version`, `brief_source`
- `guide_id`, `guide_version`, `guide_source`
- `page_id`, `page_source`
- `website_id`, `document_id`
- `keyword_ids`: list of UUIDs for matching inventory records
- `cluster_id`: UUID of associated keyword cluster
- `opportunity_ids`, `relationship_ids`, `crawled_page_ids`
- `intent_source`: name of the entity providing search intent
- `audience_source`: name of the entity providing audience
- `collected_at`: UTC timestamp of context assembly

---

## 9. Missing-Data Behavior & Database Truth vs. Presentation Defaults

`ContentAgentContext` preserves pure database truth:
- If a brand tone is not specified: `context.brand_rules.tone = None`
- If no competitors are defined: `context.competitors = []`
- If no intent or audience is set: `context.resolved_intent = None`, `context.resolved_audience = None`

**Legacy AI Editor Compatibility:**
Presentation fallbacks (such as `"Professional, clear, authoritative"`, `"Knowledgeable expert"`, or target word count fallback `1500`) are applied **exclusively** inside `ContextBuilderService.render_editor_messages()`. This guarantees that legacy editor prompts and tests continue to work without corrupting the clean structured context.

---

## 10. Consumers

The context builder is reusable across three distinct consumers:
1. **AI Editor:** Calls `ContextBuilderService.build_context()`, which delegates to `build_agent_context()` and transforms the result into `(list[AIMessage], context_snapshot)`.
2. **Content Agent Loop (Future Phase):** Calls `ContentAgentContextBuilder.build_agent_context()` to receive structured data for agent tool selection and observation.
3. **Content Harness (Future Phase):** Calls `ContentAgentContextBuilder.build_agent_context()` for isolated prompt evaluation, testing, and scoring.
