"""The small approved source registry for the first ingestion slice."""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ApprovedSource:
    """Metadata and retrieval requirements for one allow-listed official source."""

    source_key: str
    title: str
    canonical_url: str
    authority_level: str
    document_family: str
    expected_content_type: str
    raw_filename: str
    request_headers: dict[str, str] = field(default_factory=dict)
    snapshot_path: str | None = None
    snapshot_sha256: str | None = None


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
        snapshot_path=(
            "data/source-snapshots/irpf-2026-quem-deve-declarar/"
            "4e779e493e14ad8f6625da0362215fcd0b52657b0b3b6b96903f97c0492735e8/original.html"
        ),
        snapshot_sha256="4e779e493e14ad8f6625da0362215fcd0b52657b0b3b6b96903f97c0492735e8",
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
        snapshot_path=(
            "data/source-snapshots/irpf-2026-perguntas-respostas/"
            "f3740385c07fa4dc52f8614d009dd5bd038fbeb8bd935f89da4e9bc26ed2a3b0/original.pdf"
        ),
        snapshot_sha256="f3740385c07fa4dc52f8614d009dd5bd038fbeb8bd935f89da4e9bc26ed2a3b0",
    ),
    "irpf-2026-in-rfb-2312": ApprovedSource(
        source_key="irpf-2026-in-rfb-2312",
        title="Instrucao Normativa RFB no 2.312, de 13 de marco de 2026",
        canonical_url=(
            "https://www.in.gov.br/en/web/dou/-/instrucao-normativa-rfb-n-2.312-de-13-de-"
            "marco-de-2026-692748727"
        ),
        authority_level="tax_authority_norm",
        document_family="dou_norm_html",
        expected_content_type="text/html",
        raw_filename="original.html",
        snapshot_path=(
            "data/source-snapshots/irpf-2026-in-rfb-2312/"
            "f0a12419b3a23a768ceece8e0413e811fcfc63543457fd145ea13e2f9cefaf58/original.html"
        ),
        snapshot_sha256="f0a12419b3a23a768ceece8e0413e811fcfc63543457fd145ea13e2f9cefaf58",
        # The DOU disconnects generic HTTP clients but serves its public HTML when the
        # request identifies a normal browser. Keep this source-specific behavior explicit.
        request_headers={
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
        },
    ),
}
