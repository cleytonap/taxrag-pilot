# Cross-Topic Evaluation Expansion

Date: 2026-11-04
Status: Implementing

## Problem

The previous evaluation suite was intentionally scoped to the initial vertical slice (filing
obligation / *obrigatoriedade* only). With the extraction now expanded to all articles of
IN RFB 2.312/2026 (Articles 1–17) and 734 detected sections from the Perguntas e Respostas IRPF 2026
manual, the evaluation benchmark must expand to cover all ingested topics. Without an expanded
suite, there is no performance baseline across practical individual tax inquiries such as deadlines,
penalties, simplified deductions, amended returns, payment installments, dependentes, and medical
deductions.

## Scope

- Expand `docs/evals/lexical-retrieval-baseline.jsonl` to cover cross-topic retrieval across the full
  ingested corpus (from 25 to 50 cases).
- Expand `docs/evals/cited-answer-development.jsonl` to cover full cross-topic answer generation and
  evidence grounding (from 5 to 20 cases, including multiple expected abstention cases).
- Topics covered:
  1. Obrigatoriedade (filing obligation thresholds & special situations)
  2. Prazo de entrega (filing window, deadlines)
  3. Multa por atraso (late filing penalty calculation & minimum/maximum limits)
  4. Desconto simplificado (flat 20% deduction rules, cap, and compatibility)
  5. Formas de preenchimento e Meu Imposto de Renda (channels, prohibitions)
  6. Declaração Pré-Preenchida (access requirements, verification responsibility)
  7. Retificação (deadlines, rules for changing taxation regime)
  8. Pagamento do imposto e quotas (installments, Selic interest, payment channels)
  9. Declaração de bens e direitos (thresholds for reporting exemption)
  10. Dependentes e declaração em conjunto (qualification criteria)
  11. Deduções legais (despesas médicas e instrução)
  12. Rendimentos isentos (caderneta de poupança, doença grave)
  13. Out-of-scope & Abstention cases (unsupported tax years, corporate tax, state/municipal taxes)
- Update test assertions in `tests/test_evals.py` to support the expanded suite sizes and validate
  every anchor key against the newly available extraction anchors.

## Assumptions

- The sources in the knowledge base are:
  1. `irpf-2026-quem-deve-declarar` (Receita Federal guidance HTML)
  2. `irpf-2026-in-rfb-2312` (IN RFB nº 2.312/2026 DOU publication, Articles 1–17)
  3. `irpf-2026-perguntas-respostas` (P&R IRPF 2026 PDF, detected sections numbered 001–745;
     the source snapshot yields 734 sections, not 745)
- All anchors declared in `acceptable_anchor_keys` and `preferred_anchor_keys` correspond to exact
  keys produced by the version 5 extractors.

## Design Choice

- Keep the evaluation format strictly compatible with the existing `RetrievalEvalCase` and
  `AnswerEvalCase` contracts.
- In retrieval evals, for questions directly answered by legislation (e.g. IN RFB 2.312), the
  relevant article is preferred, while corresponding P&R answers are acceptable.
- For operational / guidance questions (e.g., medical expenses deductible items, list of dependent
  degrees), the specific P&R question is preferred.
- For out-of-scope questions (e.g., IRPJ rules, ICMS/ISS, or previous tax years without matching
  guidance), `expected_abstain: true` is set with an empty `acceptable_anchor_keys` array,
  exercising the application's abstention guardrails.

## Risks

- Larger test suites run longer in CI/unit tests if run against live embeddings; all test fixtures
  use deterministic unit tests or fake providers unless explicitly triggered in diagnostic runs.
- New anchors must match extraction output character-for-character to avoid false negative eval runs.

## Test And Eval Plan

- Validate that every case in both JSONL files conforms to the required JSON schema and contains
  non-empty fields.
- Validate that all anchor keys in `acceptable_anchor_keys` exist in the extracted section registry
  built from the checked-in official source snapshots.
- Run unit tests to confirm fixture validation passes cleanly.

## Definition Of Done

- `docs/evals/lexical-retrieval-baseline.jsonl` contains 50 validated cases covering the 13 topic areas.
- `docs/evals/cited-answer-development.jsonl` contains 20 validated cases (with at least 4 abstention cases).
- `tests/test_evals.py` validates the expanded suites without errors.
- Unit tests pass.

## Snapshot Coverage Note

> **Update 2026-11-05:** resolved. Extractor v6 yields all 745 questions; the suite was audited and
> revised to 60 cases. See [2026-11-05 retrieval eval audit](2026-11-05-retrieval-eval-coverage-and-label-audit.md).

The Q&A PDF's highest numbered entry is 745, while the current extractor yields 734 sections. The
evaluation anchors are validated against actual extraction output so a reference cannot silently
target a nonexistent chunk. This suite covers the product's selected cross-topic benchmark; it does
not assert that every item in the 745-number sequence has a distinct extractable body section.
