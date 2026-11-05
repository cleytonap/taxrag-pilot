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


def test_official_pdf_snapshot_extracts_every_detected_question_header() -> None:
    """The full source remains covered through its last numbered Q&A entry."""
    source = next(Path("data/source-snapshots/irpf-2026-perguntas-respostas").rglob("*.pdf"))
    result = extract_receita_questions_answers_pdf(source.read_bytes())

    assert len(result.sections) == 734
    assert result.sections[0].anchor_key == "question-001--p23"
    assert result.sections[-1].anchor_key == "question-745--p339"
    extracted_numbers = {
        int(section.anchor_key.split("--", maxsplit=1)[0].removeprefix("question-"))
        for section in result.sections
    }
    assert set(range(1, 746)) - extracted_numbers == {
        35,
        107,
        341,
        466,
        504,
        528,
        584,
        603,
        634,
        644,
        645,
    }
