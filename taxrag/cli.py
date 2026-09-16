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
from taxrag.evals import (
    load_answer_eval_cases,
    load_retrieval_eval_cases,
    run_answer_evals,
    run_retrieval_evals,
)
from taxrag.ingestion import ingest_source
from taxrag.processing import process_latest_source_version
from taxrag.retrieval import SUPPORTED_STRATEGIES, RetrievedChunk, search_chunks
from taxrag.sources import APPROVED_SOURCES


def main() -> None:
    """Parse and execute explicit background-worker commands."""
    parser = argparse.ArgumentParser(description="TaxRAG worker commands")
    subparsers = parser.add_subparsers(dest="command", required=True)
    ingest_parser = subparsers.add_parser("ingest-source", help="Fetch one approved official source")
    # Restrict the command to the registry; a CLI user cannot ingest an arbitrary URL.
    ingest_parser.add_argument("source_key", choices=sorted(APPROVED_SOURCES))
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
    answer_parser = subparsers.add_parser(
        "answer", help="Retrieve official evidence and return a citation-validated answer"
    )
    answer_parser.add_argument("question")
    answer_parser.add_argument("--strategy", choices=SUPPORTED_STRATEGIES, default="semantic")
    answer_parser.add_argument("--provider", choices=("openai", "fake"), default="openai")
    answer_parser.add_argument(
        "--debug",
        action="store_true",
        help=(
            "write an untrusted rejected draft and its retrieved chunks to stderr; "
            "use only for local debugging of non-sensitive questions"
        ),
    )
    args = parser.parse_args()

    requires_embeddings = args.command == "embed-source" or (
        args.command in {"search", "eval-retrieval", "eval-answers", "answer"}
        and args.strategy in {"semantic", "hybrid_rrf"}
    )
    if requires_embeddings and not settings.openai_api_key:
        parser.error(
            "OPENAI_API_KEY is required for semantic embeddings. "
            "Set it in the command environment before using semantic retrieval."
        )

    if args.command == "ingest-source":
        # A session is scoped to one command so connections are always released.
        with SessionLocal() as session:
            run = ingest_source(session, APPROVED_SOURCES[args.source_key])
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
                    if args.strategy in {"semantic", "hybrid_rrf"}
                    else None
                ),
            )
        passed = sum(result.passed_structural_checks for result in results)
        for result in results:
            status = "pass" if result.passed_structural_checks else "fail"
            cited = ", ".join(result.cited_anchor_keys) or "none"
            missing = ", ".join(result.missing_required_anchor_keys) or "none"
            print(
                f"{result.case_id}: structural {status}; cited {cited}; "
                f"missing required {missing}; abstain {result.answer.abstain} "
                f"(expected {result.expected_abstain})"
            )
            for criterion in result.human_review_criteria:
                print(f"   human review: {criterion}")
        print(
            f"Answer structural checks ({args.strategy}, {args.provider}): "
            f"{passed}/{len(results)} passed. Human review remains required for every case."
        )
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
                    if args.strategy in {"semantic", "hybrid_rrf"}
                    else None
                ),
                on_validation_failure=debug_handler,
            )
        print(json.dumps(answer.to_dict(), ensure_ascii=False, indent=2))


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
                    {"chunk_id": citation.chunk_id, "quote": citation.quote}
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
