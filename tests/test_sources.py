from taxrag.sources import APPROVED_SOURCES


def test_first_source_is_an_official_receita_html_page() -> None:
    source = APPROVED_SOURCES["irpf-2026-quem-deve-declarar"]

    assert source.canonical_url.startswith("https://www.gov.br/receitafederal/")
    assert source.authority_level == "official_guidance"
    assert source.document_family == "receita_guidance_html"
