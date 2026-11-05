"""Focused contracts for the local Eval Manager developer boundary."""

from __future__ import annotations

from pathlib import Path

import pytest

from taxrag import eval_manager


def test_get_artifact_rejects_path_traversal(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Artifacts are selected by a simple known file name, never a caller-controlled path."""
    monkeypatch.setattr(eval_manager, "ARTIFACTS_DIRECTORY", tmp_path)

    with pytest.raises(ValueError, match="file name"):
        eval_manager.get_artifact("../.env")


def test_list_and_get_artifact_only_exposes_supported_files(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The archive filters unrelated local files before rendering a developer history list."""
    (tmp_path / "run.txt").write_text("diagnostic", encoding="utf-8")
    (tmp_path / "secret.env").write_text("do-not-show", encoding="utf-8")
    monkeypatch.setattr(eval_manager, "ARTIFACTS_DIRECTORY", tmp_path)
    monkeypatch.setattr(eval_manager, "BASELINES_DIRECTORY", tmp_path / "no-baselines")

    assert [artifact["name"] for artifact in eval_manager.list_artifacts()] == ["run.txt"]
    assert eval_manager.get_artifact("run.txt") == {"name": "run.txt", "content": "diagnostic"}


def test_openai_debug_request_requires_explicit_confirmation() -> None:
    """The paid provider is refused before the database, retrieval, or provider boundary runs."""
    with pytest.raises(PermissionError, match="confirm_paid_request"):
        eval_manager.debug_answer(
            object(),  # type: ignore[arg-type]
            question="Posso declarar?",
            strategy="lexical",
            provider_id="openai",
            confirm_paid_request=False,
        )


def test_save_fixture_rejects_invalid_json_before_replacing_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A malformed edit leaves the Git-tracked source file unchanged."""
    source = tmp_path / "retrieval.jsonl"
    original = (eval_manager.PROJECT_ROOT / "docs/evals/lexical-retrieval-baseline.jsonl").read_text(
        encoding="utf-8"
    )
    source.write_text(original, encoding="utf-8")
    monkeypatch.setitem(eval_manager.SUITE_PATHS, "retrieval", source)

    with pytest.raises(ValueError, match="not valid JSON"):
        eval_manager.save_fixture("retrieval", "not json")

    assert source.read_text(encoding="utf-8") == original
