"""Hybrid LLM reranking and second-pass answer verification (V1 RCA follow-ups)."""

from types import SimpleNamespace

import pytest

from taxrag import answers, retrieval
from taxrag.answers import (
    AnswerDraft,
    AnswerVerification,
    DraftCitation,
    DraftClaim,
    answer_from_evidence,
)
from taxrag.evals import DELIBERATE_ABSTENTIONS
from taxrag.rerank import ordered_indexes, rerank_order


def _chunk(anchor: str, text: str = "superior a R$ 35.584,00") -> SimpleNamespace:
    return SimpleNamespace(
        chunk_id=f"id-{anchor}",
        anchor_key=anchor,
        anchor_title=anchor,
        chunk_text=text,
        source_title="IN",
        canonical_url="https://example.test",
        source_link="https://example.test",
        authority_level="tax_authority_norm",
        score=0.5,
    )


def test_reranker_output_is_validated_and_completed() -> None:
    assert ordered_indexes(["P3", "p1", "P3", "P9", "x", 2], 3) == [2, 0]

    class Picky:
        model = "test"

        def rerank(self, _question: str, _passages: list[str]) -> list[int]:
            return [2]

    assert rerank_order(Picky(), "q", ["a", "b", "c"]) == [2, 0, 1]


def test_reranker_failure_falls_back_to_fused_order() -> None:
    class Broken:
        model = "test"

        def rerank(self, _question: str, _passages: list[str]) -> list[int]:
            raise RuntimeError("network down")

    assert rerank_order(Broken(), "q", ["a", "b"]) == [0, 1]


def test_hybrid_rerank_reorders_fused_candidates(monkeypatch: pytest.MonkeyPatch) -> None:
    fused = [
        retrieval.RetrievedChunk(
            chunk_id=f"id-{anchor}",
            anchor_key=anchor,
            anchor_title=anchor,
            chunk_text=anchor,
            source_title="P&R",
            canonical_url="https://example.test",
            authority_level="official_guidance",
            strategy="hybrid_rrf",
            score=0.03,
        )
        for anchor in ("topic-neighbour", "answer")
    ]
    monkeypatch.setattr(retrieval, "_search_hybrid_rrf_chunks", lambda *_args: fused)

    class PrefersAnswer:
        model = "test"

        def rerank(self, _question: str, passages: list[str]) -> list[int]:
            return [1, 0]

    results = retrieval.search_chunks(
        None,  # type: ignore[arg-type]
        "Isso obriga a declarar?",
        limit=2,
        strategy="hybrid_rerank",
        embedding_provider=SimpleNamespace(model="m", dimensions=1536),  # type: ignore[arg-type]
        reranker=PrefersAnswer(),
    )

    assert [chunk.anchor_key for chunk in results] == ["answer", "topic-neighbour"]
    assert {chunk.strategy for chunk in results} == {"hybrid_rerank"}


class _Provider:
    model = "test"

    def __init__(self, verification: AnswerVerification | Exception) -> None:
        self._verification = verification

    def draft_answer(self, _question: str, chunks: list[SimpleNamespace]) -> AnswerDraft:
        return AnswerDraft(
            (DraftClaim("O limite é R$ 35.584,00.", (DraftCitation(chunks[0].chunk_id),)),),
            False,
            None,
            None,
        )

    def verify_answer(self, *_args: object) -> AnswerVerification:
        if isinstance(self._verification, Exception):
            raise self._verification
        return self._verification


def test_verifier_rejection_becomes_a_deliberate_abstention() -> None:
    seen: list[str] = []
    answer = answer_from_evidence(
        "Qual era o limite em 2024?",
        [_chunk("limites")],  # type: ignore[list-item]
        _Provider(AnswerVerification(False, "answers another year")),
        strategy="semantic",
        on_validation_failure=lambda _draft, error, _chunks: seen.append(str(error)),
    )

    assert answer.outcome == "verification_abstained"
    assert answer.claims == ()
    assert answer.display_text == answers.VERIFICATION_ABSTENTION_MESSAGE
    assert "answers another year" in seen[0]
    assert "verification_abstained" in DELIBERATE_ABSTENTIONS


def test_verifier_outage_fails_closed_and_approval_keeps_the_answer() -> None:
    blocked = answer_from_evidence(
        "q", [_chunk("a")], _Provider(RuntimeError("timeout")), strategy="semantic"  # type: ignore[list-item]
    )
    approved = answer_from_evidence(
        "q", [_chunk("a")], _Provider(AnswerVerification(True, "ok")), strategy="semantic"  # type: ignore[list-item]
    )

    assert blocked.outcome == "verification_abstained"
    assert approved.outcome == "answered"
    assert approved.claims[0].text == "O limite é R$ 35.584,00."


def test_short_evidence_ids_map_back_to_chunk_ids() -> None:
    draft = AnswerDraft((DraftClaim("x", (DraftCitation("E2"), DraftCitation("E9"))),), False, None, None)

    mapped = answers._with_chunk_ids(draft, [_chunk("a"), _chunk("b")])  # type: ignore[list-item]

    assert [citation.chunk_id for citation in mapped.claims[0].citations] == ["id-b", "E9"]
