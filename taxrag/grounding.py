"""Deterministic check that figures in an answer claim come from its evidence.

Citation provenance ("the cited chunk was retrieved") does not prove support: V0 produced
"R$ 81.000,00" (an MEI limit from model memory) cited to a chunk that never mentions it.
Amounts, percentages and dates are the highest-stakes facts in tax answers and the easiest to
verify mechanically, so every such figure in a claim must appear in the claim's cited evidence or
in the user's question, or be simple arithmetic on those (e.g. "R$ 3 mil por mês" -> R$ 36.000,00).

This is a safety net, not proof of correctness: wording-level misuse of evidence still needs the
human/LLM-judge review described in docs/evals/README.md.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from itertools import combinations_with_replacement

MONTHS = {
    "janeiro": 1, "fevereiro": 2, "março": 3, "marco": 3, "abril": 4, "maio": 5, "junho": 6,
    "julho": 7, "agosto": 8, "setembro": 9, "outubro": 10, "novembro": 11, "dezembro": 12,
}
# Brazilian formatted amount (thousands with dots, optional cents): 35.584,00 / 165,74 / 800
AMOUNT = r"\d{1,3}(?:\.\d{3})+(?:,\d{1,2})?|\d+(?:,\d{1,2})?"
CLAIM_MONEY = re.compile(rf"R\$\s*({AMOUNT})(?:\s*(mil|milhões|milhão|bilhões|bilhão))?", re.IGNORECASE)
EVIDENCE_AMOUNT = re.compile(rf"({AMOUNT})(?:\s*(mil|milhões|milhão))?", re.IGNORECASE)
PERCENT = re.compile(r"(\d+(?:,\d+)?)\s*%|(\d+(?:,\d+)?)\s+por\s+cento", re.IGNORECASE)
DATE_TEXT = re.compile(r"\b(\d{1,2})º?\s+de\s+(" + "|".join(MONTHS) + r")\b", re.IGNORECASE)
DATE_NUMERIC = re.compile(r"\b(\d{1,2})/(\d{1,2})/\d{2,4}\b")
MULTIPLIERS = {"mil": 1_000, "milhão": 1_000_000, "milhões": 1_000_000, "bilhão": 1e9, "bilhões": 1e9}


def _value(number: str, unit: str | None = None) -> float:
    """Parse a Brazilian-formatted number, applying a spoken multiplier such as "mil"."""
    value = float(number.replace(".", "").replace(",", "."))
    return value * MULTIPLIERS.get((unit or "").lower(), 1)


def _amounts(text: str, pattern: re.Pattern[str]) -> set[float]:
    return {_value(match.group(1), match.group(2)) for match in pattern.finditer(text)}


def _percents(text: str) -> set[float]:
    return {_value(match.group(1) or match.group(2)) for match in PERCENT.finditer(text)}


def _dates(text: str) -> set[tuple[int, int]]:
    dates = {(int(day), MONTHS[month.lower()]) for day, month in DATE_TEXT.findall(text)}
    dates |= {(int(day), int(month)) for day, month in DATE_NUMERIC.findall(text)}
    return dates


def _derivable(value: float, known: set[float], question_amounts: set[float]) -> bool:
    """Whether a value is known, or one simple arithmetic step away from known values."""
    if any(abs(value - item) < 0.01 for item in known):
        return True
    # Annualising a monthly amount from the question (x2..x13, e.g. 12 months or 13th salary).
    if any(abs(value - item * factor) < 0.01 for item in question_amounts for factor in range(2, 14)):
        return True
    # One sum or difference of two known amounts (e.g. a total or how far above a limit).
    return any(
        abs(value - (a + b)) < 0.01 or abs(value - abs(a - b)) < 0.01
        for a, b in combinations_with_replacement(known, 2)
    )


def unsupported_figures(claim: str, evidence: Sequence[str], question: str = "") -> list[str]:
    """Return the money amounts, percentages and dates in a claim that lack support."""
    source = "\n".join(evidence)
    question_amounts = _amounts(question, EVIDENCE_AMOUNT)
    known_amounts = _amounts(source, EVIDENCE_AMOUNT) | question_amounts
    problems = [
        match.group(0)
        for match in CLAIM_MONEY.finditer(claim)
        if not _derivable(_value(match.group(1), match.group(2)), known_amounts, question_amounts)
    ]
    known_percents = _percents(source) | _percents(question)
    problems += [
        match.group(0)
        for match in PERCENT.finditer(claim)
        if _value(match.group(1) or match.group(2)) not in known_percents
    ]
    known_dates = _dates(source) | _dates(question)
    problems += [
        match.group(0)
        for match in list(DATE_TEXT.finditer(claim)) + list(DATE_NUMERIC.finditer(claim))
        if next(iter(_dates(match.group(0)))) not in known_dates
    ]
    return problems
