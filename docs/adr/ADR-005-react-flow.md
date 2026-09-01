# ADR-005: Use React Flow for the Content Map

- Status: Accepted
- Date: 2026-08-31

## Context

Users need an interactive visual map of pillars, topics, clusters, pages, targets, related/supporting relationships, and internal links. The frontend is Next.js/React. The visual layer must support custom nodes, large filtered views, explicit commands, accessibility alternatives, and independent layout persistence.

## Decision

Use React Flow to render and interact with a backend graph projection. Canonical graph state stays in PostgreSQL. React Flow coordinates/layout are presentation data; structural gestures become typed revision-checked API commands. Provide an accessible tree/table and keyboard command path.

## Reason

React Flow provides mature pan/zoom, custom nodes/edges, interaction hooks, selection, and viewport handling, reducing bespoke canvas engineering. It integrates naturally with React feature architecture and leaves domain invariants on the server.

## Alternatives

- Custom SVG/canvas: maximum control but high interaction, accessibility, and performance maintenance.
- Cytoscape.js: strong graph analysis/rendering but less aligned with node-based editor UX/custom React components.
- D3: excellent primitives but requires building most editor behaviors.
- Server-rendered static diagram: insufficient for planning/review commands.

## Tradeoffs

Large graphs still need filtering/lazy expansion; library data shape can tempt canonical client state; visual graph accessibility is inherently difficult; licensing/bundle/version changes require monitoring. We use a projection adapter, bounded views, node memoization, separate layout model, and non-visual equivalent.

## Consequences

The API returns typed nodes/edges and graph revision, not raw domain tables. The UI may optimistically display commands but rolls back on conflict. Dragging never re-parents automatically. Tests cover projection, explicit commands, layout isolation, large views, keyboard/accessibility, and stale conflicts. Replacing the renderer does not require data migration because React Flow data is not canonical.

