# API Architecture

## 1. Contract principles

FastAPI exposes resource-oriented HTTPS JSON under `/api/v1`. Pydantic v2 schemas are the public contract; SQLAlchemy models never cross the transport boundary. OpenAPI is committed/snapshotted in CI and generates TypeScript types for the Next.js application. Version `v1` changes additively; breaking semantic/schema changes require `/api/v2` or an explicitly negotiated media/version mechanism.

The frontend never imports Python implementation details. Recommended generation is `openapi-typescript` plus a small reviewed `fetch` transport rather than a large generated runtime. CI creates OpenAPI from the application without live dependencies, diffs the snapshot, regenerates types, and fails on drift or unreviewed breaking changes.

## 2. Request pipeline

```text
request ID -> size/content-type limit -> rate limit -> JWT verification
-> organization/project resolution -> resource authorization
-> Pydantic validation -> thin router -> service transaction
-> response mapper -> envelope -> audit/telemetry
```

Authentication uses OIDC access tokens with verified signature, issuer, audience, expiry, and key rotation. The route derives the internal user and memberships; request bodies may not choose an organization the token cannot access. Authorization evaluates action + role + tenant + project assignment + resource status.

## 3. Envelope and errors

Success:

```json
{
  "data": {"id": "98c6b9d9-02ae-4425-b6b1-40a7f5923144"},
  "meta": {"request_id": "req_01J..."},
  "errors": []
}
```

Failure:

```json
{
  "data": null,
  "meta": {"request_id": "req_01J..."},
  "errors": [
    {
      "code": "VERSION_CONFLICT",
      "message": "The resource changed; refresh and retry against the latest version.",
      "field": null,
      "details": {"current_revision": 7}
    }
  ]
}
```

Error messages are safe, actionable, and stable enough for UI mapping; `details` never contains stack traces, SQL, secrets, raw provider payloads, or foreign-tenant identifiers.

| HTTP | Use | Representative codes |
|---:|---|---|
| 400 | malformed semantics not expressible as field validation | `BAD_REQUEST`, `INVALID_CURSOR` |
| 401 | absent/invalid/expired authentication | `AUTHENTICATION_REQUIRED`, `TOKEN_INVALID` |
| 403 | authenticated but action denied on a known/disclosable scope | `PERMISSION_DENIED`, `APPROVAL_REQUIRED` |
| 404 | missing or inaccessible tenant resource | `RESOURCE_NOT_FOUND` |
| 409 | state/uniqueness/version conflict | `VERSION_CONFLICT`, `INVALID_TRANSITION`, `CANNIBALIZATION_CONFLICT`, `DUPLICATE_RESOURCE` |
| 412 | `If-Match`/precondition failed where HTTP preconditions are used | `PRECONDITION_FAILED` |
| 422 | Pydantic field/body validation | `VALIDATION_ERROR`, with field paths |
| 429 | actor/org/provider quota or rate limit | `RATE_LIMITED`, `QUOTA_EXCEEDED`; include `Retry-After` |
| 500 | unexpected internal failure | `INTERNAL_ERROR` and request ID |
| 502/503/504 | sanitized external/dependency/unavailable/timeout | `DEPENDENCY_ERROR`, `SERVICE_UNAVAILABLE`, `TIMEOUT` |

One FastAPI handler registry maps validation, domain, database, and adapter exceptions. Unexpected errors are logged with correlation IDs and returned as generic 500.

## 4. Pagination, filters, and sorting

- Use opaque cursor pagination for changing/large collections. `limit` defaults to 50, maximum 100.
- `meta` returns `next_cursor` and `has_more`; cursors are signed/versioned encodings of stable order fields and scope, not raw SQL offsets.
- Each endpoint allowlists filters and sort fields. Syntax uses simple query parameters such as `status=approved&intent=commercial&sort=-priority,title`.
- Stable sort always adds `id` as tie-breaker. Unsupported filters/sorts return 400, not ignored behavior.
- Offset pagination is allowed only for small static admin/reference sets and must be documented.
- Search terms are length-limited, normalized, parameterized, and never interpolated into SQL.

