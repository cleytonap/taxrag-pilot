# TaxRAG

TaxRAG is a learning-first, production-minded RAG application for source-grounded
Brazilian individual income tax (IRPF) questions.

The project begins with reliable source ingestion before adding retrieval and answer generation.

## First Local Slice

```bash
docker compose up -d
uv run alembic upgrade head
uv run python -m apps.worker ingest-source irpf-2026-quem-deve-declarar
uv run python -m apps.worker process-source irpf-2026-quem-deve-declarar
```

The raw HTML is written to `var/object-storage/`. PostgreSQL retains the source,
content hash, version metadata, and ingestion-run audit record.

Run the checks with:

```bash
uv run ruff check .
uv run pytest
pnpm --dir apps/web lint
pnpm --dir apps/web build
```

Search the processed chunks and run the lexical retrieval baseline with:

```bash
uv run python -m apps.worker search "Qual é o limite de rendimentos tributáveis?"
uv run python -m apps.worker eval-retrieval
```
