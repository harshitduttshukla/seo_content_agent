# ADR-004: Use pgvector for initial vector search

- Status: Accepted
- Date: 2026-08-31

## Context

Knowledge retrieval, semantic keyword assistance, and link candidate recall may use embeddings. MVP/V1 corpus size and traffic are unknown, but tenant isolation, source deletion, metadata filtering, and transactional provenance are mandatory. Adding a vector service now would duplicate data and operations.

## Decision

Store embeddings in PostgreSQL using pgvector. Keep tenant/project/source/model/version/hash as ordinary columns and perform authorization filters before/beside similarity ranking. Combine vector with PostgreSQL full-text retrieval and optional reranking. Select exact/IVFFlat/HNSW indexing only after corpus benchmarks.

## Reason

pgvector keeps chunks, ownership, lifecycle, and embeddings transactionally close; reuses backup/RLS/observability; and is adequate for expected initial scale. It supports rapid experimentation without a separate security and synchronization plane.

## Alternatives

- Pinecone/Weaviate/Milvus: stronger specialized scaling/features, but additional vendor/operations, dual-write/deletion consistency, tenant filtering, cost, and incident surface.
- Elasticsearch/OpenSearch vectors: useful hybrid search at scale but another cluster and replication path.
- No vector search: simplest, but full-text alone may miss semantic recall needed for knowledge/linking.

## Tradeoffs

Filtered approximate-nearest-neighbor performance and very large corpora may be weaker; vector workload can compete with OLTP. Embedding dimension/model changes consume storage and reindexing. We isolate queries, batch jobs, version embeddings, measure recall/latency under tenant filters, and may use replicas/partitioning before extraction.

## Consequences

Embeddings are never unscoped blobs: rows carry tenant/source lineage and access labels. Deletion/revocation invalidates retrieval immediately. Tests assert no cross-tenant hits and benchmark recall@k/p95 at representative size. An external store requires measured SLO/cost failure, a migration/dual-write/reconciliation plan, security/backup design, and a superseding ADR.