## 5. Concurrency, idempotency, and long operations

- Mutable resource responses expose `ETag` from resource revision/version. `PUT`, state transitions, document autosave, and approvals require `If-Match` or an explicit `base_version_id`.
- `PUT` is complete replacement of the editable representation. `PATCH` uses a documented JSON Patch or domain command; no implicit nested merge.
- `Idempotency-Key` is required for import/job creation, AI generation, approval execution, and publishing. It is scoped to actor/tenant/route, stores request hash and final response reference, and rejects the same key with a different body (`409`). Retention is endpoint-specific, at least 24 hours for ordinary jobs and longer than provider uncertainty for publishing.
- Work expected beyond roughly two seconds returns `202` with a durable job/run resource and `Location`. Polling uses backoff; optional SSE supplies progress but the database run remains canonical.
- Cancelling is a state transition request. It does not claim an external provider action was reversed.

## 6. Endpoint catalog

Request/response schemas use `Create`, `Update`, `Command`, `Summary`, and `Detail` suffixes. IDs are UUID strings. This catalog defines ownership and purpose; Phase implementation adds exact OpenAPI examples and permission strings.

### Organizations, projects, websites

| Method/path | Input -> output | Permission / notes |
|---|---|---|
| `POST /organizations` | `OrganizationCreate` -> `OrganizationDetail` | authenticated; bootstrap policy/rate limit |
| `GET /organizations` | filters/cursor -> memberships with org summaries | any member; only accessible orgs |
| `POST /organizations/{org_id}/members` | invite/role -> membership | `members.manage`; audited |
| `PATCH /organizations/{org_id}/members/{user_id}` | role/status command -> membership | `members.manage`; cannot remove last admin |
| `POST /projects` | org, name, locale -> project | `project.create` |
| `GET /projects` | org/status/cursor -> summaries | `project.read` |
| `GET /projects/{project_id}` | -> project detail | `project.read`; tenant-scoped lookup |
| `PUT /projects/{project_id}` | full settings + precondition -> detail | `project.update` |
| `POST /projects/{project_id}/websites` | canonical site -> website | `website.create` |
| `GET /projects/{project_id}/websites` | filters/cursor -> sites | `website.read` |
| `POST /websites/{website_id}/verify` | verification command -> job/result | `website.verify`; idempotent |

### Strategy, brand, and rules

| Method/path | Input -> output | Permission / notes |
|---|---|---|
| `GET /projects/{project_id}/strategy` | -> active/current strategy | `strategy.read` |
| `PUT /projects/{project_id}/strategy` | structured document + base version -> new draft | `strategy.write`; immutable version |
| `GET /strategy/{strategy_id}/versions` | cursor -> versions | `strategy.read` |
| `POST /strategy/{strategy_id}/versions/{version_id}/approve` | decision -> approved version | `strategy.approve`; conflict if stale |
| `GET/PUT /projects/{project_id}/brand-profile` | versioned profile | read/write permissions |
| `GET/POST /projects/{project_id}/brand-rules` | list/create versioned rule | `brand_rules.read/write` |
| `POST /brand-rules/{rule_id}/activate` | exact version decision -> active | `brand_rules.approve`; audit |
| `GET/POST /projects/{project_id}/seo-rules` | list/create rule | `seo_rules.read/write` |
| `POST /seo-rules/{rule_id}/activate` | exact version -> active | `seo_rules.approve` |
| `GET/POST /projects/{project_id}/linking-rules` | rule-set projection/change | `link_rules.read/write` |

The V3 strategy workspace currently exposes its canvas slice under `/api/v3`:

