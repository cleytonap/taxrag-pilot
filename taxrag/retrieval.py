"""Selectable lexical and semantic retrieval over source-grounded chunks."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, replace
from typing import Literal
from urllib.parse import quote

from pgvector.sqlalchemy import Vector
from sqlalchemy import bindparam, text
from sqlalchemy.orm import Session

from taxrag.config import settings
from taxrag.embeddings import EmbeddingProvider, configured_embedding_provider
from taxrag.rerank import Reranker, configured_reranker, rerank_order

# "fixed_context" labels evidence chosen by an eval case (answer-generation suite), not retrieved.
RetrievalStrategy = Literal[
    "lexical", "lexical_authority", "semantic", "hybrid_rrf", "hybrid_rerank", "fixed_context"
]
SUPPORTED_STRATEGIES = ("lexical", "lexical_authority", "semantic", "hybrid_rrf", "hybrid_rerank")
# Strategies that embed the question (and therefore need vectors for the whole corpus).
EMBEDDING_STRATEGIES = frozenset({"semantic", "hybrid_rrf", "hybrid_rerank"})
RERANK_CANDIDATES = 20
RRF_CANDIDATE_LIMIT = 20
RRF_DAMPING_CONSTANT = 60

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
    lexical_rank: int | None = None
    semantic_rank: int | None = None
    page_start: int | None = None

    @property
    def source_link(self) -> str:
        """Link to a PDF page or best-effort HTML text location within the official document."""
        if self.page_start is not None:
            return f"{self.canonical_url}#page={self.page_start}"
        return f"{self.canonical_url}#:~:text={quote(self.anchor_title, safe='')}"


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
    reranker: Reranker | None = None,
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
    if strategy == "hybrid_rerank":
        return _search_hybrid_rerank_chunks(
            session,
            question,
            limit,
            embedding_provider or configured_embedding_provider(),
            reranker or configured_reranker(),
        )
    if strategy == "hybrid_rrf":
        return _search_hybrid_rrf_chunks(
            session,
            question,
            limit,
            embedding_provider or configured_embedding_provider(),
        )
    return _search_lexical_chunks(session, question, limit, strategy)


def _search_hybrid_rerank_chunks(
    session: Session,
    question: str,
    limit: int,
    provider: EmbeddingProvider,
    reranker: Reranker,
) -> list[RetrievedChunk]:
    """Rerank the fused lexical+semantic candidates with an LLM (see taxrag/rerank.py)."""
    candidates = _search_hybrid_rrf_chunks(session, question, RERANK_CANDIDATES, provider)
    order = rerank_order(reranker, question, [candidate.chunk_text for candidate in candidates])
    return [
        replace(candidates[index], strategy="hybrid_rerank", score=1 / position)
        for position, index in enumerate(order[:limit], start=1)
    ]


def reciprocal_rank_fusion_score(*ranks: int | None) -> float:
    """Return an unweighted RRF score from one-based ranks in independent candidate lists."""
    return sum(1 / (RRF_DAMPING_CONSTANT + rank) for rank in ranks if rank is not None)


def _search_hybrid_rrf_chunks(
    session: Session, question: str, limit: int, provider: EmbeddingProvider
) -> list[RetrievedChunk]:
    """Fuse bounded lexical and semantic candidate lists without tuning score weights."""
    candidate_limit = max(limit, RRF_CANDIDATE_LIMIT)
    lexical_matches = _search_lexical_chunks(session, question, candidate_limit, "lexical")
    semantic_matches = _search_semantic_chunks(session, question, candidate_limit, provider)
    lexical_by_chunk = {match.chunk_id: (rank, match) for rank, match in enumerate(lexical_matches, 1)}
    semantic_by_chunk = {
        match.chunk_id: (rank, match) for rank, match in enumerate(semantic_matches, 1)
    }
    fused_matches = []
    for chunk_id in lexical_by_chunk.keys() | semantic_by_chunk.keys():
        lexical_entry = lexical_by_chunk.get(chunk_id)
        semantic_entry = semantic_by_chunk.get(chunk_id)
        lexical_rank, lexical_match = lexical_entry if lexical_entry else (None, None)
        semantic_rank, semantic_match = semantic_entry if semantic_entry else (None, None)
        source_match = lexical_match or semantic_match
        assert source_match is not None
        fused_matches.append(
            RetrievedChunk(
                chunk_id=source_match.chunk_id,
                anchor_key=source_match.anchor_key,
                anchor_title=source_match.anchor_title,
                chunk_text=source_match.chunk_text,
                source_title=source_match.source_title,
                canonical_url=source_match.canonical_url,
                authority_level=source_match.authority_level,
                strategy="hybrid_rrf",
                score=reciprocal_rank_fusion_score(lexical_rank, semantic_rank),
                lexical_score=lexical_match.lexical_score if lexical_match else None,
                semantic_score=semantic_match.semantic_score if semantic_match else None,
                lexical_rank=lexical_rank,
                semantic_rank=semantic_rank,
                page_start=source_match.page_start,
            )
        )
    return sorted(
        fused_matches,
        key=lambda match: (
            -match.score,
            min(rank for rank in (match.lexical_rank, match.semantic_rank) if rank is not None),
            match.anchor_key,
        ),
    )[:limit]


def _search_lexical_chunks(
    session: Session, question: str, limit: int, strategy: RetrievalStrategy
) -> list[RetrievedChunk]:
    """Run pure lexical rank or the separately named authority-adjusted experiment."""
    # ts_rank with normalisation 1 (divide by 1 + log(document length)). The V0 baseline used
    # unnormalised ts_rank_cd, which let five very long P&R chunks fill 124 of 210 top-3 slots
    # (lexical recall@3 11/70); normalised ranking scored 49/70 on the same corpus.
    lexical_expression = "ts_rank(c.search_vector, search_query.value, 1)"
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
            a.page_start,
            {lexical_expression} AS lexical_score,
            {score_expression} AS score
        FROM chunks AS c
        JOIN source_anchors AS a ON a.id = c.source_anchor_id
        JOIN source_versions AS sv ON sv.id = c.source_version_id
        JOIN sources AS s ON s.id = sv.source_id
        CROSS JOIN search_query
        WHERE s.is_active
          AND sv.processing_status = 'processed'
          AND c.search_vector @@ search_query.value
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
            page_start=row["page_start"],
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
            a.page_start,
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
            page_start=row["page_start"],
        )
        for row in rows
    ]


def fetch_chunks_by_anchor_keys(session: Session, anchor_keys: Sequence[str]) -> list[RetrievedChunk]:
    """Load active chunks for explicit anchors, in the given order, for fixed-context evals.

    Raises when an anchor has no active chunk (e.g. excluded by source errata or not yet
    processed), because a silently shorter context would change what the case tests.
    """
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
            a.page_start
        FROM chunks AS c
        JOIN source_anchors AS a ON a.id = c.source_anchor_id
        JOIN source_versions AS sv ON sv.id = c.source_version_id
        JOIN sources AS s ON s.id = sv.source_id
        WHERE s.is_active
          AND sv.processing_status = 'processed'
          AND a.anchor_key IN :anchor_keys
        """
    ).bindparams(bindparam("anchor_keys", expanding=True))
    rows = {
        row["anchor_key"]: row
        for row in session.execute(query, {"anchor_keys": list(anchor_keys)}).mappings()
    }
    missing = [key for key in anchor_keys if key not in rows]
    if missing:
        raise ValueError(f"No active indexed chunk for context anchors: {', '.join(missing)}")
    return [
        RetrievedChunk(
            chunk_id=rows[key]["chunk_id"],
            anchor_key=key,
            anchor_title=rows[key]["anchor_title"],
            chunk_text=rows[key]["chunk_text"],
            source_title=rows[key]["source_title"],
            canonical_url=rows[key]["canonical_url"],
            authority_level=rows[key]["authority_level"],
            strategy="fixed_context",
            score=0.0,
            page_start=rows[key]["page_start"],
        )
        for key in anchor_keys
    ]
