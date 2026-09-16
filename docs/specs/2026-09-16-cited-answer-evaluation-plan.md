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
- validate every model-selected citation against the retrieved chunk before displaying an
  application-controlled excerpt
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
2. **Answering:** ask a model to produce structured output that can select only those retrieved
   chunk IDs. Application code rejects unknown citations and attaches the selected chunk text as
   the cited excerpt for review.

The initial answer evaluation will use human-authored expected claims and citation anchors. This
keeps the legal standard inspectable. An LLM-as-judge may later help scale reviews, but only after
we compare it with a human-labelled sample.

The first compact development fixture is implemented in
`docs/evals/cited-answer-development.jsonl`. Its automated result is intentionally limited to
expected abstention and required citation anchors; the fixture also carries a mandatory human
review rubric for claim correctness, scope, clarity, and repetition.

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
retrieved and its model-copied excerpts occurred verbatim in their cited chunks. Manual review still
found an answer-quality defect: it stated the capital-gain rule categorically while omitting the
source's `pessoa física residente no Brasil` condition. This confirms that citation integrity is
necessary but does not prove semantic completeness or safe wording. The provider instruction now
requires conditional, general wording and preservation of material scope conditions. The finding
must become a hand-reviewed answer-evaluation case before this slice is marked implemented.

A second run of the same question changed the categorical wording to `pode obrigar`, but still
omitted the residency condition and introduced a broad claim about `outras condições` that was not
fully supported by its attached excerpts. Prompt hardening is therefore only a mitigation. It does
not replace a human-authored answer fixture or manual review of early results.

Provider output can fail when it transcribes an excerpt imperfectly. The original exact-match
rejection was safe, but copying legal text was an unnecessary model responsibility. The answer
contract now lets the model select only retrieved `chunk_id` values and lets application code attach
the literal chunk excerpt. The answer boundary still returns safe abstention for malformed output or
unknown chunk IDs rather than exposing an internal traceback.

For local root-cause analysis, the `answer --debug` command writes a rejected untrusted draft,
the validation reason, and the retrieved chunks to `stderr`. It is opt-in and must not be used in
shared logs or with sensitive questions. The default path continues to expose only the safe
abstention result.

## Quote-Rejection Finding

The question `Recebi apenas 3 mil por mês no ano passado. Devo declarar?` produced two valid
citations and one invalid supplementary citation. The invalid citation replaced omitted portions
of a long official list with `...`; those characters are not a literal excerpt, so deterministic
validation correctly rejected it. This is not evidence to introduce fuzzy quote matching: fuzzy
matching could accept a modified monetary threshold, exception, or scope condition. The case is
recorded as `answer-005` in the answer-development fixture. The contract now uses application-
controlled excerpts keyed by retrieved chunk ID; see
`2026-09-16-application-controlled-citations.md`.

## First Real Fixture Run

On 2026-09-16, the five-case development fixture ran with `gpt-4.1-mini` and semantic retrieval.
The structural result was **3/5**: `answer-001`, `answer-003`, and `answer-005` selected their
required anchors and had the expected non-abstention outcome; `answer-002` missed required anchor
`art-2-inciso-iii`; and `answer-004` answered when the fixture expected abstention for the
unsupported exercise 2025 rule.

Human review must not treat the three structural passes as product passes:

| Case | Human review | Finding |
| --- | --- | --- |
| `answer-001` | Needs improvement | Reaches the correct threshold comparison but repeats equivalent sources and omits explicit `2025` / exercise `2026` scope in its main rule statement. |
| `answer-002` | Needs improvement | Explains the capital-gain condition but retrieval did not select the normative anchor required by the fixture; it also adds an unnecessary list of other conditions. |
| `answer-003` | Provisional pass | Directly explains voluntary filing and its dependent limitation without claiming a guaranteed refund. |
| `answer-004` | Fail | Safely signals that the source scope is exercise 2026, but should abstain instead of creating unsupported claims about exercise 2025. |
| `answer-005` | Needs improvement | Calculates R$ 36.000,00 and identifies the threshold, but omits explicit year/exercise scope, repeats conditions, and overstates unspecified possible dispensations. |

The next change may now target prompt and answer presentation, because it is supported by five
reviewed cases rather than one anecdote. It must preserve application-controlled citations and add
tests for: direct criterion-limited conclusions, explicit year/exercise scope, concise source
selection, and abstention when the requested exercise is unsupported.

The planned implementation is specified in
`2026-09-16-criterion-limited-answer-prompt.md`. The fixture must remain unchanged for the next
real run so it can measure this prompt iteration against the documented baseline.

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
