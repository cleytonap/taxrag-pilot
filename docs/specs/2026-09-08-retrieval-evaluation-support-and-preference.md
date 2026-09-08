# Retrieval Evaluation: Acceptable Support And Source Preference

Date: 2026-09-08
Status: Implemented

## Problem

The initial retrieval evaluation assigned exactly one expected anchor to each question. After
adding official guidance, the annual questions-and-answers PDF, and the normative instruction,
that rule became misleading: several passages can correctly support a question, while some sources
are preferable for a user-visible citation.

## Scope

- replace the singular evaluation anchor with explicit acceptable-anchor sets
- add an optional preferred-anchor subset for source-quality measurement
- report both acceptable-support recall@3 and preferred-source recall@3 from the worker CLI
- migrate the development fixture to reviewed, source-aware labels

## Out Of Scope

- changing lexical ranking, adding authority boosts, embeddings, or rerankers
- final answer evaluation, citation validation, or a frozen holdout set

## Options Considered

| Option | Strength | Tradeoff | Decision |
| --- | --- | --- | --- |
| One exact anchor per question | Very simple metric | Mislabels equivalent official support as failure | Not chosen |
| Any chunk from an allowed source | Low labeling effort | Lets irrelevant passages from that source pass | Not chosen |
| Explicit acceptable and preferred anchor sets | Auditable correctness and source-quality signals | Requires careful editorial labels | Chosen |

## Design Choice

`acceptable_anchor_keys` is a non-empty list of passages that directly support the question.
`preferred_anchor_keys` is an optional subset that represents the best citation when the question
is answerable by more than one source. The runner records the first rank for each set. A result
passes required retrieval recall when an acceptable anchor occurs in the top three; preferred
recall is reported separately and is not yet a release gate.

## Risks

- A broad acceptable set can hide a weak ranking if labels are not reviewed carefully.
- A higher-authority source is not always the best citation when an official guidance page is more
  direct about a procedure or user-facing exception.
- The fixture remains a development set, so it cannot establish unbiased release quality.

## Test And Eval Plan

- validate non-empty, duplicate-free anchor sets and ensure preferred anchors are acceptable
- test that the runner reports separate acceptable and preferred ranks
- run the migrated fixture against the current corpus before considering a ranking change

## Definition Of Done

- The development fixture can describe equivalent official support without losing precision.
- CLI output distinguishes support recall from preferred-source recall.
- The current baseline is recorded without altering ranking behavior.

## Implementation Evidence

Validated locally on 2026-09-08 after the HTML guidance, IRPF questions-and-answers PDF, and
IN RFB 2.312/2026 sources were processed:

- The fixture now contains nine reviewed development cases. Every case has one or more precise
  acceptable anchors; five cases also declare a preferred subset.
- The lexical baseline achieved acceptable-support recall@3 of `8/9` (89%). The remaining failure
  is the existing dependency question, which is not yet retrieved in the top three.
- Preferred-source recall@3 was `1/5` (20%). The Q&A source wins the broad-obligation case, while
  primary normative anchors for threshold and source-identification questions remain outside the
  top three.
- This metric is observational only. No ranking score, source-authority boost, or evaluation label
  was changed to improve it.
