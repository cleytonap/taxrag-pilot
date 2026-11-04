# Approved Source Snapshots

These are exact copies of the three public official sources approved for the current IRPF 2026
filing-obligation slice. The directory name for each original includes its SHA-256 hash; ingestion
checks that hash before accepting a bundled file.

| Source key | Format | SHA-256 | Canonical source |
| --- | --- | --- | --- |
| `irpf-2026-quem-deve-declarar` | HTML | `4e779e493e14ad8f6625da0362215fcd0b52657b0b3b6b96903f97c0492735e8` | [Receita Federal guidance](https://www.gov.br/receitafederal/pt-br/assuntos/meu-imposto-de-renda/quem/quem) |
| `irpf-2026-perguntas-respostas` | PDF | `f3740385c07fa4dc52f8614d009dd5bd038fbeb8bd935f89da4e9bc26ed2a3b0` | [IRPF 2026 questions and answers](https://www.gov.br/receitafederal/pt-br/centrais-de-conteudo/publicacoes/perguntas-e-respostas/dirpf/p-r-irpf-2026-v1-00-2026-04-23.pdf) |
| `irpf-2026-in-rfb-2312` | HTML | `f0a12419b3a23a768ceece8e0413e811fcfc63543457fd145ea13e2f9cefaf58` | [Diário Oficial da União publication](https://www.in.gov.br/en/web/dou/-/instrucao-normativa-rfb-n-2.312-de-13-de-marco-de-2026-692748727) |

The snapshots preserve source bytes for review and reproducible local ingestion. They do not mean
the full PDF has been extracted or evaluated: the current PDF extraction covers Questions 001–006.
For ingestion instructions and the storage policy, see the [project README](../../README.md) and
[source inventory](../../docs/source-inventory/README.md).
