# Eval Workshop Launch Script

Date: 2026-11-04
Status: Implementing

## Problem

Starting the local Eval Workshop requires several terminal commands across PostgreSQL, Alembic,
source ingestion, FastAPI, and Next.js. This makes it easy to open the UI before its database and
source corpus are ready.

## Scope

- Add one macOS-oriented script that syncs locked dependencies, starts PostgreSQL, migrates the
  schema, ingests/processes the approved snapshots, starts both app servers, waits for health
  checks, and opens Google Chrome.
- Keep server output in ignored local logs and stop only processes started by the script on exit.
- Leave PostgreSQL running so the local database persists between workshop sessions.
- Document the single-command workflow and prerequisites.

## Assumptions

- Docker Desktop, `uv`, `pnpm`, `curl`, and Google Chrome are installed.
- The bundled snapshots are the desired offline source set; startup must not fetch from the web.
- The script runs from a normal interactive macOS terminal and owns the foreground session.

## Design Choice

Use a small Bash script with explicit, idempotent setup commands and tracked child PIDs. Run the
API without auto-reload so stopping the script reliably stops the launched process; Next.js retains
its normal development hot reload. The launcher requires both app ports to be free so it can own
and stop the processes it starts.

Alternative: add a shell orchestration framework or a full-process Docker Compose stack. Those add
setup and operational concepts beyond this local learning workflow.

## Risks

- Startup depends on Docker Desktop and local ports 8000/3000 being available.
- First-time dependency installation and source processing can take several minutes.
- If ports 8000 or 3000 are occupied, startup stops with instructions to stop the existing server
  in its own terminal before retrying.

## Test And Eval Plan

- Inspect shell syntax and executable permissions.
- Run the script from the repository root on macOS and confirm the API, UI, and Chrome open.
- Stop with Ctrl+C and confirm launched app servers exit while PostgreSQL remains available.

## Definition Of Done

- One command prepares the local database and source corpus, starts API/UI, and opens the workshop.
- Startup failures identify the relevant prerequisite and point to local logs.
- The README documents prerequisites, invocation, and shutdown behavior.
