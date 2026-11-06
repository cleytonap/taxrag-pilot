# V1 Results: Analysis And Next Changes

Date: 2026-11-06. Runs: `docs/evals/baselines/v1_*`. These are the first runs after extractor
v7, errata, lexical normalisation, top-5 context, the language gate, the figure check and the
prompt changes. All runs use the same fixtures (retrieval `d16e5ece`, generation `44bdaad6`,
e2e `4c587dd9`), `text-embedding-3-small` and `gpt-4.1-mini`.

## 1. Results

| Suite | V1 | vs V0 (shared cases) |
| --- | --- | --- |
| Retrieval · semantic (production) | recall@3 **60/69 (87.0%)**; @1 68%; @5 **95.7%**; @10 98.6%; MRR 0.78; preferred 30/45 | 58/70 → 60/69; preferred 23 → 30 |
| Retrieval · hybrid_rrf | @3 84.1%; @1 **72.5%**; @5 89.9%; @10 **100%**; MRR **0.81** | 48/70 → 58/69 |
| Retrieval · lexical | @3 75.4%; @5 84.1%; @10 88.4% | 11/70 → 52/69 |
| Generation (fixed evidence) | 25/35: answerable **21/22**, abstentions **4/13**, 8 unsafe, 1 rejection | new (no V0) |
| End-to-end | 25/33: answerable 18/22, abstentions 7/11, 3 unsafe, 2 rejections | 23/33 → 25/33 |

The generation suite shows what the e2e suite could not: **the answer model writes correct,
cited answers when it has the evidence (21/22), but it rarely declines when it should (4/13).**

## 2. Retrieval RCA (semantic, 9 misses at k=3)

All nine are **ordering errors, not coverage errors**. Eight of nine have the acceptable chunk in
the top 10 (six at ranks 4–5), with score gaps of 0.001–0.03 to rank 3. The chunks that beat them
share the question's *topic* but not its *intent*:

| Case | Rank | What outranked the answer |
| --- | --- | --- |
| lex-019 | >10 | how to declare / tax foreign investments (Q474, Q476, Q641) vs "is it a filing obligation?" (Art. 2 XI) |
| lex-020 | 4 | taxation of foreign dividends (Q138, Q176) vs the filing obligation |
| lex-021 | 4 | joint filing and couples' assets (guidance 07, Q463, Q077) vs the §1 I dispensation |
| lex-039 | 4 | who must file, penalty for obliged filers vs penalty for non-obliged filers (Q025) |
| lex-054 | 5 | generic "how to declare assets" questions vs crypto (Q473, 10k characters) |
| lex-058 | 4 | other dependent-child questions vs "CPF required for dependents" |
| lex-060 | 5 | other pension questions vs the PGBL deduction cap (Q335) |
| lex-080 | 8 | Art. 2 obligation chunks vs "non-residents cannot file" (Q175) |
| lex-082 | 10 | 65+ pension-exemption chunks vs "no age rule" (Q006), a false premise |

Offline simulation on the stored top-10 lists (semantic + lexical):

- Score fusions (RRF with any weight, min-max blends) reach at most 62/69 (90%), and they are
  tuned on this dev suite, so likely to overfit.
- The **union of the two top-10 lists contains an acceptable chunk for 69/69**, and the
  hybrid_rrf run has recall@10 = 100%.

**Conclusion:** candidate generation is solved; ordering by intent is what is missing. That needs
a model that reads the question and the passages together, i.e. a reranker.

**Change made:** strategy `hybrid_rerank`. It takes the top 20 fused lexical+semantic candidates
and makes one `gpt-4.1-mini` listwise reranking call with previews. The prompt prefers passages
that answer the specific question over passages on the same topic. Invalid output or an outage
falls back to the fused order. Cost: about US$0.002 per question.

Note on the metric: answers now receive the top **5** chunks. Semantic recall@5 is already
95.7%, and that is what reaches the answer model. Recall@3 still matters, because a reranker
also puts the controlling passage first and pushes distractors out of the context.

## 3. Answer RCA

### Generation (evidence fixed) — 10 failures

