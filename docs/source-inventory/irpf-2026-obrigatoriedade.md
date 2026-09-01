# Source Inventory: IRPF 2026 Filing Obligation

Status: Approved for the first ingestion experiment

Applicable exercise: 2026

Applicable calendar year: 2025

## Approved Sources

| Source ID | Authority | Format | Citation anchor | Purpose |
| --- | --- | --- | --- | --- |
| `irpf-2026-in-rfb-2312` | `tax_authority_norm` | HTML | Art. 2 and paragraphs | Canonical annual filing-obligation criteria and dispensations |
| `irpf-2026-quem-deve-declarar` | `official_guidance` | HTML | Heading and table row | Accessible overview and current threshold table |
| `irpf-2026-perguntas-respostas` | `official_guidance` | PDF | Question 001, pages 22-23 | Detailed explanation, exceptions, and user-verifiable page citation |

## Source Records

### `irpf-2026-in-rfb-2312`

- title: Instrucao Normativa RFB no 2.312, de 13 de marco de 2026
- publisher: Receita Federal do Brasil
- authority: `tax_authority_norm`
- canonical entry point: [Receita Federal Normas search](https://normas.receita.fazenda.gov.br/sijut2consulta/consulta.action?termoBusca=declaracao+ajuste+de+renda+anual)
- discovery identifier: number `2312`, published `16/03/2026`
- applicable period: exercise 2026, calendar year 2025
- required extraction anchors: `Art. 2`, each inciso, and each paragraph
- refresh policy: once before each ingestion run and monthly while this exercise is active

### `irpf-2026-quem-deve-declarar`

- title: Quem deve declarar
- publisher: Receita Federal do Brasil
- authority: `official_guidance`
- canonical URL: <https://www.gov.br/receitafederal/pt-br/assuntos/meu-imposto-de-renda/quem/quem>
- page update observed: `16/03/2026 11:21`
- applicable period: exercise 2026, calendar year 2025
- required extraction anchors: `Voce esta obrigado se`, `Limites de valor para o exercicio 2026`, `Quem nao precisa entregar a declaracao`
- refresh policy: weekly during the filing period, monthly afterwards

### `irpf-2026-perguntas-respostas`

- title: Perguntas e Respostas IRPF 2026
- publisher: Receita Federal do Brasil
- authority: `official_guidance`
- canonical URL: <https://www.gov.br/receitafederal/pt-br/centrais-de-conteudo/publicacoes/perguntas-e-respostas/dirpf/p-r-irpf-2026-v1-00-2026-04-23.pdf>
- page update observed: `27/04/2026 10:28`
- applicable period: exercise 2026, calendar year 2025
- required extraction anchors: question `001`, pages `22-23`; questions `002-010`, pages `23-25`
- refresh policy: check monthly; retain every downloaded version by content hash

## Admission Rule

Do not add a new document simply because it mentions IRPF. Add it only if an evaluation case demonstrates a missing answerable rule, it has official provenance, and we can name the citation anchor that users will see.
