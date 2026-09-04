# IRPF Questions And Answers PDF: Ingestion And Extraction

Date: 2026-09-04
Status: Implemented

## Problem

The official IRPF 2026 questions-and-answers document supplies detailed explanations and user-facing guidance that complement the first guidance webpage. Unlike the existing HTML source, it is a PDF, so the worker must preserve its original bytes and extract page-aware text without losing question numbers or page citations.

## Scope

- admit the official `p-r-irpf-2026-v1-00-2026-04-23.pdf` URL in the executable source registry
- let ingestion preserve an approved PDF, validate `application/pdf`, and use an `.pdf` storage key
- extract PDF text page by page with page-number metadata
- create one anchor and chunk per numbered question in the initial filing-obligation section
- retain a `Question 001`-style citation anchor and its PDF page number
- add fixture tests and process the official PDF locally

## Out Of Scope

- OCR for image-only PDFs, tables requiring visual reconstruction, and all 600+ questions
- production reprocessing queues, embeddings, answer generation, and PDF rendering in the UI
- direct normative-IN ingestion; its current official interface needs a separate access adapter

## Options Considered

| Option | Strength | Tradeoff | Decision |
| --- | --- | --- | --- |
| PyMuPDF | Page-aware text extraction and block metadata in one Python package | We must define question boundaries ourselves | Chosen |
| pypdf | Lightweight and straightforward text extraction | Less layout/block control for difficult PDFs | Not chosen |
| Unstructured | Broad multi-format parsing and OCR integrations | More dependencies and hidden behavior for this text-native PDF | Revisit for OCR/layout-heavy sources |

## Design Choice

Treat each PDF page as an inspectable intermediate artifact. The PDF adapter first extracts normalized text by page, then recognizes question headers such as `001 —`. It accumulates text until the next numbered question, creating an anchor key such as `question-001--p23` and a chunk that retains the question, answer, and page number.

The source metadata continues to label this as `official_guidance`; citations must visibly distinguish it from the future `tax_authority_norm` source.

## Risks

- A new PDF edition can change pagination or question numbering.
- Text extraction can change whitespace, hyphenation, or visual order.
- Questions can span pages; a single page number may be insufficient for later citations.
- A broad question-number regex can falsely recognize a number inside body text.

## Test And Eval Plan

- Test MIME validation and the `.pdf` raw-artifact key.
- Fixture-test question-header recognition and page-number preservation.
- Verify Questions 001, 002, and 006 appear with expected anchors after processing the official PDF.
- Add executable retrieval cases only after verifying the generated anchors.

## Definition Of Done

- The official PDF is preserved as an immutable raw artifact with a content hash.
- The initial question-and-answer section produces page-aware chunks with stable question anchors.
- Each chunk has source version, question number, and page provenance.
- Extraction is idempotent for the same source version and covered by tests.

## Implementation Evidence

Validated locally on 2026-09-04:

- The official PDF was stored as an immutable `original.pdf` artifact and recorded with a
  source-version hash.
- Questions 001 through 006 produced six chunks with page-aware anchors. Question 001 spans
  pages 23-24; Questions 002 and 006 are anchored to pages 24 and 25 respectively.
- A second processing run returned `unchanged`; the database contains two extracted documents,
  fourteen anchors, and fourteen chunks across the HTML and PDF sources.
- PyMuPDF emits import-time deprecation warnings from internal SWIG types under Python 3.14;
  the project uses the current `pymupdf` import and does not suppress these warnings.