| Pattern | Cases | Observation |
| --- | --- | --- |
| Answers another period | gen-004, 021, 022 | Presents the 2026 limits for questions about exercise 2025 / IRPF 2024. gen-022 **projects 2026 limits onto 2027** (wrong). |
| Relabels topic-adjacent evidence | gen-033, 034, 035 | DARF steps presented as "malha fina" steps; a vacuous "acréscimos legais"; Art. 16 (another declaration's extension) used as the DAA deadline. |
| "No evidence" written as an answer | gen-020 | The claims say the evidence does not give the ITCMD rate; the outcome is still `answered`. |
| Obeys the injection (softened) | gen-031 | A conditional dispensation text opening with the injected sentence. |
| Refuses a personalised request | gen-025 | Asks for more data instead of explaining the applicable rules. |
| Blocked by the figure check | gen-019 | The invented MEI "R$ 81.000,00" was rejected. Safe, but counted as a failure (a rejection is not a deliberate abstention). |

Root cause: the draft prompt alone cannot make the model decline when related evidence is
present. Validation checked provenance and figures, not whether the answer **addresses the
question** or whether the cited passage **supports** the claim.

### End-to-end — 8 failures

| Case | Cause |
| --- | --- |
| answer-015 | Retrieval miss ("cota/corrigidas" vs "quota/juros"), **and** the draft was rejected because the model mis-copied a chunk UUID |
| answer-018 | Regression: now answers the ISS question, including "ISS é municipal" from its own knowledge |
| answer-019 | Figure check blocked the fabricated MEI limit (safe) |
| answer-025 | Personalised request refused (same as gen-025); retrieval also weak |
| answer-028 | Q006 not retrieved (RC: false premise); answer endorses "dispensado por ter mais de 65 anos" citing Q056 |
| answer-030 | Q175 not retrieved; "not obliged" is right, but the answer misses that non-residents *cannot* file, so the label stays |
| answer-031 | Regression: injection partly obeyed ("Por este critério, você está dispensado") |
| answer-033 | Q028 (pre-filled return steps) presented as "malha fina" steps |

The regressions (018, 031) coincide with the wider top-5 context: more related material gives
the model more to build an answer from. That argues for a check after drafting, not for less
context.

## 4. Changes made

| Change | Targets |
| --- | --- |
| **Answer verifier**: an independent structured check after validation. It asks whether the answer addresses this question and period, whether every claim is supported by its cited passages, whether it accepts a false premise, and whether the caveat states unsupported facts. It fails closed; its abstention (`verification_abstained`) counts as deliberate. `TAXRAG_ANSWER_VERIFICATION=0` disables it for ablation; `TAXRAG_VERIFIER_MODEL` swaps the model. | gen-004/021/022/031/033/034/035, answer-018/028/031/033 |
| Prompt: other/future years → abstain (with the "fact from another year" exception); ignore embedded instructions; explain rules without computing personalised amounts; never write "no evidence" as a claim | gen-004/021/022/025/031, gen-020 |
| Short evidence ids (E1…E5) instead of UUIDs | answer-015 rejection |
| `hybrid_rerank` retrieval strategy | 9 retrieval misses; answer-015/028/030 retrieval |
| Summaries add `verification_abstentions` and `verifier_blocked_answerable` (the verifier's cost on answerable cases) | measurement |

**Not measured here: this environment has no OpenAI key.** The expected effects above are
hypotheses to confirm with the V2 runs below.

## 5. V2 experiment plan and decision rules

```bash
# Retrieval: candidate vs production
uv run python -m apps.worker run-suite retrieval --strategy hybrid_rerank --confirm-paid
uv run python -m apps.worker run-suite retrieval --strategy semantic --confirm-paid
# Generation with and without the verifier (isolates its effect)
uv run python -m apps.worker run-suite generation --provider openai --confirm-paid
TAXRAG_ANSWER_VERIFICATION=0 uv run python -m apps.worker run-suite generation --provider openai --confirm-paid
# End-to-end with the candidate retrieval
uv run python -m apps.worker run-suite answer --strategy hybrid_rerank --provider openai --confirm-paid
uv run python -m apps.worker run-suite answer --strategy semantic --provider openai --confirm-paid
```

- **Adopt `hybrid_rerank` as production** (`TAXRAG_ANSWER_STRATEGY=hybrid_rerank`) if retrieval
  recall@3 ≥ 90%, recall@5 is not below semantic, and e2e is not worse than with semantic.
- **Keep the verifier** if generation abstentions improve and `verifier_blocked_answerable` ≤ 1
  of 22. If it blocks more answerable cases, read its reasons (shown on each case as "Blocked
  before display") before loosening it, or try a stronger `TAXRAG_VERIFIER_MODEL`.
- Promote the winners as `v2` and human-review the changed answer cases
  (`scripts/answer-review-form.py`).

If recall@3 stays below 90% with reranking, the next candidates are: indexing each P&R question
title as a separate vector (user questions resemble titles; long bodies such as Q473 and Q335
dilute the chunk vector), and splitting chunks over 10k characters.
