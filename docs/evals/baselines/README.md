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

| Run | Status | Headline |
| --- | --- | --- |
| retrieval · `lexical` | recorded `v0_retrieval_lexical.json` | recall@3 11/70 (15.7%); preferred 3/46 |
| retrieval · `lexical_authority` | recorded `v0_retrieval_lexical_authority.json` | recall@3 10/70 (14.3%); preferred 3/46 |
| retrieval · `semantic` | **pending**: needs `OPENAI_API_KEY` and embeddings | |
| retrieval · `hybrid_rrf` | **pending**: needs `OPENAI_API_KEY` and embeddings | |
| answer · `openai` · `semantic` | **pending**: needs `OPENAI_API_KEY`, plus human review | |

The lexical numbers are low because a few very long P&R chunks dominate `ts_rank_cd` ranking
(see the 2026-11-05 audit spec). That is exactly the kind of finding a baseline should capture
before any fix.

### Completing V0 (about 10–15 minutes, well under US$1 of OpenAI usage)

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
