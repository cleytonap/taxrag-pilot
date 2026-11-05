"""Local developer services behind the Eval Manager API.

Fixture paths are deliberately a closed registry. This lets the local UI edit the two
versioned suites without becoming a general-purpose file browser or editor.
"""

from __future__ import annotations

import hashlib
import json
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
from taxrag.config import PROJECT_ROOT
from taxrag.embeddings import configured_embedding_provider
from taxrag.evals import (
    load_answer_eval_cases,
    load_retrieval_eval_cases,
    run_answer_evals,
    run_retrieval_evals,
)
from taxrag.models import Source, SourceVersion
from taxrag.retrieval import SUPPORTED_STRATEGIES, RetrievedChunk

SuiteId = Literal["retrieval", "answer"]
ProviderId = Literal["fake", "openai"]

SUITE_PATHS: dict[SuiteId, Path] = {
    "retrieval": PROJECT_ROOT / "docs/evals/lexical-retrieval-baseline.jsonl",
    "answer": PROJECT_ROOT / "docs/evals/cited-answer-development.jsonl",
}
ARTIFACTS_DIRECTORY = PROJECT_ROOT / "var/eval-runs"


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
    """List local run artifacts without exposing arbitrary paths."""
    if not ARTIFACTS_DIRECTORY.exists():
        return []
    records = []
    for path in ARTIFACTS_DIRECTORY.iterdir():
        if path.is_file() and path.suffix in {".json", ".txt"}:
            stat = path.stat()
            records.append(
                {
                    "name": path.name,
                    "size_bytes": stat.st_size,
                    "modified_at": stat.st_mtime,
                    "format": path.suffix.removeprefix("."),
                }
            )
    return sorted(records, key=lambda record: record["modified_at"], reverse=True)


def get_artifact(name: str) -> dict[str, str]:
    """Read one local run artifact after validating its simple file name."""
    if Path(name).name != name or Path(name).suffix not in {".json", ".txt"}:
        raise ValueError("Artifact name must be a local .json or .txt file name")
    path = ARTIFACTS_DIRECTORY / name
    if not path.is_file():
        raise FileNotFoundError(name)
    return {"name": name, "content": path.read_text(encoding="utf-8")}


def run_suite(
    session: Session,
    *,
    suite_id: str,
    strategy: str,
    provider_id: str = "fake",
    confirm_paid_request: bool = False,
) -> dict[str, Any]:
    """Run one closed evaluation suite and persist a reproducible local JSON artifact."""
    path = _suite_path(suite_id)
    if strategy not in SUPPORTED_STRATEGIES:
        raise ValueError(f"Unknown retrieval strategy: {strategy}")
    if suite_id == "answer" and provider_id not in {"fake", "openai"}:
        raise ValueError(f"Unknown answer provider: {provider_id}")
    if suite_id == "retrieval" and provider_id != "fake":
        raise ValueError("The retrieval suite does not use an answer provider")
    if (provider_id == "openai" or strategy in {"semantic", "hybrid_rrf"}) and not confirm_paid_request:
        raise PermissionError("OpenAI requests require confirm_paid_request=true")

    fixture_text = path.read_text(encoding="utf-8")
    fixture_hash = hashlib.sha256(fixture_text.encode()).hexdigest()
    started_at = datetime.now(UTC)
    requires_embeddings = strategy in {"semantic", "hybrid_rrf"}
    embedding_provider = configured_embedding_provider() if requires_embeddings else None

    if suite_id == "retrieval":
        cases = load_retrieval_eval_cases(path)
        results = run_retrieval_evals(
            session, cases, strategy=strategy, embedding_provider=embedding_provider  # type: ignore[arg-type]
        )
        required = [result for result in results if result.expected_recall_at_three]
        preferred = [result for result in results if result.preferred_anchor_keys]
        passed = sum(result.passed_at_three for result in required)
        preferred_passed = sum(result.preferred_at_three is True for result in preferred)
        summary = {
            "case_count": len(results),
            "passed": passed,
            "recall_at_three": passed / len(required) if required else None,
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
        cases = load_answer_eval_cases(path)
        provider = DeterministicAnswerProvider() if provider_id == "fake" else configured_answer_provider()
        results = run_answer_evals(
            session,
            cases,
            provider,
            strategy=strategy,  # type: ignore[arg-type]
            embedding_provider=embedding_provider,
        )
        passed = sum(result.passed_structural_checks for result in results)
        summary = {"case_count": len(results), "passed": passed, "structural_pass_rate": passed / len(results)}
        case_results = [
            {
                "case_id": result.case_id,
                "question": case.question,
                "passed": result.passed_structural_checks,
                "expected_abstain": result.expected_abstain,
                "actual_outcome": result.answer.outcome,
                "acceptable_anchor_keys": list(result.acceptable_anchor_keys),
                "cited_anchor_keys": list(result.cited_anchor_keys),
                "cited_acceptable_anchor_keys": list(result.cited_acceptable_anchor_keys),
                "human_review_criteria": list(result.human_review_criteria),
                "answer": result.answer.to_dict(),
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
        "provider": provider_id if suite_id == "answer" else None,
        "embedding_model": embedding_provider.model if embedding_provider else None,
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
    return {"artifact_name": artifact_name, "summary": summary, "cases": case_results}


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
    answer = answer_question(
        session,
        question,
        provider,
        strategy=strategy,  # type: ignore[arg-type]
        embedding_provider=configured_embedding_provider() if requires_embeddings else None,
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
        "label": "Retrieval baseline" if suite_id == "retrieval" else "Cited-answer development",
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
    cases = load_retrieval_eval_cases(path) if suite_id == "retrieval" else load_answer_eval_cases(path)
    return [asdict(case) for case in cases]


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
