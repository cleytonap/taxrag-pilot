from pathlib import Path

import pymupdf

from taxrag.extraction import extract_receita_questions_answers_pdf


def test_pdf_extraction_preserves_question_boundaries_and_pages(tmp_path: Path) -> None:
    pdf_path = tmp_path / "questions.pdf"
    document = pymupdf.open()
    first_page = document.new_page()
    first_page.insert_text(
        (72, 72),
        "001 — Quem deve declarar?\nResposta da pergunta um.\n\n"
        "002 — Pessoa desobrigada pode declarar?\nResposta da pergunta dois.",
    )
    second_page = document.new_page()
    second_page.insert_text(
        (72, 72),
        "006 — Existe limite de idade?\nNão há limite de idade.\n\n"
        "007 — Pergunta fora do escopo?\nNão deve ser extraída.",
    )
    document.save(pdf_path)
    document.close()

    result = extract_receita_questions_answers_pdf(pdf_path.read_bytes())

    assert [section.anchor_key for section in result.sections] == [
        "question-001--p1",
        "question-002--p1",
        "question-006--p2",
        "question-007--p2",
    ]
    assert "Resposta da pergunta um." in result.sections[0].text
    assert "Pessoa desobrigada" not in result.sections[0].text
    assert result.sections[-1].anchor_key == "question-007--p2"
    assert result.sections[-1].page_start == 2
    assert result.sections[-1].page_end == 2


def test_official_pdf_snapshot_extracts_every_numbered_question_in_order() -> None:
    """Every Q&A entry gets its own anchor, including headers with irregular separators."""
    source = next(Path("data/source-snapshots/irpf-2026-perguntas-respostas").rglob("*.pdf"))
    result = extract_receita_questions_answers_pdf(source.read_bytes())

    numbers = [
        int(section.anchor_key.split("--", maxsplit=1)[0].removeprefix("question-"))
        for section in result.sections
    ]
    # Strict sequence: a missed header would leave a gap and merge two answers under one
    # citation; a false positive (e.g. a page number) would break the ordering.
    assert numbers == list(range(1, 746))
    assert result.sections[0].anchor_key == "question-001--p23"
    assert result.sections[-1].anchor_key == "question-745--p339"
    by_key = {section.anchor_key: section for section in result.sections}
    # Formerly merged into the previous question ("035 —Quais", "107 - Qual", "341 – Filho").
    assert by_key["question-035--p35"].display_title.startswith("Question 035: Quais são os meios")
    assert by_key["question-107--p60"].display_title.startswith("Question 107: Qual é o prazo")
    assert "Declaração Final de Espólio deve ser apresentada" not in by_key["question-106--p59"].text
    assert by_key["question-341--p176"].display_title.startswith("Question 341: Filho(a)")


def test_section_headings_belong_to_the_question_they_introduce() -> None:
    """v7: headings printed after "Retorno ao sumário" describe the next question (V0 RC4)."""
    source = next(Path("data/source-snapshots/irpf-2026-perguntas-respostas").rglob("*.pdf"))
    sections = {
        section.anchor_key: section
        for section in extract_receita_questions_answers_pdf(source.read_bytes()).sections
    }

    assert "(BETS)" in (sections["question-318--p160"].search_text or "")
    assert "BETS" not in sections["question-317--p159"].text
    assert "PREENCHIMENTO" not in sections["question-025--p31"].text
    assert all("Retorno ao sumário" not in section.text for section in sections.values())
    # Full multi-line titles: the strongest retrieval key of a P&R question.
    assert sections["question-025--p31"].display_title.endswith(
        "está sujeito à multa por atraso na entrega da declaração?"
    )
    assert all(section.display_title.endswith("?") for section in sections.values())
    assert not sections["question-025--p31"].text.startswith("multa por atraso")
