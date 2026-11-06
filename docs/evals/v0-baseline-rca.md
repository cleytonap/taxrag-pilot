# V0 Baseline: Results And Root-Cause Analysis

Date: 2026-11-06. Inputs: the six `v0_*` runs in `docs/evals/baselines/`. All used the same
fixtures (retrieval `17a66cff…`, answer `49badc93…`) and the same three source versions.
Answer model `gpt-4.1-mini` (temperature 0); embeddings `text-embedding-3-small`; the answer path
retrieves top-3. Human review: `baselines/v0-answer-review.md` (AI first pass, pending human
confirmation).

## 1. Results

| Run | Headline |
| --- | --- |
| retrieval `lexical` | recall@3 **11/70 (16%)**, preferred 3/46 |
| retrieval `lexical_authority` | 10/70 (14%), preferred 3/46 |
| retrieval `semantic` | **58/70 (83%)**, preferred 23/46 (50%); rank-1 hit on 41/70 |
| retrieval `hybrid_rrf` | 48/70 (69%), preferred 18/46 |
| answer `openai` + `semantic` | structural 23/33; **human review 12/33 pass**; 8 answers contain a legal error |
| answer `openai` + `lexical` | structural 12/33: abstained on 26/33, so "10/10 abstentions" is an artifact of junk evidence |

Slices (semantic retrieval):

| Slice | Semantic | Hybrid | Note |
| --- | --- | --- | --- |
| Targets an Art. 2 inciso/§ | **15/21** | 11/21 | weakest slice, and the core of the product |
| Targets a whole IN article (Arts. 1, 3–16) | 16/17 | 15/17 | |
| P&R-only | 23/27 | 18/27 | |
| Edge cases | 7/10 | 4/10 | |
| Preferred = IN article | **14/34** | 9/34 | the controlling norm is usually outranked by guidance/P&R |

Answer suite, with failures split by where they originate:

- Answerable cases whose acceptable evidence reached the top 3: **16/16 passed** structurally.
- Answerable cases whose acceptable evidence did *not* reach the top 3: **0/7 passed**.
- The retrieval hit rate on the answer suite's natural phrasing is 16/23 (70%), against 83% on the
  retrieval suite. The retrieval suite is optimistic.
- Expected abstentions: 7/10. All three failures (004, 019, 033) are generation failures. Two
  contain fabricated content that passed citation validation.

So the performance is poor for two separable reasons:

- **Retrieval misses cap answer quality.** A wrong top 3 means the answer is certainly wrong or
  refused.
- **The answer layer has no check that claims are supported.** When evidence is irrelevant, it
  sometimes invents an answer instead of abstaining.

## 2. Root causes

Each failure is assigned to its most likely cause. "Evidence" gives the cases and the
measurement. Causes marked *(known)* were flagged in the 2026-11-05 audit; the V0 runs now show
their impact.

### RC1 — Lexical ranker dominated by very long chunks *(known; fix now measured)*

`ts_rank_cd` without length normalisation, combined with an OR-joined query, ranks the longest
chunks first. Five long chunks (Q455 at 21.7k characters, Q639, Q140, Q331, Q130) occupy 124 of the 210 lexical top-3 slots.

- **Evidence:** lexical 11/70. Offline experiment on the same corpus: `ts_rank(…, 1)`
  (log-length normalisation) reaches **49/70** with hub slots 124 → 3. `ts_rank_cd(…, 2)` reaches
  22/70, and title weighting does worse.
- **Impact:** the lexical and lexical_authority runs; most hybrid regressions (RC2); the lexical
  answer run.

### RC2 — Unweighted RRF fusion with one noisy arm

RRF rewards agreement between the two arms. If semantic's correct rank-1 chunk is absent from the
broken lexical top-20, it earns a single term (1/61). A mediocre chunk that appears mid-list in both
arms earns two and wins.

- **Evidence:** hybrid breaks 16 cases that semantic gets right: 001, 004, 017, 020, 023, 034, 051,
  053, 064, 066, 067, 070, 073, 076, 079, 081. Six of them had semantic at **rank 1**. In lex-081,
  hybrid promotes the **stale Q088 (R$ 300k) to rank 1**.
- **But the arms are complementary.** The fixed lexical ranker (RC1 + RC3 fixes) rescues 7 of
  semantic's 12 misses (012, 014, 021, 039, 058, 065, 080). The union of the two arms' top-3 holds
  an acceptable chunk for about **65/70** cases. That is the ceiling a good fusion or reranker
  could reach.

