# Answer Evaluation Development Fixture

Date: 2026-09-16

Status: Implemented

## Problem

Valid retrieved citations do not guarantee that an answer is direct, complete, non-repetitive, or
safely scoped. The R$ 30.000,00 live answer demonstrated this: its citations were valid, but it
restated the same rule three times and did not answer the user's practical question clearly.

## Scope

- add a compact, versioned JSONL development fixture for cited answers
- automate only structural checks: expected abstention and required cited anchors
- attach concise human-review criteria for legal correctness, scope, clarity, and repetition
- provide an explicit CLI command to run the fixture against the deterministic or OpenAI provider

## Assumptions

- application citation validation remains the authority for citation identity and attaches the
  displayed excerpt from the selected chunk
- an LLM or keyword matcher cannot yet be trusted as the sole judge of legal prose quality
- this is a development fixture, not a blind holdout or a release gate

## Design Choice

Each fixture case records a question, required citation anchors, expected abstention, and a
human-review rubric. The evaluator reports a narrow structural pass/fail result and always prints
the rubric. It intentionally does not convert subjective answer quality into a misleading automatic
score.

## Risks

- structural passes can still contain legally incomplete or confusing prose
- human review does not scale indefinitely; later automation must be calibrated against reviewed
  examples, not introduced as an unquestioned judge
- real-provider runs consume API credits and should be explicit

## Test And Eval Plan

- unit-test fixture validation, required-anchor checking, abstention matching, and provider wiring
- run `uv run python -m apps.worker eval-answers --provider fake --strategy lexical` as an
  offline path check
- run `uv run python -m apps.worker eval-answers --provider openai --strategy semantic`
  intentionally with `--show-answers`, then review
  every printed rubric against the generated answers

## Definition Of Done

- the fixture contains the R$ 30.000,00 and R$ 3.000,00-per-month findings plus an abstention case
- structural results distinguish automated checks from human review
- no prompt change is made solely to improve an unmeasured live example

## First Offline Check

The deterministic provider completed the full lexical path on 2026-09-16. It failed all four
structural cases because it deliberately cites only the first retrieved chunk and never abstains.
That is expected: this provider is a wiring double, not an answer-quality baseline. The command
defaults to lexical retrieval so this check makes no embedding or answer-model API calls.

The live `R$ 3.000,00 por mês` failure became `answer-005`. It exposed a model-generated
ellipsis in a supposedly literal quote. The fixture records the expected annual calculation,
material conditions, non-repetition requirement, and application-controlled evidence display.
The answer contract now carries selected chunk IDs only; no fuzzy matching was added.

## First Real Review

The first OpenAI semantic run produced 3/5 structural passes. Human review accepted only
`answer-003` provisionally. The other cases exposed repetition, omitted period scope, a missing
normative anchor, or failure to abstain for an unsupported exercise. These are the baseline findings
for the next prompt-and-presentation iteration; they are not reasons to weaken citation identity.
