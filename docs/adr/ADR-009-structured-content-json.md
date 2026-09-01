# ADR-009: Store structured versioned JSON as canonical content

- Status: Accepted
- Date: 2026-08-31

## Context

Content must support rich editing, comments, headings/entities/links, exact AI proposals, diffs, validation, version history, rendering to several CMS formats, and future collaboration. Canonical HTML or plain text loses semantic structure and makes safe patches/schema evolution difficult.

## Decision

Store validated TipTap/ProseMirror document JSON in immutable `content_versions`, with a `schema_version`, content hash, parent version, and provenance. Derived sanitized HTML, plain text, search vector, and analytics features are projections. Long-lived strategy/rule/brief structured documents use the same versioned-JSON principles with their own schemas.

## Reason

Structured JSON preserves node semantics and stable proposal/comment anchors, supports deterministic validators/renderers, and allows multiple output formats. Immutable versions make AI/human change provenance and publication replay exact.

## Alternatives

- HTML canonical: ubiquitous output but unsafe/ambiguous structure and difficult stable diffs/validation.
- Markdown canonical: portable but limited for custom structured nodes/comments and round-trip editing.
- Relational node-per-row model: strong querying but excessive write/ordering complexity for editor transactions.
- Provider/editor proprietary format: creates lock-in and weak backend validation.

## Tradeoffs

JSONB cannot enforce every document invariant in SQL, can grow, and requires schema migrations/upcasters. Querying inside documents is less efficient. We validate with strict schemas, store query-critical metadata relationally/derived, cap size, use golden fixtures, and maintain explicit upcasters without rewriting immutable history unnecessarily.

## Consequences

Public editor APIs carry schema version/base version/hash. Stale updates conflict, not overwrite. AI emits validated patches/proposals against exact bases. Renderers are versioned and sanitize output. Published records reference exact content versions. Editor/schema upgrades need backward-read fixtures, upcasters, and a rollout plan. Raw HTML is never accepted as trusted canonical state.

