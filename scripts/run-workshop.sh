#!/usr/bin/env bash

# Prepare and run the local Eval Workshop, then open it in a browser.
#
# Usage (from the repository root):
#   bash scripts/run-workshop.sh                    # lexical strategies only, no OpenAI calls
#   bash scripts/run-workshop.sh --with-embeddings  # also embed the corpus (needs OPENAI_API_KEY;
#                                                   # ~790 chunks, about US$0.01) for semantic/hybrid
set -Eeuo pipefail

WITH_EMBEDDINGS=0
for argument in "$@"; do
  case "$argument" in
    --with-embeddings) WITH_EMBEDDINGS=1 ;;
    -h|--help) sed -n '3,8p' "$0"; exit 0 ;;
    *) printf 'Unknown option: %s (see --help)\n' "$argument" >&2; exit 2 ;;
  esac
done

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
API_URL="http://127.0.0.1:8000"
WORKSHOP_URL="http://127.0.0.1:3000"
LOG_DIR="$PROJECT_ROOT/var/logs/eval-workshop"
API_LOG="$LOG_DIR/api.log"
WEB_LOG="$LOG_DIR/web.log"
API_PID=""
WEB_PID=""

stop_process() {
  local pid="$1"
  local label="$2"
  local attempt

  if [[ -z "$pid" ]] || ! kill -0 "$pid" 2>/dev/null; then
    return 0
  fi
  printf 'Stopping %s (PID %s)...\n' "$label" "$pid"
  kill -INT "$pid" 2>/dev/null || true
  for attempt in $(seq 1 10); do
    if ! kill -0 "$pid" 2>/dev/null; then
      wait "$pid" 2>/dev/null || true
      return 0
    fi
    sleep 1
  done
  kill -TERM "$pid" 2>/dev/null || true
  wait "$pid" 2>/dev/null || true
}

cleanup() {
  local exit_code=$?
  trap - EXIT INT TERM
  stop_process "$WEB_PID" "Next.js"
  stop_process "$API_PID" "FastAPI"
  if [[ -n "$WEB_PID" || -n "$API_PID" ]]; then
    printf '\nStopped the app servers started by this script. PostgreSQL remains running.\n'
    printf 'Logs: %s\n' "$LOG_DIR"
  fi
  exit "$exit_code"
}
trap cleanup EXIT
trap 'exit 130' INT TERM

fail() {
  printf 'Error: %s\n' "$1" >&2
  exit 1
}

require_command() {
  command -v "$1" >/dev/null 2>&1 || fail "Required command '$1' was not found. Install it, then rerun this script."
}

wait_for_url() {
  local label="$1"
  local url="$2"
  local log_file="$3"
  local pid="$4"
  local attempt

  for attempt in $(seq 1 60); do
    if curl --fail --silent --output /dev/null "$url"; then
      printf '%s is ready at %s\n' "$label" "$url"
      return 0
    fi
    if [[ -n "$pid" ]] && ! kill -0 "$pid" 2>/dev/null; then
      printf '%s stopped during startup. Recent log output:\n' "$label" >&2
      tail -n 60 "$log_file" >&2 || true
      return 1
    fi
    sleep 1
  done

  printf 'Timed out waiting for %s at %s. Recent log output:\n' "$label" "$url" >&2
  tail -n 60 "$log_file" >&2 || true
  return 1
}

open_browser() {
  # Opening a browser is a convenience: never let it stop servers that are already healthy.
  if [[ "$(uname)" == "Darwin" ]]; then
    open -a "Google Chrome" "$1" 2>/dev/null || open "$1" 2>/dev/null || true
  elif command -v xdg-open >/dev/null 2>&1; then
    xdg-open "$1" >/dev/null 2>&1 || true
  fi
}

for command_name in uv pnpm docker curl; do
  require_command "$command_name"
done
docker info >/dev/null 2>&1 || fail "Docker is installed but not running. Start Docker Desktop, wait until it says 'running', then rerun this script."

cd "$PROJECT_ROOT"
mkdir -p "$LOG_DIR"
if [[ ! -f .env ]]; then
  cp .env.example .env
  printf 'Created .env from .env.example. Add OPENAI_API_KEY there to enable semantic/OpenAI runs.\n'
fi

if curl --fail --silent --output /dev/null "$API_URL/health"; then
  fail "A TaxRAG API is already using port 8000. Stop it in its original terminal, then rerun this script."
