# LAC v0.1.3 — API, MCP, integrações e rede

> Documento da v0.1.3. A autenticação por token compartilhado foi substituída na v0.1.4; siga [acesso institucional](LAC-AUTH-001_v0.1.4.md). As rotas funcionais e os adaptadores abaixo continuam disponíveis após autenticação.

## Execução e autenticação

```bash
export LAC_API_TOKEN="$(openssl rand -hex 32)"
./build/lac serve --bind 0.0.0.0 --port 8765 --webroot ./web
```

Informe esse token no painel acessado em `http://IP_DO_SERVIDOR:8765`. Ele fica em `sessionStorage`, não na URL. Fechar a sessão do navegador remove o armazenamento; trocar a variável e reiniciar o servidor revoga o token antigo. O token nunca é impresso pelo servidor. Para consultar sem UI:

```bash
curl --fail --header "Authorization: Bearer $LAC_API_TOKEN" http://127.0.0.1:8765/api/stats
```

HTTP não cifra dados ou credenciais. O bind `0.0.0.0` pode abranger interfaces além da LAN, dependendo da máquina. O firewall não é modificado; use rede confiável e regras de acesso adequadas. Não há contas, papéis ou TLS integrado.

`127.0.0.1` continua padrão e permite funcionamento sem token; definir `LAC_API_TOKEN` também protege a API nesse modo. O header `X-LAC-Local: 1` é requisito de formato para escrita, não autenticação.

## API HTTP

GETs retornam JSON, exceto `/api/report`, que retorna Markdown. POSTs usam `Content-Type: application/x-www-form-urlencoded`, `X-LAC-Local: 1` e Bearer quando configurado. POST tem limite de 16 KiB. Erros usam HTTP 400/403/404 e objeto `error`.

| Método/rota | Parâmetros ou resultado |
|---|---|
| GET `/api/health` | Estado, versão e transporte MCP disponível |
| GET `/api/stats` | Contagens e data UTC |
| GET `/api/projects`, `/api/roots` | Projetos e fontes registradas |
| GET `/api/events` | `q`, `project`, `kind`, `from`, `to`, `limit` (1–200); datas AAAA-MM-DD |
| GET `/api/todos`, `/api/relations` | Pendências abertas e relações; até 200 |
| GET `/api/verify` | Verifica cadeia interna de hashes |
| GET `/api/report` | `from`, `to`, `project`; até 5.000 eventos |
| POST `/api/roots` | `project`, `path` absoluto, `kind=git\|docs` |
| POST `/api/scan` | Observa fontes registradas |
| POST `/api/notes` | `project`, `kind=note\|decision\|todo\|correction`, `title`, `body`, `reference` |
| POST `/api/todos/close` | `id`; adiciona encerramento, preserva original |
| POST `/api/relations` | `from`, `to`, `label`, `state=candidate\|user_confirmed` |
| GET `/api/integrations` | Configuração, disponibilidade, última consulta e metadados de buckets |
| POST `/api/integrations/configure` | `integration=recoll\|activitywatch`, `enabled=true\|false` e configuração específica |
| GET `/api/integrations/recoll/search` | `q`, `limit` (máximo 50, padrão 20) |
| GET `/api/integrations/activitywatch/activity` | `bucket`, `start`, `end`, `limit` (máximo 200, padrão 100) |

A ponte MCP envia `X-LAC-Agent: mcp` nas operações. Notas, relações e encerramentos recebem atribuição LLM. `source_type=manual` representa entrada declarada; `actor=llm` e `source_ref` diferenciam a autoria. Esse header não autentica uma identidade e um cliente administrativo pode declarar sua própria origem. Relações com esse header só aceitam `candidate`.

## MCP stdio

Requer Python >= 3.9, sem dependências pip. Inicie o servidor HTTP antes da ponte. Exemplo genérico de configuração em um cliente que usa `mcpServers`:

```json
{
  "mcpServers": {
    "lac": {
      "command": "python3",
      "args": ["/CAMINHO/lac-laboratorio/scripts/lac_mcp.py", "--url", "http://127.0.0.1:8765", "--allow-write"]
    }
  }
}
```

O processo cliente precisa transmitir `LAC_API_TOKEN` ao subprocesso. Se o cliente exige um bloco `env`, configure o token apenas no arquivo privado desse cliente, fora do repositório. Em outra máquina, troque a URL pelo IP privado IPv4 do servidor. A URL não aceita credenciais, caminhos, redirecionamentos ou servidores públicos. Não use `0.0.0.0` como endereço de destino.

Remova `--allow-write` para leitura. O modo de escrita disponibiliza registro de fontes, varreduras, registros declarados, encerramento de pendências, propostas de relações e configuração das integrações. Ele delega administração completa; não impõe ACLs por projeto. Não há ferramenta de SQL, execução de comandos, exclusão, alteração de eventos ou confirmação humana de relações.

