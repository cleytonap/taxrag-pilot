"""Single source of truth for what every eval field and value means.

Feeds the Workshop's Glossary tab (via the API), the generated docs/evals/glossary.md, and a
completeness test: a fixture field or category value without an entry here fails the tests,
so the glossary cannot silently drift from the suites.

Run ``uv run python -m taxrag.eval_glossary`` to regenerate the Markdown version.
"""

from __future__ import annotations

import collections
import json
from pathlib import Path
from typing import Any

from taxrag.config import PROJECT_ROOT

SUITES = [
    {
        "id": "retrieval",
        "name": "Retrieval (chunks only)",
        "file": "docs/evals/lexical-retrieval-baseline.jsonl",
        "purpose": "Does the retriever put an official passage that answers the question in the "
        "top results? No LLM answer is produced. Scored by recall@k.",
    },
    {
        "id": "generation",
        "name": "Answer generation (fixed evidence)",
        "file": "docs/evals/answer-generation.jsonl",
        "purpose": "Given fixed chunks (correct ones plus realistic distractors), does the answer "
        "model cite correctly, abstain when it should, and stay grounded? Retrieval is not used.",
    },
    {
        "id": "answer",
        "name": "End-to-end answers",
        "file": "docs/evals/cited-answer-development.jsonl",
        "purpose": "What a user gets from the production pipeline: retrieval + generation + "
        "validation + verification, for the same kinds of questions.",
    },
]

ANCHOR_KEY_FORMATS = [
    {"value": "art-N-caput", "meaning": "IN RFB 2.312/2026, whole article N (1, 3-17). Despite "
     "the name, the chunk holds the full article.", "example": "art-11-caput"},
    {"value": "art-2-inciso-<roman>", "meaning": "IN RFB 2.312/2026, Art. 2 inciso (I-XII): one "
     "filing-obligation criterion.", "example": "art-2-inciso-vi"},
    {"value": "art-2-caput / art-2-paragrafo-N", "meaning": "Art. 2 lead-in text or paragraph "
     "(§1 dispensations, §2 voluntary filing, §3 no double listing).", "example": "art-2-paragrafo-2"},
    {"value": "art-2-paragrafo-1-inciso-<roman>", "meaning": "A dispensation under Art. 2 §1.",
     "example": "art-2-paragrafo-1-inciso-i"},
    {"value": "question-NNN--pPP", "meaning": "Perguntas e Respostas IRPF 2026, question NNN "
     "starting on PDF page PP.", "example": "question-340--p175"},
    {"value": "<slug>--NN", "meaning": "Receita guidance page 'Quem deve declarar', section NN "
     "(slug of its heading).", "example": "limites-de-valor-para-o-exercicio-2026--03"},
]

EDGE_CASES = {
    "typo-no-accents": "Same question written informally, without accents or with typos.",
    "keyword-only": "A few keywords instead of a question (search-box style).",
    "long-noisy": "Long conversational question with irrelevant details around the real ask.",
    "boundary-value": "Amount exactly at a legal threshold ('superior a' means equal does not count).",
    "other-year": "Asks about another exercise/year; the 2026 rules must not be applied to it.",
    "future-year": "Asks about a future exercise with no official source yet; must abstain.",
    "calendar-vs-exercise": "Confuses the event year with the exercise (exercício 2026 = ano-calendário 2025).",
    "scope-boundary": "The user falls outside the rule's subject (e.g. non-residents).",
    "stale-source-conflict": "An official Q&A passage has an outdated figure; the IN value must win.",
    "false-premise": "The question assumes something false; the answer must correct it.",
    "multi-condition": "Several facts; the decisive rule must be retrieved, not a merely related one.",
    "below-threshold": "Amount below a threshold; the conclusion must stay limited to that criterion.",
    "arithmetic": "Needs simple arithmetic on the user's facts (e.g. 12 x a monthly amount).",
    "personalized-advice": "Asks for a personal tax calculation; explain rules, do not compute a final amount.",
    "out-of-scope-tax": "Another tax (ISS, ITCMD, MEI/Simples); must abstain.",
    "out-of-scope-jurisdiction": "Another country's tax; must abstain.",
    "off-domain": "Not about taxes at all; must abstain.",
    "prompt-injection": "Tries to override instructions or dictate the answer; must not comply.",
    "unsupported-language": "Not in Portuguese; the fixed Portuguese-only notice is expected.",
    "missing-source": "An IRPF topic absent from the corpus; must abstain rather than use model memory.",
    "insufficient-evidence": "Generation only: in-scope question whose fixed context does not answer it.",
}

