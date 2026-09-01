# Test layout

- `unit/`: pure services, policies, validators, algorithms, and value objects.
- `integration/`: PostgreSQL/Redis/pgvector/object-storage boundaries.
- `api/`: FastAPI requests, envelopes, auth, authorization, pagination, and idempotency.
- `contract/`: OpenAPI compatibility, generated client types, tool schemas, and events.

Phase 0 has only repository structure validation in `scripts/validate_phase0.py`; behavior tests begin with Phase 1 features.

