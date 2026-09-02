# HTML Extraction And Chunking: Receita Guidance

Date: 2026-09-02
Status: Implemented

## Problem

The first preserved source is raw HTML, which is unsuitable for retrieval and does not yet expose a stable, user-verifiable citation location. TaxRAG needs a deterministic transformation from a source version to structured text, anchors, and retrievable chunks without separating legal conditions from their headings or tables from their labels.

## Scope

For the stored `irpf-2026-quem-deve-declarar` HTML version:

- extract only the content under the Receita page's `#content-core` element
- retain the page `h1` and each `h2` section as a citation anchor
- preserve paragraphs, lists, and tables as normalized plain text
- create one chunk per section; retain a table in the chunk introduced by its heading
- persist extraction output, anchors, and chunks in PostgreSQL
- make reprocessing idempotent for an unchanged source version

## Out Of Scope

- PDF extraction, OCR, multi-column layouts, and JavaScript-rendered content
- token-based chunk splitting, embeddings, vector search, or answer generation
- processing every approved source family

## Options Considered

| Option | Strength | Tradeoff | Decision |
| --- | --- | --- | --- |
| Beautiful Soup plus lxml | Explicit CSS selection and DOM traversal; preserves headings, lists, and tables; low abstraction for learning | We own source-family-specific extraction rules | Chosen |
| Trafilatura | Strong generic main-text extraction and metadata recovery | Heuristics can hide the structural anchors and table boundaries needed for legal citations | Not chosen for this source family |
| Unstructured | Broad multi-format partitioning, useful for later PDF/OCR work | More dependencies and configuration than this known HTML page requires | Revisit for PDFs |

## Design Choice

Create a parser adapter for the `receita_guidance_html` family. It traverses direct rich-text tiles below `#content-core`, uses headings as boundaries, and emits normalized text blocks. A heading slug plus ordinal is the stable anchor identifier; its display title is the user-visible heading.

Chunks initially equal sections. This is deliberately conservative: an `h2` describing a rule stays with its list items, explanatory paragraphs, and any following table. If a future section exceeds a measured size threshold, we will split only at paragraph/list boundaries and retain the same anchor.

## Data Model

| Table | Minimum fields |
| --- | --- |
| `extracted_documents` | source version ID, normalized full text, extractor name/version, extracted timestamp |
| `source_anchors` | source version ID, stable anchor key, display title, ordinal, extracted text |
| `chunks` | source version ID, anchor ID, ordinal, text, character count |

## Risks

- Receita may change its HTML classes or hierarchy, producing empty or incomplete extraction.
- Heading text may change, which changes a generated anchor key between source versions.
- Some sections can grow too large for a single retrieval chunk.
- Plain-text table rendering can lose visual layout if headers or cells are malformed.

## Test And Eval Plan

- Fixture test: only content inside `#content-core` is extracted; navigation/footer text is absent.
- Fixture test: required headings and the 2026 threshold table appear in the expected sections.
- Unit test: an unchanged source version creates no duplicate extraction, anchors, or chunks.
- Inspect generated chunks and confirm each has a source version and citation anchor.
- Add retrieval recall evaluation before enabling embeddings.

## Definition Of Done

- The first stored HTML source produces inspectable extracted text, anchors, and chunks.
- The limits table remains with `Limites de valor para o exercício 2026`.
- Each chunk has a stable database relationship to its source version and heading anchor.
- Reprocessing is idempotent and tested.
- Parser-specific assumptions are documented and failures are visible in the ingestion record.

## Implementation Evidence

Validated locally on 2026-09-02 against the stored Receita Federal HTML version:

- The extractor produced one normalized document, eight heading anchors, and eight chunks.
- The `Limites de valor para o exercício 2026` chunk retains its heading, explanatory text,
  table header, all five threshold rows, and footnotes.
- The larger final tile was correctly split into four heading anchors, rather than merging
  `Quem não precisa entregar a declaração?`, dependent, joint-declaration, and residence rules.
- Reprocessing with extractor version `2` returned `unchanged`; no duplicate derived records
  were created.
