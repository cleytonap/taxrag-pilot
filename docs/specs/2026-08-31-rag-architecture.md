# RAG Architecture: TaxRAG V1

Date: 2026-08-31
Status: Draft

## Problem

The first IRPF vertical slice needs a reliable path from an official source to a cited answer. The architecture must preserve provenance and make retrieval, citation, and evaluation independently observable.

## Scope

This is a logical architecture for V1. It defines responsibilities, data boundaries, request flows, and quality gates. It does not select framework, ORM, hosting vendor, LLM, or embedding model.

## Architecture Shape

Use a Python modular-monolith backend with a separate worker process, a Next.js web frontend, and managed infrastructure. The frontend communicates with the backend over a documented HTTP API; only the backend and worker access the relational database and object storage.

```text
                 +------------------+
                 | Official sources |
                 +--------+---------+
                          |
                          v
 +----------+      +------+-------+      +----------------+
 | Admin UI | ---> | FastAPI API   | ---> | Object storage |
 +----------+      +------+-------+      | raw HTML / PDF |
                          |              +----------------+
                          v
                  +-------+--------+
                  | PostgreSQL     |
                  | metadata/text/ |
                  | chunks/vectors |
                  +-------+--------+
                          ^
                          |
 +----------+      +------+-------+      +----------------+
 | Next.js  | ---> | FastAPI API   | ---> | LLM provider   |
 | web app  |      | retrieval +   |      | generation only|
 +----------+      | citation gate |      +----------------+
                  +------+-------+
                         |
                         v
                  +------+-------+
                  | Eval runner  |
                  | metrics/logs |
                  +--------------+
```

## Components

### Next.js Web Application

- serves the public question interface and later authenticated product features
- owns browser rendering and client-side interaction only
- calls the FastAPI API; it does not access the database, call the LLM provider, or fetch government sources

### FastAPI API

- owns input validation, authorization, rate limits, and the public API contract
- calls retrieval and answer modules; it does not fetch government sources during a user request
- is the only application process allowed to access product data on behalf of requests

### Ingestion Worker

- fetches only sources approved in the source registry
- preserves raw artifacts in object storage
- creates source versions using content hashes
- extracts structured text and citation anchors
- chunks, embeds, and indexes only validated source versions
- records every run, failure, and source change

### PostgreSQL with pgvector

- source of truth for product data and RAG metadata
- stores source records, versions, anchors, chunks, embeddings, ingestion runs, answer logs, and evaluation results
- supports lexical retrieval, vector retrieval, metadata filters, and source-to-citation joins

### Object Storage

- stores immutable raw HTML and PDF artifacts by source version
- keeps raw source files out of transactional tables while retaining a database reference, content hash, and retrieval timestamp

### Retrieval Module

- receives the normalized question and applicable exercise/year
- filters inactive sources and incompatible tax periods before ranking
- runs lexical and semantic retrieval over chunks
- applies a transparent ranking adjustment for authority, directness, effective period, and source status
- returns passages with stable citation anchors, never free-form text without provenance

### Answer Module

- receives only the user question, product limitations, and retrieved passages
- requests a structured answer containing claims, citations, limitations, and optional follow-up question
- may not invent citation identifiers
- refuses or narrows the answer when retrieval is weak, the year is unsupported, or a personal determination is requested

### Citation Gate

- verifies each cited chunk exists, belongs to an active source version, and was present in retrieval results
- verifies every answer that states an IRPF 2026 threshold includes the applicable exercise and calendar year
- prevents an answer from being shown if the required citation checks fail

### Evaluation Runner

- runs the versioned evaluation set against retrieval and answer generation
- records retrieval recall, citation validity, abstention behavior, latency, and cost
- gates source-version activation and significant retrieval/prompt changes

## Core Data Model

| Entity | Responsibility |
| --- | --- |
| `sources` | Stable identity, canonical URL, authority level, publisher, and admission status |
| `source_versions` | Hash, raw-artifact location, dates, extraction status, and activation state |
| `source_anchors` | Article, section, page, heading, or question identifiers users can verify |
| `chunks` | Extracted retrievable passages linked to one version and one or more anchors |
| `chunk_embeddings` | Embedding vector, model identifier, dimensions, and generation timestamp |
| `ingestion_runs` | Fetch/extraction/indexing outcome and errors |
| `answers` | Question, retrieved chunks, generated structured answer, and user-visible citations |
| `evaluation_cases` | Versioned query, expected anchor/source, and expected behavior |
| `evaluation_runs` | Per-case retrieval and answer results, scores, cost, and latency |

## Retrieval And Citation Policy

1. Apply hard filters first: active version, jurisdiction, language, topic, and tax period.
2. Retrieve candidates with both lexical and vector search.
3. Fuse and rerank candidates; do not use raw vector similarity as the final authority decision.
4. Prefer a source that is direct, current, and applicable over a merely more general higher-level source.
5. Pass a small set of full passages to generation.
6. Validate the generated citation references deterministically before returning the answer.

For the initial build, use lexical retrieval plus exact vector search and a small corpus. Add approximate indexing, reranking, and more sophisticated fusion only after the evaluation results justify them.

## Request Flows

### Ingestion

1. An admin action or scheduler queues an approved source.
2. The worker fetches it and computes a content hash.
3. If unchanged, record a successful no-change run.
4. If new or changed, preserve raw content, extract text and anchors, and create a pending source version.
5. Generate chunks and embeddings for the pending version.
6. Run relevant retrieval evaluations.
7. Activate the version only when validation and evaluation gates pass.

### Answering

1. The API identifies the requested topic and tax year or asks a clarifying question.
2. Retrieval returns eligible passages and their provenance.
3. The answer module produces a structured draft grounded only in those passages.
4. The citation gate checks the draft.
5. The API returns the answer, source labels, source excerpts, and limitations.
6. The system records trace data needed for debugging and evaluation without storing unnecessary personal information.

## Options Considered

| Option | Strength | Tradeoff | Decision |
| --- | --- | --- | --- |
| Python modular-monolith backend plus Next.js frontend | Clear backend ownership with a modern web client; isolated AI/data code; deployable frontend and API | Two application runtimes and an API boundary | Chosen |
| Microservices from day one | Independent scaling and deployment | Network, deployment, and observability complexity before there is a scaling need | Rejected for V1 |
| Agent framework as the core architecture | Fast experimentation with multi-step flows | Can obscure retrieval, data contracts, and failure modes | Rejected for V1; consider bounded agents later |

## Risks

- Incorrect extraction can make an otherwise correct source unretrievable.
- Approximate vector search can hide relevant passages if not evaluated.
- An LLM can produce a plausible answer that overstates retrieved support.
- A source update can silently change a rule unless versioning and evaluation gates work.
- Keeping traces without a retention policy can create avoidable privacy risk.

## Test And Eval Plan

- Unit test source-version, anchor, chunk, and citation relationships.
- Add fixture-based extraction tests for one HTML source and one PDF source.
- Run the approved evaluation cases after every retrieval, source, embedding, or prompt change.
- Compare approximate search against exact search before enabling approximate indexes.
- Test citation-gate failures deliberately: missing chunk, inactive version, unsupported year, and fabricated citation ID.

## Definition Of Done

- The architecture identifies an owner and data boundary for every part of the source-to-answer path.
- The first implementation can run locally using the initial source inventory.
- No answer can bypass source provenance and citation validation.
- Evaluation results can be inspected before a source version or retrieval change is activated.
