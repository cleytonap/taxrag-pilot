# Full Source Extraction — IN RFB 2.312 and P&R 2026

> **Update 2026-11-05:** the 734-section count was an extraction bug: 11 question headers use a
> hyphen or en dash, or omit a space. Extractor v6 yields all 745 questions in sequence. See
> [2026-11-05 retrieval eval audit](2026-11-05-retrieval-eval-coverage-and-label-audit.md).

Date: 2026-11-04
Status: Implementing

## Problem

Both extractors were scope-limited to the first vertical slice (obrigatoriedade only):

- `extract_dou_in_rfb_2312_html` starts at Art. 2 and exits on the next article match. Art. 3
  through Art. 14 (desconto simplificado, forma de elaboração, prazos, retificação, multa, bens e
  direitos, pagamento, autorização de acesso) are not indexed.
- `extract_receita_questions_answers_pdf` has a hard `> 6` cutoff after question 6. The PDF has
  question numbers through 745 across 340 pages; the current extractor detects 734 body sections.

This prevents the retrieval pipeline from finding evidence for most practical IRPF questions and
makes the eval baseline meaningless beyond obrigatoriedade.

## Scope

- Extend `extract_dou_in_rfb_2312_html` to extract all articles (Art. 1–17), including amendments
  to other normatives, preserving the complete official instrument.
- Remove the question-number cutoff from `extract_receita_questions_answers_pdf`. The checked-in
  PDF currently yields 734 detected sections, numbered 001–745 with gaps; do not confuse the
  highest question number with the number of extracted sections.
- Update `EXTRACTOR_VERSION` so re-ingestion is detected automatically.
- Keep all existing anchor key patterns stable for the 24 already-known chunks so eval fixtures
  that reference them remain valid.
- Update the error message in `_pdf_result` to reflect the broader scope.

## IN RFB 2.312 — Article Structure

The normative has 17 articles. Articles 15–17 amend other normatives. They remain indexed because
the knowledge base should preserve the complete official instrument; retrieval evaluation can show
whether these chunks help for supported questions.

Articles 1–17 and their content:

| Article | Chapter | Topic |
|---|---|---|
| Art. 1 | I – Disposições Preliminares | Scope of the normative |
| Art. 2 | II – Obrigatoriedade | Who must file (all incisos and parágrafos) |
| Art. 3 | III – Desconto Simplificado | 20% flat deduction option, R$ 16,754.34 cap |
| Art. 4 | IV – Forma de Elaboração | PGD vs "Meu Imposto de Renda" |
| Art. 5 | V – Vedações ao "Meu IR" | Cases barred from using the app |
| Art. 6 | VI – Declaração Pré-Preenchida | Pre-filled return rules |
| Art. 7 | VII – Prazo e Meios | Filing window (23 Mar – 29 May 2026) |
| Art. 8 | VII | Late filing |
| Art. 9 | VIII – Retificação | Amended return rules |
| Art. 10 | IX – Multa | Late-filing penalty: 1%/month, min R$ 165.74, max 20% |
| Art. 11 | X – Bens e Direitos | What must be declared; thresholds for exemption |
| Art. 12 | XI – Pagamento | Payment in up to 8 installments; Selic correction |
| Art. 13 | XI | Payment for taxpayers abroad |
| Art. 14 | XII – Autorização de Acesso | Third-party access authorization |
| Art. 15 | XIII | Amendment to prior normative instruction |
| Art. 16 | XIII | Amendment to prior normative instruction |
| Art. 17 | XIV | Entry into force |

## Extractor Design — IN RFB 2.312

### Article-level chunking strategy

Each article is one anchor. Within Art. 2 the existing inciso/parágrafo chunking is preserved
because each inciso is a distinct filing-obligation criterion that benefits from individual
retrieval. For other articles the paragraph structure is too procedural to warrant sub-article
splits — the full article text as one chunk is sufficient.

The existing `DOU_ARTICLE_TWO` regex and inciso/parágrafo logic are kept as-is. The outer loop
is extended to continue past Art. 2 instead of stopping.

### New regex

A general article-start pattern already exists (`DOU_ARTICLE`). The extractor will collect text
between consecutive article markers and produce one `ExtractedSection` per article.

### Anchor key pattern for new articles

```
art-{number}-caput      →  for Art. 1, 3, 4, … 14 (the whole article as one chunk)
art-2-caput             →  unchanged (Art. 2 header)
art-2-inciso-{roman}    →  unchanged
art-2-paragrafo-{n}     →  unchanged
art-2-paragrafo-{n}-inciso-{roman}  →  unchanged
```

### Exclusion rule

Continue collecting through the end of the instrument, including amendment and effective-date
articles. This keeps the extracted source complete and avoids a hand-maintained relevance cutoff.

## Extractor Design — P&R 2026

### Remove the cutoff

Delete the `if question_number > 6: return _pdf_result(sections)` guard and the associated
early-return. The loop then extracts all question headers it detects. Some question numbers visible
in the table of contents do not currently produce body sections; the snapshot test tracks the
observed 734 sections and numbering gaps rather than claiming 745 extracted questions.

### Anchor key stability

Questions 1–6 keep their existing keys (`question-001--p23` through `question-006--p25`). All
new questions follow the same pattern: `question-{NNN:03d}--p{page_start}`.

### Error message update

Change the `_pdf_result` error message from "filing-obligation questions" to "IRPF questions"
to reflect the full scope.

### Docstring update

Update `extract_receita_questions_answers_pdf` docstring from "initial IRPF filing-obligation
questions" to "all IRPF questions".

## Risks

- The IN RFB 2.312 DOU HTML uses `dou-paragraph` CSS class. Arts. 3–14 use the same class, so
  the existing paragraph selector continues to work. Verified by inspection of the raw HTML.
- Arts. 15–17 contain `Art. 15`, `Art. 16`, and `Art. 17` markers and are retained as chunks.
- The P&R PDF is 340 pages. The current question-header regex identifies 734 body sections, with
  the last at question 745 on page 339. The numbering gaps are a known limitation that requires
  source-layout investigation; the highest number is not a section count.
- Re-ingestion of both sources is required after this change. The `EXTRACTOR_VERSION` bump will
  cause the ingestion pipeline to detect a version mismatch and re-process.
- Reprocessing must delete embeddings that reference stale chunks before deleting those chunks;
  on any failed transaction, roll back before persisting the source's failed status.

## Test and Eval Plan

- Existing tests for `extract_dou_in_rfb_2312_html` must still pass (Art. 2 structure unchanged).
- New test: extracted sections include `art-3-caput` through `art-14-caput`.
- New test: extracted sections include `art-1-caput` through `art-17-caput`.
- Existing tests for `extract_receita_questions_answers_pdf` must still pass.
- New test: extraction returns more than 6 sections (at least 100 as a sanity bound).
- New test: the final section is `question-745--p339` and the source yields 734 detected sections.
- After re-ingestion: retrieval eval run shows improved coverage on non-obrigatoriedade cases.

## Definition of Done

- Both extractors produce all 17 DOU articles and all question headers currently
  detected in the source snapshot; the 11 question-number gaps remain documented for follow-up.
- `EXTRACTOR_VERSION` is incremented.
- Existing anchor keys for the 24 currently-known chunks are unchanged.
- Existing tests pass; new tests added for the extended range.
- Re-ingestion produces a database with all 734 detected P&R sections and all IN RFB 2.312
  articles.
