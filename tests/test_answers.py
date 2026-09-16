"""Offline tests for cited-answer validation and the OpenAI provider boundary."""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from taxrag import answers
from taxrag.answers import (
    AnswerDraft,
    AnswerValidationError,
    DraftCitation,
    DraftClaim,
    OpenAIAnswerProvider,
    answer_question,
    validate_answer_draft,
)
from taxrag.retrieval import RetrievedChunk


def _chunk(chunk_id: str = "chunk-1") -> RetrievedChunk:
    """Return a provenance-rich retrieved chunk suitable for citation tests."""
    return RetrievedChunk(
        chunk_id=chunk_id,
        anchor_key="art-2-inciso-iii",
        anchor_title="Art. 2, inciso III",
        chunk_text=(
            "Art. 2º. Está obrigada a apresentar a declaração a pessoa física que obteve "
            "ganho de capital na alienação de bens ou direitos sujeito à incidência do imposto."
        ),
        source_title="IN RFB nº 2.312/2026",
        canonical_url="https://example.test/in-2312",
        authority_level="tax_authority_norm",
        strategy="semantic",
        score=0.9,
        semantic_score=0.9,
    )


def _draft(*, chunk_id: str = "chunk-1") -> AnswerDraft:
    """Return a minimally valid non-abstaining draft for a known retrieved chunk."""
    return AnswerDraft(
        claims=(
            DraftClaim(
                "A obtenção de ganho de capital pode exigir a declaração.",
                (DraftCitation(chunk_id),),
            ),
        ),
        abstain=False,
        limitation="A resposta não substitui a análise da situação individual.",
        clarification_question=None,
    )


def test_validated_answer_citation_preserves_retrieved_provenance_and_excerpt() -> None:
    """The application attaches a renderable excerpt from the selected retrieved chunk."""
    claims = validate_answer_draft(_draft(), [_chunk()])

    assert claims[0].citations[0].anchor_key == "art-2-inciso-iii"
    assert claims[0].citations[0].source_title == "IN RFB nº 2.312/2026"
    assert claims[0].citations[0].excerpt == _chunk().chunk_text
    serialized = claims[0].citations[0].to_dict()
    assert serialized["excerpt"] == _chunk().chunk_text
    assert "quote" not in serialized


def test_validator_rejects_citation_to_a_chunk_that_was_not_retrieved() -> None:
    """A model cannot cite a valid-looking identifier outside this retrieval result."""
    with pytest.raises(AnswerValidationError, match="was not retrieved"):
        validate_answer_draft(_draft(chunk_id="invented-chunk"), [_chunk()])


def test_validator_rejects_an_abstention_with_factual_claims() -> None:
    """Abstention is a safety outcome, not a way to attach an unsupported answer."""
    invalid = AnswerDraft(
        claims=_draft().claims,
        abstain=True,
        limitation="Não há evidência suficiente.",
        clarification_question=None,
    )

    with pytest.raises(AnswerValidationError, match="must not include factual claims"):
        validate_answer_draft(invalid, [_chunk()])


def test_answer_question_abstains_without_calling_provider_when_retrieval_is_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No retrieved official evidence means no model-generated answer is permitted."""
    monkeypatch.setattr(answers, "search_chunks", lambda *_args, **_kwargs: [])

    class NeverCalled:
        model = "test"

        def draft_answer(self, *_args: object) -> AnswerDraft:
            raise AssertionError("provider must not be called without evidence")

    result = answer_question(None, "Pergunta", NeverCalled())  # type: ignore[arg-type]

    assert result.abstain is True
    assert result.claims == ()
    assert "fonte oficial" in result.limitation or "fonte oficial" in result.limitation.lower()


def test_answer_question_returns_safe_abstention_when_provider_citation_is_invalid(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An unsupported provider citation is rejected without exposing a traceback to callers."""
    monkeypatch.setattr(answers, "search_chunks", lambda *_args, **_kwargs: [_chunk()])

    class InvalidCitationProvider:
        model = "test"

        def draft_answer(self, *_args: object) -> AnswerDraft:
            return _draft(chunk_id="not-retrieved")

    result = answer_question(None, "Pergunta", InvalidCitationProvider())  # type: ignore[arg-type]

    assert result.abstain is True
    assert result.claims == ()
    assert "Não foi possível validar" in result.limitation


def test_answer_question_reports_rejected_draft_only_to_an_opt_in_diagnostic_hook(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Local diagnostics can inspect rejected output without letting it reach callers."""
    monkeypatch.setattr(answers, "search_chunks", lambda *_args, **_kwargs: [_chunk()])
    rejected: list[tuple[AnswerDraft | None, AnswerValidationError, list[RetrievedChunk]]] = []

    class InvalidCitationProvider:
        model = "test"

        def draft_answer(self, *_args: object) -> AnswerDraft:
            return _draft(chunk_id="not-retrieved")

    result = answer_question(
        None,
        "Pergunta",
        InvalidCitationProvider(),  # type: ignore[arg-type]
        on_validation_failure=lambda draft, error, chunks: rejected.append(
            (draft, error, list(chunks))
        ),
    )

    assert result.abstain is True
    assert rejected[0][0] is not None
    assert rejected[0][0].claims[0].citations[0].chunk_id == "not-retrieved"
    assert "was not retrieved" in str(rejected[0][1])
    assert rejected[0][2][0].chunk_id == "chunk-1"


def test_openai_provider_uses_strict_structured_output_without_storing_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The adapter sends evidence-only input and lets application code validate the result."""
    calls: list[dict[str, object]] = []
    payload = {
        "claims": [
            {
                "text": "A obtenção de ganho de capital pode exigir a declaração.",
                "citations": [
                    {
                        "chunk_id": "chunk-1",
                    }
                ],
            }
        ],
        "abstain": False,
        "limitation": None,
        "clarification_question": None,
    }

    class FakeResponses:
        def create(self, **kwargs: object) -> SimpleNamespace:
            calls.append(kwargs)
            return SimpleNamespace(output_text=json.dumps(payload))

    class FakeClient:
        def __init__(self, api_key: str) -> None:
            assert api_key == "test-key"
            self.responses = FakeResponses()

    monkeypatch.setattr(answers, "OpenAI", FakeClient)
    provider = OpenAIAnswerProvider("test-key", "test-model")

    draft = provider.draft_answer("Preciso declarar?", [_chunk()])

    assert draft.claims == _draft().claims
    assert draft.abstain is False
    assert draft.limitation is None
    assert calls[0]["model"] == "test-model"
    assert calls[0]["store"] is False
    assert calls[0]["temperature"] == 0
    assert calls[0]["text"] == {"format": answers._response_format()}
    input_payload = json.loads(calls[0]["input"])
    assert input_payload["evidence"][0]["chunk_id"] == "chunk-1"


def test_openai_provider_requires_key_before_a_network_call() -> None:
    """Answer generation is explicitly disabled until local credentials are configured."""
    with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
        OpenAIAnswerProvider(None, "test-model").draft_answer("Pergunta", [_chunk()])
