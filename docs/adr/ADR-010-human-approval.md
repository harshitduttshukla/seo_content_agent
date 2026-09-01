# ADR-010: Require human approval for high-impact AI actions

- Status: Accepted
- Date: 2026-08-31

## Context

AI may propose edits, links, strategy/rules, and later publishing. Model output is probabilistic and susceptible to hallucination, prompt injection, stale context, or ambiguous intent. Publishing, deleting content, or changing active policies can damage public sites, SEO, compliance, and tenant data.

## Decision

Classify tools as read, propose, or high impact. AI content/strategy/link changes are proposals with exact base versions and explicit accept/reject. High-impact operations (initially publish; future delete/active policy change) require a fresh authorized human approval bound to actor, exact operation digest, immutable resource/version, destination, and expiry. Execution revalidates permission and all preconditions and is idempotent/audited.

## Reason

This makes model uncertainty reversible and keeps accountability with an authorized person. Binding approval to exact inputs prevents a vague approval from authorizing later model-chosen actions. It also supplies trustworthy feedback/evaluation data.

## Alternatives

- Fully autonomous actions: lower friction but unacceptable integrity/injection/recovery risk initially.
- One session-wide confirmation: easy UX but overly broad, stale, and replayable.
- Role permission without per-action approval: proves authority, not informed consent for exact generated side effect.
- Post-action review: too late for publication/deletion/policy damage.

## Tradeoffs

Approval adds latency and UI complexity, can create queues, and reviewers can rubber-stamp. We present concise diffs/evidence/risks, support low-risk batch review only when every operation is enumerated, expire approvals, and monitor acceptance/reversal patterns. Deterministic user-initiated ordinary edits remain direct APIs.

## Consequences

The database stores immutable approvals and AI/tool/proposal lineage. Approval cannot be supplied or self-granted by a model. Changed input, destination, version, permission, or expiry invalidates it. Unknown external outcomes are reconciled before retry. Tests assert no proposal tool mutates canonical state and no high-impact executor runs on missing/stale/replayed approval. Automation levels may expand only with risk evidence, scoped policy, kill switch, monitoring, and a superseding ADR.

