# Ingestion Foundation: First Official Source

Date: 2026-09-01
Status: Draft

## Problem

TaxRAG needs to reliably preserve official sources before it can extract, chunk, embed, or answer from them. The first implementation must demonstrate a repeatable, inspectable source-to-storage path rather than a one-off download script.

## Scope

Build a local development foundation that:

- runs PostgreSQL with `pgvector` in Docker Compose
- provides a minimal FastAPI health endpoint and Next.js health page
- defines versioned database schema migrations with SQLAlchemy and Alembic
- fetches the approved Receita Federal "Quem deve declarar" HTML page
- stores its raw HTML in local object storage at `var/object-storage/`
- records the source, source version, content hash, and ingestion run in PostgreSQL

## Out Of Scope

- PDF extraction, OCR, and chunking
- embeddings, vector search, answer generation, or citations
- authentication and public question answering
- a durable scheduler or production cloud storage

## Design Choice

Use explicit Python worker commands and a PostgreSQL-backed source registry. The raw artifact is stored outside the database; the database stores its immutable version metadata and storage key.

The source record is seeded from the approved source inventory, rather than allowing arbitrary URLs. An ingestion run is idempotent: re-fetching unchanged content records a successful no-change run without creating a duplicate source version.

## Data Model

| Table | Minimum fields |
| --- | --- |
| `sources` | ID, title, canonical URL, authority level, document family, active flag |
| `source_versions` | ID, source ID, SHA-256 hash, storage key, content type, fetched timestamp, status |
| `ingestion_runs` | ID, source ID, start/finish timestamps, outcome, error message, source version ID |

## Risks

- The government page may change its HTML structure or rate-limit requests.
- The fetched response may be an error page rather than source content.
- Local artifacts may accidentally be committed to Git.
- A process crash may leave a run without a terminal status.

## Test And Eval Plan

- Run the worker command twice and verify the second run detects unchanged content.
- Verify the stored artifact hash matches the database record.
- Verify the source version is linked to the approved canonical URL and authority label.
- Verify no `var/` artifact appears in `git status`.
- Verify Docker Compose health checks and the API health endpoint succeed.

## Definition Of Done

- A developer can start local infrastructure with one Docker Compose command.
- A worker command fetches and preserves the approved HTML source.
- Database records show a source, one source version, and successful ingestion run.
- Re-running the command does not duplicate an unchanged version.
- The foundation is committed and pushed with generated artifacts excluded.
