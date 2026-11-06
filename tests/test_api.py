"""HTTP contracts for the small local developer API."""

from fastapi.testclient import TestClient

from apps.api.main import app


def test_eval_manager_lists_the_known_fixture_suites() -> None:
    """The dashboard receives a closed, useful set of suites rather than arbitrary files."""
    response = TestClient(app).get("/api/evals/suites")

    assert response.status_code == 200
    assert [suite["id"] for suite in response.json()["suites"]] == ["retrieval", "generation", "answer"]


def test_debug_openai_requires_an_explicit_paid_confirmation() -> None:
    """The API refuses the provider request before retrieval or an external OpenAI call."""
    response = TestClient(app).post(
        "/api/evals/debug-answer",
        json={
            "question": "Recebi rendimentos tributáveis. Devo declarar?",
            "strategy": "lexical",
            "provider": "openai",
            "confirm_paid_request": False,
        },
    )

    assert response.status_code == 403
    assert "confirm_paid_request" in response.json()["detail"]
