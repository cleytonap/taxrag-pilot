"""Explicit commands for background ingestion work."""

from __future__ import annotations

import argparse

from taxrag.database import SessionLocal
from taxrag.ingestion import ingest_source
from taxrag.processing import process_latest_source_version
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


if __name__ == "__main__":
    main()
