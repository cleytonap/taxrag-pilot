# ADR 002: FastAPI and Next.js Application Stack

Date: 2026-09-01

Status: Accepted

## Context

TaxRAG needs a public web interface, HTTP API, durable ingestion process, database access, source extraction, model integration, and eventual deployment. The learner is more familiar with Python but also wants to learn a widely used modern frontend stack. The product should keep Python as the authoritative backend for AI and data work.

## Decision

Use a Python backend with a separate TypeScript frontend:

- `FastAPI` for the authoritative HTTP API, domain logic, authentication integration, and AI orchestration.
- `Next.js` and React with TypeScript for the web application.
- A dedicated Python worker process in the same repository for ingestion and evaluation commands.
- PostgreSQL with `pgvector` for product data, source metadata, chunks, embeddings, and evaluations.
- S3-compatible object storage behind a small storage interface for raw HTML and PDF artifacts.
- SQLAlchemy for the Python data-access layer and Alembic for version-controlled database migrations; use raw SQL where it makes vector search or citation joins clearer.
- An LLM-provider interface. The first adapter will use the OpenAI Responses API with Structured Outputs for the answer contract.

Do not use OpenAI hosted file search for TaxRAG's canonical retrieval path. TaxRAG must retain control of source versions, tax-period filters, ranking, source authority, chunk anchors, and citations.

## Options Considered

| Option | Strength | Main tradeoff | Decision |
| --- | --- | --- | --- |
| FastAPI API plus Next.js/React frontend | Clear frontend/backend contract; modern React/TypeScript learning; Python remains best suited to source extraction and AI work | Two languages, dependency systems, and deployable applications | Chosen |
| FastAPI plus Jinja2 and HTMX | One primary language; direct API and server-rendered UI; small amount of browser-side JavaScript | Less practice with the React/TypeScript ecosystem and less suited to a rich client interface | Not chosen because modern frontend learning is a product goal |
| Django plus templates/HTMX | Mature admin, auth, ORM, and Python full-stack ecosystem | More framework conventions than FastAPI; less explicit API-first learning | Credible alternative, not chosen because FastAPI is the learner's stated preference |

## Initial Repository Shape

```text
apps/
  api/             FastAPI routes, domain orchestration, and migrations
  web/             Next.js/React web application
  worker/          ingestion and evaluation entry points
taxrag/
  core/            domain models and business rules
  database/        schema, migrations, and queries
  retrieval/       chunking, search, ranking, and citations
  ai/              provider-neutral answer contract and adapters
  source_parsers/  document-family parsers
```

The physical folders may be introduced gradually. The important constraint is dependency direction: FastAPI routes and worker commands may call domain modules; domain modules must not depend on HTTP or UI layers. The Next.js application communicates with the backend through the documented FastAPI API and does not access the database directly.

## Background Work Strategy

Start with explicit worker commands run manually in local development. The first ingestion command must be idempotent and record its run in the database.

When API-triggered or scheduled ingestion is introduced, use a PostgreSQL-backed job table before adding Redis, RabbitMQ, or a separate queue service. Revisit that choice when job volume, retries, or concurrency show that a dedicated queue is necessary.

## Database Migration Strategy

Use SQLAlchemy for database models and queries, and Alembic for migration scripts. Each schema change creates an ordered migration file committed to Git.

- `alembic revision --autogenerate` may draft a migration from model changes, but every generated migration must be reviewed before it is committed.
- `alembic upgrade head` applies all pending migrations to an environment.
- Production application startup must not silently mutate the schema; the deployment process runs migrations explicitly.
- Raw SQL migrations are allowed and expected for PostgreSQL extensions, indexes, and database-specific features such as `pgvector`.

## AI Integration Strategy

The answer module owns a provider-neutral structured contract:

- answer text
- cited chunk IDs
- limitations or abstention reason
- optional clarification question

The first OpenAI adapter uses the Responses API and JSON Schema Structured Outputs. The citation gate remains application code and validates citations against retrieved chunks before any response is shown.

## Consequences

- We will learn both a modern React/TypeScript frontend and a Python AI/backend stack.
- API boundaries make frontend and backend independently deployable, but require contract testing and CORS/auth design.
- The initial deployment will run at least a web process, an API process, a worker process, PostgreSQL, and object storage.
- Authentication, billing, and a production scheduler are intentionally deferred until the source/retrieval baseline is proven.

## Revisit Triggers

Revisit this decision if:

- the frontend complexity remains low enough that maintaining a separate React application is not justified
- worker workloads require independent compute characteristics that make the monorepo boundary impractical
- a performance or reliability benchmark shows a separate retrieval or API service is necessary
- the team composition makes a Python-first backend materially easier to maintain
