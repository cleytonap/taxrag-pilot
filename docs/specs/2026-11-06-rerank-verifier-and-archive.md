# Reranked Retrieval, Answer Verification, And A Usable Run Archive

Date: 2026-11-06
Status: Implemented. Effect to be measured in V2 (see `docs/evals/v1-results-rca.md` §5).

## Problem

From the V1 runs and their review:

1. The UI crashed (`Cannot read properties of null (reading 'toFixed')`) whenever an answer-suite
   run was shown. Evidence in answer suites has no retrieval score (`null`), and the UI only
   guarded against `undefined`. This blocked promoting the generation and e2e runs.
2. The Run archive mixed runs and baselines in an unfiltered tile list, and showed file
   modification times. Those change when files are copied or unzipped, so baselines looked
   mis-dated; file names use UTC while the UI used local time.
3. Semantic recall@3 was 87% (target ≥ 90%, ideally 95%). All misses are ordering errors between
   topic-similar chunks; the union of retrievers' top 10 contains an answer for 69/69 cases.
4. Generation: answerable 21/22 but abstentions 4/13. The model builds answers from
   topic-adjacent evidence (other years, other procedures, other declarations), which
   provenance and figure checks cannot detect.

## Decisions

- **UI:** render scores only when numeric. E2E runs now record retrieval scores too.
- **Archive:** the API returns each artifact's own metadata (suite, strategy, provider,
  `finished_at`, baseline label, headline metric, `fixture_is_current`, `promoted_from`),
  cached by file version. The UI shows a filterable table (kind, suite, strategy, label, current
  fixture only, hide runs already promoted) with time-zone-labelled local times.
- **Retrieval: `hybrid_rerank`.** The top 20 of the existing RRF fusion get one listwise LLM
  reranking call with 900-character previews; invalid output or an outage falls back to fused
  order.
  - *Alternatives:* weighted score fusion (simulated: ≤ 90% and tuned on the dev suite, so
    rejected); a local cross-encoder (adds torch and a model download, heavy for this stack);
    per-title vectors (kept as the next step if needed).
  - *Cost:* about US$0.002 and 1–2 s per question.
  - **Production stays `semantic` until V2 confirms the decision rule** (recall@3 ≥ 90%, @5
    not worse, e2e not worse). Switching is one environment variable.
- **Answers: second-pass verifier.** After deterministic validation, an independent
  structured-output call judges four things: whether the answer addresses the question and
  period, whether each claim is supported by its cited passages, whether it accepts a false
  premise, and whether the caveat is unsupported.
  - It fails closed, and its abstention (`verification_abstained`) is deliberate system
    behaviour in the metrics.
  - `verifier_blocked_answerable` exposes its false positives.
  - *Alternative:* a self-check field in the drafting call. It is cheaper, but V1 shows the same
    model writing "the evidence does not specify" and still answering, so an independent,
    single-purpose pass is preferred.
  - *Cost:* one extra call per *answered* question.
- **Answers: small fixes.**
  - Short evidence ids (E1…) instead of UUIDs: a mis-copied UUID caused a rejection.
  - Prompt rules for other and future years, embedded instructions, personalised calculations,
    and "no evidence" claims.
- **Artifacts:**
  - Per-source `processing_version` (extractor + errata), with a comparison warning when it
    differs.
  - Baselines keep excerpts only for ranks 1–3.
  - `rerank_model`, `answer_verification` and `verifier_model` are recorded and compared.

## Risks

- The verifier can block correct answers. Mitigation: the metric above; reasons shown in the
  UI per case; `TAXRAG_ANSWER_VERIFICATION=0` for ablation.
- The reranker adds latency and a paid call per question. It fails open to fused order.
- **Neither LLM component could be exercised in this environment (no API key).** Behaviour is
  covered by unit tests with fakes. Quality must come from the V2 runs.

## Test And Eval Plan

- Unit tests:
  - reranker output validation, completion and fallback;
  - hybrid reorder;
  - verifier rejection, outage fail-closed and approval;
  - short-id mapping;
  - archive metadata from artifact content, not file times.
- Browser check on the user's V1 artifacts: every archive row opens without page errors;
  filters work.
- V2 runs and decision rules in `docs/evals/v1-results-rca.md` §5.

## Definition Of Done

- All tests, ruff, ESLint and `next build` pass.
- V1 generation/e2e runs promoted; docs updated.
- V2 recorded by the user; production strategy decided by the rule above.
