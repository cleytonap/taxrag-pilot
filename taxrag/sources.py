"""The small approved source registry for the first ingestion slice."""

from dataclasses import dataclass


@dataclass(frozen=True)
class ApprovedSource:
    source_key: str
    title: str
    canonical_url: str
    authority_level: str
    document_family: str
    expected_content_type: str
    raw_filename: str


APPROVED_SOURCES = {
    "irpf-2026-quem-deve-declarar": ApprovedSource(
        source_key="irpf-2026-quem-deve-declarar",
        title="Quem deve declarar",
        canonical_url=(
            "https://www.gov.br/receitafederal/pt-br/assuntos/meu-imposto-de-renda/quem/quem"
        ),
        authority_level="official_guidance",
        document_family="receita_guidance_html",
        expected_content_type="text/html",
        raw_filename="original.html",
    ),
    "irpf-2026-perguntas-respostas": ApprovedSource(
        source_key="irpf-2026-perguntas-respostas",
        title="Perguntas e Respostas IRPF 2026",
        canonical_url=(
            "https://www.gov.br/receitafederal/pt-br/centrais-de-conteudo/publicacoes/"
            "perguntas-e-respostas/dirpf/p-r-irpf-2026-v1-00-2026-04-23.pdf"
        ),
        authority_level="official_guidance",
        document_family="receita_questions_answers_pdf",
        expected_content_type="application/pdf",
        raw_filename="original.pdf",
    ),
}
