"""Persist structure-preserving extraction output for stored source versions."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from taxrag.config import settings
from taxrag.errata import errata_fingerprint, excluded_anchor_keys
from taxrag.extraction import (
    EXTRACTOR_NAME,
    EXTRACTOR_VERSION,
    ExtractionResult,
    extract_dou_in_rfb_2312_html,
    extract_receita_guidance_html,
    extract_receita_questions_answers_pdf,
)
from taxrag.models import (
    Chunk,
    ChunkEmbedding,
    ExtractedDocument,
    Source,
    SourceAnchor,
    SourceVersion,
)
from taxrag.storage import LocalObjectStorage


@dataclass(frozen=True)
class ProcessingResult:
    """The observable outcome of processing a stored source version."""

    outcome: str
    source_version_id: str
    chunk_count: int


def process_latest_source_version(session: Session, source_key: str) -> ProcessingResult:
    """Extract and chunk the newest stored version of one approved source."""
    source = session.scalar(select(Source).where(Source.source_key == source_key))
    if source is None:
        raise ValueError(f"No stored source exists for {source_key}")

    source_version = session.scalar(
        select(SourceVersion)
        .where(SourceVersion.source_id == source.id)
        .order_by(SourceVersion.fetched_at.desc())
        .limit(1)
    )
    if source_version is None:
        raise ValueError(f"No stored source version exists for {source_key}")

    existing_document = session.scalar(
        select(ExtractedDocument).where(ExtractedDocument.source_version_id == source_version.id)
    )
    if existing_document is not None and existing_document.extractor_version == processing_version():
        chunk_count = session.query(Chunk).filter(Chunk.source_version_id == source_version.id).count()
        return ProcessingResult("unchanged", str(source_version.id), chunk_count)

    try:
        if existing_document is not None:
            # A parser change invalidates derived text, not the immutable raw source version.
            old_chunk_ids = select(Chunk.id).where(Chunk.source_version_id == source_version.id)
            session.execute(
                delete(ChunkEmbedding).where(ChunkEmbedding.chunk_id.in_(old_chunk_ids))
            )
            session.execute(delete(Chunk).where(Chunk.source_version_id == source_version.id))
            for anchor in session.scalars(
                select(SourceAnchor).where(SourceAnchor.source_version_id == source_version.id)
            ):
                session.delete(anchor)
            session.delete(existing_document)
            session.flush()

        html = LocalObjectStorage(settings.object_storage_root).get_bytes(source_version.storage_key)
        extraction = _extract(source.document_family, html)
        source = session.get(Source, source_version.source_id)
        if source is None:
            raise ValueError(f"Source version {source_version.id} has no source")
        chunk_count = _persist_extraction(
            session, source_version, source.title, extraction, excluded_anchor_keys(source.source_key)
        )
        source_version.processing_status = "processed"
        session.commit()
        return ProcessingResult("created", str(source_version.id), chunk_count)
    except Exception:
        # Restore a usable transaction before recording the failed processing status.
        session.rollback()
        source_version.processing_status = "failed"
        session.commit()
        raise


def _extract(document_family: str, raw_content: bytes) -> ExtractionResult:
    """Select the explicit parser adapter for the source's known document family."""
    if document_family == "receita_guidance_html":
        return extract_receita_guidance_html(raw_content)
    if document_family == "receita_questions_answers_pdf":
        return extract_receita_questions_answers_pdf(raw_content)
    if document_family == "dou_norm_html":
        return extract_dou_in_rfb_2312_html(raw_content)
    raise ValueError(f"No extraction adapter exists for document family {document_family}")


def processing_version() -> str:
    """Extractor version plus errata fingerprint; either changing forces a reprocess."""
    return f"{EXTRACTOR_VERSION}+errata.{errata_fingerprint()}"


def _persist_extraction(
    session: Session,
    source_version: SourceVersion,
    source_title: str,
    extraction: ExtractionResult,
    excluded: frozenset[str] = frozenset(),
) -> int:
    """Save normalized text, citation anchors, and one section-preserving chunk per anchor."""
    session.add(
        ExtractedDocument(
            source_version_id=source_version.id,
            normalized_text=extraction.normalized_text,
            extractor_name=EXTRACTOR_NAME,
            extractor_version=processing_version(),
        )
    )
    session.flush()

    chunk_count = 0
    for section in extraction.sections:
        if section.anchor_key in excluded:
            # Known-wrong official passage (data/source-errata.json): kept in the normalized
            # document for provenance, never indexed or offered as citation evidence.
            continue
        anchor = SourceAnchor(
            source_version_id=source_version.id,
            anchor_key=section.anchor_key,
            display_title=section.display_title,
            ordinal=section.ordinal,
            text=section.text,
            page_start=section.page_start,
            page_end=section.page_end,
        )
        session.add(anchor)
        session.flush()
        # Chunk equals section in this first slice, preserving heading, conditions, and tables.
        search_text = section.search_text or section.text
        # A document title is useful for source-identification queries, but including it in
        # every chunk would create duplicate lexical matches. Attach it to the root anchor only.
        if section.ordinal == 1:
            search_text = f"{source_title}\n{section.display_title}\n{search_text}"
        else:
            search_text = f"{section.display_title}\n{search_text}"
        session.add(
            Chunk(
                source_version_id=source_version.id,
                source_anchor_id=anchor.id,
                ordinal=section.ordinal,
                text=f"{section.display_title}\n{section.text}",
                search_text=search_text,
                character_count=len(section.display_title) + 1 + len(section.text),
            )
        )
        chunk_count += 1
    return chunk_count
