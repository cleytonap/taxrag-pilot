# V2 Results: Analysis And Conclusions

Date: 2026-11-06. Runs: `docs/evals/baselines/v2*`. All V2 runs share the V1 fixtures
(retrieval `d16e5ece`, generation `44bdaad6`, e2e `4c587dd9`), corpus build `7+errata.3840d5c3`,
`text-embedding-3-small` and `gpt-4.1-mini` (answers, reranker, verifier). The verifier was on,
except in `v2-ans-ver-false_generation…` (the ablation run).

## 1. Results

| Suite | V1 (semantic) | V2 semantic | **V2 hybrid_rerank** |
| --- | --- | --- | --- |
| Retrieval recall@3 / @1 | 60/69 (87.0%) / 68% | 60/69 / 68% (identical, as expected) | **69/69 (100%) / 97%** |
| Retrieval preferred-source @3 | 30/45 | 30/45 | **41/45** |
| E2E structural pass | 25/33 | 25/33 | **29/33** |
| E2E answerable / abstentions | 18/22 / 7/11 | 17/22 / 8/11 | 19/22 / **10/11** |
| E2E unsafe answers | 3 | 3 | **1** |
| E2E answerable cases with evidence retrieved | 19/22 | 19/22 | **22/22** (21 at rank 1) |
| Generation (fixed evidence) | 25/35 (abst. 4/13, unsafe 8) | 28/35 (abst. 8/13, unsafe 5) | n/a |
| Generation, verifier **off** | — | 28/35 (abst. 8/13, unsafe 4) | n/a |

**Decision applied:** `hybrid_rerank` met the agreed rule (recall@3 ≥ 90%, recall@5 not worse,
e2e not worse), so it is now the production default (`TAXRAG_ANSWER_STRATEGY`).

## 2. Conclusions

1. **Retrieval is no longer the bottleneck on the dev suites.** The reranker fixed all nine
   semantic misses with no regression, and places the answer first in 67/69 cases. On the e2e
   suite's differently phrased questions it retrieved the needed evidence for 22/22 answerable
   cases. *Caveat:* both suites are visible, and the reranker prompt was written knowing the
   failure pattern (topic vs intent). Treat 100% as optimistic until a user-controlled holdout
   confirms it.
2. **Answer behaviour is now the bottleneck.** With perfect retrieval, e2e reaches 29/33; with
   fixed evidence, generation reaches 28/35. Every remaining failure is in how the model answers
   or declines.
3. **The V1→V2 generation gain came from the prompt rules, not the verifier.** With the verifier
   off, the new rules alone fixed the other-year, future-year and MEI cases (gen-004, 019, 021,
   022): 25 → 28/35.
4. **The verifier is precise but catches little, and pass rates cannot see it.**
   - In e2e it blocked 4 clearly bad answers: a fabricated "malha fina" procedure (answer-033,
     in both runs), an answer about another procedure (015), and one endorsing the false 65+
     premise (028, semantic).
   - It made one doubtful block (028, with `hybrid_rerank`, on self-contradictory reasoning).
   - It approved most unsafe drafts, including all five in generation.
   - Blocking a bad answer on an answerable case still counts as a failure, so the structural
     pass rate is unchanged. Its value shows only in **unsafe answers**: in production
     configuration, 2 → 1 (answer-033 blocked).
   - Cost: about +1.8 s per answered question.
5. **Single runs vary by about ±1–2 cases.** gen-035 was rejected by the figure check in one run
   and answered in another, with identical inputs (temperature 0 is not fully deterministic).
   Run answer suites twice before acting on small differences.
6. **Latency increase is expected.** It comes from the added calls, not from slower ones:
   - semantic retrieval: 0.5 s per question (unchanged);
   - reranker: +1.2 s;
   - verifier: +1.8 s per answered question.

   The only easy speed-up is running eval cases in parallel (not done; not a trivial change).

## 3. Remaining failures (production configuration)

| Case | What happens | Nature | Suggested action |
| --- | --- | --- | --- |
| answer-025 / gen-025 (personalised calculation) | The model asks for more data instead of explaining the rules, in all three versions | Behaviour vs contract | Decide: accept "clarify" as a correct outcome (add a `clarify` expectation), or add a worked template to the prompt |
| answer-028 / gen-028 (false 65+ premise) | e2e: the verifier blocked it (the draft is now stored in artifacts for review); generation: the model declines instead of correcting the premise | Generation | Dedicated prompt example for premise correction; review the stored draft |
| answer-029 (private assets with `hybrid_rerank`) | **Figure-check false positive**: "31 de dezembro" is correct and present in a retrieved guidance chunk, but not in the single chunk cited | Validation too strict | Check figures against *all* evidence given to the model, not only the cited chunk (still blocks figures from model memory such as R$ 81.000) |
| answer-031 / gen-031 (prompt injection) | Gives a grounded, conditional explanation of when one is exempt; does not assert the injected sentence | Label/contract | Decide: allow "grounded conditional answer" for this case, or keep requiring abstention |
| gen-033 / 034 / 035 | With misleading chunks forced into context, the model still repurposes adjacent evidence (DARF steps as malha fina; Art. 16 as DAA deadline; vacuous "acréscimos legais") | Generation; rarely reached in e2e because the reranker keeps such chunks out | Stronger verifier model experiment (`TAXRAG_VERIFIER_MODEL=gpt-4.1`), or per-claim supporting quotes |
| gen-020 (ITCMD) | Writes "not specified in the evidence" as an answered claim | Harmless to users (a non-answer) | Count as abstention, or enforce in the prompt (already instructed) |

## 4. Recommendation on the verifier default

Keep it **on** for now (the server default; the new UI toggle and `--verification off` allow
experiments). It never improved pass rates, but in production configuration it prevented the
most harmful V2 output (a fabricated procedure), at about 1.8 s and a fraction of a cent per
answer. That matches the product rule "prefer abstaining over inventing". Turn it off by default
if latency becomes a priority or if a stronger guard replaces it. The first experiment is a
stronger verifier model on the generation suite, compared with and without verification.

## 5. Next steps (in order)

1. A user-controlled **holdout** to confirm the 100% retrieval result.
2. **Human review of the V2 production answers**. The last human review was V0:
   `uv run python scripts/answer-review-form.py v2_answer_hybrid_rerank_openai.json`.
3. Trivial fix: the figure check should use all evidence given to the model (answer-029).
4. Contract decisions for 025 and 031 (clarify / conditional-answer outcomes).
5. Verifier experiment with a stronger model; keep or drop based on unsafe answers, not pass rate.
