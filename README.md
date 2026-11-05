# TaxRAG

TaxRAG is a learning-first, production-minded RAG application for source-grounded
Brazilian individual income tax (IRPF) questions.

The project begins with reliable source ingestion before adding retrieval and answer generation.

## First Local Slice

```bash
docker compose up -d
uv run alembic upgrade head
uv run python -m apps.worker ingest-source irpf-2026-quem-deve-declarar --from-snapshot
uv run python -m apps.worker process-source irpf-2026-quem-deve-declarar
```

`--from-snapshot` loads the checked-in source file, verifies its SHA-256 hash, and copies it into
`var/object-storage/` without contacting the source website. PostgreSQL and Docker are still
required. To check for an updated official version instead, omit `--from-snapshot`; ingestion then
fetches the registered canonical URL.

To seed all three approved sources from the bundled snapshots, run the ingest and process commands
for each source key:

```bash
uv run python -m apps.worker ingest-source irpf-2026-quem-deve-declarar --from-snapshot
uv run python -m apps.worker process-source irpf-2026-quem-deve-declarar
uv run python -m apps.worker ingest-source irpf-2026-perguntas-respostas --from-snapshot
uv run python -m apps.worker process-source irpf-2026-perguntas-respostas
uv run python -m apps.worker ingest-source irpf-2026-in-rfb-2312 --from-snapshot
uv run python -m apps.worker process-source irpf-2026-in-rfb-2312
```

## Local Eval Workshop

The Eval Workshop has two application servers: FastAPI serves the API, and Next.js serves the
browser UI. Start the database first because diagnostic questions query the indexed source data:

For a one-command setup on macOS, install Docker Desktop, `uv`, `pnpm`, and Google Chrome, then run
this from the repository root:

```bash
./scripts/run-workshop.sh
```

The script syncs locked dependencies, starts PostgreSQL, applies migrations, loads and processes the
bundled official snapshots, starts the API and web UI, waits until both respond, and opens Chrome at
<http://127.0.0.1:3000>. It is safe to rerun: unchanged snapshots are not reprocessed. Press Ctrl+C
in that terminal to stop app servers launched by the script; PostgreSQL stays running and keeps its
local data. Logs are written under `var/logs/eval-workshop/`.

The launcher requires ports 8000 and 3000 to be free so it can track and stop both app servers.
If a server is already running there, stop it in its original terminal and rerun the launcher. To
start services manually and see the commands individually, use the workflow below.

```bash
docker compose up -d
uv run alembic upgrade head
```

In one terminal, start the API and leave it running:

```bash
uv run uvicorn apps.api.main:app --reload
```

Confirm the API responds at <http://127.0.0.1:8000/health>. In a second terminal, start the web
UI:

```bash
pnpm --dir apps/web dev
```

Open <http://localhost:3000>. The web server forwards the UI's API requests to
`http://127.0.0.1:8000`, so the browser does not need direct cross-origin access. Keep both
terminals running while using it. The fake answer provider does not need an API key. OpenAI
requests also require `OPENAI_API_KEY` in the local `.env` and the explicit confirmation in the
UI.

Raw source files are checked into `data/source-snapshots/`; ingested copies and generated artifacts
are written under ignored `var/`. PostgreSQL retains the source, content hash, version metadata,
and ingestion-run audit record. See the [snapshot index](data/source-snapshots/README.md).

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

The experimental cited-answer command retrieves official chunks and validates that each model
citation refers to a retrieved chunk and contains a verbatim excerpt:

```bash
uv run python -m apps.worker answer "Vendi um bem com lucro em 2025. Isso pode me obrigar a declarar?"
```

This is a development diagnostic, not tax advice. It verifies that every selected citation belongs
to the retrieved evidence; the application attaches the displayed source excerpt. Its generated
prose is still undergoing human-reviewed answer evaluation.

Run the initial cited-answer fixture with explicit provider selection. Its automated result checks
only abstention and required citation anchors; inspect the printed human-review criteria before
changing answer behavior:

```bash
uv run python -m apps.worker eval-answers --provider fake --strategy lexical
uv run python -m apps.worker eval-answers --provider openai --strategy semantic
```

If an answer is safely rejected, add `--debug` to inspect the untrusted model draft, rejection
reason, and retrieved chunks on `stderr`. Do this only locally and only for non-sensitive
questions, because the trace includes unverified model output:

```bash
uv run python -m apps.worker answer --debug "Recebi apenas 30 mil no ano passado. Devo declarar?" \
  2> var/last-answer-debug.json
```
