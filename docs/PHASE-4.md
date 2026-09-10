# Phase 4 — Content Map, SEO Guide & Internal Linking Architecture

## Overview

Phase 4 bridges the gap between strategic SEO intelligence (Phase 3) and content drafting/production (Phase 5). It establishes the formal, deterministic content architecture and operating rules for all domain pages:

1. **What pages should exist?** Planned pages inventory combining new strategic opportunities, cluster-targeted content, and existing live crawled URLs.
2. **Which keywords does each page target?** Primary target keyword mapping plus secondary keywords with priority and role assignments.
3. **Which pages belong to which topic and content pillar?** Hierarchical taxonomy mapping pages to keyword clusters, sub-topics, and overarching business content pillars.
4. **Which pages already exist vs. need to be created?** Clear segmentation between live crawled pages (`EXISTING`), net-new creation candidates (`PLANNED`), imported pages (`IMPORTED`), and redirected legacy pages (`REDIRECTED`).
5. **Which pages support other pages?** Formalized page relationships (`PARENT_CHILD`, `SUPPORTING_PILLAR`, `SIBLING_CROSS_LINK`, `CONTEXTUAL_REFERENCE`).
6. **How should pages be connected internally?** Governed internal linking engine detecting semantic link opportunities, enforcing link limits, preventing self-links, and diagnosing orphan pages.
7. **What SEO rules and outlines govern page production?** Governed, immutable SEO Guides specifying target audience, search intent, title/meta rules, character limits, outline heading hierarchies (H1 -> H2 -> H3), required topic checklists, and key entities.

---

## Implemented Domain Services & Architecture

### 1. Planned Content Pages (`app/domains/content`)
- `PlannedContentPage`: Multi-tenant entity representing pages to write or optimize.
  - Page Types: `EXISTING`, `PLANNED`, `IMPORTED`, `REDIRECTED`.
  - Content Types: `PILLAR_PAGE`, `CLUSTER_PAGE`, `SUPPORTING_PAGE`, `LANDING_PAGE`, `SERVICE_PAGE`, `PRODUCT_PAGE`, `BLOG_POST`, `GUIDE`, `COMPARISON`, `FAQ`.
  - Status Lifecycle: `PROPOSED` -> `PLANNED` -> `APPROVED` -> `IN_PROGRESS` -> `DRAFT` -> `PUBLISHED` -> `ARCHIVED`.
  - Search Intent & Business Value: Intent taxonomy (`INFORMATIONAL`, `COMMERCIAL`, `TRANSACTIONAL`, `NAVIGATIONAL`), priority (1-5), and strategic business value score (0-100).
  - Primary & Secondary Keywords: Direct link to primary target keyword, plus `PageKeyword` relational entries for secondary search queries.
  - Opportunity Conversion: Direct 1-click promotion of approved Phase 3 `ContentOpportunity` records into active `PlannedContentPage` models.

### 2. Visual Content Map & Layout (`app/domains/content_map`)
- `ContentMapNode`: Multi-layer node projections (`PILLAR`, `TOPIC`, `CLUSTER`, `PAGE`) with persistent X/Y coordinates, custom styling, status badges, inbound/outbound link counts, and cannibalization flags.
- `ContentMapEdge`: Directed edges modeling structural hierarchy and semantic internal link relationships.
- `ContentArchitectureVersion`: Immutable architectural snapshots recording graph state, node count, edge count, timestamp, user authorship, and changelog.
- `validate_architecture()`: Deterministic validation engine detecting:
  - Unmapped keyword clusters lacking a target page.
  - Planned pages without cluster assignments.
  - Content pages missing primary target keywords.
  - Topics without keyword clusters and pillars without sub-topics.
  - Keyword cannibalization collisions across pages.
  - Orphan pages with zero inbound links.
  - Broken relationships targeting non-existent pages.

### 3. SEO Guides & Outline Specifications (`app/domains/seo`)
- `SEOGuide`: Structured rulebook governing content creation per page.
  - Recommended & Meta Titles: Google SERP snippet preview with character length alerts (50-60 chars title, 135-160 chars meta description).
  - Recommended URL: Concised, lowercase, hyphenated slug guidelines.
  - Structured Outline: Strict heading hierarchy (`H1` -> `H2` -> `H3` -> `H4`) with required status and draggable reordering.
  - Secondary Keywords & Entities: Required topics checklist and semantic entities from knowledge.
  - SERP & Content Requirements: Actionable instructions derived from top search competitor gaps.
- `SEOGuideVersion`: Immutable version history snapshot created upon formal human approval (`PROPOSED` -> `APPROVED`). Ensures writers draft against frozen specifications.

### 4. Internal Linking Architecture (`app/domains/internal_linking`)
- `PageRelationship`: Architectural links connecting source and target pages (`PARENT_CHILD`, `SUPPORTING_PILLAR`, `SIBLING_CROSS_LINK`, `CONTEXTUAL_REFERENCE`).
- `LinkOpportunity`: Algorithmic link suggestions scored by a multi-signal heuristic:
  - Cluster Co-membership (+0.40): Pages sharing topic clusters.
  - Topical Relevance (+0.25): Pages belonging to the same pillar.
  - Primary Keyword in Title/Context (+0.20): Lexical semantic match.
  - Intent Progression (+0.15): Natural journey from Informational guide to Commercial/Transactional product.
  - Strategic Value Boost (+0.10): High business value target pages.