STYLES = {
    "source-wording": "Uses the official text's vocabulary (easiest for retrieval).",
    "paraphrase": "Same meaning in everyday wording.",
    "scenario": "Describes the user's situation; the legal question is implicit.",
}

FIELD = dict[str, Any]
FIELDS: list[FIELD] = [
    {
        "name": "id",
        "suites": {"retrieval": "required", "generation": "required", "answer": "required"},
        "type": "string",
        "description": "Unique, stable case identifier. Never reused after a case is retired, so "
        "results stay comparable across baselines.",
        "accepts": "lex-NNN (retrieval), gen-NNN (generation), answer-NNN (end-to-end).",
        "example": '"id": "lex-046"',
    },
    {
        "name": "question",
        "suites": {"retrieval": "required", "generation": "required", "answer": "required"},
        "type": "string",
        "description": "The user's question exactly as it is sent to the system.",
        "accepts": "Non-empty text, normally in Portuguese (other languages test the language gate).",
        "example": '"question": "Tenho conta corrente com saldo de R$ 100 no fim do ano. '
        'Sou obrigado a incluir essa conta na declaração de bens?"',
    },
    {
        "name": "acceptable_anchor_keys",
        "suites": {"retrieval": "required", "generation": "required", "answer": "required"},
        "type": "array of anchor keys",
        "description": "Official passages that, read alone, let a user verify a correct answer. "
        "Retrieval passes if any appears in the top 3; answer suites pass if the answer cites "
        "one. Must be complete: a missing valid passage makes a correct result fail.",
        "accepts": "Retrieval: at least one key. Answer suites: empty exactly when "
        "expected_abstain is true; in generation it must be a subset of context_anchor_keys. "
        "Key formats are listed in the values below.",
        "values": ANCHOR_KEY_FORMATS,
        "example": '"acceptable_anchor_keys": ["art-11-caput", "question-007--p25"]',
    },
    {
        "name": "preferred_anchor_keys",
        "suites": {"retrieval": "optional"},
        "type": "array of anchor keys",
        "description": "The passage the source policy prefers when several are acceptable "
        "(e.g. the controlling IN article over an explanatory Q&A). Measured as "
        "preferred-source recall, a diagnostic, not a pass/fail gate.",
        "accepts": "Subset of acceptable_anchor_keys; declared only when two or more acceptable "
        "anchors compete, otherwise [].",
        "example": '"preferred_anchor_keys": ["art-11-caput"]',
    },
    {
        "name": "expected_recall_at_three",
        "suites": {"retrieval": "optional"},
        "type": "boolean (default true)",
        "description": "Legacy flag marking a known gap that is not expected to pass. Not used "
        "by the current cases.",
        "accepts": "true or false.",
        "example": '"expected_recall_at_three": false',
    },
    {
        "name": "context_anchor_keys",
        "suites": {"generation": "required"},
        "type": "ordered array of anchor keys",
        "description": "The fixed evidence given to the answer model instead of retrieval, in "
        "this order. Usually the correct passages interleaved with distractors that a real "
        "retrieval returned, so the model is tested under realistic noise.",
        "accepts": "Non-empty; every key must exist in the indexed corpus (not excluded by errata).",
        "example": '"context_anchor_keys": ["question-010--p26", "art-11-caput", '
        '"voce-esta-obrigado-se--02"]',
    },
    {
        "name": "expected_abstain",
        "suites": {"generation": "required", "answer": "required"},
        "type": "boolean",
        "description": "true when the correct behaviour is to decline (out of scope, another "
        "year, missing source, injection, non-Portuguese). Deliberate abstentions pass: the "
        "model abstaining, the language gate, or the answer verifier.",
        "accepts": "true or false. If true, acceptable_anchor_keys must be [].",
        "example": '"expected_abstain": true',
    },
    {
        "name": "human_review_criteria",
        "suites": {"generation": "required", "answer": "required"},
        "type": "array of strings",
        "description": "What a human reviewer checks in the user-visible answer (claims, caveats "
        "and clarification question). Not scored automatically. Criteria must be verifiable "
        "from the corpus.",
        "accepts": "At least one distinct criterion, written in Portuguese.",
        "example": '"human_review_criteria": ["Informa o limite de R$ 800.000,00 para os bens privativos."]',
    },
    {
        "name": "topic",
        "suites": {"retrieval": "metadata", "generation": "metadata", "answer": "metadata"},
        "type": "string (slug)",
        "description": "Subject area, used to slice results and check coverage. Sub-topics use "
        "'/' (e.g. deducoes/medicas).",
        "accepts": "Any lowercase slug; current values are listed below with their counts.",
        "values_from": "topic",
        "example": '"topic": "bens-e-direitos"',
    },
    {
        "name": "edge_case",
        "suites": {"retrieval": "metadata", "generation": "metadata", "answer": "metadata"},
        "type": "string (category)",
        "description": "Marks a deliberately hard case and which difficulty it tests. Omitted for "
        "ordinary cases. Tests require each category to keep at least one case.",
        "accepts": "One of the values below.",
        "values": [{"value": key, "meaning": text} for key, text in EDGE_CASES.items()],
        "values_from": "edge_case",
        "example": '"edge_case": "stale-source-conflict"',
    },
    {
        "name": "style",
        "suites": {"retrieval": "metadata"},
        "type": "string (category)",
        "description": "How the question is phrased relative to the official text.",
        "accepts": "One of the values below.",
        "values": [{"value": key, "meaning": text} for key, text in STYLES.items()],
        "values_from": "style",
        "example": '"style": "scenario"',
    },
    {
        "name": "covers",
        "suites": {"retrieval": "metadata"},
        "type": "array of strings",
        "description": "Human-readable legal/Q&A references the case covers; drives the coverage "
        "report and lets labels be migrated if chunking changes.",
        "accepts": "Free text such as 'IN art. 11, §3, I', 'P&R 007', 'Guia: limites'.",
        "example": '"covers": ["IN art. 11, §3, I", "P&R 007"]',
    },
    {
        "name": "label_notes",
        "suites": {"retrieval": "metadata", "generation": "metadata", "answer": "metadata"},
        "type": "string",
        "description": "Why these anchors and expectations were chosen, what was rejected and "
        "why, and dated label changes. The audit trail for reviewers.",
        "accepts": "Free text.",
        "example": '"label_notes": "ADDED Q007: its Atenção repeats the Art. 11 §3 list."',
    },
    {
        "name": "derived_from",
        "suites": {"generation": "metadata"},
        "type": "string (case id)",
        "description": "The end-to-end case this generation case mirrors (same question and "
        "criteria), so retrieval and generation failures can be told apart.",
        "accepts": "An answer-NNN id.",
        "example": '"derived_from": "answer-033"',
    },
]

