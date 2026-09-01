# Internal Linking Architecture

## 1. Objective and boundaries

Internal linking connects structured content architecture to actual navigable pages. It distinguishes:

- planned relationships: pillar/topic/cluster/page support or target relations;
- recommended links: scored candidates tied to page/content/rule versions;
- approved links: reviewed edge and anchor intent;
- observed links: crawl evidence from a rendered/published page;
- published links: exact accepted content version/publication run.

These states are never conflated. A recommendation does not prove a link exists, and a crawled link does not prove it was approved.

## 2. Guide and edge model

The versioned linking guide defines eligibility (same site/locale, indexability/status), hierarchy expectations, anchor policies, minimum/maximum counts by content type, orphan and depth policy, hub/spoke behavior, exclusions, duplicate-link handling, commercial/editorial constraints, and score weights/thresholds.

Canonical `internal_links` fields are `organization_id`, `project_id`, ID, source/target page IDs, relationship type, anchor text/normalized anchor, relevance score, priority, status, origin, score/evidence JSON, source content version, guide version, approval actor/time, observed URL/location/time, and timestamps/revision. Database checks prevent self-links and cross-project edges. Duplicate policy is explicit per source/target/anchor/origin.

Relationship types begin with `parent`, `child`, `supports`, `targets`, `related`, `hub`, and `internal_link`. Hierarchy and semantic relationships may exist without an HTML link; `internal_link` represents link lifecycle.

## 3. Candidate generation

```text
source page + exact content version
-> resolve project/site/locale/link-guide version
-> select eligible targets (not self, active/indexable, allowed site/locale)
-> retrieve graph-near and semantic candidates
-> remove existing/duplicate/blocked/redirect-loop targets
-> compute interpretable features
-> rank and diversity-limit
-> identify viable source spans
-> optional AI anchor proposals
-> store recommendation with evidence/version
-> human accept/reject
-> editor patch proposal
-> published/crawl reconciliation
```

Candidate recall uses structured neighbors first (same topic/cluster, pillar-child, supporting cluster), then PostgreSQL full-text/vector similarity when enabled. SQL always prefilters tenant/project/site and status. No candidate is eligible solely because an embedding is close.

## 4. Initial scoring contract

The first offline-calibrated score is transparent and versioned:

```text
score =
    0.30 * semantic_relevance
  + 0.20 * graph_proximity
  + 0.15 * intent_complement
  + 0.10 * target_priority
  + 0.10 * orphan_or_low_indegree_boost
  + 0.10 * contextual_span_quality
  + 0.05 * freshness_need
  - duplicate_penalty
  - anchor_risk_penalty
  - navigation_depth_penalty
```

All normalized components are `[0,1]`; penalties are bounded and stored individually. The guide versions weights and thresholds per project/content type. Initial definitions:

- semantic relevance: hybrid keyword/entity/full-text/vector similarity grounded in page targets;
- graph proximity: same topic/pillar/typed relation, with distance decay;
- intent complement: whether the target answers a logical next task, not same-query duplication;
- target priority: normalized approved page priority;
- orphan boost: controlled benefit for eligible low-in-degree pages, never enough alone;
- contextual span quality: source passage exists and can accept a natural anchor;
- freshness need: optional benefit for important updated target/source relationships;
- penalties: existing equivalent link, excessive exact-match anchors, repeated target, conflicting CTA, redirect/broken/noncanonical target, excessive link density.

The score is a ranking aid, not a publish decision. Weights change only after labeled precision/acceptance evaluation and become a new algorithm version.

## 5. Anchor architecture

Anchor generation inputs the exact source span, target title/primary cluster/intent, guide rules, and recent anchor distribution. It returns multiple suggestions with rationale and risk flags. Validation rejects empty anchors, URLs when disallowed, misleading destination claims, forbidden phrases, excessive exact-match repetition, target title stuffing, and anchors already used at the same span. The editor applies an accepted suggestion as a range-anchored patch against the exact base version.

AI may phrase anchors but does not choose authorization, target eligibility, or publishing. Human-entered anchors use the same deterministic checks.

## 6. Integrity and reconciliation

- Source and target must belong to the same authorized project; cross-site links require explicit guide support.
- Source != target; canonical/redirect chains resolve to the canonical target before recommendation.
- Hierarchy cycles are handled in the content graph; link cycles are normal, but pathological reciprocal/sitewide patterns can be flagged.
- Crawl ingestion records observed href, anchor, location, response/canonical status, and crawl run. Reconciliation matches normalized source/target/anchor and marks approved links observed, missing, changed, or newly discovered.
- Page deletion/archive blocks new links and creates remediation findings for incoming approved/observed links.
- Publication never writes graph status to `observed`; only verified provider response or crawl evidence can.

## 7. API, jobs, and ownership

The internal-linking domain owns rules, edges, recommendation/scoring, and reconciliation. It reads public content/keyword/SEO snapshots and never edits editor documents directly. Endpoints are linking rules, page opportunities, edge create/decision, validation, and crawl reconciliation as listed in [API.md](API.md). Large candidate calculation and crawl work use version-keyed Celery jobs; small current-page deterministic checks may run inline.

## 8. Evaluation and tests

- Unit: feature normalization, weight/version math, eligibility, penalties, anchor policy, duplicate handling.
- Property/graph: never self/cross-tenant, no forbidden status, stable rank for stable snapshot, score bounds.
- Integration: recursive neighbors, vector/full-text filtered retrieval, same-project composite FKs, crawl reconciliation, idempotent recommendation runs.
- Evaluation: precision@k and NDCG on SEO/editor labels, acceptance/rejection reasons, orphan reduction without relevance loss, anchor diversity, false-positive rate on unrelated semantic similarity.
- Security: malicious content cannot create URLs/tool calls, knowledge/content instructions are data, tenant IDs in model output do not bypass scope.

Acceptance requires each recommendation to expose target, source location, relationship, total and component scores, evidence, algorithm/guide/content versions, and risks; a user can accept/reject; application is a versioned editor proposal; and no recommendation publishes automatically.

