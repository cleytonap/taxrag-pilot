"""Persistence models for source provenance."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint, Uuid, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Source(Base):
    __tablename__ = "sources"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    source_key: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(255))
    canonical_url: Mapped[str] = mapped_column(Text)
    authority_level: Mapped[str] = mapped_column(String(64))
    document_family: Mapped[str] = mapped_column(String(64))
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SourceVersion(Base):
    __tablename__ = "source_versions"
    __table_args__ = (UniqueConstraint("source_id", "content_hash"),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    source_id: Mapped[UUID] = mapped_column(ForeignKey("sources.id"), index=True)
    content_hash: Mapped[str] = mapped_column(String(64))
    storage_key: Mapped[str] = mapped_column(Text)
    content_type: Mapped[str] = mapped_column(String(255))
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    processing_status: Mapped[str] = mapped_column(String(32), default="pending")


class IngestionRun(Base):
    __tablename__ = "ingestion_runs"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    source_id: Mapped[UUID] = mapped_column(ForeignKey("sources.id"), index=True)
    source_version_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("source_versions.id"), nullable=True
    )
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    outcome: Mapped[str] = mapped_column(String(32), default="running")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)


class ExtractedDocument(Base):
    """Normalized text produced from one immutable raw source version."""

    __tablename__ = "extracted_documents"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    source_version_id: Mapped[UUID] = mapped_column(
        ForeignKey("source_versions.id"), unique=True, index=True
    )
    normalized_text: Mapped[str] = mapped_column(Text)
    extractor_name: Mapped[str] = mapped_column(String(100))
    extractor_version: Mapped[str] = mapped_column(String(32))
    extracted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SourceAnchor(Base):
    """A user-verifiable heading or structural location in a source version."""

    __tablename__ = "source_anchors"
    __table_args__ = (UniqueConstraint("source_version_id", "anchor_key"),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    source_version_id: Mapped[UUID] = mapped_column(ForeignKey("source_versions.id"), index=True)
    anchor_key: Mapped[str] = mapped_column(String(255))
    display_title: Mapped[str] = mapped_column(String(500))
    ordinal: Mapped[int] = mapped_column()
    text: Mapped[str] = mapped_column(Text)


class Chunk(Base):
    """A retrievable section linked to one source version and citation anchor."""

    __tablename__ = "chunks"
    __table_args__ = (UniqueConstraint("source_version_id", "ordinal"),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    source_version_id: Mapped[UUID] = mapped_column(ForeignKey("source_versions.id"), index=True)
    source_anchor_id: Mapped[UUID] = mapped_column(ForeignKey("source_anchors.id"), index=True)
    ordinal: Mapped[int] = mapped_column()
    text: Mapped[str] = mapped_column(Text)
    character_count: Mapped[int] = mapped_column()
