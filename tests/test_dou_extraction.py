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
        "art-3-caput",
    ]
    stock_operations = result.sections[2]
    assert stock_operations.display_title == "Art. 2, inciso IV"
    assert "Art. 2º Está obrigada" in stock_operations.text
    assert "a) cuja soma foi superior a R$ 40.000,00" in stock_operations.text
    assert "b) com apuração de ganhos líquidos" in stock_operations.text
    # v7: indexed text keeps the legal lead-in so the inciso means "obliged to file" on its own
    # (V0 RCA, RC3); the citation text is unchanged.
    assert stock_operations.search_text.startswith("Art. 2º Está obrigada")
    assert stock_operations.search_text.endswith(stock_operations.text.splitlines()[-1])
    assert "IV - realizou operações" in stock_operations.search_text

    dependent_exception = result.sections[5]
    assert dependent_exception.display_title == "Art. 2, § 1º, inciso II"
    assert "§ 1º Fica dispensada" in dependent_exception.text
    assert "Art. 2º Está obrigada" in dependent_exception.text

    art3 = result.sections[8]
    assert art3.display_title == "Art. 3"
    assert art3.anchor_key == "art-3-caput"
    assert "desconto simplificado" in art3.text


def test_dou_extraction_includes_amending_articles() -> None:
    """Amending provisions remain retrievable as part of the complete official source."""
    html = """
    <html><body>
    <p class="dou-paragraph">Art. 1º Disposições gerais.</p>
    <p class="dou-paragraph">Art. 2º Está obrigada a apresentar a declaração:</p>
    <p class="dou-paragraph">I - rendimentos tributáveis acima de 35 mil;</p>
    <p class="dou-paragraph">Art. 14. O contribuinte pode autorizar procurador.</p>
    <p class="dou-paragraph">Art. 15. Altera a Instrução Normativa SRF nº 81.</p>
    <p class="dou-paragraph">Art. 16. Altera a Instrução Normativa SRF nº 208.</p>
    <p class="dou-paragraph">Art. 17. Entra em vigor na data de publicação.</p>
    </body></html>
    """.encode()
    result = extract_dou_in_rfb_2312_html(html)
    anchor_keys = [section.anchor_key for section in result.sections]

    assert "art-1-caput" in anchor_keys
    assert "art-2-caput" in anchor_keys
    assert "art-14-caput" in anchor_keys
    assert "art-15-caput" in anchor_keys
    assert "art-16-caput" in anchor_keys
    assert "art-17-caput" in anchor_keys


def test_official_dou_snapshot_has_all_substantive_articles_and_unique_ordinals() -> None:
    """The checked-in official snapshot exercises the complete instrument, not a toy sample."""
    source = next(Path("data/source-snapshots/irpf-2026-in-rfb-2312").rglob("original.html"))
    result = extract_dou_in_rfb_2312_html(source.read_bytes())
    keys = {section.anchor_key for section in result.sections}

    assert {f"art-{number}-caput" for number in range(1, 18)} <= keys
    assert [section.ordinal for section in result.sections] == list(
        range(1, len(result.sections) + 1)
    )


def test_chapter_headings_index_the_article_they_introduce() -> None:
    """v7: "CAPÍTULO X ..." is context for the next article, not trailing text of the previous."""
    source = next(Path("data/source-snapshots/irpf-2026-in-rfb-2312").rglob("original.html"))
    sections = {
        section.anchor_key: section for section in extract_dou_in_rfb_2312_html(source.read_bytes()).sections
    }

    assert all("CAPÍTULO" not in section.text for section in sections.values())
    assert (sections["art-11-caput"].search_text or "").startswith("CAPÍTULO X - DA DECLARAÇÃO DE BENS")
    assert (sections["art-2-caput"].search_text or "").startswith("CAPÍTULO II - DA OBRIGATORIEDADE")
