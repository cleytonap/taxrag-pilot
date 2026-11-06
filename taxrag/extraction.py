"""Structure-preserving extraction adapters for approved source families."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

import pymupdf
from bs4 import BeautifulSoup, Tag

EXTRACTOR_NAME = "source-family-extractors"
EXTRACTOR_VERSION = "7"


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
    # Sections such as "Você está obrigado se:" only make sense under the page title; index them
    # with it (citation text is unchanged).
    page_title = _text(page_heading)
    sections = [
        section
        if section.display_title == page_title
        else ExtractedSection(
            anchor_key=section.anchor_key,
            display_title=section.display_title,
            ordinal=section.ordinal,
            text=section.text,
            search_text=f"{page_title}\n{section.text}",
        )
        for section in sections
    ]

    normalized_text = "\n\n".join(f"{section.display_title}\n{section.text}" for section in sections)
    return ExtractionResult(normalized_text=normalized_text, sections=sections)


DOU_ARTICLE_TWO = re.compile(r"^Art\. 2(?:º|o)\s+(?P<text>.+)$", re.IGNORECASE)
DOU_ARTICLE = re.compile(r"^Art\.\s+(?P<number>\d+)(?:º|o|\.)?(?:\s|$)", re.IGNORECASE)
DOU_PARAGRAPH = re.compile(r"^§\s*(?P<number>\d+)º\s+(?P<text>.+)$")
DOU_INCISO = re.compile(r"^(?P<roman>[IVXLCDM]+)\s*-\s+(?P<text>.+)$")
DOU_ALINEA = re.compile(r"^[a-z]\)\s+.+$", re.IGNORECASE)

def extract_dou_in_rfb_2312_html(html: bytes) -> ExtractionResult:
    """Extract all articles (1–17) from the official DOU publication of IN RFB 2.312.

    Art. 2 is chunked at the inciso/parágrafo level because each inciso is a distinct
    filing-obligation criterion that benefits from individual retrieval. Each inciso chunk
    repeats the article caput and, when applicable, its paragraph lead-in so a retrieved
    citation is self-contained.

    Arts. 1 and 3–17 are each stored as a single chunk covering the full article text,
    including amending provisions, so the extracted source remains complete.
    """
    soup = BeautifulSoup(html, "lxml")
    paragraphs = [_text(element) for element in soup.select("p.dou-paragraph")]
    article_index = next(
        (index for index, text in enumerate(paragraphs) if DOU_ARTICLE_TWO.match(text)), None
    )
    if article_index is None:
        raise ValueError("DOU HTML does not contain Art. 2 of IN RFB 2.312/2026")

    # --- Art. 2 fine-grained extraction (inciso/parágrafo level) ---
    article_match = DOU_ARTICLE_TWO.match(paragraphs[article_index])
    assert article_match is not None
    article_caput = paragraphs[article_index]
    sections: list[ExtractedSection] = [
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
                # v7: the indexed text keeps the legal lead-in. Without it an inciso such as
                # "V - relativamente à atividade rural: ... receita bruta ..." loses its meaning
                # ("está obrigada a apresentar") for embeddings; length-normalised lexical
                # ranking no longer needs the caput stripped (see 2026-11-06 spec).
                search_text="\n".join(context),
            )
        )

    art2_end_index = article_index + 1
    for text in paragraphs[article_index + 1 :]:
        art2_end_index += 1
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

    chapters = _chapter_headings(paragraphs)
    if 2 in chapters:
        sections[0] = ExtractedSection(
            anchor_key=sections[0].anchor_key,
            display_title=sections[0].display_title,
            ordinal=sections[0].ordinal,
            text=sections[0].text,
            search_text=f"{chapters[2]}\n{sections[0].text}",
        )

    # --- Arts. 1 and 3–17: one chunk per article ---
    # Walk from the beginning of the paragraph list to collect Art. 1, then from
    # the end of Art. 2 onwards for Arts. 3–14. Articles are stored in source order.
    _collect_whole_articles(paragraphs, sections, 0, article_index, chapters)
    _collect_whole_articles(paragraphs, sections, art2_end_index - 1, len(paragraphs), chapters)

    # Re-sort by temporary ordinal, then assign unique contiguous values required
    # by the database's per-source uniqueness constraints.
    sections.sort(key=lambda s: s.ordinal)
    sections = [
        ExtractedSection(
            anchor_key=section.anchor_key,
            display_title=section.display_title,
            ordinal=index,
            text=section.text,
            page_start=section.page_start,
            page_end=section.page_end,
            search_text=section.search_text,
        )
        for index, section in enumerate(sections, start=1)
    ]

    normalized_text = "\n\n".join(f"{section.display_title}\n{section.text}" for section in sections)
    return ExtractionResult(normalized_text=normalized_text, sections=sections)


DOU_CHAPTER = re.compile(r"^CAP[ÍI]TULO\s+[IVXLC]+$")


def _chapter_headings(paragraphs: list[str]) -> dict[int, str]:
    """Map each article number to the chapter heading printed immediately before it.

    In the DOU HTML a chapter marker ("CAPÍTULO X") and its title are separate paragraphs
    placed after the previous article. They describe the *next* article, so they are used as
    that article's retrieval context and excluded from the previous article's text.
    """
    headings: dict[int, str] = {}
    pending: str | None = None
    for index, text in enumerate(paragraphs):
        if DOU_CHAPTER.match(text):
            title = paragraphs[index + 1] if index + 1 < len(paragraphs) else ""
            pending = f"{text} - {title}" if title and not DOU_ARTICLE.match(title) else text
            continue
        article = DOU_ARTICLE.match(text)
        if article and pending:
            headings[int(article.group("number"))] = pending
            pending = None
    return headings


def _collect_whole_articles(
    paragraphs: list[str],
    sections: list[ExtractedSection],
    start: int,
    end: int,
    chapters: dict[int, str],
) -> None:
    """Collect paragraphs between consecutive article markers as single-chunk sections.

    Skips Art. 2, which is handled separately at inciso/parágrafo level, and chapter headings,
    which belong to the following article's retrieval context.
    """
    current_number: int | None = None
    current_blocks: list[str] = []
    skip_chapter_title = False

    def flush() -> None:
        if current_number is None or not current_blocks:
            return
        text = "\n".join(current_blocks).strip()
        if not text:
            return
        # Temporary sort keys place whole articles around Art. 2's finer-grained chunks.
        ordinal = 0 if current_number == 1 else 1000 + current_number
        chapter = chapters.get(current_number)
        sections.append(
            ExtractedSection(
                anchor_key=f"art-{current_number}-caput",
                display_title=f"Art. {current_number}",
                ordinal=ordinal,
                text=text,
                search_text=f"{chapter}\n{text}" if chapter else None,
            )
        )

    for text in paragraphs[start:end]:
        if DOU_CHAPTER.match(text):
            skip_chapter_title = True
            continue
        if skip_chapter_title:
            skip_chapter_title = False
            if not DOU_ARTICLE.match(text):
                continue
        m = DOU_ARTICLE.match(text)
        if m:
            number = int(m.group("number"))
            flush()
            if number == 2:
                # Art. 2 is chunked separately; every other article remains indexed.
                current_number = None
                current_blocks = []
                continue
            current_number = number
            current_blocks = [text]
        elif current_number is not None:
            current_blocks.append(text)

    flush()


def _paragraph_key(label: str) -> str:
    """Convert a visible paragraph label such as ``§ 1º`` into a stable key fragment."""
    return f"paragrafo-{label.split()[1].rstrip('º')}"


# The official PDF mostly uses "NNN — Title", but 11 of its 745 headers use a hyphen or
# en dash, or omit the space after the separator (e.g. "035 —Quais", "107 - Qual", "528—").
# Missing them silently merged those questions into the preceding question's chunk under the
# wrong citation anchor. Separators are matched only within one line ([ \t]*, not \s*): a page
# number followed by a bulleted "- 20%" line must not be mistaken for a question header.
QUESTION_HEADER = re.compile(r"(?m)^(?P<number>\d{3})[ \t]*[—·–-][ \t]*(?P<title>\S.*)$")


def extract_receita_questions_answers_pdf(pdf: bytes) -> ExtractionResult:
    """Extract all IRPF questions from the official Perguntas e Respostas PDF with page provenance.

    The P&R manual contains 745 numbered questions covering every IRPF topic. Each question
    becomes one anchor-keyed chunk whose key embeds the question number and start page, so
    citations are verifiable in the original PDF.

    Layout handled explicitly (extractor v7):
    - Each answer ends with a "Retorno ao sumário" link. Section headings printed after that link
      (e.g. "PRÊMIOS EM DINHEIRO – LOTERIAS DE APOSTAS DE QUOTA FIXA (BETS)") describe the *next*
      question. They become that question's retrieval context instead of polluting the previous
      answer.
    - Question titles often wrap onto several lines; the full title is kept in the display title.
    - Page numbers (first line of each page) and the navigation link are dropped from the text.
    """
    document = pymupdf.open(stream=pdf, filetype="pdf")
    sections: list[ExtractedSection] = []
    question: dict[str, object] | None = None
    pending_heading: list[str] = []
    answer_closed = False

    def finish() -> None:
        if question is not None:
            _append_pdf_question(sections, question)

    for page in document:
        page_number = page.number + 1
        lines = _normalize_pdf_text(page.get_text()).splitlines()
        if lines and lines[0] == str(page_number):
            lines = lines[1:]
        if question is None:
            # Before the first question, only the headings on its own page describe it (earlier
            # pages are the table of contents).
            pending_heading = []
            answer_closed = True
        index = 0
        while index < len(lines):
            line = lines[index]
            header = QUESTION_HEADER.match(line)
            if header:
                finish()
                title = [_normalize_pdf_text(header.group("title"))]
                index += 1
                # Consume wrapped title lines up to the question mark (bounded, so a title
                # without "?" never swallows the answer).
                if not title[0].endswith("?"):
                    lookahead = lines[index : index + 8]
                    end = next(
                        (offset for offset, item in enumerate(lookahead) if item.endswith("?")),
                        None,
                    )
                    if end is not None:
                        title.extend(lookahead[: end + 1])
                        index += end + 1
                question = {
                    "number": int(header.group("number")),
                    "title": " ".join(title),
                    "heading": " / ".join(pending_heading),
                    "lines": [],
                    "page_start": page_number,
                    "page_end": page_number,
                }
                pending_heading = []
                answer_closed = False
                continue
            if line == "Retorno ao sumário":
                answer_closed = True
            elif answer_closed:
                pending_heading.append(line)
            elif question is not None:
                question["lines"].append(line)  # type: ignore[union-attr]
                question["page_end"] = page_number
            index += 1

    finish()
    return _pdf_result(sections)


def _append_pdf_question(sections: list[ExtractedSection], question: dict[str, object]) -> None:
    """Persist one completed numbered PDF question as a page-aware extraction section."""
    text = "\n".join(question["lines"]).strip()  # type: ignore[arg-type]
    if not text:
        return
    number = question["number"]
    heading = question["heading"]
    title = f"Question {number:03d}: {question['title']}"
    sections.append(
        ExtractedSection(
            anchor_key=f"question-{number:03d}--p{question['page_start']}",
            display_title=title,
            ordinal=len(sections) + 1,
            text=text,
            page_start=question["page_start"],  # type: ignore[arg-type]
            page_end=question["page_end"],  # type: ignore[arg-type]
            # Retrieval context: the manual's own topic heading for this question. The title is
            # added to the indexed text by processing, so it is not repeated here.
            search_text=f"{heading}\n{text}" if heading else None,
        )
    )


def _pdf_result(sections: list[ExtractedSection]) -> ExtractionResult:
    """Validate and assemble the normalized PDF extraction result."""
    if not sections:
        raise ValueError("IRPF questions-and-answers PDF did not produce any questions")
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
