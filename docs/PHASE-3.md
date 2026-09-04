# Phase 3 — SEO Strategy, Keyword Intelligence & Content Architecture

## Overview

Phase 3 delivers the foundational SEO intelligence layer of the platform. It transforms raw business context, crawled website inventory, keyword data, and search intent into a structured, explainable, and deterministic content architecture.

### Key Philosophy
- **"Keywords are Not Pages"**: Search queries are gathered in a normalized keyword universe and clustered into topics. Multiple queries map to a single cluster or page target.
- **Deterministic by Default**: Intent classification, business value formulas, priority scores, keyword clustering, and keyword-to-page mappings run with deterministic, explainable algorithms. Selective AI proposals are subject to human review.
- **Governed Human Review**: Keyword clusters, page mappings, and content gap recommendations use an explicit approval lifecycle (`proposed` -> `reviewed` -> `approved` / `rejected`). High-impact operations are never automated without review.
- **Immutable Strategy History**: Every change to project strategy creates an immutable, audited version snapshot.

---

## Implemented Domain Services & Architecture

### 1. SEO Strategy (`app/domains/strategy`)
- `SEOStrategy`: Tenant-scoped strategy entity tied to project.
- `SEOStrategyVersion`: Immutable version history recording `version`, `created_by_id`, `change_summary`, and full JSON snapshot of business context, products, services, audience, and SEO objectives.
- Integration with keyword scoring: Products and strategic topics feed directly into the business value keyword formula.

### 2. Keyword Intelligence & Universe (`app/domains/keywords`)
- `Keyword`: Canonical keyword inventory with NFKC lowercase normalization, search volume, difficulty (KD), CPC, deterministic search intent (`INFORMATIONAL`, `COMMERCIAL`, `TRANSACTIONAL`, `NAVIGATIONAL`, `LOCAL`), funnel stage (`TOFU`, `MOFU`, `BOFU`), explainable business value score (0-100), and composite priority score (0-100).
- `KeywordImport` & `KeywordImportRow`: High-throughput CSV parser supporting UTF-8/Latin-1 encodings, custom column header aliases, deduplication, and row-level error reporting.

### 3. Deterministic Keyword Clustering (`app/domains/keywords/clustering.py`)
- Lexical & semantic similarity using token Jaccard similarity with expanded SEO stop-word filtering, root token overlap bonuses, and phrase containment.
- `ClusteringRun` & `KeywordCluster`: Groups keywords into clusters, automatically selects the primary target keyword based on search volume and priority, calculates overall cluster opportunity scores, and generates human-readable rationale.
- Cluster management: Merge clusters and move keywords between clusters.

### 4. Content Architecture & Gaps (`app/domains/content`)
- `ContentPillar` & `Topic`: Hierarchical strategic pillars and topics.
- `KeywordPageMapping`: Deterministic semantic matcher mapping keywords against crawled live website pages (URL slug, Title tag, H1 headings, cleaned body content). Classifies mapping types:
  - `PRIMARY_TARGET`
  - `SECONDARY_TARGET`
  - `NEW_PAGE_REQUIRED`
- Cannibalization Detection: Scans live site inventory to detect when multiple pages target competing Title or H1 keywords.
- `ContentOpportunity`: Generates governed content gap recommendations (`NEW_PAGE`, `UPDATE_EXISTING_PAGE`) with human review workflow (`proposed`, `approved`, `rejected`).
- `ContentArchitectureGraph`: Generates node/edge graph projections (Pillars -> Topics -> Clusters -> Target Pages) formatted for React Flow.

---

## API Endpoints Summary

| Domain | Method | Endpoint | Description |
|---|---|---|---|
| **Strategy** | `GET` | `/api/v1/projects/{project_id}/strategy` | Fetch current active strategy |
| **Strategy** | `PUT` | `/api/v1/projects/{project_id}/strategy` | Update strategy & create immutable version |
| **Strategy** | `GET` | `/api/v1/projects/{project_id}/strategy/versions` | List all strategy version snapshots |
| **Keywords** | `POST` | `/api/v1/projects/{project_id}/keywords` | Create single keyword with intent/scoring |
| **Keywords** | `GET` | `/api/v1/projects/{project_id}/keywords` | List/filter keywords by volume, difficulty, intent |
| **Keywords** | `POST` | `/api/v1/projects/{project_id}/keywords/import` | Ingest CSV file |
| **Clusters** | `POST` | `/api/v1/projects/{project_id}/clustering-runs` | Run deterministic clustering algorithm |
| **Clusters** | `GET` | `/api/v1/projects/{project_id}/clusters` | List semantic clusters with members |
| **Clusters** | `POST` | `/api/v1/projects/{project_id}/clusters/merge` | Merge multiple clusters |
| **Clusters** | `POST` | `/api/v1/projects/{project_id}/clusters/move-keywords` | Move keywords between clusters |
| **Architecture** | `POST` | `/api/v1/projects/{project_id}/content-pillars` | Create content pillar |
| **Architecture** | `GET` | `/api/v1/projects/{project_id}/content-pillars` | List content pillars |
| **Architecture** | `POST` | `/api/v1/projects/{project_id}/topics` | Create topic under pillar |
| **Architecture** | `GET` | `/api/v1/projects/{project_id}/topics` | List topics |
| **Mappings** | `POST` | `/api/v1/projects/{project_id}/keyword-mappings/analyze` | Analyze keyword-to-page mappings against site |
| **Mappings** | `GET` | `/api/v1/projects/{project_id}/keyword-mappings` | List keyword page mappings |
| **Cannibalization** | `GET` | `/api/v1/projects/{project_id}/cannibalization-warnings` | Get multi-page keyword collision warnings |
| **Opportunities** | `GET` | `/api/v1/projects/{project_id}/content-opportunities` | List content gap recommendations |
| **Opportunities** | `PUT` | `/api/v1/projects/{project_id}/content-opportunities/{id}` | Approve/reject opportunity |
| **Graph** | `GET` | `/api/v1/projects/{project_id}/content-architecture/graph` | Fetch React Flow projection data |

---

## Verification & Quality
- **Python Unit & API Tests**: 35 passed (`tests/unit/test_phase3_algorithms.py`, `tests/api/test_phase3_api.py`, `tests/contract/test_openapi.py`).
- **Python Linting & Typing**: `ruff check`, `ruff format --check`, and `mypy` running with zero errors.
- **Frontend Typecheck & Component Tests**: 18 passed (`vitest run`, `tsc --noEmit`).
- **Database Migration**: `20260901_0003_phase3_seo_strategy_keywords.py` with multi-tenant foreign keys, composite indices, check constraints, and rollback instructions.
