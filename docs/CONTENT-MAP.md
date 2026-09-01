# Content Map and Graph Architecture

## 1. Purpose

The Content Map is a visual/query projection of canonical relational data. It helps users design and inspect the chain `Pillar -> Topic -> Keyword Cluster -> Page` plus supporting, target, related, and internal-link relationships. React Flow is a renderer and command surface; its node/edge array is not the source of truth.

## 2. Graph model

### Node types

| Type | Canonical entity | Required projection metadata |
|---|---|---|
| `pillar` | `content_pillars` | ID, name, status, priority/order, child counts |
| `topic` | `topics` | ID, name, pillar/parent, status, cluster/page counts |
| `cluster` | `keyword_clusters` | ID, name, intent, volume aggregate, priority, status, keyword count, target page |
| `page` | `content_pages` | ID, title, primary keyword/cluster, intent, volume, priority, status, SEO score components/version, incoming/outgoing link counts, website/URL |

Volume and SEO/link counts are versioned projections with `as_of`; they never silently replace source metrics/findings.

### Edge types

- `parent` / `child`: hierarchical inverse view; store one directed canonical relation.
- `supports`: one node contributes to another's coverage.
- `targets`: cluster -> canonical/supporting page assignment.
- `related`: typed symmetric semantic relation stored in canonical ID order or two directed projection edges.
- `internal_link`: directed page -> page edge with lifecycle from [INTERNAL-LINKING.md](INTERNAL-LINKING.md).

Pillar/topic hierarchy must be acyclic. Cluster/page targeting obeys cannibalization uniqueness. Internal-link cycles are allowed. Generic polymorphic edge storage is avoided for core integrity: canonical foreign keys live in their domain tables, and a union/read model projects them to graph edges.

## 3. Read contract

`GET /projects/{project_id}/content-map` accepts allowlisted node types, statuses, pillar/topic subtrees, search term, website, and optional depth/edge types. It returns:

```json
{
  "data": {
    "graph_revision": 42,
    "nodes": [{"id": "...", "type": "page", "data": {}, "position": null}],
    "edges": [{"id": "...", "type": "targets", "source": "...", "target": "...", "data": {}}],
    "layout": {"id": "...", "revision": 3}
  },
  "meta": {"request_id": "...", "has_more": false},
  "errors": []
}
```

Large graphs use subtree/filter requests and a `truncated` indicator with continuation/expansion tokens; the UI must not assume every project fits one response. Graph revision changes whenever canonical membership/relation/status relevant to the projection changes. ETag/cache key includes tenant, filters, graph revision, permission fingerprint, and projection schema version.

## 4. Command contract

React Flow gestures translate into explicit commands, never send arbitrary graph replacement:

- `create_pillar`, `create_topic`, `create_page`;
- `move_topic` (new parent/position);
- `assign_cluster_to_topic`;
- `assign_cluster_to_page` as primary/supporting;
- `relate_pages` / `remove_relation`;
- `archive_node` subject to dependency analysis;
- `save_layout` (separate from domain mutation).

Each command includes `graph_revision`, affected resource revisions, a client/idempotency key, and typed fields. The backend re-authorizes and validates invariants in the owning domain service, commits atomically, and returns a graph delta plus new revision. A stale or conflicting command returns 409 with enough safe current state to refresh; the UI does not last-write-win.

Dragging a node changes only layout coordinates. Structural reparenting requires an explicit accessible action/drop zone and confirmation when it changes target architecture.

## 5. Layout persistence

Layout is non-canonical presentation data: node ID -> `{x,y,collapsed,width?}` plus viewport, layout algorithm/version, owner (`user` or shared project), base graph revision, and revision. Missing/new nodes receive deterministic fallback layout. A layout cannot create/delete domain relationships. Shared layout updates use optimistic concurrency; users can reset without altering content architecture.

## 6. Frontend implementation boundary

`features/content-map` will contain graph query hooks, typed projection adapters, React Flow node/edge components, command palette, side panel, filters, accessible table/tree alternative, and layout state. It consumes generated OpenAPI types. Node components receive data only and cannot call APIs directly; commands go through feature services to centralize optimistic updates and rollback.

Performance tactics are progressive: filtered initial view, lazy child expansion, memoized node components, viewport culling provided by React Flow, batched metric updates, and web worker/ELK layout only after profiling. Graph modifications must work by keyboard and through the table/tree view; color is not the only status indicator.

## 7. Content architecture invariants

- Every topic belongs to one pillar and optionally one parent topic in the same pillar/project; no cycles.
- A cluster can support several topics only when relation type explains the view; one topic assignment may be marked primary.
- One active cluster has at most one canonical target page for a website/locale. Supporting pages must serve distinct sub-intent and may trigger review.
- A page may be planned before content exists and keeps stable identity through versions/publication.
- Archiving a pillar/topic with active descendants requires an explicit move/archive plan.
- Cross-project edges are forbidden. Cross-website page links require an enabled guide policy.
- Computed fields carry source/as-of/version and are not editable graph metadata.

## 8. Graph queries and future scaling

PostgreSQL recursive CTEs answer ancestors/descendants and cycle checks; indexed assignment/link tables answer neighbors and degrees. A service builds a typed union projection. Cache/read models may be introduced after measuring p95 query/render targets. Snapshot revision/outbox events allow incremental projection updates.

Consider a graph database only when representative production workloads demonstrate that bounded Postgres traversals/materialized projections cannot meet SLOs and the benefit exceeds dual-store consistency, tenancy, operations, migration, and skill costs. This requires a new ADR.

## 9. Tests and acceptance

- Domain/property tests: acyclic hierarchy, same-tenant edges, unique canonical targets, valid transitions, archive dependencies.
- Repository tests: recursive traversal, degree counts, filters, stable pagination, composite FKs, query plans at representative size.
- API/contract: projection schema, command discriminators, 409 refresh path, idempotency, ETag, permissions.
- UI: node variants, keyboard commands, accessible alternative, optimistic rollback, large filtered graph, stale conflict, layout isolation.
- E2E: create hierarchy, assign cluster/page, detect cannibalization, inspect page metadata, add approved link, persist layout.

The map is acceptable when the same canonical state produces consistent visual and tabular projections, layout never changes domain state, every structural mutation enforces invariants server-side, and graphs remain usable without rendering an unbounded project.

