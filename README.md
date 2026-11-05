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

The Eval Workshop is a local web UI for managing the eval suites. You can browse and edit cases,
run a suite with any retrieval strategy, inspect per-case evidence, save a run as a baseline, and
compare later runs against it. It has two servers: FastAPI (API, port 8000) and Next.js (UI,
port 3000), backed by PostgreSQL in Docker.

**Prerequisites:** Docker Desktop (running), [`uv`](https://docs.astral.sh/uv/), `pnpm`, and
`curl`. Then, from the repository root:

```bash
bash scripts/run-workshop.sh                    # lexical strategies; no OpenAI calls
bash scripts/run-workshop.sh --with-embeddings  # also enables semantic/hybrid (OPENAI_API_KEY in .env)
```

The script syncs dependencies, starts PostgreSQL, applies migrations, loads and processes the
bundled official snapshots, optionally embeds the corpus, then starts both servers and opens
<http://127.0.0.1:3000>. Open that URL yourself if no browser window appears. Keep the terminal
open: Ctrl+C stops the app servers, while PostgreSQL keeps running with its data. The script is safe
to rerun. On first run it creates `.env` from `.env.example`. Logs: `var/logs/eval-workshop/`.

Using it:

- **Suites & cases:** pick a suite and a strategy, then press **Run suite**. Runs happen in the
  background with a live progress counter (a lexical run takes about 40 s, an OpenAI answer run a
  few minutes). Semantic, hybrid and OpenAI runs require ticking the cost confirmation.
- **Run archive:** every run is saved to `var/eval-runs/` (local, gitignored). Open a run to see its
  metrics and per-case results (filter to failures), **Save as baseline** (copied to the
  Git-tracked `docs/evals/baselines/`), or **Compare with baseline** to see regressed and improved
  cases.
- **Question lab:** try one question, inspect the retrieved chunks, and add it to a suite.

The same operations are available without the UI:

```bash
uv run python -m apps.worker run-suite retrieval --strategy lexical            # saves a run
uv run python -m apps.worker run-suite retrieval --strategy semantic --confirm-paid --baseline v0
uv run python -m apps.worker compare-runs v0_retrieval_semantic.json <run-file>.json
```

See [docs/evals/baselines/README.md](docs/evals/baselines/README.md) for the baseline protocol.

Troubleshooting:

| Symptom | Fix |
| --- | --- |
| `permission denied: ./scripts/run-workshop.sh` | Run it as `bash scripts/run-workshop.sh` (or `chmod +x` it). |
| "Docker is installed but not running" | Start Docker Desktop and wait until it reports running. |
| "A TaxRAG API is already using port 8000" (or 3000) | Stop the earlier server (Ctrl+C in its terminal, or `lsof -ti :8000 \| xargs kill`). |
| "Web UI startup failed" | Read `var/logs/eval-workshop/web.log`; run `pnpm --dir apps/web install` once manually. |
| Semantic run fails with "needs embeddings for every chunk" | Rerun the launcher with `--with-embeddings` (requires `OPENAI_API_KEY`). |
| pnpm refuses to switch to the pinned version | Install the pinned pnpm (`corepack enable && corepack prepare pnpm@11.24.0 --activate`). |

To start the services manually instead:

```bash
docker compose up -d
uv run alembic upgrade head
uv run uvicorn apps.api.main:app --reload   # terminal 1; check http://127.0.0.1:8000/health
pnpm --dir apps/web dev                      # terminal 2; open http://localhost:3000
```

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
