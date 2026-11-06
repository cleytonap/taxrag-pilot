"""Portuguese-only gate, figure grounding, and user-visible caveats in the answer path."""

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from taxrag import answers
from taxrag.answers import (
    AnswerDraft,
    AnswerValidationError,
    CitedAnswer,
    DraftCitation,
    DraftClaim,
    answer_question,
    validate_answer_draft,
)
from taxrag.extraction import extract_receita_questions_answers_pdf
from taxrag.grounding import unsupported_figures
from taxrag.language import UNSUPPORTED_LANGUAGE_MESSAGE, detect_unsupported_language

FIXTURES = [
    Path("docs/evals/lexical-retrieval-baseline.jsonl"),
    Path("docs/evals/answer-generation.jsonl"),
    Path("docs/evals/cited-answer-development.jsonl"),
]


def _questions() -> list[dict[str, object]]:
    return [json.loads(line) for path in FIXTURES for line in path.read_text().splitlines() if line]


def test_language_gate_never_refuses_a_portuguese_question() -> None:
    """Precision first: every fixture question and all 745 official P&R titles stay answerable."""
    pdf = next(Path("data/source-snapshots/irpf-2026-perguntas-respostas").rglob("*.pdf"))
    titles = [
        section.display_title.split(": ", 1)[1]
        for section in extract_receita_questions_answers_pdf(pdf.read_bytes()).sections
    ]
    portuguese = [
        str(case["question"])
        for case in _questions()
        if case.get("edge_case") != "unsupported-language"
    ]
    informal = ["quanto pago de ir em bets", "day trade paga ir?", "como declarar pgbl", "irpf 2026 multa"]

    assert [text for text in portuguese + titles + informal if detect_unsupported_language(text)] == []


@pytest.mark.parametrize(
    ("question", "language"),
    [
        ("Do I need to file a Brazilian income tax return if I earned R$ 40,000 in 2025?", "en"),
        ("What is the deadline to file my tax return in Brazil?", "en"),
        ("Can I deduct medical expenses?", "en"),
        ("¿Cuál es el plazo para presentar la declaración de renta en Brasil?", "es"),
        ("Tengo que pagar impuesto si vendí mi casa?", "es"),
    ],
)
def test_language_gate_flags_english_and_spanish(question: str, language: str) -> None:
    assert detect_unsupported_language(question) == language


def test_unsupported_language_returns_fixed_notice_without_retrieval(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def no_retrieval(*_args: object, **_kwargs: object) -> list[object]:
        raise AssertionError("retrieval must not run for an unsupported language")

    monkeypatch.setattr(answers, "search_chunks", no_retrieval)
    provider = SimpleNamespace(model="test")

    answer = answer_question(None, "What is the deadline to file my tax return?", provider)  # type: ignore[arg-type]

    assert answer.outcome == "unsupported_language"
    assert answer.abstain is True
    assert answer.display_text == UNSUPPORTED_LANGUAGE_MESSAGE


def test_figure_grounding_flags_invented_amounts_and_allows_derived_ones() -> None:
    evidence = ["superior a R$ 35.584,00 (trinta e cinco mil...) até 29 de maio de 2026; 20% do valor"]

    assert unsupported_figures("O limite do MEI é R$ 81.000,00.", evidence) == ["R$ 81.000,00"]
    assert unsupported_figures("Acima de R$ 35.584,00, até 29 de maio de 2026, 20%.", evidence) == []
    # 12 x "3 mil por mês" from the question, and the question's own amount, are supported.
    assert (
        unsupported_figures(
            "R$ 3.000,00 por mês somam R$ 36.000,00, acima de R$ 35.584,00.",
            evidence,
            "Recebi 3 mil por mês no ano passado",
        )
        == []
    )
    assert unsupported_figures("O prazo vai até 30 de abril de 2026.", evidence) == ["30 de abril"]
    assert unsupported_figures("A alíquota é de 27,5%.", evidence) == ["27,5%"]


def test_validation_rejects_a_claim_whose_figure_is_not_in_its_citation() -> None:
    chunk = SimpleNamespace(
        chunk_id="c1",
        anchor_key="question-184--p104",
        anchor_title="MEI",
        source_title="P&R",
        canonical_url="https://example.test",
        source_link="https://example.test",
        authority_level="official_guidance",
        chunk_text="O lucro do MEI é isento, observados os percentuais de presunção.",
    )
    draft = AnswerDraft(
        claims=(DraftClaim("O limite do MEI é R$ 81.000,00.", (DraftCitation("c1"),)),),
        abstain=False,
        limitation=None,
        clarification_question=None,
    )

    with pytest.raises(AnswerValidationError, match="R\\$ 81.000,00"):
        validate_answer_draft(draft, [chunk], question="Qual o limite do MEI?")  # type: ignore[list-item]


def test_display_text_includes_caveats_and_clarification_with_claims() -> None:
    citation = answers.Citation("c", "a", "t", "s", "u", "official_guidance", "x")
    answer = CitedAnswer(
        question="q",
        claims=(answers.AnswerClaim("Você não está obrigado por este critério.", (citation,)),),
        abstain=False,
        limitation="Outras hipóteses podem obrigar a declaração.",
        clarification_question="Você teve ganho de capital em 2025?",
        retrieval_strategy="semantic",
        answer_model="test",
    )

    assert answer.display_text == (
        "Você não está obrigado por este critério.\n\n"
        "Outras hipóteses podem obrigar a declaração.\n\n"
        "Você teve ganho de capital em 2025?"
    )
