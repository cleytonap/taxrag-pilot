# Evaluation Strategy

TaxRAG evaluates the whole source-grounded answer path, not only an LLM response:

```text
question -> retrieval -> source and anchor selection -> grounded answer -> citation validation
```

## Three Eval Layers

Each layer isolates one part of the pipeline. A failure is diagnosed at the lowest layer that
shows it.

| Suite (id) | File | Input | Measures | Runs |
| --- | --- | --- | --- | --- |
| Retrieval (`retrieval`) | `lexical-retrieval-baseline.jsonl` | question | whether an acceptable chunk is retrieved: recall@1/3/5/10, MRR, preferred-source recall | any strategy; no LLM |
| Answer generation (`generation`) | `answer-generation.jsonl` | question + **fixed** chunks | answer behaviour with retrieval held constant: citations, abstention, grounding, human criteria | answer provider only |
| End-to-end (`answer`) | `cited-answer-development.jsonl` | question | what the user gets from the production pipeline | production strategy + provider |

How to read them together:

- If e2e fails but generation passes, the cause is retrieval.
- If generation fails, the cause is the answer mechanism (prompt, validation, gates), whatever
  the retrieval.
- Generation contexts include realistic distractors taken from real retrievals, so the suite
  also tests resistance to misleading evidence.

## Production Focus

The product optimises **one** pipeline: `TAXRAG_ANSWER_STRATEGY` (default `semantic`; the
candidate replacement `hybrid_rerank` is adopted only if V2 meets the rule in
`v1-results-rca.md` §5). A change
is accepted on its generation and e2e results. Retrieval metrics explain those results. The other
retrieval strategies stay in the retrieval suite as diagnostics and references; they are not
required to improve. Commands and the UI default to the production strategy. Citation text and
indexed text are separate columns, so an indexing change never alters what a user sees cited.

## Scope And Source Policy

- **Portuguese only.** Questions confidently detected as another language receive a fixed
  notice (outcome `unsupported_language`, a correct abstention in evals). The gate favours
  precision: uncertain text is treated as Portuguese.
- **Known-wrong official passages are excluded** from the index via `data/source-errata.json`.
  Each entry quotes the conflicting text and the controlling norm; tests verify both. Fixtures
  must never use an excluded anchor as evidence.
- **Answers are verified before display.** After deterministic checks (citations retrieved,
  figures present in the cited evidence), an independent verifier blocks answers that do not
  address the question or rely on unsupported claims (outcome `verification_abstained`, a
  deliberate abstention; `verifier_blocked_answerable` counts its cost).
- **Answers show their caveats.** `limitation` and `clarification_question` are part of the
  user-visible answer and are graded in human review.

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

### Retrieval Labelling Rules

Full rationale: [2026-11-05 audit spec](../specs/2026-11-05-retrieval-eval-coverage-and-label-audit.md).
Coverage matrix: [retrieval-coverage.md](retrieval-coverage.md).

- **Acceptable** = a chunk that, read alone, lets a user verify a correct answer to the question *as
  asked* (same year, same kind of person, same context). Exclude chunks that state the rule only
  for another context, and chunks whose figure for the asked fact is stale. The official P&R has
  some: Q088 gives R$ 300.000,00 where the IN says R$ 800.000,00.
- **Complete** = every such chunk in the corpus is listed. Missing one turns a correct retrieval into
  a reported failure. Establish completeness by pooled review (below), not by memory.
- **Preferred** is declared only when two or more acceptable anchors compete and the source policy
  decides. Otherwise leave it empty.
- **Metadata** on every case: `topic`, `covers` (precise legal/P&R reference, e.g. `IN art. 11, §3, I`),
  `style` (`source-wording` | `paraphrase` | `scenario`), optional `edge_case`, and `label_notes`
  (why these anchors, what was rejected and why). Answer cases may carry `topic`, `edge_case` and
  `label_notes`; any other unknown key is rejected so typos in scored fields fail loudly. The loader ignores these fields, so cases added from the Workshop UI must gain
  them before merge.
- **IDs** are never reused. Label corrections keep the ID. A changed question is a new case,
  except for an outright defect fix, which is recorded in a spec.

### How To Review The Retrieval Suite

Do this after any fixture edit, extractor change, or source update. Work in topic batches of
10–15 cases so each source section stays in your head.

1. **Rebuild and run.** Reprocess the sources and regenerate embeddings (an extractor version bump
   deletes them for every source), then run all strategies. Each run is saved to `var/eval-runs/`
   and appears in the Workshop's Run archive:

   ```bash
   bash scripts/run-workshop.sh --with-embeddings   # or process-source/embed-source manually
   for st in lexical lexical_authority semantic hybrid_rrf; do
     uv run python -m apps.worker run-suite retrieval --strategy $st --confirm-paid
   done
   ```

2. **Check each case's labels (accuracy).** Open every acceptable anchor through its source link
   and ask:
   - Does this chunk alone answer *this* question?
   - Is the year right: ano-calendário 2025, exercício 2026?
   - Is the figure current (the IN wins over the P&R)?
   - Is the `covers` reference the exact provision?
   - If a preferred anchor is set, does the 2026-09-08 policy justify it?
   - Is the question realistic, unambiguous, and not simply a copy of the answer's wording?
3. **Check each case's labels (completeness).** Pool unlabelled candidates from several strategies
   and read each one. Add it, or record in `label_notes` why it was rejected:

   ```bash
   uv run python scripts/pool-retrieval-candidates.py --strategies lexical semantic hybrid_rrf --k 5
   ```

