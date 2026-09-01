# Vertical Slice: IRPF 2026 Filing Obligation

Date: 2026-08-31
Status: Draft

## Problem

People want to understand whether the rules for the 2026 IRPF declaration exercise apply to them. The information is time-sensitive, spread across a normative act and Receita Federal guidance, and has exceptions that make an uncited answer unreliable.

## Scope

V1 explains the filing-obligation rules for the 2026 exercise, covering income received in calendar year 2025, for individuals resident in Brazil.

The system must answer general questions about criteria, thresholds, exceptions, and voluntary filing. Each answer must show its source, source type, and applicable exercise/year.

## Out Of Scope

- collecting a complete taxpayer profile or issuing a personalized "you must file" decision
- calculating tax due, refunds, or penalties
- preparing or submitting a declaration
- other exercises or calendar years
- interpreting facts that need professional tax or legal advice

## Assumptions

- The authoritative annual filing rule is `IN RFB no 2.312/2026`.
- Receita Federal's public "Quem deve declarar" page and `Perguntas e Respostas IRPF 2026` accurately explain and link to that rule.
- The source inventory is intentionally limited to this topic and exercise.

## Design Choice

Use a source hierarchy in answers:

1. Cite `IN RFB no 2.312/2026`, art. 2, for the legal filing-obligation criteria and dispensations.
2. Cite Receita Federal's public guidance for a plain-language explanation and table of thresholds.
3. Cite the annual `Perguntas e Respostas IRPF 2026` for question-specific examples and context, preserving its question number and PDF page.

An answer may explain a condition only when the retrieved source passage supports it. If the question needs facts outside the scope, the assistant must explain the relevant published criteria and say that it cannot make an individualized determination.

## Risks

- Users may interpret a general explanation as personal tax advice.
- Thresholds and obligations are exercise-specific and may be applied to the wrong year.
- A guidance page can be easier to retrieve than the normative act, causing weaker legal citations.
- The annual PDF has a large amount of unrelated content, increasing retrieval noise.

## Test And Eval Plan

- Maintain the initial hand-authored evaluation cases in `docs/evals/irpf-2026-obrigatoriedade.md`.
- Measure whether retrieval returns the expected authority level and citation anchor, not only whether the prose sounds plausible.
- Require the answer to include `exercise 2026` and `calendar year 2025` when it states a threshold.
- Add adversarial cases that mention another exercise or ask for a personalized decision; they must be handled with a clarification or limitation.

## Definition Of Done

- The source inventory has the approved primary and supporting sources.
- Ingestion preserves the original artifact, extraction output, content hash, and required metadata for every source.
- At least ten evaluation cases are executable against retrieval.
- All user-facing answers show a working source link and a citation anchor.
- The assistant does not make an unsupported personalized filing determination.
