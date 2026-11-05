# Retrieval Eval Coverage And Label Audit

> **Update 2026-11-05 (later):** 10 retrieval edge cases were added (70 cases total); see
> [workshop/baselines/edge-cases spec](2026-11-05-eval-workshop-baselines-and-edge-cases.md).

Date: 2026-11-05
Status: Implemented (semantic/hybrid re-baseline pending; see Evaluation Evidence)

## Problem

The 50-case retrieval fixture was expanded in one step (2026-11-04) without a source-side audit. A
review of every case against the three extracted sources found four classes of problems:

1. **Coverage gaps.** The suite covered 10 of the 17 IN RFB 2.312/2026 articles. Arts. 1, 8, 13, 14,
   15 and 16 had no case, even though each affects some end users. Its P&R anchors covered 10 of the 49
   chapters of the Perguntas e Respostas manual, and all but three came from questions 001–066. No
   case covered capital gains (122 questions), income from work, rent, deductions other than medical,
   bens e direitos, restitution, carnê-leão or rural activity.
2. **Inaccurate labels.** Every referenced anchor existed, but many acceptable sets were incomplete.
   Other official chunks state the same rule, so a retriever returning them was scored as a failure.
   One question contradicted its own labels (`lex-010` asked about a 2026 sale under rules for
   ano-calendário 2025), and one preferred anchor could not answer its question (`lex-009`).
3. **Redundancy.** Twelve cases duplicated another case's anchors. For example, Art. 12 had 4 of the 50
   cases, and `lex-005`/`lex-048` were the same question.
4. **A citation-integrity defect in extraction.** 11 of the 745 P&R questions were merged into the
   preceding question's chunk and cited under the wrong anchor (details below).

## Scope

- Fix the P&R question-header extraction bug (extractor version 6).
- Correct acceptable and preferred labels on retained cases, using pooled candidate review.
- Retire redundant cases and add cases for uncovered articles and major P&R chapters (60 cases).
- Apply the same anchor corrections to the answer fixture where it shares the defect.
- Add a regression test for IN article coverage and strict P&R question numbering.
- Document labelling rules and a review protocol in `docs/evals/README.md`.

## Out Of Scope

- Retrieval scoring changes. The lexical collapse described below is recorded, not tuned.
- The trailing-heading and chapter-heading leakage in chunk text (see Known Extraction Issues).
  Fixing it changes chunk text for most anchors and should be its own measured change.
- Renaming `art-N-caput` anchors or the `lexical-retrieval-baseline.jsonl` file.
- A blind holdout set. This remains a visible development fixture.

## Design Choices

### Extraction fix

The regex accepted only `NNN — Title` (or a middle dot) with spaces. Eleven headers use a hyphen or
en dash, or omit a space: `035 —Quais`, `107 - Qual`, `341 – Filho`, `528—`, and others. These
questions were concatenated into the previous chunk. For example, the Declaração Final de Espólio
deadline (Q107) was retrievable only as `question-106--p59`, whose title is about something else. The
separator now accepts `— · – -`, with optional spaces or tabs. Spaces are matched with `[ \t]*`
rather than `\s*`, so a page number followed by a bulleted `- 20%` line on the next line is not taken
as a header. Verified: questions 001–745 are now extracted in strict sequence, with no false
positives. All 734 previous anchor keys are unchanged, and the 11 new ones are added. The previous
test asserted the buggy gap set and has been replaced by a strict-sequence assertion.

### Label rules (applied to every case)

- **Acceptable** means a chunk that, read alone, lets a user verify a correct answer to the question
  *as asked*. Chunks that state the rule only for a different context are excluded. Examples: Q172
  repeats deduction limits for income from abroad, and Q117 covers temporary absence, not permanent
  departure. Chunks that state a stale figure for the asked fact are also excluded: Q088 gives
  R$ 300.000,00 for the spouse-assets dispensation, which is now R$ 800.000,00.
- **Pooled review.** For each case, the top 10 of the production lexical retriever and the top 10 of
  an offline length-normalised BM25 with a Portuguese stemmer were pooled, together with a grep for
  the decisive figures. Every pooled chunk outside the acceptable set was read and either added or
  rejected with a reason in `label_notes`. Semantic pooling was not possible in this environment (no
  embedding API or model download); the protocol's first review step covers it.
