"""Baseline, comparison, background-run, and embedding-batch behaviour of the eval tooling."""

import json
import time
from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace

import pytest

from taxrag import eval_manager
from taxrag.embeddings import (
    EMBEDDING_BATCH_MAX_CHARACTERS,
    EMBEDDING_BATCH_MAX_INPUTS,
    _embedding_batches,
)
from taxrag.evals import load_answer_eval_cases


def _artifact(cases: list[dict[str, object]], **overrides: object) -> dict[str, object]:
    artifact = {
        "run_id": "abc",
        "suite_id": "retrieval",
        "strategy": "lexical",
        "provider": None,
        "embedding_model": None,
        "fixture_sha256": "f" * 64,
        "finished_at": "2026-11-05T00:00:00+00:00",
        "summary": {"case_count": len(cases), "passed": sum(bool(c["passed"]) for c in cases)},
        "source_versions": [{"source_key": "s", "source_version_id": "1", "content_hash": "h"}],
        "cases": cases,
    }
    artifact.update(overrides)
    return artifact


@pytest.fixture
def directories(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> tuple[Path, Path]:
    runs, baselines = tmp_path / "runs", tmp_path / "baselines"
    runs.mkdir()
    monkeypatch.setattr(eval_manager, "ARTIFACTS_DIRECTORY", runs)
    monkeypatch.setattr(eval_manager, "BASELINES_DIRECTORY", baselines)
    return runs, baselines


def test_embedding_batches_respect_input_and_character_limits() -> None:
    """The full P&R source is ~1.1M characters; one request would exceed the API token cap."""
    chunks = [SimpleNamespace(search_text="x" * 20_000) for _ in range(60)]
    chunks += [SimpleNamespace(search_text="y") for _ in range(200)]

    batches = _embedding_batches(chunks)  # type: ignore[arg-type]

    assert sum(len(batch) for batch in batches) == len(chunks)
    assert all(len(batch) <= EMBEDDING_BATCH_MAX_INPUTS for batch in batches)
    assert all(
        sum(len(chunk.search_text) for chunk in batch) <= EMBEDDING_BATCH_MAX_CHARACTERS
        for batch in batches
    )


def test_promoted_baseline_is_compact_labelled_and_immutable(directories: tuple[Path, Path]) -> None:
    runs, baselines = directories
    evidence = {"anchor_key": "a", "excerpt": "z" * 5_000}
    case = {"case_id": "lex-001", "question": "q", "passed": True, "retrieved_evidence": [evidence]}
    (runs / "run.json").write_text(json.dumps(_artifact([case])), encoding="utf-8")

    promoted = eval_manager.promote_to_baseline("run.json", "v0")

    saved = json.loads((baselines / promoted["name"]).read_text(encoding="utf-8"))
    assert promoted["name"] == "v0_retrieval_lexical.json"
    assert saved["baseline"]["label"] == "v0"
    assert saved["baseline"]["source_artifact"] == "run.json"
    assert len(saved["cases"][0]["retrieved_evidence"][0]["excerpt"]) <= 301
    assert [item["kind"] for item in eval_manager.list_artifacts()] == ["baseline", "run"]
    with pytest.raises(FileExistsError):
        eval_manager.promote_to_baseline("run.json", "v0")
    with pytest.raises(ValueError):
        eval_manager.promote_to_baseline("run.json", "../escape")


def test_comparison_lists_regressions_first_and_flags_corpus_changes(
    directories: tuple[Path, Path],
) -> None:
    runs, _ = directories
    baseline = _artifact(
        [
            {"case_id": "a", "question": "qa", "passed": True, "acceptable_rank": 1},
            {"case_id": "b", "question": "qb", "passed": False, "acceptable_rank": None},
            {"case_id": "c", "question": "qc", "passed": True, "acceptable_rank": 3},
            {"case_id": "gone", "question": "q", "passed": True, "acceptable_rank": 1},
        ]
    )
    candidate = _artifact(
        [
            {"case_id": "a", "question": "qa", "passed": False, "acceptable_rank": None},
            {"case_id": "b", "question": "qb", "passed": True, "acceptable_rank": 2},
            {"case_id": "c", "question": "qc", "passed": True, "acceptable_rank": 1},
            {"case_id": "new", "question": "q", "passed": True, "acceptable_rank": 1},
        ],
        strategy="semantic",
        source_versions=[{"source_key": "s", "source_version_id": "2", "content_hash": "other"}],
    )
    (runs / "base.json").write_text(json.dumps(baseline), encoding="utf-8")
    (runs / "cand.json").write_text(json.dumps(candidate), encoding="utf-8")

    comparison = eval_manager.compare_artifacts("base.json", "cand.json")

    assert [(c["case_id"], c["change"]) for c in comparison["changes"]] == [
        ("a", "regressed"),
        ("b", "improved"),
        ("c", "rank_changed"),
    ]
    assert comparison["added_case_ids"] == ["new"]
    assert comparison["removed_case_ids"] == ["gone"]
    assert any("Source versions differ" in warning for warning in comparison["warnings"])
    assert comparison["metrics"]["passed"] == {"baseline": 3, "candidate": 3, "delta": 0}


def test_background_run_reports_progress_result_and_failures(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_run_suite(_session: object, **kwargs: object) -> dict[str, object]:
        on_progress = kwargs["on_progress"]
        on_progress(1, 2)  # type: ignore[operator]
        if kwargs["strategy"] == "lexical_authority":
            raise RuntimeError("embeddings missing")
        return {"artifact_name": "run.json", "summary": {}, "cases": []}

    monkeypatch.setattr(eval_manager, "run_suite", fake_run_suite)
    monkeypatch.setattr(eval_manager, "_JOBS", {})

    def wait(job_id: str) -> dict[str, object]:
        for _ in range(100):
            job = eval_manager.get_run_job(job_id)
            if job["status"] != "running":
                return job
            time.sleep(0.01)
        raise AssertionError("job did not finish")

    ok = eval_manager.start_suite_run(
        suite_id="retrieval", strategy="lexical", session_factory=lambda: nullcontext()
    )
    assert wait(ok["job_id"])["result"] == {"artifact_name": "run.json", "summary": {}, "cases": []}

    failed = eval_manager.start_suite_run(
        suite_id="retrieval", strategy="lexical_authority", session_factory=lambda: nullcontext()
    )
    finished = wait(failed["job_id"])
    assert finished["status"] == "failed"
    assert "embeddings missing" in str(finished["error"])

    # Paid runs are validated before a thread starts, so nothing runs without consent.
    with pytest.raises(PermissionError):
        eval_manager.start_suite_run(suite_id="retrieval", strategy="semantic")


def test_answer_fixture_accepts_review_metadata_but_rejects_unknown_keys(tmp_path: Path) -> None:
    base = {
        "id": "a",
        "question": "q",
        "acceptable_anchor_keys": [],
        "expected_abstain": True,
        "human_review_criteria": ["c"],
    }
    valid = tmp_path / "valid.jsonl"
    valid.write_text(json.dumps({**base, "edge_case": "other-year", "topic": "t"}) + "\n")
    assert load_answer_eval_cases(valid)[0].case_id == "a"

    typo = tmp_path / "typo.jsonl"
    typo.write_text(json.dumps({**base, "expected_abstian": False}) + "\n")
    with pytest.raises(ValueError, match="required contract"):
        load_answer_eval_cases(typo)
