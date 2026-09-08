"""Deterministic lexical retrieval over source-grounded chunks."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.orm import Session

AUTHORITY_MULTIPLIERS = {
    "primary_legislation": 1.35,
    "regulation": 1.25,
    "tax_authority_norm": 1.20,
    "official_guidance": 1.00,
}


def authority_multiplier(authority_level: str) -> float:
    """Return the bounded authority adjustment used after lexical candidate matching."""
    return AUTHORITY_MULTIPLIERS.get(authority_level, 1.00)


AUTHORITY_SCORE_CASE = """CASE s.authority_level
    WHEN 'primary_legislation' THEN 1.35
    WHEN 'regulation' THEN 1.25
    WHEN 'tax_authority_norm' THEN 1.20
    ELSE 1.00
END"""


@dataclass(frozen=True)
class RetrievedChunk:
    """A ranked chunk with the provenance required for a later user-visible citation."""

    chunk_id: str
    anchor_key: str
    anchor_title: str
    chunk_text: str
    source_title: str
    canonical_url: str
    authority_level: str
    lexical_score: float
    score: float


def search_chunks(session: Session, question: str, limit: int = 3) -> list[RetrievedChunk]:
    """Return the highest-ranked active chunks matching a Portuguese-language question."""
    if not question.strip():
        return []
    if limit < 1:
        raise ValueError("Search limit must be at least 1")

    # `search_text` deliberately differs from citation text for legal subdivisions.
    # It removes repeated inherited context while preserving the full `chunk_text` for citations.
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
            ts_rank_cd(to_tsvector('portuguese', c.search_text), search_query.value) AS lexical_score,
            ts_rank_cd(to_tsvector('portuguese', c.search_text), search_query.value)
                * ({AUTHORITY_SCORE_CASE}) AS score
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
            lexical_score=float(row["lexical_score"]),
            score=float(row["score"]),
        )
        for row in rows
    ]