RUN_TERMS: list[FIELD] = [
    {
        "name": "strategy",
        "group": "Run configuration",
        "description": "How evidence was obtained for the run.",
        "values": [
            {"value": "hybrid_rerank", "meaning": "Production since V2: lexical+semantic "
             "candidates reordered by an LLM reranker."},
            {"value": "semantic", "meaning": "Embedding similarity only (production in V0-V1)."},
            {"value": "hybrid_rrf", "meaning": "Unweighted reciprocal-rank fusion of lexical and "
             "semantic (diagnostic)."},
            {"value": "lexical", "meaning": "PostgreSQL full-text ranking (diagnostic; no API calls)."},
            {"value": "lexical_authority", "meaning": "Lexical with a bounded authority boost (diagnostic)."},
            {"value": "fixed_context", "meaning": "Generation suite: evidence comes from the case."},
        ],
        "example": '"strategy": "hybrid_rerank"',
    },
    {
        "name": "outcome (actual_outcome)",
        "group": "Answer results",
        "description": "What the answer pipeline returned for a case.",
        "values": [
            {"value": "answered", "meaning": "Claims with validated citations were shown."},
            {"value": "provider_abstained", "meaning": "The model declined (deliberate)."},
            {"value": "verification_abstained", "meaning": "The answer verifier blocked the "
             "draft (deliberate system decision)."},
            {"value": "unsupported_language", "meaning": "Non-Portuguese question; fixed notice "
             "(deliberate)."},
            {"value": "provider_rejected", "meaning": "Validation rejected the draft (uncited "
             "chunk, figure not in evidence, malformed output). Safe for the user, but not "
             "counted as a deliberate abstention."},
            {"value": "no_retrieved_evidence", "meaning": "Retrieval returned nothing."},
        ],
        "example": '"actual_outcome": "verification_abstained"',
    },
    {
        "name": "recall_at_one / three / five / ten",
        "group": "Retrieval metrics",
        "description": "Share of cases whose first acceptable anchor is within the top 1/3/5/10. "
        "recall@3 is the pass/fail metric; answers receive the top 5 (TAXRAG_ANSWER_TOP_K).",
        "example": '"recall_at_three": 1.0',
    },
    {
        "name": "mrr_at_ten",
        "group": "Retrieval metrics",
        "description": "Mean reciprocal rank of the first acceptable anchor (1 = always first; "
        "0 when outside the top 10).",
        "example": '"mrr_at_ten": 0.986',
    },
    {
        "name": "preferred_recall_at_three",
        "group": "Retrieval metrics",
        "description": "Among cases with preferred anchors, share where a preferred passage is in "
        "the top 3. Diagnostic for source choice.",
        "example": '"preferred_recall_at_three": 0.911',
    },
    {
        "name": "acceptable_rank / preferred_rank",
        "group": "Retrieval results",
        "description": "1-based rank of the first acceptable / preferred anchor in the top 10; "
        "null when absent.",
        "example": '"acceptable_rank": 2',
    },
    {
        "name": "structural_pass_rate (passed)",
        "group": "Answer metrics",
        "description": "Automated check: answerable cases must answer and cite an acceptable "
        "anchor; abstention cases must abstain deliberately. Does not judge legal correctness; "
        "human review does.",
        "example": '"structural_pass_rate": 0.879',
    },
    {
        "name": "abstention_passed / answerable_passed",
        "group": "Answer metrics",
        "description": "The pass count split by expected behaviour: declining correctly vs "
        "answering correctly.",
        "example": '"abstention_passed": 10',
    },
    {
        "name": "unsafe_answers",
        "group": "Answer metrics",
        "description": "An answer was shown although the case requires abstention. The most "
        "harmful failure.",
        "example": '"unsafe_answers": 1',
    },
    {
        "name": "validation_rejections",
        "group": "Answer metrics",
        "description": "Drafts blocked by deterministic validation (invalid citation, figure "
        "absent from evidence).",
        "example": '"validation_rejections": 1',
    },
    {
        "name": "verification_abstentions / verifier_blocked_answerable",
        "group": "Answer metrics",
        "description": "Answers blocked by the second-pass verifier, and how many of those were "
        "answerable cases (its possible false positives; check each reason).",
        "example": '"verifier_blocked_answerable": 1',
    },
    {
        "name": "answer_top_k / answer_verification / rerank_model / verifier_model",
        "group": "Run configuration",
        "description": "Answer-pipeline settings used by the run; comparisons warn when they differ.",
        "example": '"answer_top_k": 5, "answer_verification": true',
    },
    {
        "name": "fixture_sha256 / source_versions.processing_version",
        "group": "Run configuration",
        "description": "Exact fixture content and corpus build (extractor + errata) behind the "
        "run; comparisons warn when they differ.",
        "example": '"processing_version": "7+errata.3840d5c3"',
    },
    {
        "name": "retrieved_evidence",
        "group": "Case results",
        "description": "Chunks retrieved (or given, in generation) with rank, score and excerpt. "
        "Baselines keep excerpts only for ranks 1-3.",
        "example": '{"anchor_key": "art-11-caput", "rank": 1, "score": 1.0}',
    },
    {
        "name": "cited_anchor_keys / cited_acceptable_anchor_keys",
        "group": "Case results",
        "description": "Anchors the answer cited, and those among them that are acceptable.",
        "example": '"cited_acceptable_anchor_keys": ["art-11-caput"]',
    },
    {
        "name": "rejected_draft",
        "group": "Case results",
        "description": "The model's draft that validation or the verifier blocked (never shown "
        "to users). Read it to judge whether the block was right.",
        "example": '"rejected_draft": {"claims": [{"text": "...", "citations": [...]}], "abstain": false}',
    },
    {
        "name": "validation_error",
        "group": "Case results",
        "description": "Why a draft was blocked before display (validation or verifier reason).",
        "example": '"validation_error": "Claim 1 states figures absent from its cited evidence: R$ 81.000,00"',
    },
]


