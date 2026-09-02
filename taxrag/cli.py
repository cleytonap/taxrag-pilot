"""Explicit commands for background ingestion work."""

from __future__ import annotations

import argparse

from taxrag.database import SessionLocal
from taxrag.ingestion import ingest_source
from taxrag.sources import APPROVED_SOURCES


def main() -> None:
    """Parse and execute explicit background-worker commands."""
    parser = argparse.ArgumentParser(description="TaxRAG worker commands")
    subparsers = parser.add_subparsers(dest="command", required=True)
    ingest_parser = subparsers.add_parser("ingest-source", help="Fetch one approved official source")
    # Restrict the command to the registry; a CLI user cannot ingest an arbitrary URL.
    ingest_parser.add_argument("source_key", choices=sorted(APPROVED_SOURCES))
    args = parser.parse_args()

    if args.command == "ingest-source":
        # A session is scoped to one command so connections are always released.
        with SessionLocal() as session:
            run = ingest_source(session, APPROVED_SOURCES[args.source_key])
        print(f"Ingestion run {run.id}: {run.outcome}")


if __name__ == "__main__":
    main()
