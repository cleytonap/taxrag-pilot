"""Source-constrained answer generation and deterministic citation validation."""

from __future__ import annotations

import json
import re
import unicodedata
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Protocol

from openai import OpenAI
from sqlalchemy.orm import Session

from taxrag.config import settings
from taxrag.embeddings import EmbeddingProvider
from taxrag.retrieval import RetrievalStrategy, RetrievedChunk, search_chunks

MINIMUM_QUOTE_LENGTH = 20


class AnswerValidationError(ValueError):
    """Raised when a provider draft cannot be tied to the retrieved evidence."""


@dataclass(frozen=True)
class DraftCitation:
    """A provider-proposed citation expressed in internal retrieved-chunk identifiers."""

    chunk_id: str
    quote: str


@dataclass(frozen=True)
class DraftClaim:
    """A provider-proposed factual claim and the evidence it says supports it."""

    text: str
    citations: tuple[DraftCitation, ...]


@dataclass(frozen=True)
class AnswerDraft:
    """Untrusted structured output returned by an answer provider."""

    claims: tuple[DraftClaim, ...]
    abstain: bool
    limitation: str | None
    clarification_question: str | None


@dataclass(frozen=True)
class Citation:
    """A validated citation ready for a caller to render with source provenance."""

    chunk_id: str
    anchor_key: str
    anchor_title: str
    source_title: str
    canonical_url: str
    authority_level: str
    quote: str

    def to_dict(self) -> dict[str, str]:
        """Serialize the citation without exposing mutable internal objects."""
        return {
            "chunk_id": self.chunk_id,
            "anchor_key": self.anchor_key,
            "anchor_title": self.anchor_title,
            "source_title": self.source_title,
            "canonical_url": self.canonical_url,
            "authority_level": self.authority_level,
            "quote": self.quote,
        }


@dataclass(frozen=True)
class AnswerClaim:
    """A validated claim with citations that belong to this retrieval result."""

    text: str
    citations: tuple[Citation, ...]

    def to_dict(self) -> dict[str, Any]:
        """Serialize a claim and its evidence for the API or CLI boundary."""
        return {"text": self.text, "citations": [citation.to_dict() for citation in self.citations]}


@dataclass(frozen=True)
class CitedAnswer:
    """The safe answer product returned after deterministic citation validation."""

    question: str
    claims: tuple[AnswerClaim, ...]
    abstain: bool
    limitation: str | None
    clarification_question: str | None
    retrieval_strategy: RetrievalStrategy
    answer_model: str

    @property
    def text(self) -> str:
        """Return display text assembled only from validated provider claims."""
        return "\n\n".join(claim.text for claim in self.claims)

    def to_dict(self) -> dict[str, Any]:
        """Serialize an answer together with the evidence needed to inspect it."""
        return {
            "question": self.question,
            "text": self.text,
            "claims": [claim.to_dict() for claim in self.claims],
            "abstain": self.abstain,
            "limitation": self.limitation,
            "clarification_question": self.clarification_question,
            "retrieval_strategy": self.retrieval_strategy,
            "answer_model": self.answer_model,
        }


class AnswerProvider(Protocol):
    """Provider boundary for generating an untrusted, source-constrained answer draft."""

    model: str

    def draft_answer(self, question: str, chunks: Sequence[RetrievedChunk]) -> AnswerDraft:
        """Return structured claims that the application must validate before use."""


class OpenAIAnswerProvider(AnswerProvider):
    """OpenAI Responses adapter using strict JSON Schema structured output."""

    def __init__(self, api_key: str | None, model: str) -> None:
        self._api_key = api_key
        self.model = model

    def draft_answer(self, question: str, chunks: Sequence[RetrievedChunk]) -> AnswerDraft:
        """Request source-constrained output and parse it into the untrusted draft contract."""
        if not self._api_key:
            raise RuntimeError("OPENAI_API_KEY is required for answer generation")
        response = OpenAI(api_key=self._api_key).responses.create(
            model=self.model,
            instructions=_instructions(),
            input=_answer_input(question, chunks),
            text={"format": _response_format()},
            temperature=0,
            store=False,
        )
        output_text = getattr(response, "output_text", "")
        if not isinstance(output_text, str) or not output_text.strip():
            raise AnswerValidationError("Answer provider returned no structured output")
        try:
            payload = json.loads(output_text)
        except json.JSONDecodeError as exc:
            raise AnswerValidationError("Answer provider returned invalid JSON") from exc
        return _parse_draft(payload)


class DeterministicAnswerProvider(AnswerProvider):
    """Offline provider that cites the first retrieved chunk for CLI smoke tests."""

    model = "deterministic-test-provider"

    def draft_answer(self, question: str, chunks: Sequence[RetrievedChunk]) -> AnswerDraft:
        """Return one exact, inspectable extract rather than attempting a synthetic answer."""
        if not chunks:
            return AnswerDraft((), True, "Não encontrei fonte oficial suficiente.", None)
        chunk = chunks[0]
        quote = _first_quote(chunk.chunk_text)
        return AnswerDraft(
            claims=(
                DraftClaim(
                    text=f"Trecho recuperado da fonte oficial: {quote}",
                    citations=(DraftCitation(chunk.chunk_id, quote),),
                ),
            ),
            abstain=False,
            limitation="Resposta de teste: apresenta um trecho recuperado, sem interpretação individual.",
            clarification_question=None,
        )