| Method/path | Input -> output | Permission / notes |
|---|---|---|
| `POST /canvases?organization_id={organization_id}&project_id={project_id}` | no body -> empty `CanvasFullResponse` | `strategy.write`; creates the single company canvas (`parent_id = null`); `409 COMPANY_CANVAS_EXISTS` if one already exists |
| `GET /canvases?organization_id={organization_id}&project_id={project_id}` | -> `CanvasListResponse` | `strategy.read`; tenant- and project-scoped |
| `GET /canvases/{canvas_id}?organization_id={organization_id}&project_id={project_id}` | -> `CanvasFullResponse` | `strategy.read`; tenant- and project-scoped |
| `POST /canvases/{canvas_id}/anchors?organization_id={organization_id}&project_id={project_id}` | `CanvasAnchorUpsertRequest` -> `CanvasFullResponse` | `strategy.write`; creates or replaces one typed company-level anchor |
| `POST /canvases/{canvas_id}/arguments?organization_id={organization_id}&project_id={project_id}` | `ArgumentCreateRequest` -> `CanvasFullResponse` | `strategy.write`; adds the next ordered argument and claims for supplied cells |
| `POST /canvases/{canvas_id}/claims?organization_id={organization_id}&project_id={project_id}` | `CanvasClaimCreateRequest` -> `CanvasFullResponse` | `strategy.write`; creates an unapproved v1 claim for a blank summary or argument cell |

### Keywords and content architecture

| Method/path | Input -> output | Permission / notes |
|---|---|---|
| `POST /projects/{project_id}/keyword-imports` | object/source mapping -> job | `keywords.import`; idempotency required |
| `GET /projects/{project_id}/keywords` | query/intent/status/cluster/sort/cursor -> keywords | `keywords.read` |
| `PUT /projects/{project_id}/keywords/{keyword_id}` | editable keyword fields -> keyword | `keyword.write`; normalized duplicates rejected; audited |
| `DELETE /projects/{project_id}/keywords/{keyword_id}` | -> deleted keyword identity | `keyword.write`; explicit UI confirmation; dependent assignments removed |
| `POST /projects/{project_id}/keyword-cluster-jobs` | keyword snapshot/config -> job | `clusters.generate` |
| `GET /projects/{project_id}/keyword-clusters` | filters/cursor -> clusters | `clusters.read` |
| `PUT /keyword-clusters/{cluster_id}/members` | complete member assignments + revision -> cluster | `clusters.write`; conflict analysis |
| `DELETE /projects/{project_id}/clusters/{cluster_id}` | -> deleted cluster identity | `keywords.write`; requires explicit UI confirmation; retains keywords |
| `POST /projects/{project_id}/pillars` | pillar -> detail | `content_map.write` |
| `POST /pillars/{pillar_id}/topics` | topic -> detail | `content_map.write` |
| `PUT /topics/{topic_id}/clusters` | assignments + revision -> topic | `content_map.write` |
| `POST /projects/{project_id}/pages` | planned page/target -> page/conflicts | `content.write` |
| `PUT /pages/{page_id}/target-clusters` | primary/supporting assignments -> result/conflicts | `content_map.write`; no silent collision |

### Content map, editor, validation, and links

| Method/path | Input -> output | Permission / notes |
|---|---|---|
| `GET /projects/{project_id}/content-map` | node/edge/status filters + optional revision -> graph | `content_map.read`; cacheable by revision |
| `POST /projects/{project_id}/content-map/commands` | typed add/move/relate command + graph revision -> graph delta | `content_map.write`; hierarchy cycle checks |
| `GET /pages/{page_id}` | -> page, current versions/status | `content.read` |
| `PUT /pages/{page_id}` | editable metadata + revision -> page | `content.write` |
| `POST /pages/{page_id}/briefs` | source versions/options -> immutable brief or job | `brief.write` |
| `GET /pages/{page_id}/document` | -> current TipTap JSON/version/hash | `content.read` |
| `PUT /pages/{page_id}/document` | document JSON + base version + idempotency -> new autosave version | `content.write` |
| `GET /pages/{page_id}/versions` | cursor -> version summaries | `content.read` |
| `GET /pages/{page_id}/versions/{version_id}` | -> immutable version | `content.read` |
| `POST /pages/{page_id}/versions/{version_id}/restore` | reason -> new version | `content.write`; never overwrites |
| `POST /pages/{page_id}/suggestions` | patch/rationale/source -> suggestion | `content.propose` |
| `POST /suggestions/{suggestion_id}/decision` | accept/reject + base precondition -> new version/decision | `content.write` |
| `POST /seo/analyses` | page/content + rule versions -> result or job | `seo.analyze`; deterministic/AI split |
| `GET /pages/{page_id}/link-opportunities` | filters -> scored recommendations | `links.read` |
| `POST /pages/{page_id}/internal-links` | proposed link -> edge | `links.write` |
| `POST /internal-links/{link_id}/decision` | approve/reject -> edge | `links.approve` |

