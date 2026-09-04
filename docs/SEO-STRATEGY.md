# SEO Strategy & Positioning Architecture

## Overview

The SEO Strategy module is the source of truth for all business positioning, product definitions, target audiences, and high-level organic objectives. It ensures that keyword intelligence, clustering, and content gap recommendations are anchored in commercial reality rather than abstract metrics.

## Data Model & Versioning

The strategy domain consists of:
- `seo_strategies`: Current pointer (`current_version`, `status`, `organization_id`, `project_id`).
- `seo_strategy_versions`: Immutable audit log storing:
  - `version`: Sequential integer.
  - `change_summary`: Explicit human-written summary explaining the reason for the update.
  - `created_by_id`: User ID of the editor.
  - `strategy_data`: JSONB payload conforming to `StrategyDataSchema`.

### Strategy Schema Structure
```json
{
  "business_context": {
    "business_name": "Acme SaaS",
    "description": "Enterprise content intelligence",
    "industry": "B2B Software",
    "locations": ["US", "Global"]
  },
  "audience": {
    "segments": ["Enterprise SEO Teams", "Content Directors"],
    "personas": [{ "name": "SEO Lead", "role": "Director", "pain_points": ["Content scaling"] }]
  },
  "products": [
    {
      "name": "Content Engine",
      "description": "Deterministic keyword clustering & content OS",
      "category": "Core Software",
      "priority": 1
    }
  ],
  "services": [],
  "seo_goals": [
    {
      "type": "LEAD_GENERATION",
      "description": "Rank in top 3 for transactional B2B content terms",
      "priority": 1
    }
  ],
  "brand_voice": "Authoritative, technical, clear, no fluff",
  "priority_topics": ["Keyword Clustering", "Content Architecture", "Internal Linking"]
}
```

## Downstream Integration

Strategy data is actively consumed by the Keyword Intelligence service:
- Product and service names are matched against search terms to compute a +15.0 strategic boost in `business_value_score`.
- Topic pillars inherit priorities and business goals defined in the active strategy.
