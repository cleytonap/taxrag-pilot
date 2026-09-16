"""Executable retrieval evaluation fixtures and baseline metrics."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy.orm import Session

from taxrag.answers import AnswerProvider, CitedAnswer, answer_question
from taxrag.embeddings import EmbeddingProvider
from taxrag.retrieval import RetrievalStrategy, search_chunks


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


@dataclass(frozen=True)
class AnswerEvalCase:
    """A human-reviewed answer expectation with only deterministic checks automated."""

    case_id: str
    question: str
    required_anchor_keys: tuple[str, ...]
    expected_abstain: bool
    human_review_criteria: tuple[str, ...]


@dataclass(frozen=True)
class AnswerEvalResult:
    """Structural answer outcome plus the human rubric that still needs review."""

    case_id: str
    answer: CitedAnswer
    required_anchor_keys: tuple[str, ...]
    cited_anchor_keys: tuple[str, ...]
    missing_required_anchor_keys: tuple[str, ...]
    expected_abstain: bool
    human_review_criteria: tuple[str, ...]

    @property
    def abstention_matches(self) -> bool:
        """Return whether the safe-abstention outcome matches the fixture expectation."""
        return self.answer.abstain is self.expected_abstain

    @property
    def required_anchors_present(self) -> bool:
        """Return whether every fixture-required source anchor occurs in a validated citation."""
        return not self.missing_required_anchor_keys

    @property
    def passed_structural_checks(self) -> bool:
        """Return the narrow automated result, excluding human judgment of prose quality."""
        return self.abstention_matches and self.required_anchors_present


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


def load_answer_eval_cases(path: Path) -> list[AnswerEvalCase]:
    """Load a human-authored JSONL answer fixture with a deliberately narrow contract."""
    cases = []
    for line_number, line in enumerate(path.read_text().splitlines(), start=1):
        if not line.strip():
            continue
        record = json.loads(line)
        required = {
            "id",
            "question",
            "required_anchor_keys",
            "expected_abstain",
            "human_review_criteria",
        }
        if set(record) != required:
            raise ValueError(
                f"Answer evaluation fixture line {line_number} does not match the required contract"
            )
        case_id, question = record["id"], record["question"]
        if not isinstance(case_id, str) or not case_id or not isinstance(question, str) or not question:
            raise TypeError(f"Answer evaluation fixture line {line_number} has an invalid id or question")
        expected_abstain = record["expected_abstain"]
        if not isinstance(expected_abstain, bool):
            raise TypeError(f"Answer evaluation fixture line {line_number} has invalid expected_abstain")
        required_anchors = _load_anchor_keys(
            record["required_anchor_keys"], line_number, "required", allow_empty=expected_abstain
        )
        if expected_abstain and required_anchors:
            raise ValueError(
                f"Answer evaluation fixture line {line_number} cannot require citations for abstention"
            )
        criteria = _load_review_criteria(record["human_review_criteria"], line_number)
        cases.append(
            AnswerEvalCase(case_id, question, required_anchors, expected_abstain, criteria)
        )
    if not cases:
        raise ValueError("Answer evaluation fixture contains no cases")
    if len({case.case_id for case in cases}) != len(cases):
        raise ValueError("Answer evaluation fixture contains duplicate case ids")
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


def _load_review_criteria(value: object, line_number: int) -> tuple[str, ...]:
    """Validate a non-empty, duplicate-free human review rubric."""
    if not isinstance(value, list) or not value or not all(isinstance(item, str) and item for item in value):
        raise TypeError(f"Answer evaluation fixture line {line_number} has invalid human_review_criteria")
    if len(set(value)) != len(value):
        raise ValueError(f"Answer evaluation fixture line {line_number} has duplicate human_review_criteria")
    return tuple(value)


def run_retrieval_evals(
    session: Session,
    cases: list[RetrievalEvalCase],
    strategy: RetrievalStrategy = "lexical",
    embedding_provider: EmbeddingProvider | None = None,
) -> list[RetrievalEvalResult]:
    """Measure one explicit retrieval strategy against acceptable and preferred anchors."""
    results = []
    for case in cases:
        matches = search_chunks(
            session, case.question, limit=3, strategy=strategy, embedding_provider=embedding_provider
        )
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


def run_answer_evals(
    session: Session,
    cases: list[AnswerEvalCase],
    provider: AnswerProvider,
    strategy: RetrievalStrategy = "semantic",
    embedding_provider: EmbeddingProvider | None = None,
) -> list[AnswerEvalResult]:
    """Run answer cases, keeping semantic quality assessment explicitly human-reviewed."""
    return [
        evaluate_answer(
            case,
            answer_question(
                session,
                case.question,
                provider,
                strategy=strategy,
                embedding_provider=embedding_provider,
            ),
        )
        for case in cases
    ]


def evaluate_answer(case: AnswerEvalCase, answer: CitedAnswer) -> AnswerEvalResult:
    """Evaluate citation anchors and abstention without claiming to judge legal prose automatically."""
    cited_anchor_keys = tuple(
        dict.fromkeys(
            citation.anchor_key for claim in answer.claims for citation in claim.citations
        )
    )
    missing = tuple(anchor for anchor in case.required_anchor_keys if anchor not in cited_anchor_keys)
    return AnswerEvalResult(
        case_id=case.case_id,
        answer=answer,
        required_anchor_keys=case.required_anchor_keys,
        cited_anchor_keys=cited_anchor_keys,
        missing_required_anchor_keys=missing,
        expected_abstain=case.expected_abstain,
        human_review_criteria=case.human_review_criteria,
    )


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
