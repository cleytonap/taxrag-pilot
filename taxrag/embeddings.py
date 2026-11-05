"""Explicit embedding-provider boundary and source-version embedding worker."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from openai import OpenAI
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from taxrag.config import settings
from taxrag.models import Chunk, ChunkEmbedding, Source, SourceVersion


class EmbeddingProvider(Protocol):
    """Minimal provider contract so retrieval is not coupled to one embedding vendor."""

    model: str
    dimensions: int

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Return one vector for each non-empty input text, preserving input order."""


class OpenAIEmbeddingProvider(EmbeddingProvider):
    """OpenAI embeddings adapter for the configured first semantic baseline model."""

    def __init__(self, api_key: str | None, model: str, dimensions: int) -> None:
        self.model = model
        self.dimensions = dimensions
        self._api_key = api_key

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Generate vectors through the OpenAI embeddings endpoint and validate its response."""
        if not self._api_key:
            raise RuntimeError("OPENAI_API_KEY is required to generate semantic embeddings")
        if not texts or any(not text.strip() for text in texts):
            raise ValueError("Embedding inputs must be a non-empty list of non-empty texts")
        response = OpenAI(api_key=self._api_key).embeddings.create(
            model=self.model,
            input=texts,
            dimensions=self.dimensions,
        )
        vectors = [list(item.embedding) for item in sorted(response.data, key=lambda item: item.index)]
        if len(vectors) != len(texts) or any(len(vector) != self.dimensions for vector in vectors):
            raise ValueError("Embedding provider returned an unexpected vector count or dimension")
        return vectors


def configured_embedding_provider() -> OpenAIEmbeddingProvider:
    """Build the configured provider lazily so lexical retrieval never needs an API key."""
    return OpenAIEmbeddingProvider(
        settings.openai_api_key, settings.embedding_model, settings.embedding_dimensions
    )


@dataclass(frozen=True)
class EmbeddingResult:
    """Observable result of embedding the latest processed source version."""

    source_version_id: str
    outcome: str
    embedded_chunk_count: int


def embed_latest_source_version(
    session: Session, source_key: str, provider: EmbeddingProvider
) -> EmbeddingResult:
    """Embed missing chunks from one source's latest processed version for one model."""
    source = session.scalar(select(Source).where(Source.source_key == source_key))
    if source is None:
        raise ValueError(f"No stored source exists for {source_key}")
    source_version = session.scalar(
        select(SourceVersion)
        .where(SourceVersion.source_id == source.id, SourceVersion.processing_status == "processed")
        .order_by(SourceVersion.fetched_at.desc())
        .limit(1)
    )
    if source_version is None:
        raise ValueError(f"No processed source version exists for {source_key}")
    chunks = list(
        session.scalars(
            select(Chunk)
            .where(Chunk.source_version_id == source_version.id)
            .order_by(Chunk.ordinal)
        )
    )
    existing_chunk_ids = set(
        session.scalars(
            select(ChunkEmbedding.chunk_id).where(
                ChunkEmbedding.chunk_id.in_([chunk.id for chunk in chunks]),
                ChunkEmbedding.model == provider.model,
                ChunkEmbedding.dimensions == provider.dimensions,
            )
        )
    )
    missing_chunks = [chunk for chunk in chunks if chunk.id not in existing_chunk_ids]
    if not missing_chunks:
        return EmbeddingResult(str(source_version.id), "unchanged", 0)

    # One request per bounded batch: the embeddings API rejects requests above 2,048 inputs or
    # ~300k total tokens, and the full P&R source alone is ~1.1M characters. Committing per batch
    # keeps the command resumable, because only chunks without a vector are embedded on rerun.
    for batch in _embedding_batches(missing_chunks):
        vectors = provider.embed_texts([chunk.search_text for chunk in batch])
        for chunk, vector in zip(batch, vectors, strict=True):
            session.add(
                ChunkEmbedding(
                    chunk_id=chunk.id,
                    model=provider.model,
                    dimensions=provider.dimensions,
                    embedding=vector,
                )
            )
        session.commit()
    return EmbeddingResult(str(source_version.id), "created", len(missing_chunks))


EMBEDDING_BATCH_MAX_INPUTS = 64
# Conservative character budget (~40-60k tokens for Portuguese) far below the request token cap.
EMBEDDING_BATCH_MAX_CHARACTERS = 150_000


def _embedding_batches(chunks: list[Chunk]) -> list[list[Chunk]]:
    """Split chunks into API-safe batches bounded by input count and total characters."""
    batches: list[list[Chunk]] = []
    current: list[Chunk] = []
    current_characters = 0
    for chunk in chunks:
        size = len(chunk.search_text)
        if current and (
            len(current) >= EMBEDDING_BATCH_MAX_INPUTS
            or current_characters + size > EMBEDDING_BATCH_MAX_CHARACTERS
        ):
            batches.append(current)
            current, current_characters = [], 0
        current.append(chunk)
        current_characters += size
    if current:
        batches.append(current)
    return batches


def embedding_coverage(session: Session, model: str, dimensions: int) -> tuple[int, int]:
    """Return (embedded, total) chunk counts for active processed sources and one model.

    Semantic and hybrid evaluations must not run on partial vectors: missing embeddings silently
    shrink the searchable corpus and would record a misleadingly low baseline.
    """
    active_chunk_ids = (
        select(Chunk.id)
        .join(SourceVersion, SourceVersion.id == Chunk.source_version_id)
        .join(Source, Source.id == SourceVersion.source_id)
        .where(Source.is_active.is_(True), SourceVersion.processing_status == "processed")
    )
    total = session.scalar(select(func.count()).select_from(active_chunk_ids.subquery())) or 0
    embedded = (
        session.scalar(
            select(func.count(ChunkEmbedding.chunk_id)).where(
                ChunkEmbedding.chunk_id.in_(active_chunk_ids),
                ChunkEmbedding.model == model,
                ChunkEmbedding.dimensions == dimensions,
            )
        )
        or 0
    )
    return embedded, total


def require_complete_embeddings(session: Session, model: str, dimensions: int) -> None:
    """Fail fast with an actionable message when the corpus is not fully embedded."""
    embedded, total = embedding_coverage(session, model, dimensions)
    if total == 0 or embedded < total:
        raise RuntimeError(
            f"Semantic retrieval needs embeddings for every chunk, but only {embedded} of {total} "
            f"chunks have {model} vectors. Run `uv run python -m apps.worker embed-source <source>` "
            "for each source (or rerun scripts/run-workshop.sh with OPENAI_API_KEY set)."
        )
