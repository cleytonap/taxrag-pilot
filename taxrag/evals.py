"""Executable retrieval evaluation fixtures and baseline metrics."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy.orm import Session

from taxrag.retrieval import search_chunks


@dataclass(frozen=True)
class RetrievalEvalCase:
    """A question with acceptable and optionally preferred citation anchors."""

    case_id: str
    question: str
    acceptable_anchor_keys: tuple[str, ...]
    preferred_anchor_keys: tuple[str, ...] = ()
    expected_recall_at_three: bool = True


@dataclass(frozen=True)
class RetrievalEvalResult:
    """The acceptable-support and preferred-source rank outcomes for one case."""

    case_id: str
    acceptable_anchor_keys: tuple[str, ...]
    preferred_anchor_keys: tuple[str, ...]
    acceptable_rank: int | None
    preferred_rank: int | None
    expected_recall_at_three: bool

    @property
    def passed_at_three(self) -> bool:
        """Return whether any acceptable support anchor appeared in the first three results."""
        return self.acceptable_rank is not None and self.acceptable_rank <= 3

    @property
    def preferred_at_three(self) -> bool | None:
        """Return preferred-source recall when the case declares a source preference."""
        if not self.preferred_anchor_keys:
            return None
        return self.preferred_rank is not None and self.preferred_rank <= 3

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
        required = {"id", "question", "acceptable_anchor_keys"}
        if not required <= record.keys():
            raise ValueError(f"Evaluation fixture line {line_number} is missing a required field")
        acceptable = _load_anchor_keys(record["acceptable_anchor_keys"], line_number, "acceptable")
        preferred = _load_anchor_keys(
            record.get("preferred_anchor_keys", []), line_number, "preferred", allow_empty=True
        )
        if not set(preferred) <= set(acceptable):
            raise ValueError(
                f"Evaluation fixture line {line_number} has preferred anchors outside "
                "acceptable_anchor_keys"
            )
        expected_recall_at_three = record.get("expected_recall_at_three", True)
        if not isinstance(expected_recall_at_three, bool):
            raise TypeError(f"Evaluation fixture line {line_number} has an invalid expectation flag")
        cases.append(
            RetrievalEvalCase(
                case_id=record["id"],
                question=record["question"],
                acceptable_anchor_keys=acceptable,
                preferred_anchor_keys=preferred,
                expected_recall_at_three=expected_recall_at_three,
            )
        )
    if not cases:
        raise ValueError("Evaluation fixture contains no cases")
    return cases


def _load_anchor_keys(
    value: object, line_number: int, label: str, *, allow_empty: bool = False
) -> tuple[str, ...]:
    """Validate a duplicate-free fixture anchor list, requiring content unless optional."""
    if (
        not isinstance(value, list)
        or (not value and not allow_empty)
        or not all(isinstance(item, str) and item for item in value)
    ):
        raise TypeError(
            f"Evaluation fixture line {line_number} has invalid {label}_anchor_keys"
        )
    if len(set(value)) != len(value):
        raise ValueError(
            f"Evaluation fixture line {line_number} has duplicate {label}_anchor_keys"
        )
    return tuple(value)


def run_retrieval_evals(session: Session, cases: list[RetrievalEvalCase]) -> list[RetrievalEvalResult]:
    """Measure acceptable support and preferred-source ranks using the lexical retriever."""
    results = []
    for case in cases:
        matches = search_chunks(session, case.question, limit=3)
        acceptable_rank = _first_anchor_rank(matches, case.acceptable_anchor_keys)
        preferred_rank = _first_anchor_rank(matches, case.preferred_anchor_keys)
        results.append(
            RetrievalEvalResult(
                case_id=case.case_id,
                acceptable_anchor_keys=case.acceptable_anchor_keys,
                preferred_anchor_keys=case.preferred_anchor_keys,
                acceptable_rank=acceptable_rank,
                preferred_rank=preferred_rank,
                expected_recall_at_three=case.expected_recall_at_three,
            )
        )
    return results


def _first_anchor_rank(matches: list[object], expected_anchors: tuple[str, ...]) -> int | None:
    """Return the first result rank matching one anchor in an explicitly allowed set."""
    return next(
        (
            rank
            for rank, match in enumerate(matches, start=1)
            if getattr(match, "anchor_key", None) in expected_anchors
        ),
        None,
    )
