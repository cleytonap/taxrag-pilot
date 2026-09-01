"""Explicit commands for background ingestion work."""

from __future__ import annotations

import argparse

from taxrag.database import SessionLocal
from taxrag.ingestion import ingest_source
from taxrag.sources import APPROVED_SOURCES


def main() -> None:
    parser = argparse.ArgumentParser(description="TaxRAG worker commands")
    subparsers = parser.add_subparsers(dest="command", required=True)
    ingest_parser = subparsers.add_parser("ingest-source", help="Fetch one approved official source")
    ingest_parser.add_argument("source_key", choices=sorted(APPROVED_SOURCES))
    args = parser.parse_args()

    if args.command == "ingest-source":
        with SessionLocal() as session:
            run = ingest_source(session, APPROVED_SOURCES[args.source_key])
        print(f"Ingestion run {run.id}: {run.outcome}")


if __name__ == "__main__":
    main()
