from pathlib import Path

from taxrag.extraction import extract_dou_in_rfb_2312_html

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "dou_in_rfb_2312_art_2.html"


def test_dou_extraction_preserves_article_paragraph_and_inciso_boundaries() -> None:
    """Legal anchors retain enough parent context to be understood in isolation."""
    result = extract_dou_in_rfb_2312_html(FIXTURE_PATH.read_bytes())

    assert [section.anchor_key for section in result.sections] == [
        "art-2-caput",
        "art-2-inciso-i",
        "art-2-inciso-iv",
        "art-2-paragrafo-1",
        "art-2-paragrafo-1-inciso-i",
        "art-2-paragrafo-1-inciso-ii",
        "art-2-paragrafo-2",
        "art-2-paragrafo-3",
    ]
    stock_operations = result.sections[2]
    assert stock_operations.display_title == "Art. 2, inciso IV"
    assert "Art. 2º Está obrigada" in stock_operations.text
    assert "a) cuja soma foi superior a R$ 40.000,00" in stock_operations.text
    assert "b) com apuração de ganhos líquidos" in stock_operations.text

    dependent_exception = result.sections[5]
    assert dependent_exception.display_title == "Art. 2, § 1º, inciso II"
    assert "§ 1º Fica dispensada" in dependent_exception.text
    assert "Art. 2º Está obrigada" in dependent_exception.text


def test_dou_extraction_stops_before_the_next_article() -> None:
    """The first normative slice is deliberately scoped to filing-obligation Article 2."""
    result = extract_dou_in_rfb_2312_html(FIXTURE_PATH.read_bytes())

    assert "Art. 3º" not in result.normalized_text
