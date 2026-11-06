"""Fetch approved sources and preserve immutable raw versions."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from taxrag.config import PROJECT_ROOT, settings
from taxrag.models import IngestionRun, Source, SourceVersion
from taxrag.sources import ApprovedSource
from taxrag.storage import LocalObjectStorage


def ingest_source(
    session: Session, approved_source: ApprovedSource, *, from_snapshot: bool = False
) -> IngestionRun:
    """Fetch or load one approved source and record its immutable content version."""
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
        if from_snapshot:
            content, content_type = _load_source_snapshot(approved_source)
        else:
            response = _fetch_source(approved_source)
            content, content_type = response.content, response.headers["content-type"]
        content_hash = hashlib.sha256(content).hexdigest()
        # The hash makes the ingestion operation idempotent even if it runs repeatedly.
        existing_version = session.scalar(
            select(SourceVersion).where(
                SourceVersion.source_id == source.id,
                SourceVersion.content_hash == content_hash,
            )
        )
        if existing_version is not None:
            # The database can outlive the local object store (e.g. `var/` cleaned while the
            # PostgreSQL volume persists). The bytes just verified by hash are the same object,
            # so restore it instead of leaving a version that can no longer be processed.
            storage = LocalObjectStorage(settings.object_storage_root)
            if not storage.exists(existing_version.storage_key):
                storage.put_bytes(existing_version.storage_key, content)
            run.source_version_id = existing_version.id
            run.outcome = "unchanged"
            run.finished_at = datetime.now(UTC)
            session.commit()
            return run

        storage_key = f"raw/{source.source_key}/{content_hash}/{approved_source.raw_filename}"
        LocalObjectStorage(settings.object_storage_root).put_bytes(storage_key, content)
        # Store the raw artifact outside PostgreSQL and retain its verifiable pointer in the database.
        source_version = SourceVersion(
            source_id=source.id,
            content_hash=content_hash,
            storage_key=storage_key,
            content_type=content_type,
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


def _load_source_snapshot(approved_source: ApprovedSource) -> tuple[bytes, str]:
    """Read a bundled source snapshot and verify it matches the registry's exact hash."""
    if not approved_source.snapshot_path or not approved_source.snapshot_sha256:
        raise ValueError(f"No bundled source snapshot is registered for {approved_source.source_key}")

    snapshot_path = (PROJECT_ROOT / approved_source.snapshot_path).resolve()
    if PROJECT_ROOT not in snapshot_path.parents:
        raise ValueError("Bundled source snapshot path must remain inside the project")
    content = snapshot_path.read_bytes()
    actual_hash = hashlib.sha256(content).hexdigest()
    if actual_hash != approved_source.snapshot_sha256:
        raise ValueError(
            f"Bundled source snapshot hash mismatch for {approved_source.source_key}: "
            f"expected {approved_source.snapshot_sha256}, got {actual_hash}"
        )
    return content, approved_source.expected_content_type


def _fetch_source(approved_source: ApprovedSource) -> httpx.Response:
    """Download an approved source and reject content that differs from its declared format."""
    with httpx.Client(
        follow_redirects=True,
        timeout=30.0,
        headers={
            "User-Agent": "TaxRAG learning project source ingestor",
            **approved_source.request_headers,
        },
    ) as client:
        response = client.get(approved_source.canonical_url)
        response.raise_for_status()

    content_type = response.headers.get("content-type", "")
    if not content_type.startswith(approved_source.expected_content_type):
        raise ValueError(
            f"Expected {approved_source.expected_content_type} source content but received "
            f"{content_type or 'no content type'}"
        )
    return response
