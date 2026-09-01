# Source Strategy: Brazilian IRPF V1

Date: 2026-08-31
Status: Draft

## Problem

TaxRAG needs a trustworthy, repeatable source pipeline for Brazilian individual income-tax answers. Downloading a large collection of PDFs without provenance, effective-date metadata, or a refresh process would create an opaque and quickly stale knowledge base.

## Scope

This spec defines the source policy and the data lifecycle for V1. It does not choose the application framework, database, embedding model, or vector store.

## Assumptions

- V1 serves Brazilian Portuguese questions about IRPF.
- Official sources are available online and must remain verifiable by users.
- The first domain will be narrow enough to use a curated inventory.
- V1 is informational and needs clear limitations rather than individualized advice.

## Design Choice

Use a curated, versioned source registry with four authority levels:

1. `primary_legislation`: federal laws published by Planalto.
2. `regulation`: decrees and regulations published by Planalto.
3. `tax_authority_norm`: relevant Receita Federal normative acts and binding interpretations.
4. `official_guidance`: Receita Federal manuals, FAQs, tables, and service pages.

Prefer official HTML for legal sources. Use PDFs only when an official document is natively published as a PDF. Preserve both the raw artifact and extracted text. Chunks and embeddings are generated from extracted text and can be recreated at any time.

## Content Lifecycle

1. Select: admit a source based on the V1 topic, official origin, and authority level.
2. Fetch: download or request the canonical official URL on a scheduled job.
3. Preserve: retain the raw HTML or PDF, final URL, headers when available, and content hash.
4. Extract: convert the artifact into structured text while retaining article, chapter, page, heading, or question identifiers.
5. Normalize: clean only presentation noise; never silently rewrite legal wording.
6. Version: compare hashes and metadata with the prior fetch. Keep the old version when a change is detected.
7. Chunk: create small retrievable passages that do not split an article, table row group, or question-answer pair unnecessarily.
8. Embed and index: create vector representations and searchable indexes from the chunks.
9. Evaluate: run retrieval and citation checks before activating a changed source version.
10. Serve: answer only from active, evaluated source versions, with links and excerpts for verification.

## Why We Do Not Start With "All PDFs"

- Many core legal texts are better available as structured HTML, which supports article-level citations and cleaner extraction.
- PDFs can have layout problems, scanned pages, tables, headers, and page-number ambiguity.
- A document collection alone does not tell us whether a rule is current, applicable to a tax year, or higher authority than another source.
- Embeddings are an index, not knowledge. They must be regenerated when extraction, chunking, metadata, or the model changes.

## Initial Source Families

- Planalto consolidated legislation relevant to the chosen IRPF topic.
- Relevant IRPF regulation from Planalto.
- Receita Federal annual filing rules, tables, and pages for the applicable year.
- Receita Federal `Perguntas e Respostas IRPF` for the relevant exercise.
- Relevant Receita Federal normative acts found through the Normas system.

## Risks

- Consolidated legal text may change without an easy machine-readable version history.
- Annual guidance can apply only to one declaration exercise or calendar year.
- Some pages may be rendered or linked in ways that make automated extraction brittle.
- Conflicts can arise between a broad guidance document and a specific later norm.
- A source can be official but still be outside the question's effective period.

## Test And Eval Plan

- Fetch a small, hand-reviewed set of one HTML law, one Receita HTML page, and one Receita PDF.
- Verify the stored text against the source visually, including headings, articles, tables, and PDF page numbers.
- Create at least ten questions whose expected source family and tax year are known.
- Fail the ingestion run if the raw artifact, extracted text, required metadata, or citation anchor is missing.
- Run retrieval evaluation after any source content change before activation.

## Definition Of Done

- A topic-specific source inventory lists the first approved documents and their authority labels.
- The ingestion prototype can fetch, hash, preserve, and extract each approved format.
- Each resulting chunk retains a user-visible citation anchor.
- The first retrieval evaluation can demonstrate whether the correct source passage is returned.
