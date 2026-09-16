import pytest

from taxrag import retrieval
from taxrag.retrieval import (
    RetrievedChunk,
    authority_multiplier,
    reciprocal_rank_fusion_score,
    validate_strategy,
)


def test_authority_multiplier_is_bounded_and_defaults_to_neutral() -> None:
    """Authority may rerank lexical candidates but must not dominate relevance unboundedly."""
    assert authority_multiplier("primary_legislation") == 1.35
    assert authority_multiplier("regulation") == 1.25
    assert authority_multiplier("tax_authority_norm") == 1.20
    assert authority_multiplier("official_guidance") == 1.00
    assert authority_multiplier("unknown") == 1.00


def test_retrieval_strategies_are_explicit_and_unknown_values_fail() -> None:
    """An evaluation must not silently fall back to another retrieval strategy."""
    assert validate_strategy("lexical") == "lexical"
    assert validate_strategy("lexical_authority") == "lexical_authority"
    assert validate_strategy("semantic") == "semantic"
    assert validate_strategy("hybrid_rrf") == "hybrid_rrf"
    with pytest.raises(ValueError, match="Unsupported retrieval strategy"):
        validate_strategy("hybrid_weighted")


def test_rrf_uses_rank_positions_not_incompatible_retriever_score_scales() -> None:
    """A chunk appearing in both lists gets one unweighted contribution from each rank."""
    assert reciprocal_rank_fusion_score(1, 1) == pytest.approx(2 / 61)
    assert reciprocal_rank_fusion_score(1, None) == pytest.approx(1 / 61)
    assert reciprocal_rank_fusion_score(None, 20) == pytest.approx(1 / 80)


def test_hybrid_rrf_merges_candidates_and_breaks_ties_deterministically(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Hybrid output preserves component evidence and never depends on database row order."""
    def match(chunk_id: str, anchor_key: str, *, lexical: float | None = None, semantic: float | None = None) -> RetrievedChunk:
        return RetrievedChunk(
            chunk_id=chunk_id,
            anchor_key=anchor_key,
            anchor_title=anchor_key,
            chunk_text=anchor_key,
            source_title="source",
            canonical_url="https://example.test",
            authority_level="official_guidance",
            strategy="lexical" if lexical is not None else "semantic",
            score=lexical if lexical is not None else semantic or 0,
            lexical_score=lexical,
            semantic_score=semantic,
        )

    monkeypatch.setattr(
        retrieval,
        "_search_lexical_chunks",
        lambda *_args: [match("a", "anchor-a", lexical=0.4), match("b", "anchor-b", lexical=0.3)],
    )
    monkeypatch.setattr(
        retrieval,
        "_search_semantic_chunks",
        lambda *_args: [match("b", "anchor-b", semantic=0.9), match("c", "anchor-c", semantic=0.8)],
    )

    results = retrieval._search_hybrid_rrf_chunks(None, "question", 3, object())  # type: ignore[arg-type]

    assert [result.anchor_key for result in results] == ["anchor-b", "anchor-a", "anchor-c"]
    assert results[0].lexical_rank == 2
    assert results[0].semantic_rank == 1
    assert results[0].lexical_score == 0.3
    assert results[0].semantic_score == 0.9