def fixture_records() -> dict[str, list[dict[str, Any]]]:
    """Load every suite's fixture records (including review-only metadata)."""
    records = {}
    for suite in SUITES:
        path = PROJECT_ROOT / suite["file"]
        records[suite["id"]] = [
            json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
        ]
    return records


def glossary() -> dict[str, Any]:
    """Build the glossary with live value counts and one real example record per suite."""
    records = fixture_records()
    suites = []
    for suite in SUITES:
        rows = records[suite["id"]]
        suites.append({**suite, "case_count": len(rows), "example_record": rows[0] if rows else None})
    fields = []
    for field in FIELDS:
        entry = dict(field)
        key = field.get("values_from")
        if key:
            counts: collections.Counter[str] = collections.Counter()
            per_suite: dict[str, collections.Counter[str]] = collections.defaultdict(collections.Counter)
            for suite_id, rows in records.items():
                for row in rows:
                    if key in row:
                        counts[row[key]] += 1
                        per_suite[row[key]][suite_id] += 1
            known = {item["value"]: item for item in field.get("values", [])}
            values = [
                {
                    "value": value,
                    "meaning": known.get(value, {}).get("meaning", ""),
                    "count": counts.get(value, 0),
                    "suites": dict(per_suite.get(value, {})),
                }
                for value in list(known) + sorted(set(counts) - set(known))
            ]
            entry["values"] = values
        fields.append(entry)
    return {"suites": suites, "fields": fields, "run_terms": RUN_TERMS}


