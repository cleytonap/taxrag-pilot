# Answer Outcome Provenance

Date: 2026-09-16

Status: Implemented

## Problem

The first prompt-comparison run reported `answer-004` as a structural abstention pass because the
safe fallback had `abstain=true`. Its generic limitation showed that the provider output had been
rejected instead of deliberately abstaining. Counting those outcomes together makes the evaluation
look safer than it is.

## Scope

- add an explicit outcome to every `CitedAnswer`
- distinguish a provider's valid abstention from no retrieved evidence and rejected provider output
- require `provider_abstained` for an answer fixture case expecting abstention

## Design Choice

The outcome is one of `answered`, `provider_abstained`, `no_retrieved_evidence`, or
`provider_rejected`. All non-answer outcomes remain safe user-facing abstentions, but only a valid
provider abstention can satisfy an abstention expectation in the evaluator.

## Risks

- callers must not read `abstain=true` as proof of a successful model behavior without inspecting
  `outcome`
- this is outcome provenance, not a semantic correctness judgment

## Test And Eval Plan

- unit-test every safe outcome category
- unit-test that `provider_rejected` fails an expected-abstention fixture case

## Definition Of Done

- CLI and API serialization expose the outcome
- structural answer metrics do not give credit for provider rejection
