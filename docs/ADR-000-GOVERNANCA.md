# ADR-000 — Governança do Laboratório de Continuidade

- **Estado:** Accepted para a implementação experimental v0.1.0
- **Data:** 2026-11-09
- **Decisão:** núcleo local sem LLM, contratos pequenos, eventos temporais append-only, dados originais preservados, fontes registradas por consentimento explícito.

## Contexto

O problema transversal é a perda de continuidade entre projetos. A criação de um sistema com capacidade ampla demais ameaça reproduzir a dispersão que pretende reduzir.

## Decisão

A primeira entrega observa apenas Git e diretórios, organiza evidências técnicas e declarações humanas e oferece consulta web local. A falta de evidência é tratada como lacuna, não como licença para inferência. MPRR permanece metodologicamente independente.

## Consequências

A solução é auditável e leve, mas não lê conversas privadas, conteúdo semântico de PDF ou decisões que não tenham sido documentadas. Novos adaptadores não alteram eventos históricos e devem preservar origem e controle de acesso.