def configured_answer_provider() -> OpenAIAnswerProvider:
    """Build the configured production answer provider without making a network request."""
    return OpenAIAnswerProvider(settings.openai_api_key, settings.answer_model)


def answer_question(
    session: Session,
    question: str,
    provider: AnswerProvider,
    *,
    strategy: RetrievalStrategy = "semantic",
    embedding_provider: EmbeddingProvider | None = None,
) -> CitedAnswer:
    """Retrieve official evidence, draft an answer, and return only validated citations."""
    if not question.strip():
        raise ValueError("Question must not be blank")
    chunks = search_chunks(
        session,
        question,
        limit=3,
        strategy=strategy,
        embedding_provider=embedding_provider,
    )
    if not chunks:
        return CitedAnswer(
            question=question,
            claims=(),
            abstain=True,
            limitation="Não encontrei fonte oficial suficiente para responder com segurança.",
            clarification_question="Pode reformular a pergunta com mais detalhes?",
            retrieval_strategy=strategy,
            answer_model=provider.model,
        )
    try:
        draft = provider.draft_answer(question, chunks)
        claims = validate_answer_draft(draft, chunks)
    except AnswerValidationError:
        # A malformed or misquoted provider response is untrusted output, not a CLI/API crash.
        # Do not expose its text: return the same safe outcome as insufficient evidence instead.
        return _unverified_answer(question, strategy, provider.model)
    return CitedAnswer(
        question=question,
        claims=claims,
        abstain=draft.abstain,
        limitation=draft.limitation,
        clarification_question=draft.clarification_question,
        retrieval_strategy=strategy,
        answer_model=provider.model,
    )


def _unverified_answer(
    question: str, strategy: RetrievalStrategy, answer_model: str
) -> CitedAnswer:
    """Return a safe response when provider output cannot be verified against retrieved evidence."""
    return CitedAnswer(
        question=question,
        claims=(),
        abstain=True,
        limitation=(
            "Não foi possível validar uma resposta com as fontes oficiais recuperadas. "
            "Tente novamente ou reformule a pergunta."
        ),
        clarification_question="Pode informar mais detalhes sobre a sua situação?",
        retrieval_strategy=strategy,
        answer_model=answer_model,
    )


def validate_answer_draft(
    draft: AnswerDraft, chunks: Sequence[RetrievedChunk]
) -> tuple[AnswerClaim, ...]:
    """Accept only claims with exact quotes from chunks retrieved for this question."""
    if draft.abstain:
        if draft.claims:
            raise AnswerValidationError("An abstaining answer must not include factual claims")
        return ()
    if not draft.claims:
        raise AnswerValidationError("A non-abstaining answer must include at least one claim")

    chunks_by_id = {chunk.chunk_id: chunk for chunk in chunks}
    validated_claims = []
    for claim in draft.claims:
        if not claim.text.strip():
            raise AnswerValidationError("Answer claims must not be blank")
        if not claim.citations:
            raise AnswerValidationError("Every answer claim must include at least one citation")
        citations = []
        for draft_citation in claim.citations:
            chunk = chunks_by_id.get(draft_citation.chunk_id)
            if chunk is None:
                raise AnswerValidationError("Answer cited a chunk that was not retrieved")
            _validate_quote(draft_citation.quote, chunk.chunk_text)
            citations.append(
                Citation(
                    chunk_id=chunk.chunk_id,
                    anchor_key=chunk.anchor_key,
                    anchor_title=chunk.anchor_title,
                    source_title=chunk.source_title,
                    canonical_url=chunk.canonical_url,
                    authority_level=chunk.authority_level,
                    quote=draft_citation.quote,
                )
            )
        validated_claims.append(AnswerClaim(claim.text, tuple(citations)))
    return tuple(validated_claims)


def _validate_quote(quote: str, source_text: str) -> None:
    """Require a substantial exact quote after whitespace-safe Unicode normalization."""
    normalized_quote = _normalize_quote(quote)
    if len(normalized_quote) < MINIMUM_QUOTE_LENGTH:
        raise AnswerValidationError(
            f"Citation quote must contain at least {MINIMUM_QUOTE_LENGTH} characters"
        )
    if normalized_quote not in _normalize_quote(source_text):
        raise AnswerValidationError("Citation quote does not appear in the cited retrieved chunk")


def _normalize_quote(value: str) -> str:
    """Normalize formatting differences while preserving the words being cited."""
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", value)).strip().casefold()


