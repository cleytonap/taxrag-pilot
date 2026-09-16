# Criterion-Limited Answer Prompt Iteration

Date: 2026-09-16

Status: Proposed

## Problem

The first real five-case answer evaluation found valid chunk citations but weak user-facing prose:
repetition of equivalent sources, omitted calendar/exercise scope, broad unnecessary lists of other
criteria, and a non-abstaining answer for an unsupported exercise. The R$ 30.000,00 and R$ 3.000,00
per-month cases also need a practical conclusion limited to the criterion actually established by
the evidence.

## Scope

- change only the OpenAI answer instruction
- require explicit calendar-year and exercise scope when supplied by evidence
- allow a direct conclusion only when it is explicitly limited to the established criterion
- prefer concise, non-redundant claims and citations
- require abstention, with no claims, for a requested year or exercise not supported by retrieved
  evidence

## Assumptions

- application-controlled chunk citations remain unchanged
- prompt instructions reduce, but cannot prove, answer-quality defects
- fixture review, not a single live answer, decides whether this iteration is useful

## Design Choice

The instruction will tell the provider to state conclusions in the form “por este critério” when
the question supplies enough facts for a retrieved rule. It will prohibit unrelated lists of other
filing hypotheses unless they are necessary to avoid a misleading conclusion. It will require
`abstain=true` if the requested exercise or calendar year differs from the evidence scope.

## Risks

- the model may still ignore instructions or overgeneralize from a one-sided threshold rule
- a concise answer can omit a material exception; human review must check this explicitly
- a prompt can overfit these five development cases, so the future holdout remains necessary

## Test And Eval Plan

- unit-test that the configured provider receives the new explicit policy instructions
- retain all five answer fixture cases unchanged
- run the same OpenAI semantic fixture after the change and compare structural outcomes and human
  review with the documented 3/5 baseline

## Definition Of Done

- the new policy is explicit and documented in code and this spec
- the fixture remains unchanged and the second real run is reviewed case by case
- no citation identity or ingestion behavior is weakened