- **Preferred** anchors are declared only when two or more acceptable anchors compete and the
  2026-09-08 source policy decides between them. Single-anchor cases no longer repeat the anchor as
  "preferred", which inflated the preferred-source metric with trivially identical results.
- **Metadata.** Each case carries `topic`, `covers` (human-readable legal or P&R reference), `style`
  (`source-wording`, `paraphrase` or `scenario`) and `label_notes` (rationale and deliberate
  exclusions). The loader ignores these fields; they exist for review and coverage reporting. The
  Eval Workshop can still append bare cases, but those should gain metadata before merge.
- **IDs.** Retained cases keep their IDs, including those with corrected labels. Retired IDs are never
  reused. New cases are `lex-051`…`lex-073`.

### Size: 60 instead of 50

With 16 user-relevant IN articles (Art. 17, entry into force, is excluded), Art. 2 needs 16 cases to
test each separately chunked inciso and paragraph, plus one general case. That leaves too few
cases for the major P&R topics at 50. Retrieval evals cost almost nothing to run; the real cost is
human review time (about 2–3 minutes per case). Sixty cases give one case per major topic. If the
suite must return to 50, the lowest-value candidates are `lex-017` and `lex-018` (offshore incisos
IX/X), `lex-055` (Art. 13), `lex-024`, `lex-025`, `lex-030`, `lex-039`, `lex-012`, `lex-060` and
`lex-066`. This drops anchor-level coverage of incisos IX and X and of Art. 13.

## Changes To Retained Cases

| Case | Change | Reason |
| --- | --- | --- |
| `lex-009` | acceptable `art-1-caput`, `legislacao--04`; no preferred | `art-2-caput` and Q001 do not identify the norm |
| `lex-010` | question `2026` → `2025` | IN 2.312 governs ano-calendário 2025; aligned with `answer-002` |
| `lex-011`, `lex-012` | + Q001 | Q001 states R$ 40.000,00 and R$ 177.920,00 |
| `lex-014` | + Q001, guidance list | both state the asset criterion |
| `lex-016`–`lex-020` | + Q001, guidance list | same defect the 2026-09-16 RCA fixed only for `lex-010`/`lex-015` |
| `lex-021`, `lex-022` | + Q001 | Q001's "Dispensa" section states both dispensations |
| `lex-024` | + Q004 | same "not by itself" rule for SA shareholders and cooperatives |
| `lex-027` | + Q018 | states the R$ 16.754,34 cap |
| `lex-029` | + Q012, Q014 | "independentemente ... do número de fontes pagadoras"; "qualquer contribuinte" |
| `lex-031` | + Q037, Q035 | Q037: transmission until 23h59min59s on 29/05/2026; Q035 (new in v6): the full filing period |
| `lex-035` | + Q030 | gov.br Ouro/Prata for the pre-filled return |
| `lex-041` | + Q043, Q014 | both state that the option cannot change after the deadline |
| `lex-042` | + Q064, Q051 | 8-quota table; "até o limite de oito quotas" |
| `lex-046` | + Q007 | Q007's "Atenção" reproduces Art. 11 §3 (R$ 140,00 etc.) |
| `lex-006` | + Q077, Q079, Q087, Q088 | P&R "Declaração em conjunto" answers directly |
| `lex-007` | + Q114 | full official residency definition |
| `lex-050` | + Q738 | list of exempt assets (item I: savings) |
| `lex-030`, `lex-049` | preferred removed | single acceptable anchor |

Retired: `lex-008` (vague; merged into `lex-009`), `lex-013` (same anchor as `lex-012`), `lex-026`
(→ `lex-027`), `lex-028` (low value), `lex-032` (→ `lex-031`), `lex-036` (same anchor as `lex-035`),
`lex-038` (→ `lex-037`), `lex-040` (→ `lex-041`), `lex-043` (→ `lex-042`), `lex-044` (replaced by a
salaried-income case; the interest rule stays covered by `answer-015`), `lex-045` (same anchors as
`lex-042`), `lex-047` (→ `lex-046`), `lex-048` (duplicate of `lex-005`).

