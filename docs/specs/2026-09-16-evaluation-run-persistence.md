# Evaluation Run Persistence

Date: 2026-09-16

Status: Planned

## Problem

The current retrieval evaluator prints outcomes to the terminal. The fixture itself is versioned,
and selected aggregate results are copied into implementation specs, but there is no durable,
easy-to-read record of a particular run. This prevents reliable comparison across retrieval
strategy, embedding model, prompt version, source corpus, and answer-provider changes.

## Scope

- write one self-contained JSON artifact for each retrieval or cited-answer evaluation run
- store generated artifacts under `var/eval-runs/`, outside the version-controlled fixture folder
- provide CLI commands to list and inspect saved run artifacts
- record immutable execution inputs: fixture path and content hash, run type, configuration,
  retrieval strategy, model identifiers, and source-version evidence used by each result
- record timing and provider token/cost data when available
- retain per-case results and aggregate metrics in the same human-readable artifact

## Out Of Scope

- a production analytics warehouse or dashboard
- storing raw user questions or production conversations as evaluation data
- automatically declaring a run a release gate without human review
- normalizing every claim, citation, and metric into a separate relational table before the
  evaluation format has stabilized

## Options Considered

| Option | Strength | Tradeoff | Decision |
| --- | --- | --- | --- |
| Terminal output plus specs | Minimal implementation | Results are not easy to compare or reproduce as exact run artifacts | Replaced |
| One JSON file per run | Self-contained, readable, diffable, works without a database, and fits evolving evaluation data | Querying many runs needs an index or file scan later | Chosen for the learning-stage product |
| One `evaluation_runs` table with JSON snapshots | Queryable by time/configuration and convenient for a future admin UI | Adds schema and migration work before we know which fields need reporting | Revisit when a dashboard or multi-user comparison needs it |
| Fully normalized run/case/claim/citation tables | Strong relational reporting | Commits early to an answer-evaluation schema we have not yet learned | Revisit after several persisted answer runs |

## Design Choice

Create one immutable JSON artifact for each execution under `var/eval-runs/`. A filename will
include a UTC timestamp and run ID, for example:

```text
var/eval-runs/2026-09-16T143012Z_retrieval_4f84c2.json
```

It will contain:

- run ID, type (`retrieval` or `answer`), status, and timestamps
- fixture path and SHA-256 content hash
- configuration snapshot: strategy, embedding model/dimensions, answer model, prompt version,
  and requested `top_k`
- aggregate metrics and per-case result snapshots as JSON
- elapsed time plus provider usage/cost fields when the provider supplies them

Each answer-case snapshot must include the retrieved chunk IDs, anchors, source-version IDs,
validated citations, and any manual review outcome. A later source refresh must never mutate the
historical artifact: it is evidence of what the system saw at that time.

JSON is deliberate at this stage. Evaluation case schemas will evolve as we add graded relevance,
claim-level reviews, and abstention outcomes. Separating input fixtures in `docs/evals/` from
generated output in `var/eval-runs/` keeps the distinction visible: fixtures are reviewed product
expectations, while artifacts are observed local executions. A future database index can import or
reference these artifacts without changing their readable, portable format.

## Risks

- JSON artifacts can become large; the initial fixtures are small, and the first implementation
  should set a bounded payload policy before storing provider text.
- A fixture path alone is not reproducible if its content changes, hence the required hash.
- Provider token and cost fields can be absent or change shape; store them as optional metadata,
  not as required correctness evidence.

## Test And Eval Plan

- Unit-test fixture hashing and serialization of retrieval and answer result snapshots.
- Integration-test that an artifact can be written and read after a new process starts.
- Verify a later source version does not alter an existing artifact.
- Run one retrieval and one answer fixture, then compare their saved configuration and metrics.

## Definition Of Done

- Every CLI evaluation execution can optionally write a self-contained JSON artifact.
- A developer can list recent artifacts and inspect one by ID without relying on terminal history.
- Saved artifacts identify the exact fixture content, source evidence, model/configuration, and
  aggregate outcome used for a comparison.
