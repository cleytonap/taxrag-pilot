# Evaluation Set: IRPF 2026 Filing Obligation

Status: Draft labels for the first retrieval baseline

The cases below are test specifications, not tax advice. The expected source identifies the passage retrieval must return. A later implementation will convert these cases into executable data.

| ID | User question | Expected source | Expected anchor | Expected behavior |
| --- | --- | --- | --- | --- |
| `obrig-001` | Qual e o limite de rendimentos tributaveis para declarar o IRPF 2026? | `irpf-2026-in-rfb-2312` | Art. 2, inciso I | State the threshold and both relevant years. |
| `obrig-002` | Recebi R$ 200 mil de rendimentos isentos em 2025. Sou obrigado? | `irpf-2026-in-rfb-2312` | Art. 2, inciso II | Explain that the rule is above the threshold, and avoid a definitive personalized conclusion. |
| `obrig-003` | Vendi um carro com ganho de capital em 2025. Preciso declarar? | `irpf-2026-in-rfb-2312` | Art. 2, inciso III | Explain the condition and scope limitation. |
| `obrig-004` | Fiz operacoes na bolsa abaixo de R$ 40 mil, mas tive lucro. | `irpf-2026-in-rfb-2312` | Art. 2, inciso IV | Explain both independent bolsa conditions. |
| `obrig-005` | Minha atividade rural faturou R$ 177.920 em 2025. | `irpf-2026-in-rfb-2312` | Art. 2, inciso V | Explain that the rule uses a value above the threshold. |
| `obrig-006` | Tenho bens de R$ 800 mil em 31 de dezembro. | `irpf-2026-in-rfb-2312` | Art. 2, inciso VI | Explain that the rule uses a value above the threshold. |
| `obrig-007` | Virei residente no Brasil em 2025. | `irpf-2026-in-rfb-2312` | Art. 2, inciso VII | Explain the December 31 condition and ask for missing facts if needed. |
| `obrig-008` | Estou como dependente na declaracao da minha mae. Ainda preciso entregar a minha? | `irpf-2026-in-rfb-2312` | Art. 2, paragraph 1 | Explain the dependent dispensation and its condition. |
| `obrig-009` | Nao sou obrigado. Posso declarar mesmo assim para pedir restituição? | `irpf-2026-perguntas-respostas` | Question 002, page 23 | Explain voluntary filing and the limitation about appearing in more than one declaration. |
| `obrig-010` | Tenho 70 anos. A idade me dispensa da declaracao? | `irpf-2026-perguntas-respostas` | Question 006, page 24 | State that there is no age-based exemption. |
| `obrig-011` | Preciso declarar o IRPF do exercicio 2025 com esses limites? | none | none | State that this slice supports exercise 2026 only; do not apply 2026 thresholds to another exercise. |
| `obrig-012` | Com meu salario, investimentos e despesas, diga se sou obrigado a declarar. | `irpf-2026-in-rfb-2312` | Art. 2 | Explain the criteria and decline to issue a personalized determination without a complete, verified tax assessment. |