def _first_quote(source_text: str) -> str:
    """Select a sufficiently long exact prefix for the deterministic offline provider."""
    normalized = re.sub(r"\s+", " ", source_text).strip()
    if len(normalized) < MINIMUM_QUOTE_LENGTH:
        raise AnswerValidationError("Retrieved chunk is too short to produce a citation quote")
    sentence_end = re.search(r"[.!?](?:\s|$)", normalized[MINIMUM_QUOTE_LENGTH - 1 :])
    end = MINIMUM_QUOTE_LENGTH + sentence_end.end() - 1 if sentence_end else min(len(normalized), 280)
    return normalized[:end]


def _parse_draft(payload: object) -> AnswerDraft:
    """Parse a JSON-compatible provider payload without accepting implicit defaults."""
    if not isinstance(payload, dict):
        raise AnswerValidationError("Answer provider output must be a JSON object")
    required = {"claims", "abstain", "limitation", "clarification_question"}
    if set(payload) != required:
        raise AnswerValidationError("Answer provider output does not match the required contract")
    raw_claims = payload["claims"]
    if not isinstance(raw_claims, list):
        raise AnswerValidationError("Answer provider claims must be a list")
    claims = tuple(_parse_claim(claim) for claim in raw_claims)
    abstain = payload["abstain"]
    if not isinstance(abstain, bool):
        raise AnswerValidationError("Answer provider abstain must be a boolean")
    limitation = _optional_text(payload["limitation"], "limitation")
    clarification_question = _optional_text(payload["clarification_question"], "clarification_question")
    return AnswerDraft(claims, abstain, limitation, clarification_question)


def _parse_claim(payload: object) -> DraftClaim:
    """Parse one claim and its required citations from provider JSON."""
    if not isinstance(payload, dict) or set(payload) != {"text", "citations"}:
        raise AnswerValidationError("Each answer claim must contain only text and citations")
    text = payload["text"]
    raw_citations = payload["citations"]
    if not isinstance(text, str) or not text.strip() or not isinstance(raw_citations, list):
        raise AnswerValidationError("Each answer claim has invalid text or citations")
    citations = []
    for citation in raw_citations:
        if not isinstance(citation, dict) or set(citation) != {"chunk_id", "quote"}:
            raise AnswerValidationError("Each citation must contain only chunk_id and quote")
        chunk_id, quote = citation["chunk_id"], citation["quote"]
        if not isinstance(chunk_id, str) or not chunk_id or not isinstance(quote, str) or not quote:
            raise AnswerValidationError("Each citation has an invalid chunk_id or quote")
        citations.append(DraftCitation(chunk_id, quote))
    return DraftClaim(text, tuple(citations))


def _optional_text(value: object, field_name: str) -> str | None:
    """Accept a nullable, non-blank optional structured-output field."""
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise AnswerValidationError(f"Answer provider {field_name} must be a non-blank string or null")
    return value


def _instructions() -> str:
    """Return the narrow provider instruction; application validation remains authoritative."""
    return (
        "Responda em português do Brasil usando somente as evidências fornecidas. "
        "Não determine a situação tributária individual do usuário e não diga que ele está "
        "obrigado ou dispensado. Explique a regra de forma condicional e geral. "
        "Preserve todas as condições materiais da evidência, incluindo sujeito, período, "
        "limites, exceções e requisitos de residência quando existirem. "
        "Cada afirmação factual deve ter uma ou mais citações com o chunk_id fornecido e "
        "uma citação literal exata de pelo menos 20 caracteres da evidência. "
        "Nunca invente chunk_id, citação ou regra. Se a evidência não bastar, use abstain=true "
        "e não inclua claims."
    )


def _answer_input(question: str, chunks: Sequence[RetrievedChunk]) -> str:
    """Serialize only retrieved evidence into the provider input; it has no retrieval tools."""
    evidence = [
        {
            "chunk_id": chunk.chunk_id,
            "anchor_key": chunk.anchor_key,
            "authority_level": chunk.authority_level,
            "source_title": chunk.source_title,
            "text": chunk.chunk_text,
        }
        for chunk in chunks
    ]
    return json.dumps({"question": question, "evidence": evidence}, ensure_ascii=False)


def _response_format() -> dict[str, Any]:
    """Return the strict JSON Schema that constrains provider output shape."""
    return {
        "type": "json_schema",
        "name": "taxrag_cited_answer",
        "strict": True,
        "schema": {
            "type": "object",
            "additionalProperties": False,
            "required": ["claims", "abstain", "limitation", "clarification_question"],
            "properties": {
                "claims": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": ["text", "citations"],
                        "properties": {
                            "text": {"type": "string"},
                            "citations": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "additionalProperties": False,
                                    "required": ["chunk_id", "quote"],
                                    "properties": {
                                        "chunk_id": {"type": "string"},
                                        "quote": {"type": "string"},
                                    },
                                },
                            },
                        },
                    },
                },
                "abstain": {"type": "boolean"},
                "limitation": {"type": ["string", "null"]},
                "clarification_question": {"type": ["string", "null"]},
            },
        },
    }
