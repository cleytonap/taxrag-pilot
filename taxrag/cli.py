"""Explicit commands for background ingestion work."""

from __future__ import annotations

import argparse
from pathlib import Path

from taxrag.database import SessionLocal
from taxrag.evals import load_retrieval_eval_cases, run_retrieval_evals
from taxrag.ingestion import ingest_source
from taxrag.processing import process_latest_source_version
from taxrag.retrieval import search_chunks
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
    search_parser = subparsers.add_parser("search", help="Search processed chunks with lexical retrieval")
    search_parser.add_argument("question")
    search_parser.add_argument("--limit", type=int, default=3)
    eval_parser = subparsers.add_parser(
        "eval-retrieval", help="Run the versioned lexical retrieval evaluation fixture"
    )
    eval_parser.add_argument(
        "--fixture", type=Path, default=Path("docs/evals/lexical-retrieval-baseline.jsonl")
    )
    args = parser.parse_args()

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
    elif args.command == "search":
        with SessionLocal() as session:
            matches = search_chunks(session, args.question, args.limit)
        for rank, match in enumerate(matches, start=1):
            print(f"{rank}. {match.anchor_key} ({match.score:.4f})")
            print(f"   {match.anchor_title} - {match.source_title}")
            print(f"   {match.canonical_url}")
    elif args.command == "eval-retrieval":
        cases = load_retrieval_eval_cases(args.fixture)
        with SessionLocal() as session:
            results = run_retrieval_evals(session, cases)
        required_results = [result for result in results if result.expected_recall_at_three]
        known_gap_results = [result for result in results if not result.expected_recall_at_three]
        passed = sum(result.passed_at_three for result in required_results)
        for result in results:
            rank = result.actual_rank if result.actual_rank is not None else "not found"
            expectation = "required" if result.expected_recall_at_three else "known lexical gap"
            print(
                f"{result.case_id}: expected {result.expected_anchor_key}; "
                f"rank {rank}; {expectation}"
            )
        print(f"Recall@3 (required): {passed}/{len(required_results)} ({passed / len(required_results):.0%})")
        print(f"Known lexical gaps: {len(known_gap_results)}")


if __name__ == "__main__":
    main()
