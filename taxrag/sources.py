"""The small approved source registry for the first ingestion slice."""

from dataclasses import dataclass


@dataclass(frozen=True)
class ApprovedSource:
    source_key: str
    title: str
    canonical_url: str
    authority_level: str
    document_family: str


APPROVED_SOURCES = {
    "irpf-2026-quem-deve-declarar": ApprovedSource(
        source_key="irpf-2026-quem-deve-declarar",
        title="Quem deve declarar",
        canonical_url=(
            "https://www.gov.br/receitafederal/pt-br/assuntos/meu-imposto-de-renda/quem/quem"
        ),
        authority_level="official_guidance",
        document_family="receita_guidance_html",
    )
}