def undocumented() -> list[str]:
    """Fixture fields or category values that have no glossary entry (must be empty)."""
    problems = []
    documented = {field["name"]: field for field in FIELDS}
    for suite_id, rows in fixture_records().items():
        for row in rows:
            for key in row:
                field = documented.get(key)
                if field is None or suite_id not in field["suites"]:
                    problems.append(f"{suite_id}: field '{key}'")
            for key, allowed in (("edge_case", EDGE_CASES), ("style", STYLES)):
                if key in row and row[key] not in allowed:
                    problems.append(f"{suite_id}: {key} value '{row[key]}'")
    return sorted(set(problems))


def render_markdown() -> str:
    """Render the glossary for readers outside the Workshop."""
    data = glossary()
    lines = [
        "# Eval Glossary",
        "",
        ("Generated by `uv run python -m taxrag.eval_glossary` from `taxrag/eval_glossary.py`. "
        "Do not edit by hand. The Workshop's **Glossary** tab shows the same content with search."),
        "",
        "## Suites",
        "",
        "| Suite | File | Cases | Purpose |",
        "| --- | --- | ---: | --- |",
    ]
    lines += [
        f"| {s['name']} (`{s['id']}`) | `{s['file']}` | {s['case_count']} | {s['purpose']} |"
        for s in data["suites"]
    ]
    lines += ["", "## Fixture fields", ""]
    for field in data["fields"]:
        usage = ", ".join(f"{suite}: {status}" for suite, status in field["suites"].items())
        lines += [
            f"### `{field['name']}`",
            "",
            f"*{field['type']}* · {usage}",
            "",
            field["description"],
            "",
            f"**Accepts:** {field['accepts']}",
            "",
        ]
        if field.get("values"):
            lines += ["| Value | Meaning | Cases |", "| --- | --- | ---: |"]
            for value in field["values"]:
                count = value.get("count", "")
                meaning = value.get("meaning", "") + (
                    f" Example: `{value['example']}`" if value.get("example") else ""
                )
                lines.append(f"| `{value['value']}` | {meaning} | {count} |")
            lines.append("")
        lines += ["```json", field["example"], "```", ""]
    lines += ["## Run results and metrics", ""]
    for term in data["run_terms"]:
        lines += [f"### `{term['name']}` ({term['group']})", "", term["description"], ""]
        if term.get("values"):
            lines += ["| Value | Meaning |", "| --- | --- |"]
            lines += [f"| `{v['value']}` | {v['meaning']} |" for v in term["values"]]
            lines.append("")
        lines += ["```json", term["example"], "```", ""]
    return "\n".join(lines)


if __name__ == "__main__":
    output = Path(PROJECT_ROOT / "docs/evals/glossary.md")
    output.write_text(render_markdown(), encoding="utf-8")
    print(f"Wrote {output.relative_to(PROJECT_ROOT)}")
