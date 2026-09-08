# Evaluation Strategy

TaxRAG evaluates the whole source-grounded answer path, not only an LLM response:

```text
question -> retrieval -> source and anchor selection -> grounded answer -> citation validation
```

## Evaluation Sets

### Development Set

Use this set during normal development. It may guide changes to extraction, chunking, lexical or semantic retrieval, prompts, guardrails, and citations.

The current `lexical-retrieval-baseline.jsonl` is a development set. Known failure cases are explicitly labeled rather than silently removed.

Each retrieval case declares `acceptable_anchor_keys`: exact passages that can support the
question. A case may also declare the subset `preferred_anchor_keys`, used to measure source
quality separately from basic support retrieval. For example, a current normative inciso can be
preferred over an explanatory page, while the explanatory page remains acceptable when it directly
supports the same answer. Do not treat preferred-source recall as a release gate until its labels
have been reviewed for directness, currency, and authority.

Re-run development retrieval evaluations whenever the source corpus changes. A source expansion
can reveal both genuine ranking regressions and overly narrow exact-anchor expectations; record
and classify each change rather than changing labels merely to restore a passing score.

### Holdout Set

Create and freeze the V1 holdout set after all intended V1 source families are ingested and chunked: Receita guidance HTML, the applicable normative instruction, and the official IRPF questions-and-answers PDF.

Do not inspect individual holdout failures while iterating on the system. Run the set only for meaningful comparisons, such as the lexical baseline, semantic retrieval candidate, hybrid retrieval candidate, and release candidate.

When a holdout case is inspected and used to improve the system, move it to the development set and replace it with a new holdout case.

For a strictly blind holdout, keep the questions and labels under user or external-reviewer control. Repository-visible cases remain useful frozen regression tests, but are not blind to an agent that can read the repository.

### Production Monitoring Set

After launch, collect anonymized, reviewed failure patterns. Promote them to the development set or a future holdout set rather than repeatedly tuning against the same production examples.

## V1 Holdout Coverage

Target 40-60 cases after the source inventory is complete. Cover:

- threshold boundary wording, including equal-to versus above-threshold cases
- multiple or overlapping filing conditions
- Portuguese paraphrases and vocabulary mismatch
- exercise and calendar-year traps
- normative source versus explanatory-guidance selection
- unsupported questions and missing-source abstention
- personalized-advice requests that require scope limitation
- valid source, anchor, and excerpt citations

## Metrics

- retrieval recall@k: expected source anchor appears in the first `k` results
- citation validity: cited chunk was retrieved and belongs to the cited active source version
- grounded-answer support: each material claim is supported by the cited excerpt
- abstention quality: unsupported or individualized requests are safely narrowed or declined
- year/period accuracy: answer does not apply a rule to an unsupported exercise or calendar year
