# Generated API contracts

Generate TypeScript types and a thin client from the FastAPI OpenAPI document in CI. The recommended tool is `openapi-typescript` for types plus a small reviewed `fetch` wrapper. Generated files must include the source schema checksum and must never be hand-edited.

CI fails when the committed OpenAPI snapshot or generated types differ from the backend schemas. See `docs/API.md`.

