# Web application boundary

The Phase 0 web package declares only the Next.js/React/TypeScript boundary. Its manifest uses the Next.js 16.2 Active LTS and compatible React 19.2 baseline current at the Phase 0 review date; Phase 1 creates and commits a lockfile before installation. Tailwind CSS, React Flow, TipTap, the generated API client, test tooling, and product routes are added with the Phase 1 feature that uses them rather than installed speculatively.

Feature code belongs in `src/features/<domain>`. Server/client boundaries, authentication session handling, caching, and editor/map architecture are defined in `docs/ARCHITECTURE.md` and `docs/CONTENT-MAP.md`.