- Governance Lifecycle: `PROPOSED` -> `APPROVED` (automatically activates a `PageRelationship`) or `REJECTED`.
- Orphan Page Remediation: Dynamic detection of pages with zero incoming internal links and 1-click relationship creation.

---

## API Endpoints Summary

| Domain | Method | Endpoint | Description |
|---|---|---|---|
| **Content Pages** | `POST` | `/api/v1/projects/{project_id}/content-pages` | Create new planned content page |
| **Content Pages** | `GET` | `/api/v1/projects/{project_id}/content-pages` | List planned content pages with filters |
| **Content Pages** | `POST` | `/api/v1/projects/{project_id}/content-opportunities/{opp_id}/convert-to-page` | Convert Phase 3 opportunity into page |
| **Content Pages** | `GET` | `/api/v1/content-pages/{page_id}` | Get single planned content page detail |
| **Content Pages** | `PUT` | `/api/v1/content-pages/{page_id}` | Update planned content page |
| **Content Pages** | `DELETE` | `/api/v1/content-pages/{page_id}` | Delete planned content page |
| **Content Pages** | `GET` | `/api/v1/content-pages/{page_id}/keywords` | List secondary keywords assigned to page |
| **Content Pages** | `POST` | `/api/v1/content-pages/{page_id}/keywords` | Assign secondary keyword with role |
| **Content Pages** | `DELETE` | `/api/v1/content-pages/{page_id}/keywords/{keyword_id}` | Remove keyword assignment |
| **Content Map** | `GET` | `/api/v1/projects/{project_id}/content-map` | Project full IA graph (nodes, edges, stats) |
| **Content Map** | `POST` | `/api/v1/projects/{project_id}/content-map/generate` | Auto-generate initial map from Phase 3 |
| **Content Map** | `PUT` | `/api/v1/projects/{project_id}/content-map/layout` | Save customized canvas node coordinates |
| **Content Map** | `GET` | `/api/v1/projects/{project_id}/content-map/validation` | Run deterministic architecture validation |
| **Content Map** | `POST` | `/api/v1/projects/{project_id}/content-map/versions` | Create immutable architecture snapshot |
| **Content Map** | `GET` | `/api/v1/projects/{project_id}/content-map/versions` | List architecture version snapshots |
| **SEO Guides** | `GET` | `/api/v1/content-pages/{page_id}/seo-guide` | Get or initialize SEO guide for page |
| **SEO Guides** | `PUT` | `/api/v1/content-pages/{page_id}/seo-guide` | Update outline, keywords, and rules |
| **SEO Guides** | `POST` | `/api/v1/content-pages/{page_id}/seo-guide/approve` | Approve guide & generate immutable version |
| **SEO Guides** | `GET` | `/api/v1/content-pages/{page_id}/seo-guide/versions` | List approved guide version history |
| **Linking** | `GET` | `/api/v1/projects/{project_id}/page-relationships` | List architectural page relationships |
| **Linking** | `POST` | `/api/v1/projects/{project_id}/page-relationships` | Create governed page relationship |
| **Linking** | `DELETE` | `/api/v1/projects/{project_id}/page-relationships/{id}` | Delete page relationship |
| **Linking** | `GET` | `/api/v1/projects/{project_id}/link-opportunities` | List proposed internal link suggestions |
| **Linking** | `POST` | `/api/v1/projects/{project_id}/link-opportunities/analyze` | Run semantic link opportunity detector |
| **Linking** | `POST` | `/api/v1/projects/{project_id}/link-opportunities/{id}/approve` | Approve opportunity -> active relationship |
| **Linking** | `POST` | `/api/v1/projects/{project_id}/link-opportunities/{id}/reject` | Dismiss link opportunity |
| **Linking** | `GET` | `/api/v1/projects/{project_id}/orphan-pages` | Audit pages with zero inbound links |
| **Linking** | `GET` | `/api/v1/content-pages/{page_id}/internal-links` | Get inbound/outbound links summary for page |

---

## Verification & Quality
- **Python Unit & API Tests**: 46 passed (`test_phase4_api.py`, `test_phase4_algorithms.py`, and full backend test suite).
- **Python Linting & Formatting**: Clean across all 136 files (`ruff check .` and `ruff format --check .`).
- **TypeScript Type Safety**: 0 errors (`tsc --noEmit` in `apps/web`).
- **Frontend Component Tests**: 24 passed across 6 test suites (`vitest run` in `apps/web`).
- **Next.js Production Build**: Succeeded with all static & dynamic routes optimized (`next build`).
- **Database Migration**: `20260901_0004_phase4_content_map_seo_linking.py` with multi-tenant foreign keys, composite constraints, and rollback plans.
