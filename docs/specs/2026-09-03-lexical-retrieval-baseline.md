# Lexical Retrieval Baseline

Date: 2026-09-03
Status: Implemented

## Problem

TaxRAG has source-grounded chunks but cannot yet find a relevant passage for a user question. We need a deterministic, inspectable retrieval baseline and an executable evaluation set before adding embeddings or an LLM.

## Scope

- search active, processed chunks using PostgreSQL full-text search in Portuguese
- rank matches with `ts_rank_cd` and return chunk provenance for each result
- add a GIN functional index over chunk text
- define executable evaluation cases only for the currently ingested Receita guidance page
- provide CLI commands for ad hoc search and retrieval evaluation

## Out Of Scope

- embeddings, pgvector similarity search, reranking, synonym expansion, and typo tolerance
- answer generation, citation validation, API endpoints, and UI integration
- evaluation cases whose expected sources have not been ingested
- persisted evaluation-run history; command output is sufficient for this baseline

## Options Considered

| Option | Strength | Tradeoff | Decision |
| --- | --- | --- | --- |
| PostgreSQL full-text search | Native query parsing, ranking, and metadata filters; no additional service | Literal vocabulary mismatch remains a weakness | Chosen |
| `pg_trgm` | Helps partial matching and typos | Does not provide the term-aware ranking baseline we need | Revisit as a fallback feature |
| Elasticsearch/OpenSearch | Mature search features for a large corpus | Adds an operational service before evaluation proves PostgreSQL is insufficient | Not chosen for V1 |

## Design Choice

Use `websearch_to_tsquery('portuguese', question)` with the question terms joined by `OR`, so an ordinary user question becomes a safe PostgreSQL text-search query without requiring every conversational filler word to occur in the source. Match it against `to_tsvector('portuguese', chunks.text)`, rank with `ts_rank_cd`, and return the chunk, source anchor, source title, canonical URL, and score.

The query hard-filters to active sources and source versions with `processing_status = 'processed'`. A functional GIN index uses the same expression as the query, preventing a mismatch between what is indexed and what is searched.

The initial metric is recall@3: the expected citation anchor must appear in the first three results. The evaluation fixture contains only expected anchors currently present in the database. One deliberately flagged known lexical-gap case uses the synonym `instrução normativa` for a chunk labeled `IN RFB`; it is not counted as a required-pass case and becomes a future semantic-retrieval comparison case. Cases for the normative instruction and PDF remain documented but are not executable until those sources are ingested.

## Risks

- Users may phrase a concept with words absent from the source, producing no result or a low rank.
- Broad `OR` matching favors recall but can return a weakly related chunk when a common term occurs often.
- The eight-chunk corpus is too small to establish production-quality ranking behavior.
- Ranking may overvalue a frequent term rather than a direct rule.
- A GIN index does not solve semantic synonym matching.

## Test And Eval Plan

- Unit test evaluation-fixture loading and required fields.
- Integration-run the retrieval command for every case against the local database.
- Require all required baseline cases to meet recall@3 before recording the baseline.
- Add a deliberate paraphrase failure case before considering embeddings, to demonstrate the lexical limitation.

## Definition Of Done

- A developer can search chunks from a CLI command and inspect citation provenance.
- A GIN index supports the exact full-text expression used by retrieval.
- An executable evaluation command reports per-case rank and aggregate recall@3.
- The resulting score and known lexical limitation are recorded in this spec.

## Implementation Evidence

Validated locally on 2026-09-03 against the eight chunks from the approved Receita guidance page:

- Migration `20260903_01` created `ix_chunks_portuguese_search`, a GIN index over the
  same Portuguese text-vector expression used by retrieval.
- Eight required cases achieved recall@3 of `8/8` (100%).
- One explicit known-gap case did not retrieve the expected `legislacao--04` anchor:
  the user phrase `instrução normativa` has no lexical overlap with the source label
  `IN RFB`. This case is retained for a future semantic/hybrid retrieval comparison.

## Source-Expansion Recheck

After the official questions-and-answers PDF added six chunks on 2026-09-04, the original
exact-anchor development score changed from `8/8` to `6/8` required cases. This is not treated
as a reason to relabel cases until we distinguish two concerns:

- a detailed PDF passage can be an equivalent, acceptable support source for a broad question;
- broad `OR` lexical matching can rank a generic passage above a more direct heading-level chunk.

The next retrieval-quality slice must introduce permitted-support sets in evaluation cases and
compare heading-weighted ranking before this baseline is used as a release gate again.

After the IN RFB 2.312/2026 DOU source added eighteen legal chunks on 2026-09-08, the required
development score remained `6/8` (75%). A threshold query retrieved the primary legal anchor
`art-2-inciso-i`, but only at rank five. This is evidence that the next slice must evaluate both
acceptable support and authority preference; source authority exists in metadata but is not yet a
retrieval-ranking signal.
