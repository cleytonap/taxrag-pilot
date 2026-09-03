from pathlib import Path

import pytest

from taxrag.evals import load_retrieval_eval_cases

FIXTURE_PATH = Path("docs/evals/lexical-retrieval-baseline.jsonl")


def test_lexical_retrieval_fixture_has_unique_cases_and_expected_anchors() -> None:
    cases = load_retrieval_eval_cases(FIXTURE_PATH)

    assert len(cases) == 9
    assert len({case.case_id for case in cases}) == len(cases)
    assert all(case.question and case.expected_anchor_key for case in cases)
    assert sum(not case.expected_recall_at_three for case in cases) == 1


def test_retrieval_fixture_requires_all_contract_fields(tmp_path: Path) -> None:
    invalid_fixture = tmp_path / "invalid.jsonl"
    invalid_fixture.write_text('{"id":"missing-fields"}\n')

    with pytest.raises(ValueError, match="missing a required field"):
        load_retrieval_eval_cases(invalid_fixture)
