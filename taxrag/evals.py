"""Executable retrieval evaluation fixtures and baseline metrics."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy.orm import Session

from taxrag.retrieval import search_chunks


@dataclass(frozen=True)
class RetrievalEvalCase:
    """A question paired with the citation anchor retrieval is expected to return."""

    case_id: str
    question: str
    expected_anchor_key: str
    expected_recall_at_three: bool = True


@dataclass(frozen=True)
class RetrievalEvalResult:
    """The rank outcome for one retrieval evaluation case."""

    case_id: str
    expected_anchor_key: str
    actual_rank: int | None
    expected_recall_at_three: bool

    @property
    def passed_at_three(self) -> bool:
        """Return whether the expected anchor appeared in the first three results."""
        return self.actual_rank is not None and self.actual_rank <= 3

    @property
    def outcome_matches_expectation(self) -> bool:
        """Return whether the retrieval result matches the case's required or known-gap behavior."""
        return self.passed_at_three is self.expected_recall_at_three


def load_retrieval_eval_cases(path: Path) -> list[RetrievalEvalCase]:
    """Load a versioned JSONL fixture and validate its minimal retrieval contract."""
    cases = []
    for line_number, line in enumerate(path.read_text().splitlines(), start=1):
        if not line.strip():
            continue
        record = json.loads(line)
        required = {"id", "question", "expected_anchor_key"}
        if not required <= record.keys():
            raise ValueError(f"Evaluation fixture line {line_number} is missing a required field")
        expected_recall_at_three = record.get("expected_recall_at_three", True)
        if not isinstance(expected_recall_at_three, bool):
            raise TypeError(f"Evaluation fixture line {line_number} has an invalid expectation flag")
        cases.append(
            RetrievalEvalCase(
                case_id=record["id"],
                question=record["question"],
                expected_anchor_key=record["expected_anchor_key"],
                expected_recall_at_three=expected_recall_at_three,
            )
        )
    if not cases:
        raise ValueError("Evaluation fixture contains no cases")
    return cases


def run_retrieval_evals(session: Session, cases: list[RetrievalEvalCase]) -> list[RetrievalEvalResult]:
    """Measure the rank of each expected anchor using the current lexical retriever."""
    results = []
    for case in cases:
        matches = search_chunks(session, case.question, limit=3)
        actual_rank = next(
            (rank for rank, match in enumerate(matches, start=1) if match.anchor_key == case.expected_anchor_key),
            None,
        )
        results.append(
            RetrievalEvalResult(
                case_id=case.case_id,
                expected_anchor_key=case.expected_anchor_key,
                actual_rank=actual_rank,
                expected_recall_at_three=case.expected_recall_at_three,
            )
        )
    return results
