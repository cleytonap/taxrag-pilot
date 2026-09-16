# Cited Answer Evaluation Plan

Date: 2026-09-16

Status: In Progress

## Problem

Retrieval evaluation shows whether TaxRAG selected useful evidence. It does not show whether an
answer is correct, whether each claim is supported, whether citations point to the right passage,
or whether the system abstains when evidence is missing. These are separate risks for a tax
product and must be measured separately.

## Scope

- use `semantic` retrieval as the development default for the first cited-answer vertical slice
- define a structured answer contract: answer text, citations, limitations/abstention, and an
  optional clarification question
- validate every returned citation against the exact retrieved chunk before displaying an answer
- add a small, human-authored answer-evaluation set with expected claims, required citations, and
  expected abstention or clarification behaviour where applicable
- measure answer correctness, claim grounding, citation correctness/completeness, and abstention
  behaviour alongside retrieval metrics

## Out Of Scope

- further hybrid weights, reranking, or embedding-model changes without a diagnosed retrieval
  failure
- automatic tax determinations or personalised tax advice
- treating an LLM judge as the sole authority on legal correctness

## Design Choice

We will separate the pipeline into two observable stages:

1. **Retrieval:** select up to three official chunks and record their anchors, source versions,
   ranks, and strategy.
2. **Answering:** ask a model to produce structured output that can cite only those retrieved
   chunk IDs. Application code rejects unknown citations and preserves the cited excerpts for
   review.

The initial answer evaluation will use human-authored expected claims and citation anchors. This
keeps the legal standard inspectable. An LLM-as-judge may later help scale reviews, but only after
we compare it with a human-labelled sample.

## Metrics

| Layer | Metric | Question answered |
| --- | --- | --- |
| Retrieval | Required acceptable recall@3 | Is usable evidence present? |
| Retrieval | Preferred-source recall@3 (diagnostic only) | Is a policy-designated legal basis present for an applicable case? |
| Retrieval | MRR / nDCG@3 | Is the evidence ranked early and by authority/relevance? |
| Answer | Claim correctness | Are the required legal facts stated correctly? |
| Answer | Claim grounding | Is each material claim supported by cited retrieved text? |
| Citation | Citation correctness | Does each displayed citation support its adjacent claim? |
| Citation | Citation completeness | Do all material claims carry adequate citations? |
| Safety | Abstention / clarification accuracy | Does the system avoid an unsupported individual conclusion? |
| Operations | Latency and token cost | Is the answer path practical to operate? |

## Transition Criteria

- The current 25-case development retrieval fixture remains for diagnosis and iteration.
- Preferred-source recall is an optional citation-policy diagnostic. It must not be tuned as a
  general ranking target; future labels require a written source-policy rationale.
- Before selecting a release/default retrieval configuration, create a separately authored frozen
  holdout set; it must not be used to tune ranking parameters.
- Do **not** wait for perfect retrieval before building cited answers. The answer contract must
  expose uncertainty and abstain when retrieved support is insufficient.
- Retrieval changes after this point require evidence: a failed holdout case, a traced answer
  failure, or a source-corpus change.

## Risks

- A fluent model can make unsupported statements even with good retrieval; citation validation
  checks citation identity, not semantic entailment.
- A single concise legal chunk may be sufficient for a retrieval pass but inadequate for a clear
  answer. Answer evaluation must therefore assess required claims separately.
- The small current corpus and evaluation set cannot justify broad quality claims.

## First Live-Path Finding

The first live answer on 2026-09-16 passed deterministic citation validation: its chunk IDs were
retrieved and both quoted excerpts occurred verbatim in their cited chunks. Manual review still
found an answer-quality defect: it stated the capital-gain rule categorically while omitting the
source's `pessoa física residente no Brasil` condition. This confirms that citation integrity is
necessary but does not prove semantic completeness or safe wording. The provider instruction now
requires conditional, general wording and preservation of material scope conditions. The finding
must become a hand-reviewed answer-evaluation case before this slice is marked implemented.

A second run of the same question changed the categorical wording to `pode obrigar`, but still
omitted the residency condition and introduced a broad claim about `outras condições` that was not
fully supported by its attached excerpts. Prompt hardening is therefore only a mitigation. It does
not replace a human-authored answer fixture or manual review of early results.

Provider output can also fail deterministic quote validation when it transcribes an excerpt
imperfectly. This is a safe rejection, not a reason to weaken exact quote validation. The answer
boundary must return a verified-abstention result rather than expose an internal traceback; future
work may reduce these rejections by letting the model select stable application-provided excerpt
identifiers instead of copying quote text.

For local root-cause analysis, the `answer --debug` command writes a rejected untrusted draft,
the validation reason, and the retrieved chunks to `stderr`. It is opt-in and must not be used in
shared logs or with sensitive questions. The default path continues to expose only the safe
abstention result.

## Test And Eval Plan

- Unit-test structured-output parsing and rejection of a citation ID that was not retrieved.
- Integration-test a cited answer with a deterministic fake provider before making a paid model
  call.
- Run the answer fixture against the real provider only after the deterministic path is green;
  save the model, prompt version, retrieval anchors, latency, and token use with each run. The
  storage design is defined in `2026-09-16-evaluation-run-persistence.md`.
- Manually review all initial answer failures and a representative passing sample.

## Definition Of Done

- A command can answer a question from retrieved chunks and return structured citations.
- Invalid or unsupported citation IDs cannot reach the caller.
- A compact answer fixture reports the metrics above, including at least one abstention or
  clarification case.
- The source version and cited excerpt are preserved with every evaluation result.
