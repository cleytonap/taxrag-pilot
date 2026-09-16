# Application-Controlled Citations

Date: 2026-09-16

Status: Implemented

## Problem

The first cited-answer contract required the model to return both a retrieved `chunk_id` and a
literal quote. A live answer about monthly income selected correct chunks but inserted `...` into a
long quote, causing safe rejection of the entire answer. Generic sentence splitting to create more
granular identifiers would be fragile for legal numbering, lists, abbreviations, and PDF text.

## Scope

- keep the current ingestion, anchors, chunks, and embeddings unchanged
- require the model to select only `chunk_id` values from the retrieved evidence
- attach the displayed excerpt from the selected chunk in application code
- preserve validation that a selected chunk belongs to the current retrieval result

## Assumptions

- the current chunks are bounded, provenance-rich evidence units suitable for the first answer
  slice
- selecting a retrieved chunk proves citation identity, not that the generated claim is semantically
  entailed by every part of that chunk
- claim correctness, scope, clarity, and repetition remain human-reviewed evaluation concerns

## Design Choice

The model returns a claim and one or more `chunk_id` values. The application looks each ID up in
the retrieved result and creates a `Citation` with immutable provenance plus `excerpt=chunk_text`.
The UI can initially display the anchor title and an expandable full chunk. This avoids model
transcription errors without inventing sentence-level evidence IDs.

The existing UUID `chunk_id` is the initial evidence identity. It is already tied to the stored
source version; no database migration or source re-ingestion is needed. If product needs later
require shorter citations, add editorially structured evidence units based on articles, incisos,
questions, and sections, not generic punctuation splitting.

## Risks

- a full chunk can be longer than an ideal user-facing excerpt
- chunk selection alone does not prove that a claim is fully supported; it must not be confused
  with a legal-correctness guardrail
- changing the JSON output key from `quote` to `excerpt` is a deliberate contract change before a
  public API exists

## Test And Eval Plan

- unit-test that an accepted citation receives exactly the selected retrieved chunk text
- unit-test rejection of a chunk ID outside the retrieved result
- run the answer-development fixture against the real provider and review the human rubric before
  changing answer wording or ranking

## Definition Of Done

- providers no longer generate quote text
- output citations contain application-controlled excerpts and source provenance
- existing ingestion data remains usable without reprocessing
