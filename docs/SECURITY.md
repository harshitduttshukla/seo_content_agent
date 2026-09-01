# Security Architecture

## 1. Security objectives

Protect tenant confidentiality and integrity, prevent unauthorized/public AI side effects, preserve reviewable provenance, isolate knowledge and provider data, and recover safely from application or integration failure. The highest-risk assets are membership/permissions, unpublished strategy/content, source documents, provider/CMS credentials, approval records, AI/tool actions, publication state, and audit evidence.

Security is enforced at every boundary; hiding controls in the UI is never authorization.

## 2. Threat model summary

| Threat | Primary controls | Verification |
|---|---|---|
| IDOR/cross-tenant access | tenant keys, scoped repositories, composite FKs, non-disclosing 404, PostgreSQL RLS | negative API/repository/RLS tests for every resource |
| Role escalation/stale membership | internal membership source of truth, short token/session lifetime, permission intersection, cache invalidation | role matrix and revoke-during-session tests |
| Prompt/tool injection | retrieved content labeled data, strict tool schemas/allowlist, independent authorization, URL egress policy, approval gates | adversarial corpus and tool-denial tests |
| AI publishes/changes policy without review | proposal-only tools; exact single-use approval digest for high impact | approval expiry/replay/input-change tests |
| Malicious upload/parser exploit | private quarantine, size/type/signature validation, malware scan, sandboxed/time-limited parser, sanitized filename/output | malicious/polyglot/bomb fixture tests |
| Secret or sensitive-content leakage | secret manager references, log redaction, provider policy, least-context prompts, encrypted transport/storage | secret scanning and telemetry snapshot tests |
| SSRF through crawl/import/CMS | normalized URL, DNS/IP checks before and after redirect, private/link-local deny, egress allowlist, response limits | redirect/DNS rebinding/private-IP tests |
| Replay/duplicate external action | signed callbacks, idempotency, durable operation status, approval binding | duplicate webhook/publish tests |
| Supply-chain compromise | lockfiles, automated scanning, minimal images, signature/SBOM policy, reviewed upgrades | CI scanning and provenance checks |
| Data loss/corrupt migration | backups/PITR, expand-contract, tested restore, immutable versions/outbox/audit | scheduled restoration and migration tests |

## 3. Authentication

Use a standards-based OIDC provider. The API verifies JWT signature with cached/rotated JWKS, exact issuer/audience, expiry/not-before with bounded skew, and allowed algorithm. Identity key is `(issuer, subject)`, not email. Opaque tokens, if chosen by provider, use controlled introspection through an adapter. Browser session/refresh-token strategy is selected in Phase 1; refresh or provider credentials never enter client-readable storage.

Local development uses an explicit development identity adapter only in `APP_ENV=local/test`, cannot start in staging/production, and is visibly named as a dev/test mechanism. Do not implement custom passwords in MVP.

## 4. Authorization and tenant isolation

Authorization inputs are principal, organization, project assignment, permission string, resource ownership/status, and action context. Organization roles give a ceiling; project memberships may narrow scope. Services receive the authenticated `Principal`; body/path IDs are resolved inside its tenant scope.

Defense layers:

1. FastAPI authentication constructs an internal principal from verified identity and current membership.
2. Endpoint/action dependency checks coarse permission and project assignment.
3. Repository queries require organization/project and resource ID.
4. Domain services check status/invariant-specific permissions (approve/publish/last-admin).
5. Composite foreign keys prevent cross-tenant relationships.
6. PostgreSQL RLS before production uses transaction-local trusted tenant settings and a non-bypass application role.
7. Audit records outcome of privileged/denied activity.

Celery jobs store tenant/resource references and re-resolve authorization/policy appropriate to system work. A user-initiated delayed high-impact job revalidates actor membership and approval at execution.

## 5. AI tool permissions

| Level | Examples | Enforcement |
|---|---|---|
| Read | get strategy, search keywords/knowledge, get map/rules | ordinary resource read permission; bounded result |
| Propose | update strategy, rewrite, brief/outline, anchor suggestions | create proposal only; no canonical mutation; actor must have propose permission |
| High impact | publish page; future delete/active rule changes | exact human approval, current high-impact permission, immutable input version, idempotency, audit |

The registry exposes only task/role-allowed tools. Each invocation independently validates Pydantic input, re-resolves IDs in tenant scope, checks permission/effect, enforces timeout/quota, calls a declared domain service, validates output, and audits. The LLM never receives a database handle or generic HTTP/SQL/file-shell tool.

## 6. Prompt injection and knowledge isolation

