# ADR-008: Isolate AI providers behind a typed abstraction

- Status: Accepted
- Date: 2026-08-31

## Context

The system will generate text, stream responses, produce embeddings, and use structured tools. Provider/model price, quality, capability, API, retention, regional availability, and rate limits change. Coupling domain services/prompts/tools to one SDK would make migration and evaluation unsafe.

## Decision

Domain/application code depends on internal `AIProvider.generate`, `stream`, and `embed` contracts. Provider SDKs exist only in adapters. An AI service owns policy, model selection, retry/circuit/rate/cost behavior, normalized errors, provenance, and evaluation gates. Tool/context schemas remain provider-neutral Pydantic models.

## Reason

The abstraction creates a stable test seam, keeps vendor payloads out of business logic/data contracts, enables task-specific provider/model policy, and makes controlled migrations/comparisons possible.

## Alternatives

- Direct SDK calls: fastest first call but causes scattered policy, error, usage, and migration logic.
- A third-party universal LLM framework/gateway as core abstraction: may accelerate integrations but adds its own semantics/dependency and can obscure provider capability/security.
- Separate AI microservice: stronger isolation but unnecessary deployment/network complexity initially.

## Tradeoffs

A lowest-common-denominator interface can hide useful capabilities; adapters require maintenance; output may not be identical across providers. We keep a small stable core and versioned optional capability descriptors rather than leaking SDK types. Migration requires evaluations, not merely interface compatibility.

## Consequences

Every call records provider/model/template/context/tool versions, usage/cost/latency/status. Tests use deterministic fake adapters plus provider contract suites. Model/provider changes run evaluation datasets and staged rollout. Secrets/config remain in deployment adapters. Provider-specific feature use needs a declared capability and fallback/error behavior, never conditional vendor logic in domain services.

