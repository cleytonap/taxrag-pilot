# Semantic Retrieval Baseline

Date: 2026-09-08
Status: Foundation Implemented; Evaluation Blocked on API Key

## Problem

Lexical retrieval depends on shared words and Portuguese stemming. It cannot reliably retrieve a
passage when the user paraphrases a rule, uses a different term, or expresses a numeric threshold
in a different form. Before combining retrieval methods, TaxRAG needs an independently measurable
semantic baseline.

## Scope

- make `lexical`, `lexical_authority`, and `semantic` explicit retrieval strategies
- preserve the original lexical-only behavior as a reproducible baseline
- store chunk embeddings separately from chunks, with embedding model and dimensions recorded
- generate embeddings through a small provider interface and an OpenAI implementation
- retrieve semantic candidates with pgvector cosine distance
- add worker commands to embed sources and evaluate a selected strategy
- compare semantic-only results against lexical-only using the same development fixture

## Out Of Scope

- hybrid fusion, reranking, LLM answer generation, or a frozen holdout set
- hiding provider calls behind a framework such as LangChain or LlamaIndex
- API-key provisioning; the adapter must fail clearly until `OPENAI_API_KEY` is configured

## Options Considered

| Option | Strength | Tradeoff | Decision |
| --- | --- | --- | --- |
| OpenAI `text-embedding-3-small` | Managed API, low operational burden, inexpensive baseline | Official source text is sent to an external provider | Chosen first baseline |
| OpenAI `text-embedding-3-large` | More capable option for non-English retrieval | Higher cost; no evidence yet that this small corpus needs it | Revisit after evaluation |
| Local multilingual model such as BGE-M3 | No external text transfer and provider independence | Model download, CPU/memory, and serving complexity | Revisit as a privacy/offline comparison |

## Design Choice

Use `text-embedding-3-small` with its native 1536 dimensions through an explicit
`EmbeddingProvider` interface. The official OpenAI embeddings endpoint represents text as vectors
for relatedness and search, and the `text-embedding-3` models support a dimensions parameter.
The chosen model is the low-cost first comparator, not a permanent provider commitment.

Create one `chunk_embeddings` row per chunk, embedding model, and dimension count. Store the vector,
model name, dimensions, and generation timestamp. This first migration deliberately fixes the database
vector column at the selected model's native 1536 dimensions. Changing dimensions is a future explicit
schema migration, never an environment-only change. Embed the derived `search_text`, not the full citation text:
the semantic and lexical strategies must compare the same retrieval representation, while full
chunk text remains available for citations.

`lexical` uses Portuguese full-text rank without authority adjustment. `lexical_authority` retains
the existing documented experiment. `semantic` orders only by cosine distance. Every evaluation
run selects one strategy explicitly; this prevents an authority experiment from being misreported
as the original lexical baseline.

## Risks

- A tiny development set cannot establish semantic quality or choose a permanent model.
- Embedding a document creates a derived representation that must be regenerated for a model or
  text change.
- Semantic retrieval can return conceptually related but legally inapplicable passages.
- The initial provider requires an API key and sends approved public-source text externally.

## Test And Eval Plan

- unit-test provider response validation with a fake client
- unit-test strategy parsing and ensure unknown strategies fail clearly
- migration-test the database schema through local upgrade and inspect model/dimension metadata
- embed the three active sources after a key is configured
- record lexical-only, lexical-authority, and semantic-only acceptable/preferred recall@3

## Definition Of Done

- All three retrieval strategies are independently selectable and observable.
- Embeddings have model- and source-version provenance and can be regenerated.
- Semantic search uses pgvector cosine distance and returns normal citation provenance.
- A same-fixture comparison records semantic-only results without adding hybrid fusion.

## Implementation Evidence

Validated locally on 2026-09-08:

- Migration `20260908_02` created the empty, additive `chunk_embeddings` table with a 1536-
  dimension pgvector column and model/dimension provenance. No existing source, anchor, or chunk
  data was changed.
- The offline suite has 21 passing tests. It covers provider ordering and malformed-response
  rejection, missing-key failure, explicit retrieval strategies, and strategy forwarding from the
  evaluation runner.
- The same nine-case development fixture was run before semantic embedding generation:

| Strategy | Required acceptable recall@3 | Preferred-source recall@3 |
| --- | --- | --- |
| `lexical` | 8/9 (89%) | 2/5 (40%) |
| `lexical_authority` | 8/9 (89%) | 2/5 (40%) |

The authority experiment has no measured advantage on this fixture, so it remains separately
named and is not substituted for the lexical reference score.

Semantic results are correctly not recorded yet: `OPENAI_API_KEY` is not configured in this local
environment. Once configured, embed each active source with `embed-source`, then run
`eval-retrieval --strategy semantic` against this exact fixture. Only after reviewing that
semantic-only comparison should we implement and compare a named hybrid approach.
