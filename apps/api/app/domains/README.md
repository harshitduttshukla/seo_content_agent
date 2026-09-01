# Domain ownership

Each child directory is a future vertical domain module. A module may own ORM models, API schemas, repository implementations, services, policies, validators, algorithms, and events. Phase 0 keeps these directories empty because adding placeholder services or fake behavior would obscure implementation status.

Cross-domain access must use a domain's public service or a declared event. See `docs/ARCHITECTURE.md` for the dependency map.

