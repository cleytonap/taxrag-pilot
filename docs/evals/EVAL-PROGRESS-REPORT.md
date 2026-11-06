# TaxRAG Evaluation Progress Report: V0 → V2

**Audience:** technical leads, PM · **Date:** 2026-11-06 · **Status:** V2 complete ·
**Production pipeline:** `hybrid_rerank` retrieval + `gpt-4.1-mini` answers (top-5 context) +
answer verifier

## Summary

- **Retrieval (production strategy):** Recall@3 went from **82.9% to 100%** and MRR@10 reached
  **0.986**. `hybrid_rerank` (lexical + semantic candidates reordered by an LLM) replaced
  `semantic` in V2. The result is on visible dev suites and is not yet confirmed on a holdout set.
- **Lexical diagnostic:** Recall@3 went from 15.7% to 75.4% after the ranking fix in V1 (length
  normalisation).
- **End-to-end (e2e):** pass rate went from **23/33 to 29/33**, and unsafe answers from 3 to 1.
  With `hybrid_rerank`, every answerable case has its evidence in context (22/22).
- **Answer generation (fixed evidence):** 25/35 → 28/35. Answerable cases are strong (20–21/22);
  **abstention remains the weak point (8/13)**.
- **Bottleneck:** retrieval on the dev suites is no longer limiting; answer behaviour is. The
  last human review was V0 (12/33).

## Version log

| | V0 (2026-11-05) | V1 (2026-11-06) | V2 (2026-11-06) |
| --- | --- | --- | --- |
| Corpus / processing | 787 chunks, extractor v6 | 785 chunks, extractor v7 + errata (2 stale Q&A passages excluded) | same as V1 |
| Fixtures (cases) | retrieval 70 · e2e 33 | retrieval 69 · generation 35 (new) · e2e 33 | same as V1 |
| Production strategy | `semantic`, top-3 context | `semantic`, top-5 context | **`hybrid_rerank`**, top-5 context |
| Main changes | Baseline; no answer validation beyond citation provenance | Contextual indexing (Art. 2 lead-in, Q&A headings, full titles); `ts_rank` length normalisation; Portuguese-only gate; figure-grounding check; caveats displayed; scope prompt rules | LLM reranker; answer verifier; short evidence ids; prompt rules (other/future year, injection, personalised requests) |

## Retrieval suite (pass = acceptable anchor in the top 3)

| Version | Strategy | n | Recall@1 | **Recall@3** | Recall@5 | Recall@10 | MRR@10 | Preferred Recall@3 | s/query |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| V0 | lexical | 70 | 5.7% | 15.7% | n/a | n/a | n/a | 6.5% | 0.53 |
| V0 | lexical_authority | 70 | 5.7% | 14.3% | n/a | n/a | n/a | 6.5% | 0.53 |
| V0 | **semantic** (prod) | 70 | 58.6% | **82.9%** | n/a | n/a | n/a | 50.0% | 0.49 |
| V0 | hybrid_rrf | 70 | 40.0% | 68.6% | n/a | n/a | n/a | 39.1% | 0.74 |
| V1 | lexical | 69 | 50.7% | 75.4% | 84.1% | 88.4% | 0.651 | 53.3% | 0.02 |
| V1 | **semantic** (prod) | 69 | 68.1% | **87.0%** | 95.7% | 98.6% | 0.784 | 66.7% | 0.52 |
| V1 | hybrid_rrf | 69 | 72.5% | 84.1% | 89.9% | 100% | 0.806 | 73.3% | 0.51 |
| V2 | lexical (= V1) | 69 | 50.7% | 75.4% | 84.1% | 88.4% | 0.651 | 53.3% | 0.02 |
| V2 | semantic (= V1) | 69 | 68.1% | 87.0% | 95.7% | 98.6% | 0.784 | 66.7% | 0.52 |
| V2 | **hybrid_rerank** (prod) | 69 | **97.1%** | **100%** | 100% | 100% | **0.986** | **91.1%** | 1.71 |

n/a: V0 artifacts stored only the top 3. V0 → V1 case counts differ (one English case retired),
so compare percentages. `lexical_authority` was not re-run after V0 (diagnostic).

## Answer generation suite (fixed evidence; isolates the answer model from retrieval)

| Version | Config | n | **Pass rate** | Answerable | Abstention | Unsafe | Validation rejections | Verifier blocks | s/case |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| V1 | no verifier | 35 | 71.4% (25) | 21/22 | 4/13 | 8 | 1 | — | 2.69 |
| V2 | verifier **off** | 35 | **80.0% (28)** | 20/22 | 8/13 | **4** | 1 | 0 | 2.74 |
| V2 | verifier on (prod) | 35 | **80.0% (28)** | 20/22 | 8/13 | 5 | 0 | 1 | 4.51 |

