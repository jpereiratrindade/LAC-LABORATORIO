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

## v0.1.3 — Integrações, API/MCP e rede local (2026-11-09)

- Ponte MCP por stdio, sem pacotes Python externos: consultas por padrão, administração habilitada por `--allow-write`.
- Proveniência LLM em notas, decisões, pendências, encerramentos e relações candidatas; sem alterar eventos históricos ou esquema do banco.
- Adaptadores opcionais Recoll e ActivityWatch com escopos explícitos, limites e consultas sob demanda.
- Nova seção Integrações no painel, busca documental e resumos de intervalos por aplicativo; nenhuma importação automática.
- Bind IPv4 configurável, incluindo `0.0.0.0`; token obrigatório para API em rede, com acesso pelo painel e MCP.
- Testes de protocolo, autenticação, integridade e adaptadores com executável/serviço simulados.
- Instalação persistente em `~/.local` e serviço systemd com linger para inicialização no boot e funcionamento sem login.

## Próximas alterações

- Comando único `./iniciar.sh` para compilar, testar, instalar e iniciar ou atualizar o serviço persistente.
- Instalação repetida reinicia a versão instalada, preserva token/banco e verifica a saúde da API antes de informar sucesso.
- README reorganizado para começar pela execução e pelo primeiro acesso; detalhes técnicos reunidos em `docs/OPERACAO-E-LIMITES.md`.

## v0.1.4 — Acesso institucional restrito (2026-11-09)

- Login por código de uso único enviado via SMTP TLS ao domínio exato @embrapa.br; sem fallback anônimo ou código de desenvolvimento.
- Código de seis dígitos, validade de dez minutos, até cinco tentativas e reenvio mínimo de sessenta segundos; limites persistentes por e-mail/IP.
- Sessão de doze horas com cookie HttpOnly/SameSite=Strict, revogação no logout e hashes em banco auxiliar, preservando eventos históricos.
- Antigo token compartilhado retirado do login; credenciais de serviço opcionais e desabilitadas por padrão.
- Ponte MCP com autenticação institucional interativa e sessão privada; configuração SMTP pode reaproveitar o remetente do MORFO local.
- Integração opcional do LAC no catálogo Outros sistemas do sister-synth, com descoberta observada e redirecionamento em allowlist.
