# ADR 001: Modular Monolith With PostgreSQL and pgvector

Date: 2026-08-31

Status: Accepted

## Context

TaxRAG needs a web product, background ingestion, source/version records, RAG retrieval, citations, and evaluations. The first corpus is small, but the product needs a credible path to grow.

## Decision

Start with a modular monolith and a separate worker process. Use PostgreSQL as the product database and `pgvector` for embeddings and vector search. Store raw source artifacts in object storage.

Use the database as the source of truth. The vector index is derived from active chunk records and can be rebuilt.

## Options Considered

| Option | Why it is credible | Why it is not chosen now |
| --- | --- | --- |
| PostgreSQL plus pgvector | One transactional data model; SQL joins make citations, source versions, and evaluations inspectable; supports lexical and vector retrieval | Chosen; requires recall and index-tuning discipline as scale grows |
| PostgreSQL plus Pinecone | Managed vector infrastructure with metadata filtering and dense, sparse, and full-text search | Requires synchronization and operations across two data systems before scale validates that cost |
| PostgreSQL plus Qdrant | Vector-native filtering and hybrid/multi-stage retrieval capabilities | Also adds a second data system; its extra retrieval features are not yet justified by evaluation evidence |

## Consequences

- The first retrieval baseline can use exact search, making quality easier to verify.
- We can join a chunk directly to its source version, authority label, tax period, and user-visible anchor.
- We accept future migration work if corpus size, query load, or measured recall/latency require a dedicated vector database.
- PostgreSQL remains required even if a dedicated vector database is adopted later.

## Revisit Triggers

Reconsider this decision when one or more of these is observed in production-like evaluation:

- corpus growth makes retrieval latency or index build time unacceptable
- filtered approximate search produces insufficient recall after tuning
- query volume requires independent vector-search scaling
- hybrid or multi-stage retrieval features materially improve the benchmark but are impractical to operate in PostgreSQL