### RC3 — Art. 2 incisos are indexed without their legal meaning *(new)*

To stop lexical matching on the repeated article caput, the extractor strips the caput from
`search_text`, and embeddings are computed from that same `search_text`. Inciso V's embedding
therefore reads "relativamente à atividade rural: obteve receita bruta…", with no "está obrigada a
apresentar a Declaração". §1 incisos lose "fica dispensada".

- **Evidence:** Art. 2 targets are the weakest slice (15/21 semantic). IN-preferred recall is
  14/34. Misses on lex-012, 014, 016, 019, 021 and 078 retrieve topical P&R questions about
  *taxation* instead of the *obligation* rule. answer-002 cites the guidance list because Art. 2 III
  was not retrieved.
- **Offline lexical check:** prepending the caput or § lead-in raises preferred-source recall from
  18 to **24/46** and recall from 49 to 51/70. The embedding effect is unmeasured but should be
  larger, because the caput carries the meaning.

### RC4 — Chunk boundary contamination in short P&R chunks *(known; impact now visible)*

Each P&R chunk ends with the next question's section heading. In a 300–450 character chunk, that
heading is a large share of the embedded text. The heading also belongs semantically to the
*following* question, which then lacks it.

- **Evidence:**
  - Q025 ends with "PREENCHIMENTO IRPF 2026 / FORMAS DE PREENCHIMENTO" (lex-039 miss).
  - Q059 ends with "CÓPIA DA DECLARAÇÃO DE AJUSTE ANUAL" (lex-058).
  - Q175 ends with "NÃO RESIDENTE - LUCROS/DIVIDENDOS" (lex-080, answer-030).
  - Q006 ends with "BENS E DIREITOS - AVALIAÇÃO" (lex-082, answer-028).
  - "…QUOTA FIXA (**BETS**)" sits at the end of Q317, so Q317 beats Q318 (lex-065).
- `display_title` keeps only the first line of multi-line question titles, so the strongest
  retrieval key of a P&R chunk is truncated (Q025, Q059, Q175 and Q006 all have two-line titles).

### RC5 — Topic matched instead of intent

The corpus has many specialised P&R questions that share a topic's vocabulary. Embeddings match
the topic ("imóvel residencial 180 dias", "aplicações no exterior", "65 anos", "multa"), not the
question's intent (is this a filing obligation? is there an age rule? when is the deadline?).

- **Evidence:**
  - lex-016 → GC-exemption Q579–581.
  - lex-019 → Q474/476/642.
  - lex-082/answer-028 → 65+ pension exemption chunks.
  - answer-008 ("…sem pagar multa") → penalty chunks and Art. 16 instead of Art. 7.
  - answer-023 → Q729/Q519.
  - lex-003 → guidance intro without the list.
- No cheap ranking tweak fixes these. They need a reranker that reads the question and the
  candidate together, or query rewriting that states the intent.

### RC6 — Vocabulary and language mismatch between queries and sources

- **Evidence:**
  - English questions: lex-078 and answer-032 retrieve unrelated chunks.
  - "cota/corrigidas" vs "quota/juros Selic" in answer-015 → vacuous answer.
  - The edge-case slice scores 7/10.
- The retrieval suite's questions are cleaner than real users' (see §1: 70% vs 83%), so this cause
  is under-measured.

### RC7 — Top-3 context for answers

The answer path passes exactly the top 3 chunks, with no reranking. Every answerable failure (7/7)
had no acceptable chunk in those three. The run artifacts cannot show whether the evidence sat at
rank 4–10, because they store only the top 3 without scores.

### RC8 — No check that claims are supported *(new; most important for safety)*

`validate_answer_draft` only checks that each cited `chunk_id` was retrieved. It never checks that
the chunk supports the claim.

- **Evidence:**
  - answer-019 states the MEI limit "R$ 81.000,00" citing Q184, which does not contain that figure.
  - answer-033 relabels Q067's DARF-payment steps as "how to consult malha fina".
  - answer-008 sources the DAA deadline to Art. 16 (saída definitiva extension) and calls it a
    "prorrogação".
  - answer-023 draws the wrong year conclusion from the guidance list.

  All four passed validation.

### RC9 — No deterministic scope or year gate; abstention is left to the model

Abstention depends entirely on the LLM judging whether retrieved chunks suffice. With loosely
related chunks, it answers out-of-scope questions. With missing evidence, it refuses in-scope ones.

