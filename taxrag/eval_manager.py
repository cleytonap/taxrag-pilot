"""Local developer services behind the Eval Manager API.

Fixture paths are deliberately a closed registry. This lets the local UI edit the two
versioned suites without becoming a general-purpose file browser or editor.
"""

from __future__ import annotations

import hashlib
import json
import re
import threading
from collections.abc import Callable
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from taxrag.answers import (
    AnswerDraft,
    AnswerValidationError,
    DeterministicAnswerProvider,
    answer_question,
    configured_answer_provider,
)
from taxrag.config import PROJECT_ROOT, settings
from taxrag.embeddings import configured_embedding_provider, require_complete_embeddings
from taxrag.evals import (
    load_answer_eval_cases,
    load_generation_eval_cases,
    load_retrieval_eval_cases,
    run_answer_evals,
    run_generation_evals,
    run_retrieval_evals,
)
from taxrag.models import Source, SourceVersion
from taxrag.retrieval import SUPPORTED_STRATEGIES, RetrievedChunk

SuiteId = Literal["retrieval", "generation", "answer"]
ProviderId = Literal["fake", "openai"]

# Three layers (see docs/evals/README.md): retrieval only, generation only (fixed evidence),
# and end-to-end. The "answer" id is kept for the e2e suite so V0 artifacts stay comparable.
SUITE_PATHS: dict[SuiteId, Path] = {
    "retrieval": PROJECT_ROOT / "docs/evals/lexical-retrieval-baseline.jsonl",
    "generation": PROJECT_ROOT / "docs/evals/answer-generation.jsonl",
    "answer": PROJECT_ROOT / "docs/evals/cited-answer-development.jsonl",
}
SUITE_LABELS = {
    "retrieval": "Retrieval (chunks only)",
    "generation": "Answer generation (fixed evidence)",
    "answer": "End-to-end answers (retrieval + generation)",
}
ARTIFACTS_DIRECTORY = PROJECT_ROOT / "var/eval-runs"
# Promoted baselines are Git-tracked so a reference result survives `var/` cleanup and is shared.
BASELINES_DIRECTORY = PROJECT_ROOT / "docs/evals/baselines"
BASELINE_EXCERPT_CHARACTERS = 300
BASELINE_LABEL = re.compile(r"^[a-z0-9][a-z0-9.-]{0,39}$")


def list_suites() -> list[dict[str, Any]]:
    """Return the known suite summaries and their parsed, validated cases."""
    return [_suite_summary(suite_id) for suite_id in SUITE_PATHS]


def get_fixture(suite_id: str) -> dict[str, Any]:
    """Return a known fixture's source text and parsed cases for local editing."""
    path = _suite_path(suite_id)
    content = path.read_text(encoding="utf-8")
    return {
        "id": suite_id,
        "path": str(path.relative_to(PROJECT_ROOT)),
        "content": content,
        "sha256": hashlib.sha256(content.encode()).hexdigest(),
        "cases": _load_cases(suite_id, path),
    }


def save_fixture(suite_id: str, content: str) -> dict[str, Any]:
    """Validate then replace one known local fixture, preserving Git as its review layer."""
    if not content.strip():
        raise ValueError("Fixture content must not be blank")
    path = _suite_path(suite_id)
    _validate_fixture_text(suite_id, content)
    path.write_text(content.rstrip() + "\n", encoding="utf-8")
    return get_fixture(suite_id)


def list_artifacts() -> list[dict[str, Any]]:
    """List local run artifacts and promoted baselines without exposing arbitrary paths."""
    records = []
    for kind, directory in (("run", ARTIFACTS_DIRECTORY), ("baseline", BASELINES_DIRECTORY)):
        if not directory.exists():
            continue
        for path in directory.iterdir():
            if path.is_file() and path.suffix in {".json", ".txt"}:
                stat = path.stat()
                records.append(
                    {
                        "name": path.name,
                        "kind": kind,
                        "size_bytes": stat.st_size,
                        "modified_at": stat.st_mtime,
                        "format": path.suffix.removeprefix("."),
                    }
                )
    return sorted(records, key=lambda record: record["modified_at"], reverse=True)


def get_artifact(name: str) -> dict[str, str]:
    """Read one local run artifact or baseline after validating its simple file name."""
    return {"name": name, "content": _artifact_path(name).read_text(encoding="utf-8")}


