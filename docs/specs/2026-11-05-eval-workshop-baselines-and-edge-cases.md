# Eval Workshop Reliability, Baselines, And Edge Cases

Date: 2026-11-05
Status: Implemented (semantic/hybrid/OpenAI V0 runs pending an API key)

## Problem

We need a V0 baseline to compare optimisations against, but three things blocked it:

1. **The Eval Workshop could not be opened with the launcher.** The script lacked its execute bit
   (`./scripts/run-workshop.sh` → "permission denied"). Worse, it started Next.js from the
   repository root, so Next.js looked for `app/` there, exited with "Couldn't find any pages or app
   directory", and the script tore down both servers. It also required Google Chrome and aborted
   (stopping healthy servers) if Chrome could not be opened.
2. **Suite runs could not finish from the UI, and results were not durable.** The UI aborted every
   request after 10 seconds. A lexical suite run takes ~40 s and an OpenAI answer run takes
   minutes, so the user saw "timed out" instead of results. Run artifacts live only in the
   gitignored `var/eval-runs/`, and the archive showed raw JSON with no way to mark or compare a
   baseline.
3. **A semantic baseline would have been silently wrong.** The launcher never creates embeddings,
   and a semantic run over an unembedded corpus "succeeds" with 0% recall. `embed-source` also sent
   all ~790 chunks (~1.1M characters) in one OpenAI request, which is near or above the 300k-token
   per-request limit.

The suites also lacked edge cases. The only ones were four abstention cases in the answer suite.

## Scope

- Launcher fixes: execute bit, explicit Next.js app directory, Docker-running preflight,
  `.env` bootstrap, a non-fatal cross-platform browser open, and an opt-in `--with-embeddings` step
  that reports embedding coverage.
- Embeddings: bounded batches (≤ 64 inputs, ≤ 150k characters), with a commit per batch so reruns
  resume. A `require_complete_embeddings` guard runs before any semantic/hybrid eval or debug
  question.
- Runs: background jobs with progress (`POST /api/evals/suites/{id}/jobs`,
  `GET /api/evals/jobs/{id}`), one run at a time, and paid-run consent checked before the thread
  starts. The synchronous endpoint is kept for compatibility.
- Baselines: `promote_to_baseline` writes an immutable, excerpt-truncated copy to
  `docs/evals/baselines/` (Git-tracked, ~200 KB instead of ~2.5 MB). `compare_artifacts` reports
  metric deltas, per-case regressions/improvements/rank changes, and warnings for fixture, source or
  model drift.
- CLI parity: `run-suite` (same artifact as the UI, optional `--baseline`), `promote-baseline`,
  `compare-runs`. Expected operator errors print one line instead of a traceback.
- UI: per-call timeouts, job polling with a progress notice, an archive rendered as results (not
  raw JSON), a baseline badge, save-as-baseline, a compare panel, a failures-only filter, and
  topic/edge-case tags.
- Fixtures: 10 retrieval edge cases (70 total) and 13 answer edge cases (33 total, 10 abstentions).
  Answer cases may carry `topic`/`edge_case`/`label_notes`; unknown keys are still rejected.
- Answer summary now splits abstention and answerable pass counts.
- `scripts/retrieval-coverage-report.py` regenerates `docs/evals/retrieval-coverage.md`.
- The three pre-existing failing tests (stale fakes without evidence fields) are fixed, and new
  tests cover batching, baselines, comparison, jobs and metadata.

## Design Choices

- **Polling jobs instead of longer HTTP timeouts.** The Next.js proxy (undici) and browsers have
  their own limits, and an OpenAI answer run can exceed five minutes. A job registry in the local
  API process is the smallest robust design. The on-disk artifact remains the durable record, so
  losing a job on API restart loses only the progress view. A queue or worker service was rejected
  as unnecessary for a single-user local tool.
- **Baselines in Git, runs not.** A baseline must survive `var/` cleanup and be reviewable in a
  pull request. Full chunk text is omitted (300-character excerpts) because it is reproducible
  from the recorded source-version hashes. Immutability (no overwrite) keeps the reference stable,
  and re-baselining requires a new label.
- **Embeddings opt-in in the launcher.** They are cheap (about US$0.01) but call a paid external
  API. This is consistent with the explicit paid-request consent used everywhere else.
- **Where edge cases live.** Retrieval is scored by recall, so it holds only answerable edge cases.
  Refusal-type cases (another year, out of scope, injection, missing source) have no correct chunk
  and belong in the answer suite, where abstention is scored. Ambiguous questions that should
  trigger a clarification are excluded until the answer contract supports a `clarify` outcome.

## Risks

- Jobs are in-memory and single-process. If the API restarts mid-run, the UI shows an error, but
  no partial artifact is written.
- The largest P&R chunk (~22k characters) is close to the embedding model's 8,192-token input
  limit. A future chunking change should split oversized chunks rather than truncate them.
- The lexical strategies are dominated by very long chunks, so the V0 lexical numbers are low
  (15.7%). This is recorded, not fixed: that is what a baseline is for.
- Human review of the answer baseline is manual. `v0-answer-review.md` provides the checklist.

## Test And Eval Plan

- Unit tests: embedding batch bounds; baseline compaction, labelling and immutability; comparison
  classification and drift warnings; job success, failure and consent; answer metadata acceptance
  and typo rejection; presence of edge-case categories; IN article coverage.
- Manual end-to-end check (done on Linux with a Docker shim): the launcher starts both servers;
  the UI runs a suite with live progress; the archive saves a baseline and compares two runs; TERM
  stops both servers; a semantic run without embeddings fails with the actionable message.

## Definition Of Done

- The Workshop opens via `bash scripts/run-workshop.sh`, and runs complete and render in the UI.
- Baselines can be saved and compared from the UI and the CLI.
- V0 lexical baselines are recorded. Semantic, hybrid and OpenAI-answer V0 runs are recorded by the
  user with an API key (commands in `docs/evals/baselines/README.md`), and the answer run is
  human-reviewed.
- All tests, ruff, ESLint and `next build` pass.