- **Evidence:**
  - Answered when it should abstain: 004 (exercise 2025), 019 (MEI/PJ), 033 (malha fina).
  - Refused when it should answer: 025, 030 and 032 (retrieval misses).
  - answer-028 is a non-answer marked `answered`.

### RC10 — User-visible answer drops the caveats and the answer shape is unconstrained *(new)*

`CitedAnswer.display_text` shows only the claims when claims exist. The model's `limitation` and
`clarification_question` are dropped, in both the UI and the API output.

- **Evidence:** answer-001 shows "você não está obrigado" with no caveat, although the model wrote
  "válida apenas para o critério…". answer-011's clarification question is hidden.
- The prompt says to preserve residency and period conditions, but nothing enforces it: residency
  is omitted in 001 and 002, and the "apenas na hipótese do inciso VI" condition is dropped in 029.
- Six answers are correct but incomplete (002, 006, 011, 012, 013, 024). The prompt's "responda de
  forma concisa… não liste outras hipóteses" pushes against the criteria.

### RC11 — Evaluation gaps that limit this RCA *(new)*

- Artifacts store only the top 3 without scores, so recall@k curves and abstention thresholds
  cannot be computed.
- Structural answer checks cannot detect an unsupported claim in an *answerable* case.
- Some criteria require facts that are not in the corpus (018, 020: "ISS is municipal", "ITCMD is
  state"), which conflicts with the grounding rule. answer-012's second criterion is not asked by
  the question.
- One run per configuration: temperature 0 reduces, but does not remove, run-to-run variance.

## 3. Failure-to-cause map

| Case (run) | Cause(s) |
| --- | --- |
| lex-012, 014, 021 (semantic) | RC3 (rescued by the fixed lexical ranker) |
| lex-016, 019 (all strategies) | RC3 + RC5 |
| lex-039, 058, 080 (semantic) | RC4 (rescued by the fixed lexical ranker) |
| lex-065 (semantic) | RC4 (BETS heading on Q317) |
| lex-078 / answer-032 | RC6 (+RC3) |
| lex-082 / answer-028 | RC5 (+RC4 on Q006); answer-028 also RC9 |
| lex-003 | RC5 (guidance intro split from its list) |
| 16 hybrid-only regressions | RC2 (caused by RC1) |
| answer-008, 015, 023, 025, 030 | RC7 with RC5/RC6 behind the retrieval miss; 008 and 023 also RC8 |
| answer-004, 019, 033 | RC9 + RC8 |
| answer-001, 029 | RC10 (caveat hidden, condition dropped) |
| answer-002, 006, 011, 012, 013, 024 | RC10 (incomplete shape); 012 also RC11 (criterion) |
| answer-018, 020, 027 | RC11 (criteria expect facts outside the corpus or UX wording) |

## 4. Recommendations (new; in addition to the 2026-11-05 flags)

Ordered by safety first, then expected gain per effort. Each item should be one spec, one change,
then a `compare-runs` against V0.

**P0: stop wrong answers from reaching users**

1. **Claim-support verification (RC8).**
   - (a) Deterministic number/date grounding: every amount, percentage and date in a claim must
     appear in its cited chunks. This catches answer-019-type fabrications at no cost.
   - (b) Require a verbatim `support_quote` per citation and check it is a substring of the chunk.
   - (c) Run an entailment check per claim: a small LLM judge at runtime, or at least in evals.
     This catches 033, 023 and 008.

   Reject or abstain on any failure.
2. **Deterministic scope and year gate before generation (RC9).** Parse years and exercise
   references. Anything other than exercise 2026 / calendar year 2025 → abstain with a fixed
   message, or ask to clarify when ambiguous ("IR 2025"). Add a light in-scope classifier (IRPF
   for individuals vs PJ/MEI, other taxes, other countries, off-domain). This fixes 004 and 019 and
   makes abstentions explainable.
3. **Always show caveats, and structure the answer (RC10).**
   - Render `limitation` (and any clarification question) with the claims.
   - Extend the answer schema with required `conditions` (residency, period, exceptions) and
     `scope_note`, rendered as fixed sections.
   - Relax the "be concise / don't list other criteria" instruction to "mention that other
     criteria may apply".

**P1: retrieval quality (expected to move most numbers)**

4. **Fix lexical ranking (RC1):** `ts_rank(vector, query, 1)` instead of
   `ts_rank_cd(vector, query)`. Measured 11 → 49/70 offline. Also store a precomputed `tsvector`
   column (today about 0.34 s per query is spent re-parsing long chunks).
5. **Contextual indexing text (RC3, RC4).** Keep citation text unchanged, but build the
   embedded/indexed text from document hierarchy:
   - IN: norm title → chapter → Art. 2 caput → § lead-in → inciso.
   - P&R: chapter → section heading (moved to the question it describes) → **full** question
     title → answer.
   - Guidance: page title → section.

   Re-embed and compare. This also lets "caput stripping" go, since normalised ranking (item 4)
   no longer needs it.
6. **Candidate union + reranker instead of plain RRF (RC2, RC5).** Take the top 20 from each arm,
   rerank with a cross-encoder or a small LLM reranker, and keep the top 5. Ceiling: ~65/70.
   Cheaper interim option: weighted RRF, chosen on the dev suite and confirmed on the holdout.
7. **Wider answer context (RC7).** Pass the reranked top 5 (with per-chunk length caps) instead of
   the raw top 3.
8. **Query rewriting (RC5, RC6).** One small LLM call turns the user question into 1–3 Portuguese
   retrieval queries in the sources' vocabulary. It translates English, expands
   "cota→quota", "PLR→participação nos lucros" and "informe→comprovante", and states the
   underlying legal question for false premises ("existe dispensa por idade?").
9. **Split oversized chunks.** Q455, Q639, Q331, Q130 and Q140 exceed 10k characters. Split them
   into sub-chunks that each repeat the question title, so no chunk averages many topics or nears
   the 8,192-token embedding limit.

**P2: make the evals more decisive**

10. Store the top 10 with scores in run artifacts. Report recall@1/3/5/10 and MRR. Use score
    distributions on answerable vs out-of-scope questions to test a retrieval-confidence abstention
    threshold.
11. Add automated groundedness scoring to the answer suite (numeric grounding plus an LLM judge on
    the existing criteria) and record criterion-level results, so human review focuses on
    disagreements.
12. Add the answer suite's answerable questions to the retrieval suite: their natural phrasing
    exposes misses the retrieval suite hides (70% vs 83%).
13. Revise criteria that require facts outside the corpus (018, 020) or go beyond the question
    (012). Add a `clarify` expected outcome.
14. For answer runs, repeat 2–3 times when comparing close candidates, and treat single-case flips
    as noise unless they repeat.

**Suggested order of experiments**

| Step | Change | Compare against |
| --- | --- | --- |
| 1 | item 4, no re-embedding needed | V0 lexical and hybrid |
| 2 | item 5, re-embed | V0 semantic |
| 3 | item 6 or weighted RRF, with item 7 | step 2 |
| 4 | items 1–3 | V0 answer, with human review of changed cases |

Re-baseline as `v1` once steps 1–4 land, and run the holdout before release decisions.

## 5. Status (2026-11-06)

Implemented in [the three-layer evals spec](../specs/2026-11-06-three-layer-evals-and-v0-fixes.md).
Semantic/OpenAI effects are pending the `v1` runs.

| Cause | Status |
| --- | --- |
| RC1 lexical length bias | **Fixed**: normalised `ts_rank` over a stored `tsvector`. Lexical recall@3 11/70 → 52/69. |
| RC2 RRF with a noisy arm | Partly addressed: the lexical arm is fixed; fusion and reranker deferred |
| RC3 Art. 2 context | **Fixed** in extractor v7 (caput / § lead-in in the indexed text); needs re-embedding |
| RC4 boundary contamination | **Fixed** in extractor v7 (headings move to their own question, full titles, no nav text) |
| RC5 topic vs intent | Deferred (reranker / query rewriting); guidance sections now indexed under the page title |
| RC6 language | **Scoped out**: Portuguese-only gate; lex-078 retired; answer-032 expects the notice |
| RC7 top-3 context | **Configurable**, default 5 (`TAXRAG_ANSWER_TOP_K`) |
| RC8 claim support | **Partly fixed**: figure grounding (amounts, percentages, dates) in validation; support quotes and LLM judge deferred |
| RC9 scope/year gate | Prompt-level scope list and abstention wording; deterministic year gate deferred (false-refusal risk) |
| RC10 caveats/shape | **Fixed**: caveats always displayed; prompt requires "other criteria may apply" on negative conclusions |
| RC11 eval gaps | **Fixed**: generation suite, top-10 + scores, recall@k/MRR, unsafe/rejection counts, criteria revised, review-form generator |
| Stale official passages (Q088, Q066) | **Excluded** via `data/source-errata.json`; a corpus scan found no others |
