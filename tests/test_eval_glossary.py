"""The glossary must document every fixture field, category value, strategy and outcome."""

from typing import get_args

from fastapi.testclient import TestClient

from apps.api.main import app
from taxrag.answers import AnswerOutcome
from taxrag.eval_glossary import RUN_TERMS, glossary, undocumented
from taxrag.retrieval import SUPPORTED_STRATEGIES


def _values(term_name: str) -> set[str]:
    term = next(term for term in RUN_TERMS if term["name"].startswith(term_name))
    return {value["value"] for value in term["values"]}


def test_every_fixture_field_and_category_value_is_documented() -> None:
    assert undocumented() == []


def test_strategies_and_outcomes_match_the_code() -> None:
    assert _values("strategy") == {*SUPPORTED_STRATEGIES, "fixed_context"}
    assert _values("outcome") == set(get_args(AnswerOutcome))


def test_glossary_endpoint_serves_suites_fields_and_live_counts() -> None:
    response = TestClient(app).get("/api/evals/glossary")

    assert response.status_code == 200
    body = response.json()
    assert [suite["id"] for suite in body["suites"]] == ["retrieval", "generation", "answer"]
    edge = next(field for field in body["fields"] if field["name"] == "edge_case")
    assert all(value["meaning"] for value in edge["values"])
    assert sum(value["count"] for value in edge["values"]) > 0


def test_markdown_glossary_is_current() -> None:
    """docs/evals/glossary.md must be regenerated when the glossary or fixtures change."""
    from pathlib import Path

    from taxrag.eval_glossary import render_markdown

    assert Path("docs/evals/glossary.md").read_text(encoding="utf-8") == render_markdown()
    assert glossary()["fields"]
