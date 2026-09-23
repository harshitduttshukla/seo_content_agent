# V3 Step 0: Foundations & Data Models

**Date**: 2026-09-18
**Status**: Implemented

## Overview

This document describes the implementation of **Step 0: Foundations & Data Models** of the V3 SaaS Handoff. As specified in `seo-geo-system-handoff-v3.md`, Step 0 establishes the core infrastructure for V3 without modifying or breaking the existing Phase 1–6 functionality.

The focus is exclusively on the data model, database schema, and domain invariants. No business logic, endpoints, or complex state machines were fully implemented in this step.

## Domain Module Additions

We created four new domain modules alongside existing Phase 1–6 domains. Each owns its respective V3 entities.

### 1. Canvas (`app/domains/canvas`)

Provides the central strategic framework defining what the product does and for whom.

- **Canvas**: Supports self-referential inheritance (`parent_id`) for company-level vs. product-level differentiation. Contains typed anchor models for Company, Persona, Use Case, Alternative, and Category.
- **Argument**: Strategic building blocks for the canvas (Sub-Problem, Differentiation Pillar, Capability, Benefit). Supports inheritance and overrides (`inherited_from`, `override`).
- **Claim**: The atomic units of content that back arguments. Implements a full version chain (`superseded_by`) and is strictly validated against the `ClaimRow` enum (e.g., capability, pitch). Claims track approval state and market-level overrides.
- **Area**: A Canvas-scoped product-tree node with a parent relation, readable `name`, and optional `default_argument_id`. Areas are tenant/RLS scoped and Demand Nodes reference them through a nullable foreign key.

### 2. Demand (`app/domains/demand`)

Consolidates both SEO keywords and prompt demand into a unified scoring model.

- **DemandNode**: Supports two types: `keyword` and `prompt`.
- **Scoring**: Validates different formulas for each type. Prompts use `citation_gap × platforms` while keywords rely on `volume`, `competitor_gap`, and `funnel_weight`.

### 3. Content Cards (`app/domains/content_cards`)

The "travelling object" that moves across the V3 lifecycle (Strategy → Content Hub → Production → Live → Iteration Lab).

- **ContentCard**: Exists as a distinct entity from the old `PlannedContentPage` to accommodate the V3 9-state machine (`backlog` to `live`).
- **Dual-Primary Demand**: Follows V3 §4.7 to allow a card to have both a `primary_demand_id` (keyword) and a `primary_prompt_id` (prompt).
- **Market Variants**: Utilizes the `variant_of` self-referential key and typed `Market` objects for localization.

### 4. Job Runs (`app/domains/job_runs`)

Universal model-call audit log replacing the previous disparate execution tracking.

- **JobRun**: Validates `prompt_version` as a mandatory, strictly non-nullable field to guarantee provenance.
- **Polymorphism**: Uses `entity_type` and `entity_id` for flexible association with any domain object. Tracks token usage, latency, and costs for the five planned production calls (Outline, Draft, QA, Repair, Regen).

### 5. Projects Configuration (`app/domains/projects`)

- **Workspace Config**: Added the `workspace_config` JSONB column to the `Project` model.
- **Pydantic Validation**: Backed by a heavily typed `WorkspaceConfig` schema covering scoring weights, word budgets, market arrays, auto-approval gates, and thresholds. This separates V3 configs from the legacy `settings` dict.

## Database Migrations & Security

All models were introduced in a single migration (`20260918_0011_v3_step0_foundations.py`).

- **Tenant Isolation**: Every project-scoped table utilizes the standard composite foreign key `(organization_id, project_id) → projects`.
- **Row-Level Security (RLS)**: Enforced via `app_has_project_access()` for every new table, mimicking the pattern established in Phase 1.
- **Backwards Compatibility**: Existing tables were not modified, except for the additive `workspace_config` column on the `projects` table.

## Deviations and Clarifications

- **ContentCard vs PlannedContentPage**: Rather than altering `PlannedContentPage` and breaking existing pipelines, `ContentCard` was created as a standalone table. This perfectly models the new 9-step state machine without causing regressions.
- **Python-level Defaults**: In SQLAlchemy 2.0, column defaults like `version = 1` are not immediately visible in Python before flush. Tests were structured to respect this ORM behavior, either by explicit initialization or bypassing un-flushed assertions.

## Next Steps

With Step 0 completed, the foundation is ready for **Step 1: Canvas & Strategy Layer (API + Basic UI)**. Step 1 will introduce the services and endpoints to manipulate these entities, specifically focusing on CRUD for Canvas, Argument, and Claim entities.
