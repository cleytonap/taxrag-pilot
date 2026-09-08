# Authority-Aware Lexical Reranking

Date: 2026-09-08
Status: Implemented

## Problem

The development evaluation retrieves acceptable official support in `8/9` cases but retrieves a
preferred source in only `1/5` cases. A naive global authority multiplier was simulated first and
rejected: inherited `Art. 2` caput text appears in many normative chunks, so a large boost raises
unrelated incisos instead of the direct legal rule.

## Scope

- retain complete user-visible citation text for every chunk
- add a derived `search_text` representation for lexical retrieval
- remove repeated inherited legal context from the DOU inciso search representation
- add the document title only to the root anchor's search representation
- apply a bounded authority multiplier after a chunk already passes lexical matching
- compare the resulting development metrics to the pre-change baseline

## Out Of Scope

- embeddings, semantic search, LLM reranking, learned ranking, or answer generation
- automatic determination of directness; the reviewed preferred-anchor labels remain the measure
- production activation gates or holdout-set evaluation

## Options Considered

| Option | Strength | Tradeoff | Decision |
| --- | --- | --- | --- |
| Global authority boost on current chunk text | Very small code change | Simulation promoted irrelevant repeated legal context | Rejected |
| Source-level deduplication plus authority boost | Limits duplicate results | Can hide useful separate rules from one source | Not chosen now |
| Separate retrieval text and bounded authority reranking | Keeps citation context while ranking distinctive evidence | Adds one derived database field and reprocessing step | Chosen |

## Ranking Rules

1. Apply existing hard filters: active source version and lexical match in Portuguese.
2. Rank using `search_text`, not the full citation excerpt. A DOU inciso's `search_text` contains
   its title, operative text, and alíneas, but not the inherited caput or paragraph lead-in.
3. Add a document title only to the first/root anchor. This supports source-identification queries
   without repeating the title in every chunk from that source.
4. Multiply the lexical score of already-matching candidates by a bounded authority value:
   `primary_legislation=1.35`, `regulation=1.25`, `tax_authority_norm=1.20`, and
   `official_guidance=1.00`.
5. Break equal adjusted scores by lexical score, then source order. The response still receives the
   complete `chunk.text` for user-visible citations.

Authority is a preference, not a substitute for relevance. A document with no lexical match is
never introduced by the multiplier. The values are an initial, inspectable hypothesis and must be
kept only if the development evaluation improves preferred-source recall without reducing
acceptable-support recall.

## Risks

- Lexical matching still misses paraphrases and number-format variants.
- A fixed authority order cannot model every question; guidance can be more direct than a norm for
  procedural questions.
- Reprocessing is required after a retrieval-representation change.

## Test And Eval Plan

- fixture-test that DOU citation text retains context while its search text omits duplicated caput
- test every authority multiplier and its neutral fallback
- migrate and reprocess all active sources
- compare both acceptable-support and preferred-source recall@3 before accepting the change

## Definition Of Done

- Retrieval and citation text are visibly separate in the data model and documented.
- The GIN index matches the search expression used by the retriever.
- CLI output exposes both lexical and adjusted scores with the authority label.
- Evaluation results are recorded and the rule is retained only if it passes the stated gate.

## Implementation Evidence

Validated locally on 2026-09-08:

- Migration `20260908_01` added `chunks.search_text`, backfilled it from existing citation text,
  and rebuilt `ix_chunks_portuguese_search` over the exact Portuguese search expression now used
  by retrieval.
- Reprocessing rebuilt all active source versions: eight HTML-guidance chunks, six PDF chunks, and
  eighteen DOU legal chunks. User-visible `chunks.text` remains the full citation excerpt.
- The development evaluation retained acceptable-support recall@3 at `8/9` (89%) and improved
  preferred-source recall@3 from `1/5` (20%) to `2/5` (40%). It therefore meets the stated
  retention gate.
- The threshold and instruction-identification queries still rank the detailed Q&A source above
  the normative anchor. This is expected from the bounded rule: a 20% authority adjustment must
  not override a much stronger lexical score. Increasing the multiplier without a new evaluation
  design would repeat the rejected global-boost failure mode.
