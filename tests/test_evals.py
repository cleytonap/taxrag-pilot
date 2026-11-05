from pathlib import Path
from types import SimpleNamespace

import pytest

from taxrag import evals
from taxrag.answers import (
    AnswerClaim,
    AnswerDraft,
    Citation,
    CitedAnswer,
    DraftCitation,
    DraftClaim,
)
from taxrag.cli import _format_answer_eval_result
from taxrag.evals import (
    evaluate_answer,
    load_answer_eval_cases,
    load_retrieval_eval_cases,
    run_answer_evals,
    run_retrieval_evals,
)
from taxrag.extraction import (
    extract_dou_in_rfb_2312_html,
    extract_receita_guidance_html,
    extract_receita_questions_answers_pdf,
)

FIXTURE_PATH = Path("docs/evals/lexical-retrieval-baseline.jsonl")
ANSWER_FIXTURE_PATH = Path("docs/evals/cited-answer-development.jsonl")


def test_lexical_retrieval_fixture_has_unique_cases_and_valid_anchor_sets() -> None:
    cases = load_retrieval_eval_cases(FIXTURE_PATH)

    assert len(cases) == 50
    assert len({case.case_id for case in cases}) == len(cases)
    assert all(case.question and case.acceptable_anchor_keys for case in cases)
    assert all(set(case.preferred_anchor_keys) <= set(case.acceptable_anchor_keys) for case in cases)


def test_retrieval_fixture_requires_all_contract_fields(tmp_path: Path) -> None:
    invalid_fixture = tmp_path / "invalid.jsonl"
    invalid_fixture.write_text('{"id":"missing-fields"}\n')

    with pytest.raises(ValueError, match="missing a required field"):
        load_retrieval_eval_cases(invalid_fixture)


def test_retrieval_fixture_rejects_preferred_anchors_outside_acceptable_set(tmp_path: Path) -> None:
    invalid_fixture = tmp_path / "invalid.jsonl"
    invalid_fixture.write_text(
        '{"id":"case","question":"question","acceptable_anchor_keys":["a"],'
        '"preferred_anchor_keys":["b"]}\n'
    )

    with pytest.raises(ValueError, match="outside acceptable_anchor_keys"):
        load_retrieval_eval_cases(invalid_fixture)


def test_retrieval_evaluation_tracks_acceptable_and_preferred_ranks(monkeypatch: pytest.MonkeyPatch) -> None:
    cases = load_retrieval_eval_cases(FIXTURE_PATH)
    monkeypatch.setattr(
        evals,
        "search_chunks",
        lambda _session, _question, limit, **_kwargs: [
            SimpleNamespace(anchor_key="question-001--p23"),
            SimpleNamespace(anchor_key="art-2-inciso-i"),
        ][:limit],
    )

    result = run_retrieval_evals(None, [cases[0]])[0]  # type: ignore[arg-type]

    assert result.acceptable_rank == 1
    assert result.preferred_rank == 2
    assert result.passed_at_three is True
    assert result.preferred_at_three is True


