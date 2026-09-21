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
- discard rather than reject draft claims when `abstain=true`, because abstention claims are never
  rendered in the final answer

## Design Choice

The outcome is one of `answered`, `provider_abstained`, `no_retrieved_evidence`, or
`provider_rejected`. All non-answer outcomes remain safe user-facing abstentions, but only a valid
provider abstention can satisfy an abstention expectation in the evaluator.

An abstaining draft is normalized to an empty final claim list. The prompt still asks the provider
to put its explanation in `limitation` and leave `claims` empty, but a stray draft claim is not
shown to the user and does not justify replacing an otherwise useful abstention with a generic
fallback. Non-abstaining claims remain subject to full retrieved-chunk validation.

`CitedAnswer.text` remains the claim-only field used for citation/provenance inspection.
`CitedAnswer.display_text` is the user-facing field: it returns claims for an ordinary answer, or
the limitation followed by the clarification question for an abstention. Callers rendering an
answer must use `display_text` rather than treating an empty claim list as an empty response.

## Risks

- callers must not read `abstain=true` as proof of a successful model behavior without inspecting
  `outcome`
- this is outcome provenance, not a semantic correctness judgment
- `limitation` remains provider prose, so this normalization does not prove its legal correctness;
  the answer fixture and human review continue to assess its scope

## Test And Eval Plan

- unit-test every safe outcome category
- unit-test that `provider_rejected` fails an expected-abstention fixture case
- unit-test that an abstaining draft with stray claims produces no final claims and retains its
  limitation
- unit-test that an abstention has empty claim text but non-empty user-facing display text

## Definition Of Done

- CLI and API serialization expose the outcome
- structural answer metrics do not give credit for provider rejection
