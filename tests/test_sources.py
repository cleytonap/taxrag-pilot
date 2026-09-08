from taxrag.sources import APPROVED_SOURCES


def test_first_source_is_an_official_receita_html_page() -> None:
    source = APPROVED_SOURCES["irpf-2026-quem-deve-declarar"]

    assert source.canonical_url.startswith("https://www.gov.br/receitafederal/")
    assert source.authority_level == "official_guidance"
    assert source.document_family == "receita_guidance_html"


def test_questions_and_answers_source_is_an_official_pdf() -> None:
    source = APPROVED_SOURCES["irpf-2026-perguntas-respostas"]

    assert source.canonical_url.startswith("https://www.gov.br/receitafederal/")
    assert source.expected_content_type == "application/pdf"
    assert source.raw_filename == "original.pdf"


def test_normative_source_is_an_official_dou_html_publication() -> None:
    source = APPROVED_SOURCES["irpf-2026-in-rfb-2312"]

    assert source.canonical_url.startswith("https://www.in.gov.br/")
    assert source.authority_level == "tax_authority_norm"
    assert source.document_family == "dou_norm_html"
    assert source.request_headers["Accept-Language"].startswith("pt-BR")
