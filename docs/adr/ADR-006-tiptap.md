# ADR-006: Use TipTap for the structured content editor

- Status: Accepted
- Date: 2026-08-31

## Context

The editor needs structured documents, custom SEO/AI UX, node/range-aware suggestions, comments, autosave, immutable versions, and future collaboration. Storing HTML alone cannot safely preserve structure, diff anchors, schema evolution, or exact AI changes.

## Decision

Use TipTap (ProseMirror-based) with a pinned allowlisted schema. Persist validated document JSON and schema version as canonical; derive sanitized HTML/plain text. Autosave and AI patches bind to exact base version/hash. AI changes appear as explicit suggestions accepted/rejected by a human.

## Reason

TipTap offers extensible React-friendly APIs over ProseMirror's robust document model and transaction primitives. It supports custom nodes/marks and future collaboration while allowing backend schema validation and versioned JSON storage.

## Alternatives

- Lexical: capable and React-native, but TipTap/ProseMirror has a mature structured-document/plugin ecosystem for this editor shape.
- Slate: flexible but more responsibility for normalization/edge cases.
- CKEditor/TinyMCE: rich packaged editors, but customization/licensing/data-model fit and proposal mechanics require evaluation.
- Markdown or HTML textarea: insufficient structured editing, comments, and safe proposals.

## Tradeoffs

ProseMirror concepts are complex; extension/schema upgrades can break old JSON; collaboration adds separate operational choices; backend cannot import browser code to validate directly. We pin extensions, publish a language-neutral JSON schema, version/upcast documents, maintain golden fixtures, and defer real-time collaboration until needed.

## Consequences

HTML is a derived render and always sanitized. Node IDs/range anchors plus quoted fallback support comments/suggestions. Restores create new versions. The frontend owns editing transactions; backend owns canonical version/concurrency/permission checks. Tests cover schema fixtures, migrations, autosave/idempotency/conflict, diff/application, comments, and safe render. Editor replacement must read/write the canonical schema or migrate versions explicitly.

