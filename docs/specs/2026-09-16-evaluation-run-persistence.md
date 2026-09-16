# Evaluation Run Persistence

Date: 2026-09-16

Status: Planned

## Problem

The current retrieval evaluator prints outcomes to the terminal. The fixture itself is versioned,
and selected aggregate results are copied into implementation specs, but there is no durable,
queryable record of a particular run. This prevents reliable comparison across retrieval strategy,
embedding model, prompt version, source corpus, and answer-provider changes.

## Scope

- persist retrieval and cited-answer evaluation runs in PostgreSQL
- record immutable execution inputs: fixture path and content hash, run type, configuration,
  retrieval strategy, model identifiers, and source-version evidence used by each result
- record timing and provider token/cost data when available
- retain a JSON snapshot of per-case results and aggregate metrics
- provide CLI commands to list and inspect persisted runs

## Out Of Scope

- a production analytics warehouse or dashboard
- storing raw user questions or production conversations as evaluation data
- automatically declaring a run a release gate without human review
- normalizing every claim, citation, and metric into a separate relational table before the
  evaluation format has stabilized

## Options Considered

| Option | Strength | Tradeoff | Decision |
| --- | --- | --- | --- |
| Terminal output plus specs | Minimal implementation | Results are not queryable or reproducible as exact run artifacts | Replaced |
| One `evaluation_runs` table with JSON snapshots | Preserves the full evolving result shape while keeping runs queryable by time/configuration | SQL analytics inside nested JSON is less convenient later | Chosen for the learning-stage product |
| Fully normalized run/case/claim/citation tables | Strong relational reporting | Commits early to an answer-evaluation schema we have not yet learned | Revisit after several persisted answer runs |

## Design Choice

Create an immutable `evaluation_runs` record for each execution. It will contain:

- run ID, type (`retrieval` or `answer`), status, and timestamps
- fixture path and SHA-256 content hash
- configuration snapshot: strategy, embedding model/dimensions, answer model, prompt version,
  and requested `top_k`
- aggregate metrics and per-case result snapshots as JSON
- elapsed time plus provider usage/cost fields when the provider supplies them

Each answer-case snapshot must include the retrieved chunk IDs, anchors, source-version IDs,
validated citations, and any manual review outcome. A later source refresh must never mutate the
historical run: it is evidence of what the system saw at that time.

JSON is deliberate at this stage. Evaluation case schemas will evolve as we add graded relevance,
claim-level reviews, and abstention outcomes. The stable relational boundary is the run itself;
we will normalize repeated fields only after real comparison needs demonstrate the shape is stable.

## Risks

- JSON snapshots can become large; the initial fixtures are small, and the first implementation
  should set a bounded payload policy before storing provider text.
- A fixture path alone is not reproducible if its content changes, hence the required hash.
- Provider token and cost fields can be absent or change shape; store them as optional metadata,
  not as required correctness evidence.

## Test And Eval Plan

- Unit-test fixture hashing and serialization of retrieval and answer result snapshots.
- Integration-test that a run and its case results can be persisted and read after a new session.
- Verify a later source version does not alter stored run evidence.
- Run one retrieval and one answer fixture, then compare their stored configuration and metrics.

## Definition Of Done

- Every CLI evaluation execution can optionally persist a self-contained run record.
- A developer can list recent runs and inspect one run by ID without relying on terminal history.
- Stored snapshots identify the exact fixture content, source evidence, model/configuration, and
  aggregate outcome used for a comparison.
