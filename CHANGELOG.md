# CHANGELOG — LAC

## v0.1.0 — 2026-11-09

- Núcleo C++26 com SQLite3/FTS5, observação Git e documentos, SHA-256 via OpenSSL.
- Eventos append-only e dupla temporalidade; idempotência em observações repetidas.
- API e interface web local com linha do tempo, busca, registros manuais, pendências e relações.
- Exportação de diário Markdown e âncoras de integridade externas.
- Testes end-to-end CLI, HTTP e banco; documentação REA/RIT/MPRR e ADR-000/001.
- Limites explícitos: sem LLM, sem busca semântica em PDF, sem integração com ChatGPT.

## v0.1.1 — Identidade visual SisTer (2026-11-09)

- Ícone vetorial original do LAC: duas trajetórias contínuas, ciano e âmbar.
- Interface web harmonizada com a linguagem visual do ecossistema SisTer/EVIDA, sem recursos remotos.
- Dashboard, navegação, indicadores, estado vazio e responsividade redesenhados sem alterar contratos de API.
- Favicon SVG e logo vetorial servidos por rotas estáticas explícitas.
- Target moderno `SQLite3::SQLite3` substitui o alias obsoleto de CMake.
- Sem alteração do esquema do banco, de proveniência, de idempotência ou de rotinas de observação.

## v0.1.2 — Continuidade Integrada (2026-11-09)

- Licenciamento sob GNU General Public License v3.0 (GPL-3.0-only), com texto completo em `LICENSE`.
- Interface alinhada ao painel de referência: marca superior, menu lateral e coluna de ações rápidas.
- Navegação funcional por visão geral, projetos, eventos, linha do tempo, relações, fontes, pendências, observação, integridade, relatórios e preferências.
- Ações ligadas exclusivamente às APIs existentes: `/api/stats`, `/api/events`, `/api/roots`, `/api/projects`, `/api/scan`, `/api/verify`, `/api/report`, `/api/notes`, `/api/todos` e `/api/relations`.
- Marca do LAC redesenhada com filamentos em SVG, sem fontes, ícones ou bibliotecas externas.
- Preferências da interface armazenadas somente no navegador, sem mudança no banco.
- Sem migrações, sem novas permissões, sem telemetria ou inferência automatizada.
