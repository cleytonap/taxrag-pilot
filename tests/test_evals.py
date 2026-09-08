from pathlib import Path
from types import SimpleNamespace

import pytest

from taxrag import evals
from taxrag.evals import load_retrieval_eval_cases, run_retrieval_evals

FIXTURE_PATH = Path("docs/evals/lexical-retrieval-baseline.jsonl")


def test_lexical_retrieval_fixture_has_unique_cases_and_valid_anchor_sets() -> None:
    cases = load_retrieval_eval_cases(FIXTURE_PATH)

    assert len(cases) == 9
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
        lambda _session, _question, limit: [
            SimpleNamespace(anchor_key="question-001--p23"),
            SimpleNamespace(anchor_key="art-2-inciso-i"),
        ][:limit],
    )

    result = run_retrieval_evals(None, [cases[0]])[0]  # type: ignore[arg-type]

    assert result.acceptable_rank == 1
    assert result.preferred_rank == 2
    assert result.passed_at_three is True
    assert result.preferred_at_three is True
