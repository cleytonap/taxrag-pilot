"""Explicit commands for background ingestion work."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from taxrag.answers import (
    AnswerDraft,
    AnswerValidationError,
    DeterministicAnswerProvider,
    answer_question,
    configured_answer_provider,
)
from taxrag.config import settings
from taxrag.database import SessionLocal
from taxrag.embeddings import configured_embedding_provider, embed_latest_source_version
from taxrag.eval_manager import compare_artifacts, promote_to_baseline, run_suite
from taxrag.evals import (
    AnswerEvalResult,
    load_answer_eval_cases,
    load_retrieval_eval_cases,
    run_answer_evals,
    run_retrieval_evals,
)
from taxrag.ingestion import ingest_source
from taxrag.processing import process_latest_source_version
from taxrag.retrieval import (
    EMBEDDING_STRATEGIES,
    SUPPORTED_STRATEGIES,
    RetrievedChunk,
    search_chunks,
)
from taxrag.sources import APPROVED_SOURCES


def _format_answer_eval_result(result: AnswerEvalResult, *, show_answer: bool) -> list[str]:
    """Render one answer-evaluation result as a self-contained review record.

    The structural checker and human review answer different questions, so the
    report keeps their expected and actual values visibly separate.
    """
    answer = result.answer
    acceptable = ", ".join(result.acceptable_anchor_keys) or "none"
    cited = ", ".join(result.cited_anchor_keys) or "none"
    cited_acceptable = ", ".join(result.cited_acceptable_anchor_keys) or "none"
    structural_status = "pass" if result.passed_structural_checks else "fail"

    lines = [
        result.case_id,
        f"  question: {answer.question}",
        "  expected:",
        f"    acceptable official citation anchors: {acceptable}",
        f"    provider abstention: {result.expected_abstain}",
        "  actual:",
        f"    cited anchors: {cited}",
        f"    cited acceptable anchors: {cited_acceptable}",
        f"    abstain: {answer.abstain}",
        f"    outcome: {answer.outcome}",
        f"  automated structural result: {structural_status}",
        "  human-review checklist (not automatically scored):",
    ]
    lines.extend(f"    - {criterion}" for criterion in result.human_review_criteria)
    if not result.passed_structural_checks:
        lines.extend(_format_answer_eval_trace(result))
    if show_answer:
        lines.append(f"  display answer: {answer.display_text or '[no display text]'}")
        if answer.limitation:
            lines.append(f"  limitation: {answer.limitation}")
        if answer.clarification_question:
            lines.append(f"  clarification: {answer.clarification_question}")
    return lines


def _format_answer_eval_trace(result: AnswerEvalResult) -> list[str]:
    """Render local RCA facts for a failed evaluation without presenting drafts as answers."""
    trace = result.trace
    retrieved_anchors = {evidence.anchor_key for evidence in trace.retrieved_evidence}
    acceptable_retrieved = set(result.acceptable_anchor_keys) & retrieved_anchors
    lines = ["  failure diagnostics:"]
    if trace.retrieved_evidence:
        lines.append("    retrieved evidence:")
        lines.extend(
            "      - "
            f"{evidence.anchor_key} ({evidence.chunk_id}; {evidence.source_title})"
            for evidence in trace.retrieved_evidence
        )
    else:
        lines.append("    retrieved evidence: none")
    if result.acceptable_anchor_keys and not acceptable_retrieved:
        lines.append(
            "    acceptable evidence absent from retrieval: "
            f"{', '.join(result.acceptable_anchor_keys)}"
        )
    if acceptable_retrieved and not result.cited_acceptable_anchor_keys:
        lines.append(
            "    acceptable evidence retrieved but not cited by the provider: "
            f"{', '.join(sorted(acceptable_retrieved))}"
        )
    if trace.validation_error:
        lines.append(f"    validator rejection: {trace.validation_error}")
        lines.append("    untrusted provider draft (not shown to an end user):")
        lines.extend(_indent_json(_draft_to_dict(trace.rejected_draft), spaces=6))
    return lines


def _indent_json(value: object, *, spaces: int) -> list[str]:
    """Format local diagnostic data as indented JSON lines for terminal inspection."""
    prefix = " " * spaces
    return [f"{prefix}{line}" for line in json.dumps(value, ensure_ascii=False, indent=2).splitlines()]


def main() -> None:
    """Parse and execute explicit background-worker commands."""
    parser = argparse.ArgumentParser(description="TaxRAG worker commands")
    subparsers = parser.add_subparsers(dest="command", required=True)
    ingest_parser = subparsers.add_parser("ingest-source", help="Fetch one approved official source")
    # Restrict the command to the registry; a CLI user cannot ingest an arbitrary URL.
    ingest_parser.add_argument("source_key", choices=sorted(APPROVED_SOURCES))
    ingest_parser.add_argument(
        "--from-snapshot",
        action="store_true",
        help="ingest the bundled hash-verified source file without making an HTTP request",
    )
    process_parser = subparsers.add_parser(
        "process-source", help="Extract and chunk the newest stored source version"
    )
    process_parser.add_argument("source_key", choices=sorted(APPROVED_SOURCES))
    embed_parser = subparsers.add_parser(
        "embed-source", help="Generate missing semantic embeddings for one processed source"
    )
    embed_parser.add_argument("source_key", choices=sorted(APPROVED_SOURCES))
    search_parser = subparsers.add_parser(
        "search", help="Search processed chunks with a selected retrieval strategy"
    )
    search_parser.add_argument("question")
    search_parser.add_argument("--limit", type=int, default=3)
    search_parser.add_argument("--strategy", choices=SUPPORTED_STRATEGIES, default="lexical")
    eval_parser = subparsers.add_parser(
        "eval-retrieval", help="Evaluate one selected retrieval strategy against the versioned fixture"
    )
    eval_parser.add_argument(
        "--fixture", type=Path, default=Path("docs/evals/lexical-retrieval-baseline.jsonl")
    )
    eval_parser.add_argument("--strategy", choices=SUPPORTED_STRATEGIES, default="lexical")
    answer_eval_parser = subparsers.add_parser(
        "eval-answers", help="Run structural checks for the human-reviewed cited-answer fixture"
    )
    answer_eval_parser.add_argument(
        "--fixture", type=Path, default=Path("docs/evals/cited-answer-development.jsonl")
    )
    answer_eval_parser.add_argument("--strategy", choices=SUPPORTED_STRATEGIES, default="lexical")
    answer_eval_parser.add_argument("--provider", choices=("openai", "fake"), default="fake")
    answer_eval_parser.add_argument(
        "--show-answers",
        action="store_true",
        help="print each generated answer for the mandatory human review step",
    )
    answer_parser = subparsers.add_parser(
        "answer", help="Retrieve official evidence and return a citation-validated answer"
    )
    answer_parser.add_argument("question")
    answer_parser.add_argument(
        "--strategy", choices=SUPPORTED_STRATEGIES, default=settings.answer_strategy
    )
    answer_parser.add_argument("--provider", choices=("openai", "fake"), default="openai")
    answer_parser.add_argument(
        "--debug",
        action="store_true",
        help=(
            "write an untrusted rejected draft and its retrieved chunks to stderr; "
            "use only for local debugging of non-sensitive questions"
        ),
    )
    run_parser = subparsers.add_parser(
        "run-suite",
        help="Run a suite exactly like the Eval Workshop and save a JSON artifact in var/eval-runs/",
    )
    run_parser.add_argument(
        "suite",
        choices=("retrieval", "generation", "answer"),
        help="retrieval = chunks only; generation = answers from fixed evidence; answer = end-to-end",
    )
    run_parser.add_argument(
        "--strategy",
        choices=SUPPORTED_STRATEGIES,
        default=settings.answer_strategy,
        help=f"default: the production pipeline ({settings.answer_strategy}); others are diagnostics",
    )
    run_parser.add_argument("--provider", choices=("fake", "openai"), default="fake")
    run_parser.add_argument(
        "--confirm-paid",
        action="store_true",
        help="required for semantic/hybrid retrieval or the OpenAI provider (billable API calls)",
    )
    run_parser.add_argument(
        "--baseline",
        metavar="LABEL",
        help="also promote the saved run to docs/evals/baselines/ under this label (e.g. v0)",
    )
    promote_parser = subparsers.add_parser(
        "promote-baseline", help="Copy a saved run artifact to the Git-tracked baselines directory"
    )
    promote_parser.add_argument("artifact_name")
    promote_parser.add_argument("--label", required=True)
    compare_parser = subparsers.add_parser(
        "compare-runs", help="Compare a candidate run artifact against a baseline artifact"
    )
    compare_parser.add_argument("baseline")
    compare_parser.add_argument("candidate")
    args = parser.parse_args()

    requires_embeddings = args.command == "embed-source" or (
        args.command in {"search", "eval-retrieval", "eval-answers", "answer", "run-suite"}
        and args.strategy in EMBEDDING_STRATEGIES
        and getattr(args, "suite", None) != "generation"
    )
    if requires_embeddings and not settings.openai_api_key:
        parser.error(
            "OPENAI_API_KEY is required for semantic embeddings. "
            "Set it in the command environment before using semantic retrieval."
        )

    try:
        _dispatch(args)
    except (FileExistsError, FileNotFoundError, PermissionError, RuntimeError, ValueError) as error:
        # Expected operator errors (missing embeddings, immutable baseline, unknown artifact)
        # are shown as one actionable line instead of a traceback.
        parser.exit(2, f"Error: {type(error).__name__}: {error}\n")


def _dispatch(args: argparse.Namespace) -> None:
    """Execute one parsed worker command."""
    if args.command == "ingest-source":
        # A session is scoped to one command so connections are always released.
        with SessionLocal() as session:
            run = ingest_source(
                session,
                APPROVED_SOURCES[args.source_key],
                from_snapshot=args.from_snapshot,
            )
        print(f"Ingestion run {run.id}: {run.outcome}")
    elif args.command == "process-source":
        with SessionLocal() as session:
            result = process_latest_source_version(session, args.source_key)
        print(
            f"Processing source version {result.source_version_id}: "
            f"{result.outcome} ({result.chunk_count} chunks)"
        )
    elif args.command == "embed-source":
        with SessionLocal() as session:
            result = embed_latest_source_version(
                session, args.source_key, configured_embedding_provider()
            )
        print(
            f"Embedding source version {result.source_version_id}: "
            f"{result.outcome} ({result.embedded_chunk_count} chunks)"
        )
    elif args.command == "search":
        with SessionLocal() as session:
            matches = search_chunks(session, args.question, args.limit, args.strategy)
        for rank, match in enumerate(matches, start=1):
            score_details = [f"score {match.score:.4f}"]
            if match.lexical_score is not None:
                score_details.append(f"lexical {match.lexical_score:.4f}")
            if match.semantic_score is not None:
                score_details.append(f"semantic {match.semantic_score:.4f}")
            if match.lexical_rank is not None:
                score_details.append(f"lexical rank {match.lexical_rank}")
            if match.semantic_rank is not None:
                score_details.append(f"semantic rank {match.semantic_rank}")
            score_details.append(f"authority {match.authority_level}")
            print(f"{rank}. {match.anchor_key} ({'; '.join(score_details)})")
            print(f"   {match.anchor_title} - {match.source_title}")
            print(f"   {match.canonical_url}")
    elif args.command == "eval-retrieval":
        cases = load_retrieval_eval_cases(args.fixture)
        with SessionLocal() as session:
            results = run_retrieval_evals(
                session,
                cases,
                strategy=args.strategy,
                embedding_provider=(
                    configured_embedding_provider() if args.strategy == "semantic" else None
                ),
            )
        required_results = [result for result in results if result.expected_recall_at_three]
        passed = sum(result.passed_at_three for result in required_results)
        preferred_results = [result for result in results if result.preferred_at_three is not None]
        preferred_passed = sum(result.preferred_at_three for result in preferred_results)
        for result in results:
            rank = result.acceptable_rank if result.acceptable_rank is not None else "outside top 3"
            expectation = "required" if result.expected_recall_at_three else "known lexical gap"
            print(
                f"{result.case_id}: acceptable {', '.join(result.acceptable_anchor_keys)}; "
                f"rank {rank}; {expectation}"
            )
            if result.preferred_anchor_keys:
                preferred_rank = (
                    result.preferred_rank if result.preferred_rank is not None else "outside top 3"
                )
                print(
                    f"   preferred {', '.join(result.preferred_anchor_keys)}; "
                    f"rank {preferred_rank}"
                )
        print(
            f"Recall@3 ({args.strategy}, required): "
            f"{passed}/{len(required_results)} ({passed / len(required_results):.0%})"
        )
        if preferred_results:
            print(
                "Preferred-source recall@3: "
                f"{preferred_passed}/{len(preferred_results)} "
                f"({preferred_passed / len(preferred_results):.0%})"
            )
    elif args.command == "eval-answers":
        cases = load_answer_eval_cases(args.fixture)
        provider = DeterministicAnswerProvider() if args.provider == "fake" else configured_answer_provider()
        with SessionLocal() as session:
            results = run_answer_evals(
                session,
                cases,
                provider,
                strategy=args.strategy,
                embedding_provider=(
                    configured_embedding_provider()
                    if args.strategy in EMBEDDING_STRATEGIES
                    else None
                ),
            )
        passed = sum(result.passed_structural_checks for result in results)
        for result in results:
            print("\n".join(_format_answer_eval_result(result, show_answer=args.show_answers)))
        print(
            f"Answer structural checks ({args.strategy}, {args.provider}): "
            f"{passed}/{len(results)} passed. Human review remains required for every case."
        )
    elif args.command == "run-suite":
        with SessionLocal() as session:
            outcome = run_suite(
                session,
                suite_id=args.suite,
                strategy=args.strategy,
                provider_id=args.provider,
                confirm_paid_request=args.confirm_paid,
                on_progress=lambda done, total: print(
                    f"\r  {done}/{total} cases", end="", file=sys.stderr, flush=True
                ),
            )
        print(file=sys.stderr)
        print(f"Saved var/eval-runs/{outcome['artifact_name']}")
        print(json.dumps(outcome["summary"], indent=2))
        if args.baseline:
            promoted = promote_to_baseline(outcome["artifact_name"], args.baseline)
            print(f"Baseline saved to {promoted['path']} (commit it to share and keep it)")
    elif args.command == "promote-baseline":
        promoted = promote_to_baseline(args.artifact_name, args.label)
        print(f"Baseline saved to {promoted['path']} (commit it to share and keep it)")
    elif args.command == "compare-runs":
        print("\n".join(_format_comparison(compare_artifacts(args.baseline, args.candidate))))
    elif args.command == "answer":
        provider = DeterministicAnswerProvider() if args.provider == "fake" else configured_answer_provider()
        debug_handler = _print_answer_validation_debug if args.debug else None
        with SessionLocal() as session:
            answer = answer_question(
                session,
                args.question,
                provider,
                strategy=args.strategy,
                embedding_provider=(
                    configured_embedding_provider()
                    if args.strategy in EMBEDDING_STRATEGIES
                    else None
                ),
                on_validation_failure=debug_handler,
            )
        print(json.dumps(answer.to_dict(), ensure_ascii=False, indent=2))


def _format_comparison(comparison: dict[str, object]) -> list[str]:
    """Render a baseline/candidate comparison with regressions listed first."""
    lines = [
        f"Baseline:  {comparison['baseline']}",
        f"Candidate: {comparison['candidate']}",
        f"Strategies: {' -> '.join(comparison['strategies'])}",  # type: ignore[arg-type]
    ]
    lines += [f"WARNING: {warning}" for warning in comparison["warnings"]]  # type: ignore[union-attr]
    lines.append("Metrics:")
    for name, values in comparison["metrics"].items():  # type: ignore[union-attr]
        lines.append(
            f"  {name}: {values['baseline']:.3g} -> {values['candidate']:.3g} "
            f"({values['delta']:+.3g})"
        )
    changes = comparison["changes"]
    lines.append(f"Case changes: {len(changes)}")  # type: ignore[arg-type]
    for change in changes:  # type: ignore[union-attr]
        detail = (
            f"rank {change['baseline_rank']} -> {change['candidate_rank']}"
            if change["baseline_outcome"] is None
            else f"outcome {change['baseline_outcome']} -> {change['candidate_outcome']}"
        )
        lines.append(f"  {change['change'].upper():12} {change['case_id']}: {detail}")
    for label in ("added_case_ids", "removed_case_ids"):
        if comparison[label]:
            lines.append(f"{label.replace('_', ' ')}: {', '.join(comparison[label])}")  # type: ignore[arg-type]
    return lines


def _print_answer_validation_debug(
    draft: AnswerDraft | None,
    error: AnswerValidationError,
    chunks: Sequence[RetrievedChunk],
) -> None:
    """Write rejected, untrusted provider output to stderr for local diagnosis only."""
    payload = {
        "event": "answer_validation_rejected",
        "reason": str(error),
        "draft": _draft_to_dict(draft),
        "retrieved_chunks": [
            {
                "chunk_id": chunk.chunk_id,
                "anchor_key": chunk.anchor_key,
                "anchor_title": chunk.anchor_title,
                "source_title": chunk.source_title,
                "chunk_text": chunk.chunk_text,
            }
            for chunk in chunks
        ],
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2), file=sys.stderr)


def _draft_to_dict(draft: AnswerDraft | None) -> dict[str, object] | None:
    """Serialize untrusted structured output without converting it into a validated answer."""
    if draft is None:
        return None
    return {
        "claims": [
            {
                "text": claim.text,
                "citations": [
                    {"chunk_id": citation.chunk_id}
                    for citation in claim.citations
                ],
            }
            for claim in draft.claims
        ],
        "abstain": draft.abstain,
        "limitation": draft.limitation,
        "clarification_question": draft.clarification_question,
    }


if __name__ == "__main__":
    main()
