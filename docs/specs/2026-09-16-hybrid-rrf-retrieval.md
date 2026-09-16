# Hybrid RRF Retrieval

Date: 2026-09-16
Status: Implemented; No Improvement Over Semantic on Development Fixture

## Problem

Lexical and semantic retrieval expose different evidence: lexical rank rewards exact legal terms,
while semantic rank handles paraphrase and vocabulary mismatch. After measuring each independently,
TaxRAG needs a simple hybrid comparator that does not tune weights against its tiny development
fixture.

## Scope

- add an explicit `hybrid_rrf` retrieval strategy
- retrieve a fixed candidate set from pure lexical and semantic retrieval
- fuse candidates with Reciprocal Rank Fusion (RRF)
- retain each component's rank and score for inspection
- evaluate `hybrid_rrf` against the same versioned development fixture

## Out Of Scope

- learned weights, authority multipliers, cross-encoder reranking, LLM reranking, and answer generation
- changing source labels or evaluation expectations to improve a score
- selecting a final retrieval approach from the development fixture alone

## Options Considered

| Option | Strength | Tradeoff | Decision |
| --- | --- | --- | --- |
| Reciprocal Rank Fusion | Combines rank positions without comparing incompatible score scales or tuning weights | Fixed candidate depth and constant still need documentation | Chosen first hybrid |
| Weighted score fusion | Can favor a preferred retriever | Requires calibrated weights; unsuitable for nine inspected cases | Not chosen |
| Candidate union plus cross-encoder reranker | Often stronger final ranking | Adds another model, latency, cost, and a second source of evaluation ambiguity | Revisit after hybrid baseline |

## Design Choice

For each question, retrieve the top 20 candidates from `lexical` and the top 20 from `semantic`.
For every unique chunk, calculate:

```text
RRF score = sum(1 / (60 + rank)) for each retrieval list where the chunk appears
```

The constant `60` is the conventional RRF damping constant. It makes the contribution of rank one
only modestly larger than nearby ranks, preventing one retriever from dominating solely because its
numeric score scale differs. The candidate depth and constant are fixed implementation parameters,
not values fitted to development cases.

`hybrid_rrf` preserves lexical and semantic component scores and ranks on every result. It applies
no authority adjustment. The final ordering is RRF score, then best component rank, then anchor key
for deterministic ties.

## Risks

- A candidate present in both lists can outrank a more direct result present in only one list.
- RRF cannot fix an error shared by both retrievers.
- The small inspected development fixture can diagnose behavior but cannot choose a production winner.
- Hybrid retrieval adds one embedding API call per query, just as semantic retrieval does.

## Test And Eval Plan

- unit-test RRF score calculation, duplicate merging, missing component ranks, and deterministic ties
- unit-test strategy validation and CLI exposure
- run lexical, semantic, and hybrid RRF evaluations on the unchanged development fixture
- record both acceptable and preferred-source recall@3 without modifying labels

## Definition Of Done

- `hybrid_rrf` is independently selectable and reports component rank evidence.
- The fusion rule has no fitted weights or hidden authority adjustment.
- A same-fixture comparison is recorded, with no claim of final model selection.

## Evaluation Evidence

Validated locally on 2026-09-16 against the unchanged nine-case development fixture:

| Strategy | Required acceptable recall@3 | Preferred-source recall@3 |
| --- | --- | --- |
| `lexical` | 8/9 (89%) | 2/5 (40%) |
| `semantic` | 9/9 (100%) | 4/5 (80%) |
| `hybrid_rrf` | 9/9 (100%) | 2/5 (40%) |

The hybrid result matches semantic's required-support score but loses two preferred-source hits.
We therefore retain `semantic` as the leading development-set strategy and do not promote RRF as a
default. This is not a final rejection of hybrid retrieval: the fixture is small and inspected, and
RRF's value can change as sources and independently authored evaluation cases expand.
