"""Fetch approved sources and preserve immutable raw versions."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from taxrag.config import settings
from taxrag.models import IngestionRun, Source, SourceVersion
from taxrag.sources import ApprovedSource
from taxrag.storage import LocalObjectStorage


def ingest_source(session: Session, approved_source: ApprovedSource) -> IngestionRun:
    """Fetch one allow-listed source and record an immutable content version when it changes."""
    # Create the durable source identity once; each fetch is tracked separately as a run.
    source = session.scalar(select(Source).where(Source.source_key == approved_source.source_key))
    if source is None:
        source = Source(
            source_key=approved_source.source_key,
            title=approved_source.title,
            canonical_url=approved_source.canonical_url,
            authority_level=approved_source.authority_level,
            document_family=approved_source.document_family,
        )
        session.add(source)
        session.commit()

    run = IngestionRun(source_id=source.id)
    session.add(run)
    session.commit()

    try:
        response = _fetch_html(approved_source.canonical_url)
        content_hash = hashlib.sha256(response.content).hexdigest()
        # The hash makes the ingestion operation idempotent even if it runs repeatedly.
        existing_version = session.scalar(
            select(SourceVersion).where(
                SourceVersion.source_id == source.id,
                SourceVersion.content_hash == content_hash,
            )
        )
        if existing_version is not None:
            run.source_version_id = existing_version.id
            run.outcome = "unchanged"
            run.finished_at = datetime.now(UTC)
            session.commit()
            return run

        storage_key = f"raw/{source.source_key}/{content_hash}/original.html"
        LocalObjectStorage(settings.object_storage_root).put_bytes(storage_key, response.content)
        # Store the raw artifact outside PostgreSQL and retain its verifiable pointer in the database.
        source_version = SourceVersion(
            source_id=source.id,
            content_hash=content_hash,
            storage_key=storage_key,
            content_type=response.headers["content-type"],
        )
        session.add(source_version)
        session.flush()
        run.source_version_id = source_version.id
        run.outcome = "created"
        run.finished_at = datetime.now(UTC)
        session.commit()
        return run
    except Exception as error:
        run.outcome = "failed"
        run.error_message = str(error)
        run.finished_at = datetime.now(UTC)
        session.commit()
        raise


def _fetch_html(url: str) -> httpx.Response:
    """Download an HTML source, following official redirects and rejecting unexpected content."""
    with httpx.Client(
        follow_redirects=True,
        timeout=30.0,
        headers={"User-Agent": "TaxRAG learning project source ingestor"},
    ) as client:
        response = client.get(url)
        response.raise_for_status()

    content_type = response.headers.get("content-type", "")
    if not content_type.startswith("text/html"):
        raise ValueError(f"Expected HTML source content but received {content_type or 'no content type'}")
    return response
