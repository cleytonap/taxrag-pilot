# Development Retrieval Evaluation Expansion

Date: 2026-09-16
Status: Implemented

## Problem

The initial nine-case development fixture established lexical, semantic, and hybrid baselines, but
it under-covers the 2026 corpus. In particular, most obligation rules from IN RFB 2.312/2026 and
several official Q&A clarifications have no executable retrieval check.

## Scope

- expand the existing development fixture from 9 to 25 cases
- cover each substantive Art. 2 obligation condition, the three relevant exceptions, and two Q&A
  clarifications
- use only already-ingested, active source anchors
- keep `acceptable_anchor_keys` and `preferred_anchor_keys` semantics unchanged
- rerun lexical, semantic, and hybrid RRF retrieval without changing any retrieval implementation

## Out Of Scope

- a hidden or frozen holdout set
- changing retrieval scoring, chunking, sources, or labels to improve measured outcomes
- answer-generation evaluation

## Design Choice

Use one direct question per legal condition, with natural Portuguese phrasing but no intentionally
unanswerable ambiguity. For rules stated directly in IN RFB 2.312/2026, the corresponding Art. 2
anchor is both acceptable and preferred. An official Q&A passage is preferred when it is the direct
source for a clarification such as company ownership or age.

This remains a development fixture: the cases are visible and will be used to diagnose changes.
It increases coverage; it does not establish a blind final benchmark.

## Risks

- More cases can lower an aggregate score without representing a product regression; each failure
  needs classification before any retrieval change.
- A concise legal anchor may omit context needed for an eventual generated answer; this slice tests
  retrieval, not answer sufficiency.
- Current source coverage is limited to 2026 filing obligations and related clarifications.

## Test And Eval Plan

- validate the fixture schema and unique case IDs in unit tests
- run all selectable strategies against the unchanged source corpus
- record required and preferred recall@3 per strategy
- inspect failures as diagnostics only; do not tune parameters in this slice

## Definition Of Done

- 25 valid, source-grounded development cases cover the stated scope.
- Every strategy is rerun against the expanded fixture.
- The results and remaining limitations are recorded without choosing a final model.

## Evaluation Evidence

Validated locally on 2026-09-16 after expanding the unchanged source corpus to 25 development
questions. The 9-case and 25-case scores are not directly comparable because the denominator and
coverage changed.

| Strategy | Required acceptable recall@3 | Preferred-source recall@3 |
| --- | --- | --- |
| `lexical` | 13/25 (52%) | 4/19 (21%) |
| `lexical_authority` | 14/25 (56%) | 5/19 (26%) |
| `semantic` | 23/25 (92%) | 14/19 (74%) |
| `hybrid_rrf` | 19/25 (76%) | 7/19 (37%) |

Semantic retrieval remains the leading development strategy. The two required-support gaps are
`lex-010` (gain of capital on asset disposal) and `lex-015` (becoming a Brazilian resident during
the year). They are recorded as future diagnostic targets, not reasons to alter ranking parameters
in this evaluation-expansion slice.

The unweighted RRF hybrid is weaker than semantic on both metrics. It remains a reproducible
comparator, but is not a default or a reason to begin weight calibration. The next quality step
should be independently authored holdout construction and/or failure analysis, not another ranking
parameter experiment.