### AI, knowledge, learning, publishing, and analytics

| Method/path | Input -> output | Permission / notes |
|---|---|---|
| `POST /ai/chat` | message, project, current resource, allowed context -> run/stream ref | `ai.read/propose`; tools separately authorized |
| `POST /ai/rewrite` | page/version/selection/instruction -> proposal run | `ai.propose`; never direct mutation |
| `GET /ai/runs/{run_id}` | -> run, sanitized context/proposals/tool summary | actor or audit permission |
| `POST /ai/runs/{run_id}/cancel` | -> state | run owner/admin; best effort |
| `POST /projects/{project_id}/knowledge-sources` | upload/source descriptor -> ingestion job | `knowledge.write`; file security |
| `GET /projects/{project_id}/knowledge-sources` | filters/cursor -> sources | `knowledge.read` |
| `POST /knowledge/search` | project, query, filters -> attributed chunks | `knowledge.read`; tenant-bound filters |
| `POST /learning/candidates` | evidence/proposed rule -> candidate | `learning.propose` |
| `GET /projects/{project_id}/learning-candidates` | status/type/cursor -> candidates | `learning.read` |
| `POST /learning/{candidate_id}/approve` | exact candidate/version/target -> approved rule version | `learning.approve`; audit, no auto-activation unless same approved command says so |
| `POST /publication-runs` | destination/page/version/action/approval -> run | `publish.execute`; high impact, idempotent |
| `GET /publication-runs/{run_id}` | -> sanitized status/external URL | `publish.read` |
| `POST /performance/imports` | integration/date window -> job | `analytics.import` |
| `GET /pages/{page_id}/performance` | range/dimensions -> metric series | `analytics.read` |
| `GET /projects/{project_id}/analytics` | range/views -> aggregates | `analytics.read`; bounded dimensions |
| `GET /jobs/{job_id}` | -> durable state/progress/result ref | permission inherited from referenced resource |
| `POST /jobs/{job_id}/cancel` | -> requested state | owning operation permission |

Delete operations are omitted until each resource's archive/retention semantics are specified. `publish_page` in the AI tool vocabulary maps to an approval-bound publication service; the model cannot directly call a general HTTP publish route.

## 7. Rate limits and quotas

Limits are layered by IP for unauthenticated/bootstrap traffic, actor, organization, and expensive operation class. Reads use token-bucket limits; AI, crawling, imports, and publish actions also use concurrency and daily quota controls. `429` includes retry metadata. Provider limits are translated without exposing account details. Admins can inspect usage; limit changes are audited. Redis may enforce fast counters, while durable billable/AI/job usage is recorded in PostgreSQL.

## 8. Webhooks and external callbacks

Future callbacks use adapter-specific paths, signature and timestamp verification, replay windows, raw-body size limits, provider event idempotency, and a durable receipt before asynchronous processing. They do not trust tenant/resource IDs from payloads without matching the stored integration. Outbound webhooks, if added, are signed, allowlisted, retried with bounded policy, and never contain document content unless explicitly configured.

## 9. Contract acceptance

An endpoint is complete only when its Pydantic request/response, permission, tenant path, error cases, concurrency/idempotency behavior, audit events, OpenAPI examples, service transaction, and success/cross-tenant/validation/conflict tests exist. Frontend generation drift is a release failure.