- Source text, websites, metadata, alt text, comments, and model output are untrusted data. Prompts delimit and identify them; instructions inside them have no authority.
- Context retrieval applies organization/project/access-label filters before semantic ranking. It never retrieves globally then removes foreign hits in application memory.
- Embedding rows include tenant keys and source lineage; vector queries use same-tenant predicates and are covered by RLS/negative tests.
- Context manifests record source/version/hash. Answers/proposals cite these sources; hallucinated/missing IDs are rejected.
- Tool results expose the minimum fields and are redacted before returning to the model. High-impact secrets, approval tokens, and raw CMS credentials never enter context.
- Provider data-use/retention/training settings must meet deployment policy. Sensitive project classifications can disable certain providers/tasks.
- Deleting/revoking a source immediately marks it ineligible and invalidates context caches; background deletion removes chunks/vectors/objects according to retention.

## 7. API and browser security

- TLS everywhere; HSTS and secure headers at the edge. Restrictive CORS allowlist and allowed methods/headers.
- If browser auth uses cookies, set `Secure`, `HttpOnly`, appropriate `SameSite`, and CSRF tokens/origin checks for mutations. Bearer tokens still require XSS defenses.
- Strict request content type/size, Pydantic `extra=forbid`, bounded strings/lists, safe Unicode normalization where identifiers require it.
- React never injects unsanitized rendered HTML. TipTap JSON uses an allowlisted schema and derived HTML sanitizer. CSP disallows unsafe scripts and narrows connections/images/frames.
- Cursor/query parameters and sort/filter names are allowlisted; SQLAlchemy parameters only.
- Rate limits exist by IP/actor/org and expensive operation; quotas prevent cost abuse.
- Responses use safe errors and request IDs. No stack traces, SQL, secrets, foreign IDs, prompt text, or provider internals.

## 8. File, crawl, and object security

Upload flow is `quarantine -> validate declared/actual type and size -> malware scan -> isolated parser -> normalized output -> approved private storage`. Use random object keys, never user filenames; preserve sanitized display name separately. Buckets block public access and use encryption. Signed download URLs are short-lived, content-disposition safe, tenant-authorized at issuance, and not logged.

ZIP/PDF/DOCX parsing enforces decompression ratio, page/object/macro/external-reference limits, CPU/memory/time limits, and patched parser images. Reject unsupported active content.

Crawlers accept only authorized website scopes. Normalize and validate every initial/redirect URL, resolve DNS, block localhost/private/link-local/metadata networks and non-HTTP schemes, cap redirects/body/time/concurrency, recheck destination after redirect/DNS resolution, and use a controlled egress network.

## 9. Secrets, encryption, and privacy

- Secrets live in deployment secret manager; `.env` is local and ignored. Database stores provider/destination `secret_ref`, not secret material.
- Separate credentials/keys per environment and integration. Rotate on schedule and incident; use least-privilege DB, bucket, provider, and CMS scopes.
- Encrypt traffic in transit and managed database/object storage at rest. If threat/compliance needs it, add application-level envelope encryption for selected source/prompt fields under a documented key policy.
- AI logs/audits prefer IDs, hashes, counts, and redacted summaries. Define data classification and retention before production ingestion.
- Support export/deletion/legal hold through audited jobs. Erasure propagates to DB, object storage, vectors, cache, providers where applicable, and backups according to policy while retaining legally required minimal audit evidence.

## 10. Auditing and detection

Append-only audit events cover login/membership changes, permission denials, strategy/rule approvals, AI/tool attempts, proposal decisions, source upload/delete, connector/secret-reference changes, publishing, exports, learning approval, and retention actions. Events include actor/tenant/resource/action/outcome/time/request/trace and before/after or operation hashes. Access to audits is permissioned and itself audited.

Alerts cover cross-tenant/RLS denials, repeated auth failures, unusual exports/uploads, approval failures/replays, anomalous AI cost/tool denial spikes, secret-scan detections, publication error/volume anomalies, malware hits, and disabled security controls. Incident runbooks identify containment (disable connector/tool/provider), evidence preservation, credential rotation, tenant communication, recovery, and postmortem.

## 11. Production security gate

Before production: threat model reviewed; OIDC and role matrix tested; RLS enabled/tested with non-bypass role; secret manager/rotation working; CSP/CORS/CSRF/rate limits configured; upload/parser/crawler isolation tested; backup restore proven; audit/alerts routed; dependency/container scans clean or accepted; external provider data terms reviewed; high-impact approval E2E demonstrated; penetration test/high-severity findings resolved; privacy/retention/deletion policy approved.

