# Three-Layer Evals, Production Focus, And V0 Fixes

Date: 2026-11-06
Status: Implemented. Semantic/OpenAI effect to be measured as baseline `v1`.

## Problem

The V0 RCA (`docs/evals/v0-baseline-rca.md`) showed two separable failure sources:

- retrieval misses, which cap answer quality;
- an answer layer that neither verifies claims nor shows its caveats.

The answer suite mixed both, so generation problems could not be studied in isolation. The
review also raised five product decisions: language scope, the visibility of caveats, stale
official excerpts, which strategy to optimise, and which fixes to apply now.

## Decisions

1. **Three eval layers.**
   - Retrieval: chunks only.
   - Generation (`answer-generation.jsonl`, new): answers from **fixed evidence**, no retrieval.
   - End-to-end: the existing answer suite, kept under id `answer` so V0 stays comparable.

   Generation cases are derived from the e2e cases. Their context is the acceptable evidence
   plus the distractors V0 actually retrieved, interleaved. Abstention cases get exactly the
   loosely related chunks that made V0 answer. Two additional cases test faithful abstention
   on insufficient in-scope evidence (gen-034, gen-035).

   *Alternative rejected:* converting the e2e suite in place. End-to-end quality is what users
   experience and must stay measured.
2. **One production pipeline.** `TAXRAG_ANSWER_STRATEGY` (default `semantic`, the V0 winner)
   is what answers users and what optimisation targets. Lexical, lexical+authority and hybrid
   remain diagnostics and are not required to improve. A change is accepted on **e2e plus
   generation** results, with retrieval metrics as the explanation.

   The worry that one chunking helps lexical but hurts semantic is handled structurally.
   Citation text (`chunks.text`) and indexed text (`chunks.search_text`) are already separate,
   and the indexed representation can diverge per retriever later if evidence demands it. The
   v7 contextual indexing helped lexical in measurements and targets a semantic failure mode,
   so no divergence is needed today.

   Hybrid becomes the candidate production pipeline only if it beats semantic on e2e after a
   proper fusion or reranker (RCA recommendation 6).
3. **Portuguese only.** A deterministic gate (`taxrag/language.py`) runs before retrieval. It
   flags a question only when distinctive English or Spanish words clearly dominate, so
   uncertain text is answered normally. Refused questions receive a fixed bilingual notice
   (outcome `unsupported_language`, which counts as a correct abstention).
   - Verified: zero flags on 848 real Portuguese questions (all 745 P&R titles and all fixture
     questions, including accent-free and keyword-only ones).
   - Verified: English and Spanish samples are flagged.
   - *Alternatives rejected:* a language-ID library (adds a model dependency, unreliable on
     short text) and an LLM call (cost, latency, non-determinism).
4. **Caveats are part of the answer.** `display_text` always includes `limitation` and
   `clarification_question`, in the UI, the API and review forms. The prompt now tells the model
   the field is shown and is for essential conditions.
5. **Known-wrong official passages are not indexed.** `data/source-errata.json` lists Q088 (R$
   300.000,00 vs the IN's R$ 800.000,00) and Q066 ("11 e 31 de maio de 2024"), with the
   conflicting and controlling text. A full corpus scan for previous-exercise thresholds and
   stale deadline dates found no others. Processing skips these sections (the extracted document
   keeps them for provenance). The errata hash is part of the processing version, so an edit
   forces reprocessing.
   - Tests verify that each quoted conflicting text exists in its passage, and that no fixture
     uses an excluded anchor.
   - Whole-passage exclusion was chosen over redaction. Redacting would alter an official
     excerpt shown as a verbatim citation, and the correct parts of both passages are covered
     by other chunks (Q087/Q077; Art. 12/Q065).

## Changes (no major refactor)

| Area | Change | RCA |
| --- | --- | --- |
| Lexical | `ts_rank(search_vector, q, 1)` (log-length normalisation) over a stored generated `tsvector` column | RC1 |
| Extraction v7 | P&R section headings move to the question they introduce; full multi-line titles; no nav links or page numbers in text | RC4 |
| Extraction v7 | Art. 2 provisions indexed with the caput / § lead-in; chapter headings index the next article; guidance sections indexed under the page title | RC3, RC5 |
| Answer path | Portuguese-only gate; caveats displayed; figure-grounding validation (amounts, percentages, dates must be in the cited evidence or the question, or be one arithmetic step from them); prompt: out-of-scope list, false premises, no own knowledge, abstention wording | RC8, RC9, RC10 |
| Answer path | `TAXRAG_ANSWER_TOP_K` (default 5; V0 used 3) | RC7 |
| Evals | generation suite and runner (same `answer_from_evidence` code as production); retrieval runs record top 10 with scores, recall@1/3/5/10 and MRR; e2e/generation summaries add `unsafe_answers` and `validation_rejections`; review-form generator from run artifacts | RC11 |
| Fixtures | lex-078 retired (English out of scope); errata anchors removed from lex-006 and lex-055; answer-032 now expects the language notice; criteria of 012/018/020 fixed; Q014 acceptable for answer-006 | |
| Robustness | ingestion restores a missing object-store file when the DB already has the version; anchor titles widened to `text` (longest is 515 characters) | |

Deferred, because each is a larger change that deserves its own measured spec:
- candidate union + reranker;
- LLM query rewriting;
- per-claim support quotes / LLM entailment judge;
- splitting chunks over 10k characters;
- a deterministic year gate. A naive one would refuse legitimate questions such as "how do I
  file my 2024 return late?" (lex-072, Q042).

## Evidence (offline; no OpenAI key in this environment)

| Measure | V0 | Now |
| --- | --- | --- |
| Lexical recall@3 (shared cases) | 11/70 | **52/69** (recall@5 84%, @10 88%) |
| Lexical preferred-source recall@3 | 3/46 | 24/45 |
| Lexical+authority recall@3 | 10/70 | 51/69 (preferred 30/45) |
| Lexical suite runtime | ~40 s | ~4 s |
| Figure check on all 40 V0 OpenAI claims | — | flags only answer-019's invented R$ 81.000,00 |
| Language gate on 848 Portuguese questions | — | 0 false refusals |

The semantic, hybrid and OpenAI-answer effects are **unmeasured** until re-embedding and the
`v1` runs. Several changes land at once. To attribute an effect, use the env knobs
(`TAXRAG_ANSWER_TOP_K=3`) or compare the generation suite, which is independent of retrieval.

## Risks

- **Reprocessing deletes all embeddings.** Semantic and hybrid runs fail fast until
  `bash scripts/run-workshop.sh --with-embeddings` (or `embed-source` per source) completes.
- **Top-5 context is longer.** It may add distractors and cost. Measure it with the knob.
- **The figure check can reject a correct answer** that uses arithmetic beyond one step. The
  rejection is a safe abstention and is counted in `validation_rejections`; review those.
- **The language gate misses some short foreign questions** by design. They get a normal
  answer attempt.

## Test And Eval Plan

Unit tests cover:
- the language gate (both directions and full precision corpus) and the figure check (V0
  fabrication plus derived amounts);
- display text;
- errata integrity and exclusion;
- extraction layout fixes;
- the generation contract and runner;
- recall@k summaries.

Then record `v1` as described in `docs/evals/baselines/README.md`, human-review the generation
and e2e answer runs, and compare against V0.

## Definition Of Done

- All tests, ruff, ESLint and `next build` pass.
- `v1` baselines recorded for retrieval (semantic + diagnostics), generation and e2e, with
  human review.