def test_retrieval_evaluation_forwards_the_selected_strategy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Evaluation labels cannot drift from the retrieval code actually being measured."""
    cases = load_retrieval_eval_cases(FIXTURE_PATH)
    observed: dict[str, object] = {}

    def fake_search(_session: object, _question: str, limit: int, **kwargs: object) -> list[object]:
        observed.update(kwargs)
        return [SimpleNamespace(anchor_key="art-2-inciso-i")][:limit]

    monkeypatch.setattr(evals, "search_chunks", fake_search)
    provider = SimpleNamespace(model="test", dimensions=1536)

    run_retrieval_evals(
        None,  # type: ignore[arg-type]
        [cases[0]],
        strategy="semantic",
        embedding_provider=provider,
    )

    assert observed == {"strategy": "semantic", "embedding_provider": provider}


def test_answer_fixture_has_reviewable_cases_and_an_abstention_case() -> None:
    """The answer fixture keeps subjective quality criteria visible rather than automating them."""
    cases = load_answer_eval_cases(ANSWER_FIXTURE_PATH)

    assert len(cases) == 20
    assert len({case.case_id for case in cases}) == len(cases)
    assert any(case.expected_abstain for case in cases)
    assert all(case.human_review_criteria for case in cases)


def test_all_eval_anchors_exist_in_the_checked_in_official_sources() -> None:
    """Fixture labels are checked against the exact local source snapshots and extractors."""
    source_root = Path("data/source-snapshots")
    dou = extract_dou_in_rfb_2312_html(
        next((source_root / "irpf-2026-in-rfb-2312").rglob("original.html")).read_bytes()
    )
    guidance = extract_receita_guidance_html(
        next((source_root / "irpf-2026-quem-deve-declarar").rglob("original.html")).read_bytes()
    )
    questions = extract_receita_questions_answers_pdf(
        next((source_root / "irpf-2026-perguntas-respostas").rglob("*.pdf")).read_bytes()
    )
    available = {section.anchor_key for result in (dou, guidance, questions) for section in result.sections}
    retrieval_cases = load_retrieval_eval_cases(FIXTURE_PATH)
    answer_cases = load_answer_eval_cases(ANSWER_FIXTURE_PATH)
    used = {
        anchor
        for case in (*retrieval_cases, *answer_cases)
        for anchor in case.acceptable_anchor_keys
    }

    assert used <= available, f"unknown evaluation anchors: {sorted(used - available)}"


def test_answer_fixture_rejects_support_anchors_for_an_abstention(tmp_path: Path) -> None:
    """An abstention cannot be made to pass by attaching irrelevant citations."""
    invalid_fixture = tmp_path / "invalid.jsonl"
    invalid_fixture.write_text(
        '{"id":"case","question":"question","acceptable_anchor_keys":["anchor"],'
        '"expected_abstain":true,"human_review_criteria":["review"]}\n'
    )

    with pytest.raises(ValueError, match="cannot declare support anchors"):
        load_answer_eval_cases(invalid_fixture)


def test_answer_evaluation_reports_structural_checks_without_judging_prose() -> None:
    """Anchor and abstention checks are deterministic; human criteria remain attached to the result."""
    case = load_answer_eval_cases(ANSWER_FIXTURE_PATH)[0]
    citation = Citation(
        chunk_id="chunk-1",
        anchor_key="art-2-inciso-i",
        anchor_title="Art. 2, inciso I",
        source_title="IN RFB nº 2.312/2026",
        canonical_url="https://example.test",
        authority_level="tax_authority_norm",
        excerpt="recebeu rendimentos tributáveis cuja soma foi superior ao limite.",
    )
    answer = CitedAnswer(
        question=case.question,
        claims=(AnswerClaim("Uma resposta propositalmente ruim, mas citada.", (citation,)),),
        abstain=False,
        limitation=None,
        clarification_question=None,
        retrieval_strategy="semantic",
        answer_model="test",
    )

    result = evaluate_answer(case, answer)

    assert result.passed_structural_checks is True
    assert result.human_review_criteria == case.human_review_criteria


def test_answer_evaluation_accepts_any_fixture_approved_official_anchor() -> None:
    """Guidance is valid support when the fixture explicitly lists it as acceptable."""
    case = load_answer_eval_cases(ANSWER_FIXTURE_PATH)[1]
    guidance_citation = Citation(
        chunk_id="chunk-1",
        anchor_key="voce-esta-obrigado-se--02",
        anchor_title="Você está obrigado se:",
        source_title="Quem deve declarar",
        canonical_url="https://example.test",
        authority_level="official_guidance",
        excerpt="Obteve ganho de capital.",
    )
    answer = CitedAnswer(
        question=case.question,
        claims=(AnswerClaim("Resposta apoiada em orientação oficial.", (guidance_citation,)),),
        abstain=False,
        limitation=None,
        clarification_question=None,
        retrieval_strategy="semantic",
        answer_model="test",
    )

    result = evaluate_answer(case, answer)

    assert result.cited_acceptable_anchor_keys == ("voce-esta-obrigado-se--02",)
    assert result.passed_structural_checks is True


def test_answer_eval_report_shows_question_expected_and_actual_values() -> None:
    """The CLI report must not make review rubrics look like generated output."""
    case = load_answer_eval_cases(ANSWER_FIXTURE_PATH)[0]
    citation = Citation(
        chunk_id="chunk-1",
        anchor_key="art-2-inciso-i",
        anchor_title="Art. 2, inciso I",
        source_title="IN RFB nº 2.312/2026",
        canonical_url="https://example.test",
        authority_level="tax_authority_norm",
        excerpt="recebeu rendimentos tributáveis cuja soma foi superior ao limite.",
    )
    result = evaluate_answer(
        case,
        CitedAnswer(
            question=case.question,
            claims=(AnswerClaim("Resposta de teste.", (citation,)),),
            abstain=False,
            limitation=None,
            clarification_question=None,
            retrieval_strategy="semantic",
            answer_model="test",
        ),
    )

    report = "\n".join(_format_answer_eval_result(result, show_answer=True))

    assert f"question: {case.question}" in report
    assert "expected:\n    acceptable official citation anchors: art-2-inciso-i" in report
    assert "actual:\n    cited anchors: art-2-inciso-i" in report
    assert "human-review checklist (not automatically scored):" in report
    assert "display answer: Resposta de teste." in report


def test_answer_evaluation_does_not_count_a_rejected_provider_output_as_abstention() -> None:
    """Safe fallback is not evidence that the provider followed an abstention instruction."""
    case = next(case for case in load_answer_eval_cases(ANSWER_FIXTURE_PATH) if case.expected_abstain)
    answer = CitedAnswer(
        question=case.question,
        claims=(),
        abstain=True,
        limitation="Não foi possível validar uma resposta com as fontes oficiais recuperadas.",
        clarification_question=None,
        retrieval_strategy="semantic",
        answer_model="test",
        outcome="provider_rejected",
    )

    result = evaluate_answer(case, answer)

    assert result.abstention_matches is False
    assert result.passed_structural_checks is False


def test_answer_evaluation_trace_explains_missing_retrieval_and_rejected_draft(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A failed development case identifies both retrieval and validation root causes."""
    case = load_answer_eval_cases(ANSWER_FIXTURE_PATH)[0]
    chunk = SimpleNamespace(
        chunk_id="available-chunk",
        anchor_key="unrelated-anchor",
        anchor_title="Unrelated evidence",
        source_title="Official source",
    )
    monkeypatch.setattr("taxrag.answers.search_chunks", lambda *_args, **_kwargs: [chunk])

    class InvalidCitationProvider:
        model = "test"

        def draft_answer(self, *_args: object) -> AnswerDraft:
            return AnswerDraft(
                claims=(
                    DraftClaim(
                        "Unsupported claim.",
                        (DraftCitation("invented-chunk"),),
                    ),
                ),
                abstain=False,
                limitation=None,
                clarification_question=None,
            )

    result = run_answer_evals(
        None,  # type: ignore[arg-type]
        [case],
        InvalidCitationProvider(),  # type: ignore[arg-type]
    )[0]
    report = "\n".join(_format_answer_eval_result(result, show_answer=False))

    assert result.trace.retrieved_evidence[0].anchor_key == "unrelated-anchor"
    assert result.trace.validation_error == "Claim 1, citation 1 cited a chunk that was not retrieved"
    assert result.trace.rejected_draft is not None
    assert "acceptable evidence absent from retrieval: art-2-inciso-i, limites-de-valor-para-o-exercicio-2026--03, question-001--p23" in report
    assert "validator rejection: Claim 1, citation 1 cited a chunk that was not retrieved" in report
    assert '"chunk_id": "invented-chunk"' in report


def test_answer_evaluation_forwards_provider_and_retrieval_configuration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Answer evaluations must record the same answer path and strategy they claim to measure."""
    case = load_answer_eval_cases(ANSWER_FIXTURE_PATH)[0]
    observed: dict[str, object] = {}

    def fake_answer_question(_session: object, question: str, provider: object, **kwargs: object) -> CitedAnswer:
        observed.update({"question": question, "provider": provider, **kwargs})
        return CitedAnswer(question, (), False, None, None, "semantic", "test")

    monkeypatch.setattr(evals, "answer_question", fake_answer_question)
    provider = SimpleNamespace(model="test")
    embedding_provider = SimpleNamespace(model="embedding-test", dimensions=1536)

    results = run_answer_evals(
        None,  # type: ignore[arg-type]
        [case],
        provider,  # type: ignore[arg-type]
        strategy="semantic",
        embedding_provider=embedding_provider,  # type: ignore[arg-type]
    )

    assert {
        "question": case.question,
        "provider": provider,
        "strategy": "semantic",
        "embedding_provider": embedding_provider,
    }.items() <= observed.items()
    assert callable(observed["on_retrieved_chunks"])
    assert callable(observed["on_validation_failure"])
    assert results[0].passed_structural_checks is False
