"""Structure-preserving extraction adapters for approved source families."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

import pymupdf
from bs4 import BeautifulSoup, Tag

EXTRACTOR_NAME = "receita-guidance-html"
EXTRACTOR_VERSION = "2"


@dataclass(frozen=True)
class ExtractedSection:
    """One heading-bounded, user-verifiable section of an extracted document."""

    anchor_key: str
    display_title: str
    ordinal: int
    text: str
    page_start: int | None = None
    page_end: int | None = None


@dataclass(frozen=True)
class ExtractionResult:
    """Normalized document content and its heading-level sections."""

    normalized_text: str
    sections: list[ExtractedSection]


def extract_receita_guidance_html(html: bytes) -> ExtractionResult:
    """Extract heading-bounded text from the known Receita guidance-page structure."""
    soup = BeautifulSoup(html, "lxml")
    content_root = soup.select_one("#content-core")
    if content_root is None:
        raise ValueError("Receita guidance HTML does not contain #content-core")

    page_heading = content_root.select_one("h1") or soup.select_one("h1")
    if page_heading is None:
        raise ValueError("Receita guidance HTML does not contain a page heading")

    current_title = _text(page_heading)
    current_blocks: list[str] = []
    sections: list[ExtractedSection] = []

    # Walk semantic elements rather than visual tiles: some Receita tiles contain
    # multiple headings, and each heading must remain a distinct citation anchor.
    for element in content_root.find_all(["h2", "p", "ul", "ol", "table"]):
        if _is_nested_structure(element):
            continue
        if element.name == "h2":
            _append_section(sections, current_title, current_blocks)
            current_title = _text(element)
            current_blocks = []
            continue

        block = _render_element(element)
        if block:
            current_blocks.append(block)

    _append_section(sections, current_title, current_blocks)
    if not sections:
        raise ValueError("Receita guidance HTML did not produce any text sections")

    normalized_text = "\n\n".join(f"{section.display_title}\n{section.text}" for section in sections)
    return ExtractionResult(normalized_text=normalized_text, sections=sections)


# The official PDF uses an em dash. Some valid PDF text extractors expose the same
# visual separator as a middle dot, so accept both while still requiring a 3-digit line start.
QUESTION_HEADER = re.compile(r"(?m)^(?P<number>\d{3})\s+[—·]\s+(?P<title>.+)$")


def extract_receita_questions_answers_pdf(pdf: bytes) -> ExtractionResult:
    """Extract the initial IRPF filing-obligation questions with their PDF page provenance."""
    document = pymupdf.open(stream=pdf, filetype="pdf")
    sections: list[ExtractedSection] = []
    current_number: int | None = None
    current_title = ""
    current_blocks: list[str] = []
    page_start: int | None = None
    page_end: int | None = None

    for page in document:
        page_number = page.number + 1
        page_text = _normalize_pdf_text(page.get_text())
        matches = list(QUESTION_HEADER.finditer(page_text))
        if not matches:
            if current_number is not None:
                current_blocks.append(page_text)
                page_end = page_number
            continue

        cursor = 0
        for match in matches:
            question_number = int(match.group("number"))
            before_question = page_text[cursor : match.start()].strip()
            if current_number is not None and before_question:
                current_blocks.append(before_question)
                page_end = page_number

            _append_pdf_question(
                sections,
                current_number,
                current_title,
                current_blocks,
                page_start,
                page_end,
            )
            if question_number > 6:
                return _pdf_result(sections)

            current_number = question_number
            current_title = _normalize_pdf_text(match.group("title"))
            current_blocks = []
            page_start = page_number
            page_end = page_number
            cursor = match.end()

        trailing_text = page_text[cursor:].strip()
        if current_number is not None and trailing_text:
            current_blocks.append(trailing_text)

    _append_pdf_question(sections, current_number, current_title, current_blocks, page_start, page_end)
    return _pdf_result(sections)


def _append_pdf_question(
    sections: list[ExtractedSection],
    question_number: int | None,
    title: str,
    blocks: list[str],
    page_start: int | None,
    page_end: int | None,
) -> None:
    """Persist one completed numbered PDF question as a page-aware extraction section."""
    if question_number is None:
        return
    text = "\n\n".join(block for block in blocks if block).strip()
    if not text:
        return
    sections.append(
        ExtractedSection(
            anchor_key=f"question-{question_number:03d}--p{page_start}",
            display_title=f"Question {question_number:03d}: {title}",
            ordinal=len(sections) + 1,
            text=text,
            page_start=page_start,
            page_end=page_end,
        )
    )


def _pdf_result(sections: list[ExtractedSection]) -> ExtractionResult:
    """Validate and assemble the normalized PDF extraction result."""
    if not sections:
        raise ValueError("IRPF questions-and-answers PDF did not produce filing-obligation questions")
    normalized_text = "\n\n".join(f"{section.display_title}\n{section.text}" for section in sections)
    return ExtractionResult(normalized_text=normalized_text, sections=sections)


def _append_section(sections: list[ExtractedSection], title: str, blocks: list[str]) -> None:
    """Create a section when its heading has meaningful content."""
    text = "\n\n".join(blocks).strip()
    if not text:
        return
    ordinal = len(sections) + 1
    sections.append(
        ExtractedSection(
            anchor_key=f"{_slugify(title)}--{ordinal:02d}",
            display_title=title,
            ordinal=ordinal,
            text=text,
        )
    )


def _is_nested_structure(element: Tag) -> bool:
    """Avoid rendering table cells, nested lists, and paragraphs inside list items twice."""
    if element.name == "p":
        return element.find_parent(["li", "table"]) is not None
    if element.name in {"ul", "ol"}:
        return element.find_parent(["li", "table"]) is not None
    return element.name == "table" and element.find_parent("table") is not None


def _render_element(element: Tag) -> str:
    """Render one semantic HTML element into normalized, retrieval-ready text."""
    if element.name == "table":
        return _render_table(element)
    if element.name in {"ul", "ol"}:
        return _render_list(element)
    return _text(element)


def _render_list(list_element: Tag) -> str:
    """Render top-level list items as distinct, readable plain-text lines."""
    items = []
    for item in list_element.find_all("li", recursive=False):
        fragment = BeautifulSoup(str(item), "lxml")
        for nested_list in fragment.find_all(["ul", "ol"]):
            nested_list.decompose()
        text = _text(fragment)
        if text:
            items.append(f"- {text}")
    return "\n".join(items)


def _render_table(table: Tag) -> str:
    """Render a table as rows so headers and values remain together in plain text."""
    rows = []
    for row in table.find_all("tr"):
        cells = [_text(cell) for cell in row.find_all(["th", "td"], recursive=False)]
        if cells:
            rows.append(" | ".join(cells))
    return "\n".join(rows)


def _text(element: Tag) -> str:
    """Return normalized visible text from one HTML element."""
    return re.sub(r"\s+", " ", element.get_text(" ").replace("\u00a0", " ")).strip()


def _normalize_text(text: str) -> str:
    """Normalize whitespace without changing the underlying source wording."""
    return "\n".join(
        re.sub(r"[ \t]+", " ", line.replace("\u00a0", " ")).strip()
        for line in text.splitlines()
        if line.strip()
    )


def _normalize_pdf_text(text: str) -> str:
    """Normalize PDF extraction whitespace while preserving page-level line boundaries."""
    return "\n".join(re.sub(r"[ \t]+", " ", line).strip() for line in text.splitlines() if line.strip())


def _slugify(value: str) -> str:
    """Create a predictable ASCII key from a user-visible heading."""
    normalized = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", normalized.lower()).strip("-")
