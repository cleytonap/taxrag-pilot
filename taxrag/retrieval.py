"""Selectable lexical and semantic retrieval over source-grounded chunks."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from pgvector.sqlalchemy import Vector
from sqlalchemy import bindparam, text
from sqlalchemy.orm import Session

from taxrag.config import settings
from taxrag.embeddings import EmbeddingProvider, configured_embedding_provider

RetrievalStrategy = Literal["lexical", "lexical_authority", "semantic"]
SUPPORTED_STRATEGIES = ("lexical", "lexical_authority", "semantic")

AUTHORITY_MULTIPLIERS = {
    "primary_legislation": 1.35,
    "regulation": 1.25,
    "tax_authority_norm": 1.20,
    "official_guidance": 1.00,
}


def authority_multiplier(authority_level: str) -> float:
    """Return the bounded authority adjustment used by the lexical experiment."""
    return AUTHORITY_MULTIPLIERS.get(authority_level, 1.00)


AUTHORITY_SCORE_CASE = """CASE s.authority_level
    WHEN 'primary_legislation' THEN 1.35
    WHEN 'regulation' THEN 1.25
    WHEN 'tax_authority_norm' THEN 1.20
    ELSE 1.00
END"""


@dataclass(frozen=True)
class RetrievedChunk:
    """A ranked chunk with provenance and strategy-specific score evidence."""

    chunk_id: str
    anchor_key: str
    anchor_title: str
    chunk_text: str
    source_title: str
    canonical_url: str
    authority_level: str
    strategy: RetrievalStrategy
    score: float
    lexical_score: float | None = None
    semantic_score: float | None = None


def validate_strategy(strategy: str) -> RetrievalStrategy:
    """Reject unknown retrieval modes before they can silently change an evaluation."""
    if strategy not in SUPPORTED_STRATEGIES:
        raise ValueError(
            f"Unsupported retrieval strategy {strategy!r}; choose one of {', '.join(SUPPORTED_STRATEGIES)}"
        )
    return strategy  # type: ignore[return-value]


def search_chunks(
    session: Session,
    question: str,
    limit: int = 3,
    strategy: RetrievalStrategy = "lexical",
    embedding_provider: EmbeddingProvider | None = None,
) -> list[RetrievedChunk]:
    """Return chunks using one explicit, independently measurable retrieval strategy."""
    strategy = validate_strategy(strategy)
    if not question.strip():
        return []
    if limit < 1:
        raise ValueError("Search limit must be at least 1")
    if strategy == "semantic":
        return _search_semantic_chunks(
            session, question, limit, embedding_provider or configured_embedding_provider()
        )
    return _search_lexical_chunks(session, question, limit, strategy)


def _search_lexical_chunks(
    session: Session, question: str, limit: int, strategy: RetrievalStrategy
) -> list[RetrievedChunk]:
    """Run pure lexical rank or the separately named authority-adjusted experiment."""
    lexical_expression = "ts_rank_cd(to_tsvector('portuguese', c.search_text), search_query.value)"
    score_expression = (
        f"{lexical_expression} * ({AUTHORITY_SCORE_CASE})"
        if strategy == "lexical_authority"
        else lexical_expression
    )
    query = text(
        f"""
        WITH search_query AS (
            SELECT websearch_to_tsquery(
                'portuguese',
                regexp_replace(trim(:question), '[[:space:]]+', ' OR ', 'g')
            ) AS value
        )
        SELECT
            c.id::text AS chunk_id,
            a.anchor_key,
            a.display_title AS anchor_title,
            c.text AS chunk_text,
            s.title AS source_title,
            s.canonical_url,
            s.authority_level,
            {lexical_expression} AS lexical_score,
            {score_expression} AS score
        FROM chunks AS c
        JOIN source_anchors AS a ON a.id = c.source_anchor_id
        JOIN source_versions AS sv ON sv.id = c.source_version_id
        JOIN sources AS s ON s.id = sv.source_id
        CROSS JOIN search_query
        WHERE s.is_active
          AND sv.processing_status = 'processed'
          AND to_tsvector('portuguese', c.search_text) @@ search_query.value
        ORDER BY score DESC, lexical_score DESC, c.ordinal ASC
        LIMIT :limit
        """
    )
    rows = session.execute(query, {"question": question, "limit": limit}).mappings()
    return [
        RetrievedChunk(
            chunk_id=row["chunk_id"],
            anchor_key=row["anchor_key"],
            anchor_title=row["anchor_title"],
            chunk_text=row["chunk_text"],
            source_title=row["source_title"],
            canonical_url=row["canonical_url"],
            authority_level=row["authority_level"],
            strategy=strategy,
            score=float(row["score"]),
            lexical_score=float(row["lexical_score"]),
        )
        for row in rows
    ]


def _search_semantic_chunks(
    session: Session, question: str, limit: int, provider: EmbeddingProvider
) -> list[RetrievedChunk]:
    """Embed a question and rank matching-model chunks by exact cosine similarity."""
    if provider.dimensions != settings.embedding_dimensions:
        raise ValueError(
            "The configured database schema supports "
            f"{settings.embedding_dimensions}-dimension embeddings, not {provider.dimensions}"
        )
    question_vector = provider.embed_texts([question])[0]
    if len(question_vector) != provider.dimensions:
        raise ValueError("Embedding provider returned a query vector with unexpected dimensions")
    query = text(
        """
        SELECT
            c.id::text AS chunk_id,
            a.anchor_key,
            a.display_title AS anchor_title,
            c.text AS chunk_text,
            s.title AS source_title,
            s.canonical_url,
            s.authority_level,
            1 - (ce.embedding <=> :embedding) AS semantic_score
        FROM chunk_embeddings AS ce
        JOIN chunks AS c ON c.id = ce.chunk_id
        JOIN source_anchors AS a ON a.id = c.source_anchor_id
        JOIN source_versions AS sv ON sv.id = c.source_version_id
        JOIN sources AS s ON s.id = sv.source_id
        WHERE ce.model = :model
          AND ce.dimensions = :dimensions
          AND s.is_active
          AND sv.processing_status = 'processed'
        ORDER BY ce.embedding <=> :embedding, c.ordinal ASC
        LIMIT :limit
        """
    ).bindparams(bindparam("embedding", type_=Vector(settings.embedding_dimensions)))
    rows = session.execute(
        query,
        {
            "embedding": question_vector,
            "model": provider.model,
            "dimensions": provider.dimensions,
            "limit": limit,
        },
    ).mappings()
    return [
        RetrievedChunk(
            chunk_id=row["chunk_id"],
            anchor_key=row["anchor_key"],
            anchor_title=row["anchor_title"],
            chunk_text=row["chunk_text"],
            source_title=row["source_title"],
            canonical_url=row["canonical_url"],
            authority_level=row["authority_level"],
            strategy="semantic",
            score=float(row["semantic_score"]),
            semantic_score=float(row["semantic_score"]),
        )
        for row in rows
    ]
