# Source Inventory

This directory holds the curated registry of sources that TaxRAG is allowed to retrieve from.

It is intentionally not a folder of arbitrary downloaded files. Each source must have a reason for inclusion, an official canonical URL, an authority label, and a freshness policy.

## Initial Source Families

| Family | Official publisher | Preferred format | Authority label | Role |
| --- | --- | --- | --- | --- |
| Consolidated federal laws | Presidencia da Republica / Planalto | HTML | `primary_legislation` | Legal basis and article-level citations |
| IRPF regulation | Presidencia da Republica / Planalto | HTML | `regulation` | Regulatory detail and definitions |
| Receita Federal Normas | Receita Federal | HTML | `tax_authority_norm` | Instrucoes Normativas and binding interpretations where relevant |
| IRPF tables and official service pages | Receita Federal | HTML | `official_guidance` | Current thresholds, procedures, and user-facing explanations |
| Annual Perguntas e Respostas IRPF | Receita Federal | PDF | `official_guidance` | Practical filing guidance for a specific exercise and calendar year |

## Required Metadata

Every source record will eventually contain at least:

- stable source ID and title
- canonical URL and final download URL when different
- publisher and authority label
- document type and content format
- publication, update, effective, and retrieval dates when available
- applicable tax year or effective-period range
- SHA-256 content hash
- extraction method and extraction status
- whether the source is currently active in retrieval

## Initial Official Entry Points

- Planalto consolidated text for [Lei no 9.250/1995](https://planalto.gov.br/ccivil_03/leis/l9250compilado.htm)
- Receita Federal [Meu Imposto de Renda](https://www.gov.br/receitafederal/pt-br/assuntos/meu-imposto-de-renda)
- Receita Federal [IRPF tables for 2026](https://www.gov.br/receitafederal/pt-br/assuntos/meu-imposto-de-renda/tabelas/2026)
- Receita Federal [Perguntas e Respostas IRPF archive](https://www.gov.br/receitafederal/pt-br/centrais-de-conteudo/publicacoes/perguntas-e-respostas/dirpf)
- Receita Federal [Normas search system](https://normas.receita.fazenda.gov.br/sijut2consulta/normas.receisulta/consulta.action)

The exact documents admitted for the first retrieval experiment will be listed in a later, topic-specific inventory file.
