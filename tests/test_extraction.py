from pathlib import Path

from taxrag.extraction import extract_receita_guidance_html

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "receita_guidance.html"


def test_receita_extraction_preserves_sections_and_tables() -> None:
    result = extract_receita_guidance_html(FIXTURE_PATH.read_bytes())

    assert [section.display_title for section in result.sections] == [
        "Quem deve declarar",
        "Você está obrigado se:",
        "Limites de valor para o exercício 2026",
        "Quem não precisa entregar a declaração?",
    ]
    limits = result.sections[2]
    assert "Motivo | Limite" in limits.text
    assert "Rendimentos tributáveis | R$ 35.584,00" in limits.text
    assert limits.anchor_key == "limites-de-valor-para-o-exercicio-2026--03"
    assert "Recebeu rendimentos tributáveis acima do limite." in result.sections[1].text


def test_receita_extraction_excludes_navigation_and_footer() -> None:
    result = extract_receita_guidance_html(FIXTURE_PATH.read_bytes())

    assert "Navigation that must not be extracted" not in result.normalized_text
    assert "Footer that must not be extracted" not in result.normalized_text
