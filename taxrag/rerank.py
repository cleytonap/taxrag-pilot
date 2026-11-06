"""LLM listwise reranking of hybrid retrieval candidates.

V1 RCA: semantic recall@3 was 87% but recall@10 of the lexical+semantic union was 100%. Every
miss was an ordering error in which a chunk on the same *topic* (how to declare foreign
investments, how the 65+ exemption works) outranked the chunk that answers the *question*
(is this a filing obligation? is there an age rule?). Vector similarity and keyword scores cannot
tell these apart. A model reading the question and the candidates together can.

Design:
- Candidates come from both retrievers, so the reranker only reorders; it never adds content.
- One structured-output call per question with short previews (about US$0.002 with gpt-4.1-mini).
- Any failure (network, malformed output) falls back to the fused order. A reranker outage
  degrades quality but never breaks retrieval.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Sequence
from typing import Protocol

from openai import OpenAI

from taxrag.config import settings

logger = logging.getLogger(__name__)
PREVIEW_CHARACTERS = 900


class Reranker(Protocol):
    """Orders candidate passages by how directly they answer a question."""

    model: str

    def rerank(self, question: str, passages: Sequence[str]) -> list[int]:
        """Return candidate indexes, best first (may omit irrelevant ones)."""


class OpenAIReranker:
    """Listwise reranker using strict JSON Schema structured output."""

    def __init__(self, api_key: str | None, model: str) -> None:
        self._api_key = api_key
        self.model = model

    def rerank(self, question: str, passages: Sequence[str]) -> list[int]:
        """Ask the model for an ordering of passage ids; validated by ``ordered_indexes``."""
        if not self._api_key:
            raise RuntimeError("OPENAI_API_KEY is required for reranking")
        listing = "\n\n".join(
            f"[P{index}]\n{_preview(text)}" for index, text in enumerate(passages, start=1)
        )
        response = OpenAI(api_key=self._api_key).responses.create(
            model=self.model,
            instructions=RERANK_INSTRUCTIONS,
            input=f"Pergunta do usuário:\n{question}\n\nTrechos candidatos:\n\n{listing}",
            text={"format": RERANK_FORMAT},
            temperature=0,
            store=False,
        )
        payload = json.loads(getattr(response, "output_text", "") or "{}")
        return ordered_indexes(payload.get("ranking", []), len(passages))


def ordered_indexes(ranking: Sequence[object], count: int) -> list[int]:
    """Turn ["P3", "P1", ...] into 0-based indexes, dropping invalid or repeated ids."""
    seen: list[int] = []
    for item in ranking:
        if isinstance(item, str) and item.upper().startswith("P") and item[1:].isdigit():
            index = int(item[1:]) - 1
            if 0 <= index < count and index not in seen:
                seen.append(index)
    return seen


def rerank_order(reranker: Reranker | None, question: str, passages: Sequence[str]) -> list[int]:
    """Full ordering: reranked indexes first, then the remaining candidates in fused order."""
    ranked: list[int] = []
    if reranker is not None and passages:
        try:
            ranked = reranker.rerank(question, passages)
        except Exception as error:  # noqa: BLE001 - any reranker failure must fall back safely
            logger.warning("Reranker failed; using fused order: %s", error)
            ranked = []
    return ranked + [index for index in range(len(passages)) if index not in ranked]


def configured_reranker() -> OpenAIReranker:
    """Build the configured reranker lazily (no network call until used)."""
    return OpenAIReranker(settings.openai_api_key, settings.rerank_model)


def _preview(text: str) -> str:
    compact = " ".join(text.split())
    return compact if len(compact) <= PREVIEW_CHARACTERS else compact[:PREVIEW_CHARACTERS] + "…"


RERANK_INSTRUCTIONS = (
    "Você ordena trechos oficiais sobre o Imposto sobre a Renda da Pessoa Física (IRPF 2026) "
    "para um assistente que responde perguntas de contribuintes. Ordene os trechos do mais útil "
    "ao menos útil para responder EXATAMENTE à pergunta feita. Critérios, em ordem: "
    "1) o trecho responde à pergunta específica (a mesma situação, a mesma regra perguntada), "
    "e não apenas trata do mesmo assunto: por exemplo, se a pergunta é se algo obriga a "
    "declarar, prefira o trecho sobre obrigatoriedade ao trecho sobre como tributar ou "
    "declarar aquele item; "
    "2) se a pergunta parte de uma premissa, prefira o trecho que confirma ou corrige a premissa; "
    "3) entre trechos igualmente diretos, prefira a norma (Instrução Normativa) ou a pergunta "
    "do Perguntas e Respostas cujo título corresponde à pergunta. "
    "Inclua em ranking os identificadores (P1, P2, ...) de pelo menos os 8 trechos mais úteis, "
    "em ordem; não invente identificadores."
)
RERANK_FORMAT = {
    "type": "json_schema",
    "name": "passage_ranking",
    "strict": True,
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "properties": {"ranking": {"type": "array", "items": {"type": "string"}}},
        "required": ["ranking"],
    },
}
