"""Deterministic Portuguese-only gate for user questions.

Product scope is Brazilian IRPF questions asked in Portuguese. Questions in another language
get a fixed, bilingual notice instead of a retrieval attempt over a Portuguese-only corpus
(V0 showed such questions retrieve unrelated chunks).

Design: precision over recall. A Portuguese question must never be refused, including
informal, accent-free or keyword-only ones and ones with English loanwords ("bets",
"day trade", "PGBL"). The gate therefore flags a question only when it has several distinctive
words of English or Spanish and clearly outweighs the Portuguese evidence. Anything uncertain
(short queries, mixed text) is treated as Portuguese and answered normally. No model or
dependency is involved, so the behaviour is explainable and unit-tested.
"""

from __future__ import annotations

import re

# Words that are common in questions and distinctive for each language. Words shared between
# Portuguese and Spanish (de, que, se, para, como, no...) are deliberately absent.
PORTUGUESE = frozenset(
    ["não", "nao", "você", "voce", "vocês", "meu", "minha", "meus", "minhas", "sou", "tenho", "tive", "preciso", "posso", "devo", "é", "são", "estou", "está", "estão", "foi", "fui", "qual", "quais", "quanto", "quanta", "quantos", "quando", "onde", "quem", "pra", "pro", "pelo", "pela", "pelos", "pelas", "ao", "aos", "à", "às", "do", "da", "dos", "das", "na", "nas", "num", "numa", "uma", "uns", "umas", "ou", "isso", "esse", "essa", "este", "esta", "também", "tambem", "mas", "já", "ja", "ainda", "até", "ate", "sobre", "entre", "declaração", "declaracao", "declarar", "declarei", "imposto", "renda", "receita", "obrigado", "obrigada", "rendimento", "rendimentos", "ano", "anos", "mês", "mes", "mil", "reais", "prazo", "multa", "pagar", "paguei", "recebi", "vendi", "comprei", "filho", "filha", "mãe", "mae", "pai", "dependente", "restituição", "restituicao"]
)
ENGLISH = frozenset(
    ["the", "is", "are", "was", "were", "be", "been", "do", "does", "did", "i", "my", "me", "you", "your", "we", "our", "they", "their", "it", "its", "what", "how", "when", "where", "which", "who", "whom", "why", "can", "could", "should", "would", "will", "shall", "must", "have", "has", "had", "if", "in", "on", "of", "to", "for", "from", "with", "without", "and", "or", "not", "about", "this", "that", "these", "those", "there", "income", "tax", "taxes", "return", "returns", "file", "filing", "need", "brazil", "brazilian", "resident", "earned", "earn", "pay", "paid", "owe", "deadline", "penalty", "deduct", "deduction", "deductions", "expenses", "medical", "refund", "salary", "dependents", "sold", "bought", "house", "property", "gains"]
)
SPANISH = frozenset(
    ["el", "los", "las", "del", "al", "y", "es", "son", "está", "están", "soy", "tengo", "tuve", "puedo", "debo", "necesito", "qué", "cómo", "cuál", "cuáles", "cuánto", "cuándo", "dónde", "quién", "usted", "ustedes", "mi", "mis", "su", "sus", "pero", "también", "muy", "hay", "impuesto", "impuestos", "renta", "declaración", "declarar", "ingresos", "año", "años", "pagar", "multa", "plazo"]
)
# Spanish forms that Portuguese never uses; they outweigh shared words such as "declarar".
SPANISH_ONLY = frozenset(
    ["el", "los", "las", "del", "y", "es", "son", "soy", "tengo", "tuve", "puedo", "necesito", "qué", "cómo", "cuál", "cuáles", "cuánto", "cuándo", "dónde", "quién", "usted", "ustedes", "pero", "muy", "hay", "impuesto", "impuestos", "ingresos", "año", "años", "declaración", "plazo", "mi", "mis", "si", "vendí", "compré"]
)
WORD = re.compile(r"[a-zà-öø-ÿ]+", re.IGNORECASE)

UNSUPPORTED_LANGUAGE_MESSAGE = (
    "Este assistente responde apenas a perguntas em português sobre o Imposto sobre a Renda da "
    "Pessoa Física (IRPF 2026). Por favor, reescreva sua pergunta em português.\n\n"
    "This assistant only answers questions written in Portuguese. / Este asistente solo "
    "responde preguntas en portugués."
)


def detect_unsupported_language(question: str) -> str | None:
    """Return "en" or "es" when the question is confidently not Portuguese, else None."""
    words = [word.lower() for word in WORD.findall(question)]
    if len(words) < 4:
        return None  # too short to judge; never refuse a terse Portuguese query
    portuguese = sum(word in PORTUGUESE for word in words)
    # Portuguese-only letters are strong evidence (ã, õ, ç, ê, ô).
    if re.search(r"[ãõçêô]", question, re.IGNORECASE):
        portuguese += 2
    english = sum(word in ENGLISH for word in words)
    spanish = sum(word in SPANISH_ONLY for word in words)
    if re.search(r"[ñ¿¡]|ción\b", question, re.IGNORECASE):
        spanish += 2
    for language, score in (("en", english), ("es", spanish)):
        if score >= 3 and score > 2 * portuguese and score / len(words) >= 0.25:
            return language
    return None
