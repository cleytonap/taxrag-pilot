# Evaluation Baselines

A baseline is a frozen, Git-tracked copy of one eval run. Later runs are compared against it to
answer one question: *did this change make the system better or worse, and on which cases?*

Local runs are written to `var/eval-runs/`, which is gitignored, disposable and 2–3 MB per run.
Promoting a run copies it here, shortens chunk excerpts to 300 characters (the full text is
reproducible from the recorded source versions) and adds a `baseline` block with its label.
Baselines are **immutable**: promotion refuses to overwrite an existing label. To re-baseline,
use a new label (`v1`, `v0.1`, …).

Each file records the fixture SHA-256, strategy, provider, embedding and answer models, source
version hashes, summary metrics, and per-case results with retrieved anchors and ranks.
File name: `<label>_<suite>_<strategy>[_<provider>].json`.

## V0 baseline (pre-optimisation reference)

Fixtures: `lexical-retrieval-baseline.jsonl` (70 cases, 10 edge cases) and
`cited-answer-development.jsonl` (33 cases, 19 edge cases, 10 expected abstentions). Corpus:
extractor v6, 787 chunks.

| Run | File | Headline |
| --- | --- | --- |
| retrieval · `lexical` | `v0_retrieval_lexical.json` | recall@3 11/70 (15.7%); preferred 3/46 |
| retrieval · `lexical_authority` | `v0_retrieval_lexical_authority.json` | recall@3 10/70 (14.3%); preferred 3/46 |
| retrieval · `semantic` | `v0_retrieval_semantic.json` | recall@3 **58/70 (82.9%)**; preferred 23/46 |
| retrieval · `hybrid_rrf` | `v0_retrieval_hybrid_rrf.json` | recall@3 48/70 (68.6%); preferred 18/46 |
| answer · `openai` · `semantic` | `v0_answer_semantic_openai.json` | structural 23/33; **human review 12/33**; abstentions 7/10 |
| answer · `openai` · `lexical` | `v0_answer_lexical_openai.json` | structural 12/33 (abstained on 26/33) |

V0 is complete. Analysis and recommendations: [../v0-baseline-rca.md](../v0-baseline-rca.md).
Human review (AI first pass, pending confirmation): [v0-answer-review.md](v0-answer-review.md).

## V1 baseline (after the 2026-11-06 fixes)

Fixtures: retrieval 69 cases (`d16e5ece`), generation 35 (`44bdaad6`), e2e 33 (`4c587dd9`).
Corpus: extractor v7 + errata, 785 chunks, re-embedded. Answers: `gpt-4.1-mini`, top-5 context.

| Run | File | Headline |
| --- | --- | --- |
| retrieval · `semantic` (production) | `v1_retrieval_semantic.json` | recall@3 **60/69 (87.0%)**, @5 95.7%, @10 98.6%, MRR 0.78; preferred 30/45 |
| retrieval · `hybrid_rrf` | `v1_retrieval_hybrid_rrf.json` | @3 84.1%, @1 72.5%, @10 100%, MRR 0.81 |
| retrieval · `lexical` | `v1_retrieval_lexical.json` | @3 75.4%, @5 84.1% |
| generation · `openai` | `v1_generation_fixed_context_openai.json` | 25/35: answerable 21/22, **abstentions 4/13**, 8 unsafe |
| e2e · `semantic` · `openai` | `v1_answer_semantic_openai.json` | 25/33: answerable 18/22, abstentions 7/11, 3 unsafe |

Notes:

- The generation and e2e runs were promoted from your run artifacts after the UI crash was fixed
  (2026-11-06). They are labelled `v1` because they belong to the same session as the V1
  retrieval runs; the V0 answer baselines already exist.
- `lexical_authority` was not recorded for V1 (diagnostic only).
- The V0 semantic retrieval file carries the label `v0-retrieval-semantic` inside it, so it does
  not appear under the `v0` label filter in the Run archive.
- Artifacts from V1 onwards record top-10 ranks with scores. Baselines promoted after this date
  keep excerpts only for ranks 1–3, plus a per-source `processing_version`, so that comparisons
  warn when extraction changed but the raw sources did not.

Analysis: [../v1-results-rca.md](../v1-results-rca.md).

## Recording V2

Run the experiment plan in [../v1-results-rca.md](../v1-results-rca.md) §5 (reranked retrieval,
generation with and without the verifier, e2e with both strategies), then promote the chosen
configuration with `--baseline v2`. For example:

```bash
uv run python -m apps.worker run-suite retrieval  --strategy hybrid_rerank --confirm-paid --baseline v2
uv run python -m apps.worker run-suite generation --provider openai --confirm-paid --baseline v2
uv run python -m apps.worker run-suite answer --strategy hybrid_rerank --provider openai --confirm-paid --baseline v2
uv run python -m apps.worker compare-runs v1_retrieval_semantic.json v2_retrieval_hybrid_rerank.json
uv run python -m apps.worker compare-runs v1_generation_fixed_context_openai.json v2_generation_fixed_context_openai.json
uv run python scripts/answer-review-form.py v2_answer_hybrid_rerank_openai.json
```

No re-embedding is needed for V2: the corpus did not change.

### How V0 was recorded (repeat this procedure for later baselines)

```bash
# 1. Put OPENAI_API_KEY in .env, then prepare the corpus including embeddings.
bash scripts/run-workshop.sh --with-embeddings      # leave it running for the UI, or Ctrl+C

# 2. Record the remaining runs (CLI shown; the Workshop UI does the same, see below).
uv run python -m apps.worker run-suite retrieval --strategy semantic   --confirm-paid --baseline v0
uv run python -m apps.worker run-suite retrieval --strategy hybrid_rrf --confirm-paid --baseline v0
uv run python -m apps.worker run-suite answer --strategy semantic --provider openai --confirm-paid --baseline v0

# 3. Commit the baseline files and fixtures together; tag the commit.
git add docs/evals && git commit -m "Eval baseline v0" && git tag eval-baseline-v0
```

In the Workshop UI: **Suites & cases** → choose suite and strategy → tick the cost confirmation →
**Run suite** → **Run archive** → open the run → **Save as baseline** with label `v0`.

### Human review of the answer baseline

The answer suite's automated check is structural only: correct abstain/answer outcome and at least
one acceptable citation. Legal correctness needs a person. For each case in
`v0_answer_semantic_openai.json`, judge the answer against its `human_review_criteria` (all are
visible in the Run archive) and record pass/fail per criterion in `v0-answer-review.md` in this
folder. Score the V0 answer quality as the share of cases whose criteria all pass. Re-review only
the changed cases when comparing later runs.

## Comparing a change against V0

```bash
uv run python -m apps.worker run-suite retrieval --strategy semantic --confirm-paid
uv run python -m apps.worker compare-runs v0_retrieval_semantic.json <new-run-file>.json
```

Or use **Run archive** → open the new run → **Compare with baseline**. The comparison lists
regressed cases first, then improved cases and rank changes. It warns when the fixture, source
versions or models differ between the two runs, because then a score change is not caused by the
code change alone.

Guidelines:

- Compare like with like: same suite, same strategy (unless the change *is* the strategy).
- A change to fixtures, extraction or sources invalidates direct comparison. Record a new baseline
  label after re-labelling, and note why in a spec.
- Read every regressed case before accepting a change, even when the total improves.
- Repository-visible cases are development cases. Release decisions need the user-controlled
  holdout described in `docs/evals/README.md`.