O transporte implementa mensagens JSON-RPC delimitadas por linha, negociação de versão, `notifications/initialized`, `ping`, `tools/list` e `tools/call`. Versões negociáveis: `2025-11-25`, `2025-06-18`, `2025-03-26`, `2024-11-05`; em versão desconhecida, oferece `2025-11-25` para decisão do cliente. Não anuncia resources, prompts, sampling ou MCP HTTP. Mensagens e respostas têm limite de 1 MiB; consultas maiores devem ser divididas. Não há retries automáticos de escrita: em timeout, consulte o histórico antes de tentar novamente, pois a operação pode ter concluído.

Especificações usadas: [transporte](https://modelcontextprotocol.io/specification/2025-11-25/basic/transports), [ciclo de vida](https://modelcontextprotocol.io/specification/2025-11-25/basic/lifecycle), [ferramentas](https://modelcontextprotocol.io/specification/2025-11-25/server/tools).

## Recoll

Prepare o índice externamente, com os extratores necessários para os formatos desejados. O LAC não instala Recoll, não cria índices e não altera sua configuração.

Configure `config_dir` absoluto contendo `recoll.conf` e `roots` com diretórios autorizados separados por nova linha. Consultas usam `recollq` ou `recoll -t`, sem shell, com timeout de 5 segundos. O formato `-F` usa campos codificados em base64. Caminhos são canonicalizados; URLs não locais e resultados fora das pastas autorizadas são descartados, incluindo escapes por symlink.

O limite aplica-se à fatia do índice antes do filtro de pastas; pode haver resultados autorizados em fatias posteriores que não aparecem nessa consulta. Recomenda-se um índice dedicado ao acervo do LAC. Títulos, datas e abstracts podem estar ausentes; trechos refletem o estado do índice, não uma leitura atual do arquivo. Nenhum resultado é importado automaticamente. “Preparar nota com referência” abre um formulário para revisão.

Referência: [interface de linha de comando do Recoll](https://recoll.org/usermanual/webhelp/docs/RCL.SEARCH.COMMANDLINE.html).

## ActivityWatch

Configure `url` loopback (padrão `http://127.0.0.1:5600`) e `buckets`, um ID autorizado por linha. Esse endereço é relativo ao computador do servidor LAC. A API deve aceitar consultas locais sem chave adicional; servidores ActivityWatch com autenticação própria ainda não são suportados.

O status consulta apenas metadados. “API acessível” não verifica a coleta. O operador deve configurar os watchers compatíveis com sua sessão gráfica. A consulta exige bucket autorizado; `start` e `end` são RFC3339 com fuso e intervalo máximo de sete dias, padrão últimas 24h. A resposta limita eventos e informa quando o resumo pode estar truncado. Durações são recortadas ao período solicitado.

O resumo agrega intervalos por aplicativo/status, omitindo títulos, URLs e payloads brutos. Não corrige AFK, não elimina sobreposições e não atribui projetos nem produtividade. Desabilitar a integração no LAC não desliga o ActivityWatch. Não há importação automática, sincronização contínua ou gráficos de produtividade.

Referência: [API REST do ActivityWatch](https://docs.activitywatch.net/en/latest/api/rest.html).

## Configuração, instalação e serviço

Por padrão, configurações ficam em `CAMINHO_DO_DB.integrations.json`, com permissão 0600 e gravação atômica. O arquivo guarda habilitação, escopo e última consulta, sem tokens ou cópia de resultados. Sobrescreva com `--integration-config CAMINHO`; o diretório deve ser privado. `--integration-helper SCRIPT` permite indicar a localização do adaptador Python quando o layout de instalação é diferente.

`cmake --install build --prefix "$HOME/.local"` instala o binário, a UI e ambos os scripts em `~/.local/share/lac/scripts/`. Para LAN via systemd, `scripts/install_service.sh` instala `systemd/lac-lan.service`, habilita linger e cria o token. O serviço inicia no boot e persiste após logout, sem depender do diretório de desenvolvimento. Para instalação manual, crie `~/.config/lac/server.env`, permissão 0600, contendo `LAC_API_TOKEN=SEU_TOKEN`. Escolha entre o serviço local e o de LAN: ambos usam a mesma porta e não devem executar simultaneamente. Não inclua esse arquivo no Git. Verifique com `loginctl show-user "$USER" -p Linger` (deve mostrar `yes`) e `systemctl --user is-enabled lac-lan.service` (deve mostrar `enabled`). O home precisa estar disponível no boot; homes criptografados desbloqueados somente por login exigem outra estratégia de instalação.

## Validação

A suíte testa CLI, HTTP, SQLite, cadeia histórica, MCP real por subprocesso, token e bind `0.0.0.0`. Recoll é testado com executável simulado e ActivityWatch com servidor HTTP simulado, incluindo escopos, dados filtrados e indisponibilidade. Isso valida os adaptadores, mas não substitui a validação dos índices, extratores e watchers reais instalados pelo operador.
