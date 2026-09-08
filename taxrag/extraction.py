"""Structure-preserving extraction adapters for approved source families."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

import pymupdf
from bs4 import BeautifulSoup, Tag

EXTRACTOR_NAME = "source-family-extractors"
EXTRACTOR_VERSION = "4"


@dataclass(frozen=True)
class ExtractedSection:
    """One heading-bounded, user-verifiable section of an extracted document."""

    anchor_key: str
    display_title: str
    ordinal: int
    text: str
    page_start: int | None = None
    page_end: int | None = None
    search_text: str | None = None


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


DOU_ARTICLE_TWO = re.compile(r"^Art\. 2(?:º|o)\s+(?P<text>.+)$", re.IGNORECASE)
DOU_ARTICLE = re.compile(r"^Art\.\s+\d+(?:º|o)?\s+", re.IGNORECASE)
DOU_PARAGRAPH = re.compile(r"^§\s*(?P<number>\d+)º\s+(?P<text>.+)$")
DOU_INCISO = re.compile(r"^(?P<roman>[IVXLCDM]+)\s*-\s+(?P<text>.+)$")
DOU_ALINEA = re.compile(r"^[a-z]\)\s+.+$", re.IGNORECASE)


def extract_dou_in_rfb_2312_html(html: bytes) -> ExtractionResult:
    """Extract Art. 2 legal units from the official DOU HTML publication.

    Each inciso repeats the article caput and, when applicable, its paragraph lead-in.
    This makes a retrieved citation understandable without relying on neighboring chunks.
    """
    soup = BeautifulSoup(html, "lxml")
    paragraphs = [_text(element) for element in soup.select("p.dou-paragraph")]
    article_index = next(
        (index for index, text in enumerate(paragraphs) if DOU_ARTICLE_TWO.match(text)), None
    )
    if article_index is None:
        raise ValueError("DOU HTML does not contain Art. 2 of IN RFB 2.312/2026")

    article_match = DOU_ARTICLE_TWO.match(paragraphs[article_index])
    assert article_match is not None
    article_caput = paragraphs[article_index]
    sections = [
        ExtractedSection(
            anchor_key="art-2-caput",
            display_title="Art. 2, caput",
            ordinal=1,
            text=article_caput,
        )
    ]
    current_paragraph_label: str | None = None
    current_paragraph_text: str | None = None
    current_inciso_label: str | None = None
    current_inciso_blocks: list[str] = []

    def append_inciso() -> None:
        """Persist the current inciso with all necessary article and paragraph context."""
        if current_inciso_label is None:
            return
        context = [article_caput]
        if current_paragraph_text is not None:
            context.append(current_paragraph_text)
        context.extend(current_inciso_blocks)
        label = (
            f"Art. 2, {current_paragraph_label}, inciso {current_inciso_label}"
            if current_paragraph_label
            else f"Art. 2, inciso {current_inciso_label}"
        )
        key = (
            f"art-2-{_paragraph_key(current_paragraph_label)}-inciso-"
            f"{current_inciso_label.lower()}"
            if current_paragraph_label
            else f"art-2-inciso-{current_inciso_label.lower()}"
        )
        sections.append(
            ExtractedSection(
                anchor_key=key,
                display_title=label,
                ordinal=len(sections) + 1,
                text="\n".join(context),
                # Citation text retains inherited legal context. Search text must not:
                # otherwise every inciso matches the repeated article caput equally.
                search_text="\n".join(current_inciso_blocks),
            )
        )

    for text in paragraphs[article_index + 1 :]:
        if DOU_ARTICLE.match(text):
            break
        paragraph_match = DOU_PARAGRAPH.match(text)
        if paragraph_match:
            append_inciso()
            current_inciso_label = None
            current_inciso_blocks = []
            current_paragraph_label = f"§ {paragraph_match.group('number')}º"
            current_paragraph_text = text
            sections.append(
                ExtractedSection(
                    anchor_key=f"art-2-{_paragraph_key(current_paragraph_label)}",
                    display_title=f"Art. 2, {current_paragraph_label}",
                    ordinal=len(sections) + 1,
                    text=f"{article_caput}\n{text}",
                    search_text=text,
                )
            )
            continue
        inciso_match = DOU_INCISO.match(text)
        if inciso_match:
            append_inciso()
            current_inciso_label = inciso_match.group("roman")
            current_inciso_blocks = [text]
            continue
        if current_inciso_label is not None:
            current_inciso_blocks.append(text)
        elif DOU_ALINEA.match(text):
            raise ValueError("DOU alinea appeared without a parent inciso")

    append_inciso()
    normalized_text = "\n\n".join(f"{section.display_title}\n{section.text}" for section in sections)
    return ExtractionResult(normalized_text=normalized_text, sections=sections)


def _paragraph_key(label: str) -> str:
    """Convert a visible paragraph label such as ``§ 1º`` into a stable key fragment."""
    return f"paragrafo-{label.split()[1].rstrip('º')}"


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