def _artifact_path(name: str) -> Path:
    """Resolve a bare artifact file name inside the run or baseline directory only."""
    if Path(name).name != name or Path(name).suffix not in {".json", ".txt"}:
        raise ValueError("Artifact name must be a local .json or .txt file name")
    for directory in (ARTIFACTS_DIRECTORY, BASELINES_DIRECTORY):
        path = directory / name
        if path.is_file():
            return path
    raise FileNotFoundError(name)


def run_suite(
    session: Session,
    *,
    suite_id: str,
    strategy: str,
    provider_id: str = "fake",
    confirm_paid_request: bool = False,
    on_progress: Callable[[int, int], None] | None = None,
) -> dict[str, Any]:
    """Run one closed evaluation suite and persist a reproducible local JSON artifact."""
    path = _validate_run_request(suite_id, strategy, provider_id, confirm_paid_request)

    fixture_text = path.read_text(encoding="utf-8")
    fixture_hash = hashlib.sha256(fixture_text.encode()).hexdigest()
    metadata = _case_metadata(fixture_text)
    started_at = datetime.now(UTC)
    if suite_id == "generation":
        strategy = "fixed_context"  # evidence comes from each case, not from a retriever
    requires_embeddings = strategy in {"semantic", "hybrid_rrf"}
    embedding_provider = configured_embedding_provider() if requires_embeddings else None
    if embedding_provider is not None:
        # A partially embedded corpus would silently produce a low, non-comparable score.
        require_complete_embeddings(session, embedding_provider.model, embedding_provider.dimensions)

    if suite_id == "retrieval":
        cases = load_retrieval_eval_cases(path)
        results = run_retrieval_evals(
            session,
            cases,
            strategy=strategy,  # type: ignore[arg-type]
            embedding_provider=embedding_provider,
            on_progress=on_progress,
        )
        required = [result for result in results if result.expected_recall_at_three]
        preferred = [result for result in results if result.preferred_anchor_keys]
        passed = sum(result.passed_at_three for result in required)
        preferred_passed = sum(result.preferred_at_three is True for result in preferred)
        ranks = [result.acceptable_rank for result in required]
        summary = {
            "case_count": len(results),
            "passed": passed,
            "recall_at_three": passed / len(required) if required else None,
            "recall_at_one": _recall(ranks, 1),
            "recall_at_five": _recall(ranks, 5),
            "recall_at_ten": _recall(ranks, 10),
            "mrr_at_ten": sum(1 / rank for rank in ranks if rank) / len(ranks) if ranks else None,
            "preferred_case_count": len(preferred),
            "preferred_passed": preferred_passed,
            "preferred_recall_at_three": (
                preferred_passed / len(preferred) if preferred else None
            ),
        }
        case_results = [
            {
                "case_id": result.case_id,
                "question": case.question,
                **metadata.get(result.case_id, {}),
                "passed": result.outcome_matches_expectation,
                "acceptable_anchor_keys": list(result.acceptable_anchor_keys),
                "preferred_anchor_keys": list(result.preferred_anchor_keys),
                "acceptable_rank": result.acceptable_rank,
                "preferred_rank": result.preferred_rank,
                "expected_recall_at_three": result.expected_recall_at_three,
                "retrieved_evidence": [asdict(item) for item in result.retrieved_evidence],
            }
            for case, result in zip(cases, results, strict=True)
        ]
    else:
        provider = DeterministicAnswerProvider() if provider_id == "fake" else configured_answer_provider()
        if suite_id == "generation":
            cases = load_generation_eval_cases(path)
            results = run_generation_evals(session, cases, provider, on_progress=on_progress)
        else:
            cases = load_answer_eval_cases(path)
            results = run_answer_evals(
                session,
                cases,
                provider,
                strategy=strategy,  # type: ignore[arg-type]
                embedding_provider=embedding_provider,
                on_progress=on_progress,
            )
        passed = sum(result.passed_structural_checks for result in results)
        abstain_cases = [result for result in results if result.expected_abstain]
        answer_cases = [result for result in results if not result.expected_abstain]
        summary = {
            "case_count": len(results),
            "passed": passed,
            "structural_pass_rate": passed / len(results),
            "abstention_case_count": len(abstain_cases),
            "abstention_passed": sum(result.passed_structural_checks for result in abstain_cases),
            "answerable_case_count": len(answer_cases),
            "answerable_passed": sum(result.passed_structural_checks for result in answer_cases),
            # Shown an answer where the case requires abstention: the most harmful failure.
            "unsafe_answers": sum(result.unsafe for result in results),
            "validation_rejections": sum(
                result.answer.outcome == "provider_rejected" for result in results
            ),
        }
        case_results = [
            {
                "case_id": result.case_id,
                "question": case.question,
                **metadata.get(result.case_id, {}),
                "passed": result.passed_structural_checks,
                "expected_abstain": result.expected_abstain,
                "actual_outcome": result.answer.outcome,
                "acceptable_anchor_keys": list(result.acceptable_anchor_keys),
                "cited_anchor_keys": list(result.cited_anchor_keys),
                "cited_acceptable_anchor_keys": list(result.cited_acceptable_anchor_keys),
                "human_review_criteria": list(result.human_review_criteria),
                "answer": result.answer.to_dict(),
                "context_anchor_keys": list(getattr(case, "context_anchor_keys", ())),
                "retrieved_evidence": [asdict(item) for item in result.trace.retrieved_evidence],
                "validation_error": result.trace.validation_error,
            }
            for case, result in zip(cases, results, strict=True)
        ]

    finished_at = datetime.now(UTC)
    source_versions = session.execute(
        select(Source.source_key, SourceVersion.id, SourceVersion.content_hash)
        .join(SourceVersion, SourceVersion.source_id == Source.id)
        .where(SourceVersion.processing_status == "processed", Source.is_active.is_(True))
        .order_by(Source.source_key, SourceVersion.fetched_at.desc())
    ).all()
    run_id = uuid4().hex[:12]
    artifact = {
        "run_id": run_id,
        "suite_id": suite_id,
        "suite_path": str(path.relative_to(PROJECT_ROOT)),
        "fixture_sha256": fixture_hash,
        "started_at": started_at.isoformat(),
        "finished_at": finished_at.isoformat(),
        "strategy": strategy,
        "provider": provider_id if suite_id in {"answer", "generation"} else None,
        "embedding_model": embedding_provider.model if embedding_provider else None,
        "answer_model": settings.answer_model if suite_id != "retrieval" and provider_id == "openai" else None,
        "answer_top_k": settings.answer_top_k if suite_id == "answer" else None,
        "summary": summary,
        "source_versions": [
            {"source_key": row.source_key, "source_version_id": str(row.id), "content_hash": row.content_hash}
            for row in source_versions
        ],
        "cases": case_results,
    }
    ARTIFACTS_DIRECTORY.mkdir(parents=True, exist_ok=True)
    stamp = finished_at.strftime("%Y-%m-%dT%H%M%SZ")
    artifact_name = f"{stamp}_{suite_id}_{run_id}.json"
    destination = ARTIFACTS_DIRECTORY / artifact_name
    temporary = destination.with_suffix(".tmp")
    temporary.write_text(json.dumps(artifact, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(destination)
    if on_progress:
        on_progress(len(case_results), len(case_results))
    return {"artifact_name": artifact_name, "summary": summary, "cases": case_results}


def _validate_run_request(
    suite_id: str, strategy: str, provider_id: str, confirm_paid_request: bool
) -> Path:
    """Reject invalid or unconfirmed paid runs before any work or background job starts."""
    path = _suite_path(suite_id)
    if strategy not in SUPPORTED_STRATEGIES:
        raise ValueError(f"Unknown retrieval strategy: {strategy}")
    if suite_id in {"answer", "generation"} and provider_id not in {"fake", "openai"}:
        raise ValueError(f"Unknown answer provider: {provider_id}")
    if suite_id == "retrieval" and provider_id != "fake":
        raise ValueError("The retrieval suite does not use an answer provider")
    uses_embeddings = suite_id != "generation" and strategy in {"semantic", "hybrid_rrf"}
    if (provider_id == "openai" or uses_embeddings) and not confirm_paid_request:
        raise PermissionError("OpenAI requests require confirm_paid_request=true")
    return path


def _recall(ranks: list[int | None], k: int) -> float | None:
    """Share of cases whose first acceptable anchor is within the top k."""
    return sum(rank is not None and rank <= k for rank in ranks) / len(ranks) if ranks else None


def _case_metadata(fixture_text: str) -> dict[str, dict[str, Any]]:
    """Carry review-only fixture fields (topic, edge_case) into run artifacts for slicing."""
    metadata: dict[str, dict[str, Any]] = {}
    for line in fixture_text.splitlines():
        if line.strip():
            record = json.loads(line)
            metadata[record["id"]] = {
                key: record[key] for key in ("topic", "edge_case") if key in record
            }
    return metadata


# --- Background runs -------------------------------------------------------------------------
# Suite runs take from ~30 seconds (lexical) to several minutes (OpenAI answers), longer than a
# browser or proxy should hold one HTTP request open. The UI starts a job and polls its progress.
# Jobs live in this local API process only; the artifact on disk is the durable record.
_JOBS: dict[str, dict[str, Any]] = {}
_JOBS_LOCK = threading.Lock()


def start_suite_run(
    *,
    suite_id: str,
    strategy: str,
    provider_id: str = "fake",
    confirm_paid_request: bool = False,
    session_factory: Callable[[], Any] | None = None,
) -> dict[str, Any]:
    """Validate a run request, start it in a background thread, and return its job record."""
    _validate_run_request(suite_id, strategy, provider_id, confirm_paid_request)
    with _JOBS_LOCK:
        # One run at a time avoids accidental duplicate paid runs and database contention.
        if any(job["status"] == "running" for job in _JOBS.values()):
            raise RuntimeError("Another suite run is still in progress; wait for it to finish.")
        job_id = uuid4().hex[:12]
        _JOBS[job_id] = {
            "job_id": job_id,
            "suite_id": suite_id,
            "strategy": strategy,
            "provider": provider_id,
            "status": "running",
            "completed": 0,
            "total": None,
            "started_at": datetime.now(UTC).isoformat(),
            "result": None,
            "error": None,
        }
    if session_factory is None:
        from taxrag.database import SessionLocal

        session_factory = SessionLocal

    def update(**changes: Any) -> None:
        with _JOBS_LOCK:
            _JOBS[job_id].update(changes)

    def work() -> None:
        try:
            with session_factory() as session:
                result = run_suite(
                    session,
                    suite_id=suite_id,
                    strategy=strategy,
                    provider_id=provider_id,
                    confirm_paid_request=confirm_paid_request,
                    on_progress=lambda done, total: update(completed=done, total=total),
                )
            update(status="succeeded", result=result)
        except Exception as error:  # noqa: BLE001 - reported to the local developer, not swallowed
            update(status="failed", error=f"{type(error).__name__}: {error}")

    threading.Thread(target=work, name=f"eval-run-{job_id}", daemon=True).start()
    return get_run_job(job_id)


def get_run_job(job_id: str) -> dict[str, Any]:
    """Return a snapshot of one background run, including its result once finished."""
    with _JOBS_LOCK:
        if job_id not in _JOBS:
            raise KeyError(f"Unknown run job: {job_id}")
        return dict(_JOBS[job_id])


# --- Baselines and comparison ----------------------------------------------------------------


def promote_to_baseline(artifact_name: str, label: str) -> dict[str, Any]:
    """Copy a run artifact into the Git-tracked baselines directory as an immutable reference.

    Excerpts are shortened: a baseline must record *what* was retrieved (chunk ids, anchors,
    ranks, source-version hashes), while full chunk text stays reproducible from the source
    version. This keeps committed baselines ~20x smaller than local run artifacts.
    """
    if not BASELINE_LABEL.match(label):
        raise ValueError("Baseline label must be 1-40 lowercase letters, digits, dots or dashes")
    source_path = ARTIFACTS_DIRECTORY / artifact_name
    if Path(artifact_name).name != artifact_name or not source_path.is_file():
        raise FileNotFoundError(artifact_name)
    artifact = json.loads(source_path.read_text(encoding="utf-8"))
    parts = [label, artifact["suite_id"], artifact["strategy"]]
    if artifact.get("provider"):
        parts.append(artifact["provider"])
    name = "_".join(parts) + ".json"
    destination = BASELINES_DIRECTORY / name
    if destination.exists():
        raise FileExistsError(
            f"Baseline {name} already exists. Baselines are immutable; choose a new label."
        )
    for case in artifact["cases"]:
        for evidence in case.get("retrieved_evidence", []):
            excerpt = evidence.get("excerpt") or ""
            if len(excerpt) > BASELINE_EXCERPT_CHARACTERS:
                evidence["excerpt"] = excerpt[:BASELINE_EXCERPT_CHARACTERS] + "…"
    artifact["baseline"] = {
        "label": label,
        "promoted_at": datetime.now(UTC).isoformat(),
        "source_artifact": artifact_name,
        "excerpts_truncated_to": BASELINE_EXCERPT_CHARACTERS,
    }
    BASELINES_DIRECTORY.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(artifact, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    path = destination.relative_to(PROJECT_ROOT) if destination.is_relative_to(PROJECT_ROOT) else destination
    return {"name": name, "path": str(path)}


def compare_artifacts(baseline_name: str, candidate_name: str) -> dict[str, Any]:
    """Compare two runs of the same suite: metric deltas and per-case pass/rank changes.

    Warnings flag differences that make a comparison less clean (fixture, sources, models);
    they do not block it, because comparing strategies on the same fixture is the main use.
    """
    baseline = json.loads(get_artifact(baseline_name)["content"])
    candidate = json.loads(get_artifact(candidate_name)["content"])
    if baseline["suite_id"] != candidate["suite_id"]:
        raise ValueError("Only runs of the same suite can be compared")
    warnings = []
    if baseline["fixture_sha256"] != candidate["fixture_sha256"]:
        warnings.append("Fixture changed between runs; only shared case ids are compared.")
    if {v["content_hash"] for v in baseline["source_versions"]} != {
        v["content_hash"] for v in candidate["source_versions"]
    }:
        warnings.append("Source versions differ; score changes may come from the corpus.")
    for key in ("embedding_model", "answer_model", "provider", "answer_top_k"):
        if baseline.get(key) != candidate.get(key):
            warnings.append(f"{key} differs: {baseline.get(key)} -> {candidate.get(key)}")

    metrics = {}
    for key, value in baseline["summary"].items():
        other = candidate["summary"].get(key)
        if isinstance(value, int | float) and isinstance(other, int | float):
            metrics[key] = {"baseline": value, "candidate": other, "delta": other - value}

    baseline_cases = {case["case_id"]: case for case in baseline["cases"]}
    candidate_cases = {case["case_id"]: case for case in candidate["cases"]}
    changes = []
    for case_id, old in baseline_cases.items():
        new = candidate_cases.get(case_id)
        if new is None:
            continue
        if old["passed"] and not new["passed"]:
            change = "regressed"
        elif not old["passed"] and new["passed"]:
            change = "improved"
        elif old.get("acceptable_rank") != new.get("acceptable_rank"):
            change = "rank_changed"
        else:
            continue
        changes.append(
            {
                "case_id": case_id,
                "question": new["question"],
                "change": change,
                "baseline_passed": old["passed"],
                "candidate_passed": new["passed"],
                "baseline_rank": old.get("acceptable_rank"),
                "candidate_rank": new.get("acceptable_rank"),
                "baseline_outcome": old.get("actual_outcome"),
                "candidate_outcome": new.get("actual_outcome"),
            }
        )
    order = {"regressed": 0, "improved": 1, "rank_changed": 2}
    changes.sort(key=lambda item: (order[item["change"]], item["case_id"]))
    return {
        "baseline": baseline_name,
        "candidate": candidate_name,
        "suite_id": baseline["suite_id"],
        "strategies": [baseline["strategy"], candidate["strategy"]],
        "warnings": warnings,
        "metrics": metrics,
        "added_case_ids": sorted(set(candidate_cases) - set(baseline_cases)),
        "removed_case_ids": sorted(set(baseline_cases) - set(candidate_cases)),
        "changes": changes,
    }


def debug_answer(
    session: Session,
    *,
    question: str,
    strategy: str,
    provider_id: str,
    confirm_paid_request: bool,
) -> dict[str, Any]:
    """Run one explicit local diagnostic question and return safe output plus RCA facts."""
    if not question.strip():
        raise ValueError("Question must not be blank")
    if len(question) > 4_000:
        raise ValueError("Question must be at most 4000 characters")
    if strategy not in SUPPORTED_STRATEGIES:
        raise ValueError(f"Unknown retrieval strategy: {strategy}")
    if provider_id not in {"fake", "openai"}:
        raise ValueError(f"Unknown answer provider: {provider_id}")
    if (provider_id == "openai" or strategy in {"semantic", "hybrid_rrf"}) and not confirm_paid_request:
        raise PermissionError("OpenAI requests require confirm_paid_request=true")

    chunks: list[RetrievedChunk] = []
    rejected_draft: AnswerDraft | None = None
    validation_error: str | None = None

    def record_chunks(retrieved: list[RetrievedChunk]) -> None:
        chunks.extend(retrieved)

    def record_rejection(
        draft: AnswerDraft | None, error: AnswerValidationError, _chunks: list[RetrievedChunk]
    ) -> None:
        nonlocal rejected_draft, validation_error
        rejected_draft = draft
        validation_error = str(error)

    provider = DeterministicAnswerProvider() if provider_id == "fake" else configured_answer_provider()
    requires_embeddings = strategy in {"semantic", "hybrid_rrf"}
    embedding_provider = configured_embedding_provider() if requires_embeddings else None
    if embedding_provider is not None:
        require_complete_embeddings(session, embedding_provider.model, embedding_provider.dimensions)
    answer = answer_question(
        session,
        question,
        provider,
        strategy=strategy,  # type: ignore[arg-type]
        embedding_provider=embedding_provider,
        on_retrieved_chunks=record_chunks,
        on_validation_failure=record_rejection,
    )
    return {
        "answer": answer.to_dict(),
        "provider": provider_id,
        "retrieved_chunks": [_chunk_to_dict(index, chunk) for index, chunk in enumerate(chunks, 1)],
        "diagnostics": {
            "validation_error": validation_error,
            "rejected_draft": _draft_to_dict(rejected_draft),
        },
    }


def _suite_summary(suite_id: SuiteId) -> dict[str, Any]:
    """Build a compact display summary for one fixture suite."""
    fixture = get_fixture(suite_id)
    return {
        "id": suite_id,
        "label": SUITE_LABELS[suite_id],
        "path": fixture["path"],
        "case_count": len(fixture["cases"]),
        "cases": fixture["cases"],
    }


def _suite_path(suite_id: str) -> Path:
    """Resolve a suite id through the closed fixture registry."""
    try:
        return SUITE_PATHS[suite_id]  # type: ignore[index]
    except KeyError as error:
        raise KeyError(f"Unknown suite: {suite_id}") from error


def _load_cases(suite_id: str, path: Path) -> list[dict[str, Any]]:
    """Load a fixture through its existing contract and serialize its immutable cases."""
    loaders = {
        "retrieval": load_retrieval_eval_cases,
        "generation": load_generation_eval_cases,
        "answer": load_answer_eval_cases,
    }
    return [asdict(case) for case in loaders[suite_id](path)]


def _validate_fixture_text(suite_id: str, content: str) -> None:
    """Validate unsaved JSONL through the exact parser used by command-line evaluations."""
    records = []
    for line_number, line in enumerate(content.splitlines(), 1):
        if not line.strip():
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError as error:
            raise ValueError(f"Fixture line {line_number} is not valid JSON: {error.msg}") from error
    if not records:
        raise ValueError("Fixture contains no JSONL records")
    temporary = PROJECT_ROOT / "var" / ".eval-manager-validation.jsonl"
    temporary.parent.mkdir(parents=True, exist_ok=True)
    try:
        temporary.write_text(content, encoding="utf-8")
        _load_cases(suite_id, temporary)
    finally:
        temporary.unlink(missing_ok=True)


def _chunk_to_dict(rank: int, chunk: RetrievedChunk) -> dict[str, Any]:
    """Serialize all retrieval evidence that a developer needs for local RCA."""
    return {
        "rank": rank,
        "chunk_id": chunk.chunk_id,
        "anchor_key": chunk.anchor_key,
        "anchor_title": chunk.anchor_title,
        "source_title": chunk.source_title,
        "canonical_url": chunk.canonical_url,
        "source_link": chunk.source_link,
        "page_start": chunk.page_start,
        "authority_level": chunk.authority_level,
        "strategy": chunk.strategy,
        "score": chunk.score,
        "lexical_score": chunk.lexical_score,
        "semantic_score": chunk.semantic_score,
        "lexical_rank": chunk.lexical_rank,
        "semantic_rank": chunk.semantic_rank,
        "chunk_text": chunk.chunk_text,
    }


def _draft_to_dict(draft: AnswerDraft | None) -> dict[str, Any] | None:
    """Serialize untrusted output only inside the local diagnostic boundary."""
    if draft is None:
        return None
    return {
        "claims": [
            {"text": claim.text, "citations": [{"chunk_id": item.chunk_id} for item in claim.citations]}
            for claim in draft.claims
        ],
        "abstain": draft.abstain,
        "limitation": draft.limitation,
        "clarification_question": draft.clarification_question,
    }
