from pathlib import Path
from types import SimpleNamespace

import pytest

from taxrag import evals
from taxrag.answers import AnswerClaim, Citation, CitedAnswer
from taxrag.evals import (
    evaluate_answer,
    load_answer_eval_cases,
    load_retrieval_eval_cases,
    run_answer_evals,
    run_retrieval_evals,
)

FIXTURE_PATH = Path("docs/evals/lexical-retrieval-baseline.jsonl")
ANSWER_FIXTURE_PATH = Path("docs/evals/cited-answer-development.jsonl")


def test_lexical_retrieval_fixture_has_unique_cases_and_valid_anchor_sets() -> None:
    cases = load_retrieval_eval_cases(FIXTURE_PATH)

    assert len(cases) == 25
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

    assert len(cases) == 4
    assert len({case.case_id for case in cases}) == len(cases)
    assert any(case.expected_abstain for case in cases)
    assert all(case.human_review_criteria for case in cases)


def test_answer_fixture_rejects_anchor_requirements_for_an_abstention(tmp_path: Path) -> None:
    """An abstention cannot be made to pass by attaching irrelevant citations."""
    invalid_fixture = tmp_path / "invalid.jsonl"
    invalid_fixture.write_text(
        '{"id":"case","question":"question","required_anchor_keys":["anchor"],'
        '"expected_abstain":true,"human_review_criteria":["review"]}\n'
    )

    with pytest.raises(ValueError, match="cannot require citations"):
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
        quote="recebeu rendimentos tributáveis cuja soma foi superior ao limite.",
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

    assert observed == {
        "question": case.question,
        "provider": provider,
        "strategy": "semantic",
        "embedding_provider": embedding_provider,
    }
    assert results[0].passed_structural_checks is False