The V1 → V2 gain comes from the prompt rules; the verifier has no effect on this suite.

## End-to-end suite (production pipeline; gpt-4.1-mini)

| Version | Strategy | n | **Pass rate** | Answerable | Abstention | Unsafe | Rejections | Verifier blocks | Evidence hit | Top-k | s/case |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| V0 | lexical | 33 | 36.4% (12) | 2/23 | 10/10* | 0* | 1 | — | 2/23 | 3 | 2.39 |
| V0 | **semantic** (prod) | 33 | 69.7% (23) | 16/23 | 7/10 | 3 | 0 | — | 16/23 | 3 | 2.76 |
| V1 | **semantic** (prod) | 33 | 75.8% (25) | 18/22 | 7/11 | 3 | 2 | — | 19/22 | 5 | 3.06 |
| V2 | semantic | 33 | 75.8% (25) | 17/22 | 8/11 | 3 | 0 | 3 | 19/22 | 5 | 4.28 |
| V2 | **hybrid_rerank** (prod) | 33 | **87.9% (29)** | 19/22 | **10/11** | **1** | 1 | 2 | **22/22** | 5 | 5.43 |

\* V0 lexical abstained on 26/33 cases because its evidence was irrelevant; its abstention score
is an artefact, not good behaviour. **Human review** (legal correctness, shown answer incl.
caveats): V0 semantic 12/33 passed with 8 legal errors. Not repeated since.

**Metric definitions** (full glossary: `docs/evals/glossary.md`)

| Metric | Definition |
| --- | --- |
| Recall@k | Share of cases with an acceptable anchor in the top k. @3 is pass/fail; answers receive the top 5. |
| MRR@10 | Mean of 1/rank of the first acceptable anchor (0 if outside the top 10). |
| Preferred Recall@3 | Share of cases where the policy-preferred source (usually the IN article) is in the top 3. |
| Pass rate (structural) | Answerable cases answer and cite an acceptable anchor; abstention cases decline deliberately. Does not judge legal correctness. |
| Unsafe | Answered when abstention was required. |
| Evidence hit | Answerable cases with an acceptable chunk in the answer context. |
| Rejections / Verifier blocks | Drafts blocked by deterministic validation (citation, figures) / by the LLM verifier. |

## Key findings

1. **Reranking fixed every semantic Recall@3 miss** (9/9) without regressions. All misses were
   ordering errors between topic-similar chunks; the lexical ∪ semantic top-10 already contained
   the answer for 69/69.
2. **Answer behaviour is now the limiting factor:** 4 e2e and 7 generation failures remain, all
   in generation or in the contract itself.
    - Personalised-calculation requests get a clarifying question instead of the rules (025).
    - False-premise correction (028).
    - A figure-check false positive (029).
    - Prompt injection answered with a grounded conditional text (031); the label decision is
      pending.
    - Misleading forced evidence is repurposed (gen-033/034/035).
3. **The verifier is precise but has low recall.** In e2e it blocked 4 clearly bad drafts and 1
   doubtful one, and missed most unsafe drafts in generation. Pass rate is unchanged. Unsafe
   answers in production e2e fell 2 → 1. It is kept on (about +1.8 s per answered question) until
   a stronger guard is tested.
4. **Latency:** e2e went from 2.8 s/case (V0) to 5.4 s/case (V2). The increase is entirely the
   added calls: reranker about +1.2 s, verifier about +1.8 s.
5. **Run variance:** about ±1–2 cases between identical answer runs (temperature 0 is not fully
   deterministic).

## Gaps and next steps

| # | Gap / step | Why | Owner | Effort |
| --- | --- | --- | --- | --- |
| 1 | User-controlled **holdout** (40–60 cases) | 100% Recall@3 is on visible dev suites; the reranker prompt was designed after seeing the failures | PM / domain expert | 2–3 d |
| 2 | **Human review of V2** production e2e | The structural pass rate does not measure legal correctness; last review was V0 | Domain expert | ½ d |
| 3 | Figure check against all context chunks, not only cited ones | One false rejection (029) | Eng | < 1 h |
| 4 | Decide the expected outcome for personalised requests and injection (`clarify` / conditional answer) | Binary answer/abstain contract mislabels reasonable behaviour | Tech lead + PM | 1 meeting |
| 5 | Stronger verifier model (`TAXRAG_VERIFIER_MODEL`); keep only if unsafe answers drop | Verifier recall is low | Eng | ½ d |
| 6 | Coverage: 16/49 Q&A chapters untested; 3 sources; 137 cases | Known blind spots | Eng + domain | ongoing |
| 7 | Optional: parallel eval execution | Suite runs take 2–3 min | Eng | ½ d |

*Sources: `docs/evals/baselines/` (all runs) · `v2-results-analysis.md` (case-level analysis)
· `glossary.md` (every field and metric).*
