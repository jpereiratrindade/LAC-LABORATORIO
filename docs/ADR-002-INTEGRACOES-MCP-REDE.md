# ADR-002 — Integrações opcionais, administração por MCP e rede local

- **Estado:** Accepted para v0.1.3
- **Data:** 2026-11-09
- **Decisão:** preservar o núcleo determinístico e oferecer administração por cliente LLM externo, adaptadores opcionais e bind IPv4 configurável.

## Contratos

O servidor C++ mantém a API HTTP e o banco. Uma ponte Python padrão implementa MCP JSON-RPC por stdio e chama somente rotas conhecidas da API. Não oferece SQL, shell, leitura arbitrária, edição ou exclusão de eventos. Python só é necessário em execução para MCP e integrações; o núcleo continua independente.

A leitura é padrão no MCP. `--allow-write` delega administração, incluindo registro de novas fontes e configuração dos escopos externos. O operador do cliente deve autorizar os caminhos/buckets. Esse modo não é um sandbox por projeto: o token HTTP compartilhado permite administração completa.

Registros enviados com `X-LAC-Agent: mcp` continuam em `source_type=manual`, com prefixo `llm:mcp:` em `source_ref`, preservado pela cadeia de hashes. O campo JSON `actor` e o painel tornam essa atribuição visível. Declarações continuam `declared`; relações geradas pela LLM são sempre `candidate`/`proposed`. A autoria é informação declarada pelo cliente, não identidade criptograficamente verificada. Nenhuma inferência vira confirmação humana automaticamente.

Recoll e ActivityWatch são consultados sob demanda. Não há coleta automática adicional nem cópia de todos os resultados para eventos permanentes. O estado da última consulta fica em arquivo auxiliar com permissão 0600, substituído atomicamente. Não equivale à última indexação ou ao funcionamento de um coletor.

Recoll usa configuração explícita e filtra caminhos canônicos pelas pastas autorizadas. ActivityWatch usa somente API loopback no servidor e buckets autorizados; devolve agregados limitados, sem títulos de janelas ou URLs. Intervalos não são produtividade, tempo corrigido por AFK nem atribuição a projetos.

## Rede e limites

O bind padrão permanece `127.0.0.1`; `--bind 0.0.0.0` escuta em todas as interfaces IPv4. Binds diferentes do padrão exigem `LAC_API_TOKEN` com pelo menos 32 caracteres. Todas as rotas `/api/*`, inclusive leituras, exigem Bearer quando há token. Assets públicos permitem abrir o formulário de acesso sem revelar dados do banco. `Host` aceita localhost/IP loopback e, em modo rede, IPv4 numérico com a porta correta. `Origin`, quando presente, deve corresponder exatamente a `http://Host`.

Não há TLS, papéis por usuário ou proteção contra um administrador local que modifique o banco. O token concede os mesmos poderes administrativos da interface. Acesso remoto deve ficar em rede confiável. O firewall do sistema não é alterado automaticamente.

O LAC não chama provedores LLM. Um cliente externo pode enviar resultados ao seu provedor; o operador controla essa escolha. Conteúdo recuperado é dado não confiável e não deve virar instrução para o agente.

## Compatibilidade

Nenhuma migração ou reescrita do histórico. `source_type` e estados existentes são preservados. Encerramentos usam a chave estável `todo_closed:ID` para resolver pendências independentemente da autoria. Desabilitar um adaptador bloqueia consultas seguintes, preservando a configuração e qualquer registro já declarado.
