# V2 Decisions, Verification Toggle, And Eval Glossary

Date: 2026-11-06
Status: Implemented

## Problem

V2 results raised three needs.

- **Choosing production.** `hybrid_rerank` met the adoption rule, so it should become the
  production default.
- **Experimenting with the verifier.** Its value was unclear, and it could only be switched off
  through an environment variable.
- **Understanding the suites.** Anyone reading a suite or run needs a reliable reference for
  every field, category value, outcome and metric.

Latency rose in V2. This was investigated but not changed (see below).

## Decisions

- **Production strategy = `hybrid_rerank`** (config default and `.env.example`). Evidence and
  caveats are in `docs/evals/v2-results-analysis.md`.
- **Verifier stays on by default.**
  - It does not move pass rates, but in production configuration it reduced unsafe answers
    (2 → 1) at about +1.8 s per answered question.
  - A **per-run override** exists end to end: UI toggle (answer suites and Question lab) →
    API `answer_verification` → eval manager → answer path.
  - CLI: `run-suite --verification on|off`.
  - The effective value is recorded in each artifact. `GET /api/evals/config` exposes the server
    defaults.
- **Blocked drafts are stored** in answer artifacts (`rejected_draft`) and shown collapsed on the
  result card, so verifier and validation blocks can be reviewed.
- **Glossary** has one source, `taxrag/eval_glossary.py`, which serves:
  - `GET /api/evals/glossary` and the new **Glossary** tab (search, suite filters, live value
    counts, example records);
  - the generated `docs/evals/glossary.md`.

  Tests fail if a fixture field or category value is undocumented, if the documented strategies
  or outcomes differ from the code, or if the Markdown is stale.
- **Latency (not changed).** Every extra second comes from an added call: about 1.2 s for the
  reranker and about 1.8 s for the verifier per answered question. Embedding calls are unchanged
  at about 0.5 s. Parallelising eval cases would shorten suite runs, but it needs per-worker DB
  sessions, so it is not a trivial change; deferred.

## Test Plan

- Unit and API tests:
  - glossary completeness and endpoint;
  - Markdown freshness;
  - strategy and outcome parity with the code.
- Browser check:
  - the Glossary renders, searches and filters;
  - the toggle starts at the server default, flips, and the resulting run records
    `answer_verification: false`.
- Full suite, ruff, ESLint and `next build`.