fi
if curl --fail --silent --output /dev/null "$WORKSHOP_URL"; then
  fail "A web server is already using port 3000. Stop it in its original terminal, then rerun this script."
fi

printf 'Syncing the locked Python and web dependencies...\n'
uv sync --locked
pnpm --dir apps/web install --frozen-lockfile

printf 'Starting PostgreSQL...\n'
docker compose up -d postgres
database_ready=0
for attempt in $(seq 1 30); do
  if docker compose exec -T postgres pg_isready -U taxrag -d taxrag >/dev/null 2>&1; then
    database_ready=1
    break
  fi
  sleep 2
done
if [[ "$database_ready" != "1" ]]; then
  docker compose logs --tail=60 postgres >&2 || true
  fail "PostgreSQL did not become ready. Check Docker Desktop and the log output above."
fi

printf 'Applying database migrations...\n'
uv run alembic upgrade head

source_keys=(
  irpf-2026-quem-deve-declarar
  irpf-2026-perguntas-respostas
  irpf-2026-in-rfb-2312
)
for source_key in "${source_keys[@]}"; do
  printf 'Loading the bundled snapshot: %s\n' "$source_key"
  uv run python -m apps.worker ingest-source "$source_key" --from-snapshot
  uv run python -m apps.worker process-source "$source_key"
done

# Semantic and hybrid retrieval need one vector per chunk. Processing a changed extractor
# deletes old vectors, so embeddings are (re)created here only when explicitly requested.
has_openai_key="$(uv run python -c 'from taxrag.config import settings; print("yes" if settings.openai_api_key else "")')"
if [[ "$WITH_EMBEDDINGS" == "1" ]]; then
  [[ -n "$has_openai_key" ]] || fail "--with-embeddings needs OPENAI_API_KEY in .env or the environment."
  for source_key in "${source_keys[@]}"; do
    printf 'Embedding missing chunks (OpenAI, billable): %s\n' "$source_key"
    uv run python -m apps.worker embed-source "$source_key"
  done
fi
embedding_status="$(uv run python -c '
from taxrag.config import settings
from taxrag.database import SessionLocal
from taxrag.embeddings import embedding_coverage
with SessionLocal() as session:
    done, total = embedding_coverage(session, settings.embedding_model, settings.embedding_dimensions)
print(f"{done}/{total}")
')"

printf 'Starting FastAPI...\n'
: > "$API_LOG"
"$PROJECT_ROOT/.venv/bin/uvicorn" apps.api.main:app --host 127.0.0.1 --port 8000 >"$API_LOG" 2>&1 &
API_PID=$!
wait_for_url "TaxRAG API" "$API_URL/health" "$API_LOG" "$API_PID" || fail "API startup failed."

printf 'Starting Next.js...\n'
: > "$WEB_LOG"
# Pass the app directory explicitly: started from the repository root, Next.js would look for
# `app/` there and exit with "Couldn't find any pages or app directory".
"$PROJECT_ROOT/apps/web/node_modules/.bin/next" dev "$PROJECT_ROOT/apps/web" --hostname 127.0.0.1 --port 3000 >"$WEB_LOG" 2>&1 &
WEB_PID=$!
wait_for_url "Eval Workshop" "$WORKSHOP_URL" "$WEB_LOG" "$WEB_PID" || fail "Web UI startup failed."

open_browser "$WORKSHOP_URL"
printf '\nEval Workshop is ready at %s (open it manually if no browser window appeared).\n' "$WORKSHOP_URL"
printf 'Chunk embeddings: %s.' "$embedding_status"
if [[ "${embedding_status%%/*}" != "${embedding_status##*/}" ]]; then
  printf ' Semantic/hybrid runs are unavailable until you rerun with --with-embeddings.'
fi
printf '\nRun results are saved in var/eval-runs/; baselines in docs/evals/baselines/.\n'
printf 'Press Ctrl+C here to stop the app servers (PostgreSQL keeps running).\n'

while { [[ -z "$API_PID" ]] || kill -0 "$API_PID" 2>/dev/null; } \
  && { [[ -z "$WEB_PID" ]] || kill -0 "$WEB_PID" 2>/dev/null; }; do
  sleep 1
done

fail "An app server exited. Check the logs in $LOG_DIR."