Answer fixture: `answer-006` + Q012, `answer-008` + Q037/Q035, `answer-013` + Q043/Q014, `answer-015` + Q063,
`answer-016` + Q007, for the same reasons.

## Known Extraction Issues (Not Fixed Here)

- **Trailing headings.** Each P&R chunk ends with the next question's section heading and sometimes a
  page number. Q317 ends with `LOTERIAS DE APOSTAS DE QUOTA FIXA (BETS)`, which belongs to Q318;
  Q178 ends with Q179's PLR heading. This attaches topical words to the wrong answer. The fix is to
  move each heading to the following question.
- **Chapter headings.** In the DOU extraction, `CAPÍTULO X / DA DECLARAÇÃO DE BENS...` is appended to
  Art. 10's chunk rather than starting Art. 11's.
- **Anchor naming.** `art-N-caput` for N ≠ 2 is the whole article. Labels such as `art-11-caput` for
  a § 3º rule are correct, but they read as wrong to reviewers. The `covers` field records the
  precise provision so a future paragraph-level chunking can migrate labels mechanically.
- **Source inconsistencies in the official P&R.** Q088 says R$ 300.000,00 (IN: R$ 800.000,00), and
  Q066 says "entre 11 e 31 de maio de 2024" for automatic debit (IN Art. 12 §3: 11 May 2026 to the
  deadline). These are good answer-eval traps: the model must prefer the IN.

## Risks

- Broader acceptable sets can hide weak ranking. Mitigation: every addition has a written reason,
  and preferred-source recall still tracks source choice.
- Visible cases written by the same person who audited the corpus are easier than real user
  questions. Mitigation: 35 of 60 questions are paraphrases or user scenarios (19 scenario-style), not source wording. A user-controlled holdout is still
  required before release decisions.
- Extractor v6 reprocesses the P&R source and deletes its embeddings. Semantic and hybrid runs are
  invalid until embeddings are regenerated.

## Test And Eval Plan

- `test_official_pdf_snapshot_extracts_every_numbered_question_in_order`: strict 001–745 sequence.
- `test_retrieval_fixture_covers_every_user_relevant_in_rfb_2312_article`: Arts. 1–16 covered.
- Existing anchor-existence test validates every label against v6 extraction.
- Re-run `lexical`, `lexical_authority`, `semantic` and `hybrid_rrf` on the revised suite and record
  the results below.

## Definition Of Done

- 60 cases, all anchors valid against extractor v6, and every case has a written label rationale.
- Arts. 1–16 covered; 32/49 P&R chapters covered, with the remainder listed in
  `docs/evals/retrieval-coverage.md`.
- Semantic and hybrid re-baselines recorded (pending: requires an API key and re-embedding).

## Evaluation Evidence

Local run, 2026-11-05, extractor v6, 787 chunks (745 P&R + 34 IN + 8 guidance).

| Strategy | Old suite (50) | Revised suite (60) |
| --- | --- | --- |
| `lexical` | 4/50 (8%) | 10/60 (17%) |
| `lexical_authority` | 4/50 (8%) | 9/60 (15%) |
| `semantic` | not run | **pending** |
| `hybrid_rrf` | not run | **pending** |

The lexical collapse from the 15/25 recorded on 2026-09-16 is not a label artifact. After the P&R
expansion, `ts_rank_cd` without length normalisation, combined with an OR-joined query, lets a few
very long chunks dominate. Q455 (21.7k characters), Q140, Q639 (21.9k) and Q331 (18k) appear in the
top 3 for most questions. This is a retrieval finding to investigate in its own spec. It also means
the old recorded lexical numbers are not comparable to the current corpus.

Offline diagnostic only (not a project strategy): a length-normalised BM25 with a Portuguese
stemmer scores 40/60 on the revised suite and 32/50 on the old one. It passes 17 of the 23 new cases,
so the new cases are achievable without being trivial. Its misses are the intended vocabulary
mismatch and trap cases (`lex-051`, `lex-053`, `lex-054`, `lex-059`, `lex-068`, `lex-069`).