4. **Triage every failure** before touching anything. Classify it as:
   - *retrieval miss*: a valid label was not retrieved. Keep the case and record it.
   - *label too narrow*: add the anchor, with a reason.
   - *question ambiguous or defective*: fix it or retire it, with a reason.
   - *extraction defect*: fix the extractor in its own spec.

   Only the last three justify a fixture edit. Never edit labels because a score went down.
5. **Coverage.** Regenerate `retrieval-coverage.md` and confirm that every user-relevant IN article
   is still covered. `test_retrieval_fixture_covers_every_user_relevant_in_rfb_2312_article`
   enforces Arts. 1–16. Regenerate the report with
   `uv run python scripts/retrieval-coverage-report.py`.
6. **Second reviewer.** Have a second person independently label a random ~20% sample, blind to the
   existing labels. Disagreements show where the rules above are unclear. Someone other than the
   suite's author should write the holdout set.

### Edge Cases

A RAG eval suite needs more than "normal" questions. Real users misspell words, ask about the wrong
year, bundle several facts into one question, ask things the corpus cannot answer, and
occasionally try to subvert the assistant. Each edge case is tagged with `edge_case` so runs can be
sliced by category, and `test_fixtures_keep_their_edge_case_categories` stops a category from
silently disappearing.

Where an edge case lives depends on what "correct" means for it:

- **Retrieval suite (answerable, hard form).** A correct chunk exists, so recall can be scored.
  Categories: `typo-no-accents`, `keyword-only`, `long-noisy`, `boundary-value`,
  `other-year` (the guidance table maps each exercise to its norm),
  `scope-boundary`, `stale-source-conflict` (the official P&R contains an outdated figure),
  `false-premise`, `multi-condition` (the decisive criterion must be retrieved, not just a
  related one).
- **Answer suite (refuse, narrow, or correct).** Either no correct chunk exists, or the difficulty
  is in how the answer behaves. Expected abstention: `other-year`, `future-year`,
  `out-of-scope-tax`, `out-of-scope-jurisdiction`, `off-domain`, `prompt-injection`,
  `unsupported-language` (fixed Portuguese-only notice), `insufficient-evidence` (generation
  suite: in-scope question, context that does not answer it),
  `missing-source` (an IRPF topic absent from the corpus, which tests hallucination from model
  memory). Expected grounded answer: `calendar-vs-exercise`, `boundary-value`,
  `personalized-advice` (scope-limited, no computed amount), `false-premise` (correct the
  premise), `stale-source-conflict` (use the IN figure, never the stale P&R one), `scope-boundary`,
  `arithmetic`, `below-threshold`.

Known contract limitation: answer cases are scored as *answer* or *abstain* only. A genuinely
ambiguous question (e.g. "IR 2025", which may mean exercise 2025 or calendar year 2025) should
ideally trigger a clarification question, which the binary contract cannot score. Such cases are
excluded until the contract gains an explicit `clarify` outcome. Retrieval also has no "no-answer"
metric yet. Once retrieval gets a confidence threshold, out-of-scope questions should be added
there too, with the expectation that nothing is retrieved above the threshold.

### Human Review Of Answer Runs

Generate a review form from any generation or e2e run. It shows each answer exactly as the user
sees it, with its citations:
`uv run python scripts/answer-review-form.py <run-or-baseline>.json`.
Review only changed cases when comparing against a reviewed baseline.

### Baselines

Record a baseline before optimising, then compare every change against it. The protocol, the
current V0 status and the comparison commands are in [baselines/README.md](baselines/README.md).

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

## Cited Answer Development Fixture

This is the **end-to-end** suite (id `answer`). Its fixed-evidence counterpart is
`answer-generation.jsonl` (id `generation`).

`cited-answer-development.jsonl` is a small human-authored development fixture for the answer
path. Each case contains acceptable official citation anchors, expected abstention, and a
human-review rubric. A passing non-abstention needs at least one of those anchors; selecting a
primary normative source rather than directly supporting official guidance is not yet a gate.
The command below reports only structural checks; it does **not** claim to automatically judge
legal correctness, clarity, or repetition:

```bash
uv run python -m apps.worker eval-answers --provider fake --strategy lexical
uv run python -m apps.worker eval-answers --provider openai --strategy semantic --show-answers
```

The fake run only checks the offline wiring; its deliberately extractive provider is not expected
to satisfy the full fixture. The OpenAI run is intentional and billable. Review each generated
answer against the printed criteria before changing the prompt, retrieval, or guardrails.

## Retrieval Comparison Protocol

Compare retrieval approaches on the same development fixture before combining them. Record both
required `acceptable_anchor_keys` recall@3 and optional `preferred_anchor_keys` recall@3; they
answer different questions:

- acceptable recall asks whether the system found a passage that can support the answer;
- preferred-source recall asks whether it found the most direct/current/authoritative passage when
  the fixture makes that distinction.

The current sequence is intentionally incremental:

1. `lexical`: PostgreSQL Portuguese full-text rank only. This is the stable reference score.
2. `lexical_authority`: the existing bounded authority multiplier, reported separately as an
   experiment rather than folded into the baseline.
3. `semantic`: cosine similarity over model-versioned chunk embeddings. It tests paraphrase and
   vocabulary-mismatch retrieval without lexical ranking assistance.
4. `hybrid_rrf`: the current hybrid candidate. It fuses the top 20 lexical and semantic candidates
   using the documented Reciprocal Rank Fusion rule with damping constant 60.
5. Future hybrid candidates: weighted score fusion or candidate-union plus a reranker. Do not call
   any mixed method simply "hybrid" without recording its exact rule and parameters.

Do not choose weights or source-preference rules merely to improve a few development examples.
The development fixture is a diagnostic tool: it shows where a method succeeds or fails. A frozen
holdout set is the eventual decision gate once the V1 source inventory and labels are complete.
