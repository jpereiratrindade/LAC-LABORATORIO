# LAC-IDV-002 — Painel de Continuidade Integrada

- **Versão:** 0.1.2
- **Data:** 2026-11-09
- **Estado:** Implementado para validação em ambiente local
- **Substitui como referência visual:** LAC-IDV-001 v0.1.1 (sem apagar o histórico)

## Objetivo

Harmonizar o laboratório ao padrão SisTer/EVIDA, aproximando-se do primeiro painel de referência: faixa superior escura, marca de laço filamentado, navegação lateral, área central de trabalho, coluna de ações rápidas e cartões de indicadores.

## Contratos funcionais

| Seção | Fonte de dados / operação | Limites |
|---|---|---|
| Visão geral | `/api/stats`, `/api/events`, `/api/verify` | Somente fatos observados e declarações |
| Projetos | `/api/projects`, `/api/roots` | Projeto não equivale a resultado validado |
| Eventos | `/api/events` | Até 200 registros por vista |
| Linha do tempo | `/api/events` com filtros | Ordenação por ocorrência; registro preservado |
| Fontes | `/api/roots` | Somente caminhos cadastrados |
| Observação | `/api/scan` | Idempotência e ausência de inferências |
| Relações | `/api/relations` | Relação candidata não é causa |
| Pendências | `/api/todos`, `/api/todos/close` | Encerramento é novo evento |
| Integridade | `/api/verify` | Cadeia interna; âncora externa via CLI |
| Relatórios | `/api/report` | Máximo de 5.000 eventos |
| Preferências | `localStorage` | Sem persistência no SQLite |

## Decisões de engenharia

1. A API e o SQLite permanecem inalterados; patch restrito à interface, testes e documentação.
2. Elementos sem operação real não são apresentados como botões.
3. Nenhuma fonte é observada sem autorização/cadastro explícito.
4. Os indicadores contam registros, não inferem completude nem causalidade.
5. Símbolo SVG próprio, raster PNG gerado localmente, sem fontes externas.
6. Nenhum LLM é requisitado pelo sistema.

## Critérios de validação

- Compilação C++26 no GCC disponível; integração end-to-end.
- `node --check web/app.js` e testes de rotas estáticas.
- Verificação manual no Firefox, especialmente largura da sidebar e dos filtros.
- Continuidade das bases SQLite existentes; sem migração.

## Limites / trabalho futuro

Não há integração automática com conversas privadas, classificação semântica nem verificação de âncora externa na interface. A semelhança com uma imagem conceitual não implica implementação de funcionalidades que não existam no núcleo.
