"""Explicit embedding-provider boundary and source-version embedding worker."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from openai import OpenAI
from sqlalchemy import select
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

    vectors = provider.embed_texts([chunk.search_text for chunk in missing_chunks])
    for chunk, vector in zip(missing_chunks, vectors, strict=True):
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
