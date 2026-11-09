# Operação, evidências e limites do LAC

## O que os registros permitem afirmar

| Origem | Tipo de registro | O que pode afirmar |
|---|---|---|
| Git | `git_commit`, `observed` | O commit e sua mensagem foram encontrados em um repositório registrado. **Não comprova funcionalidade validada.** |
| Diretório | `file_added`, `file_changed`, `file_missing`, `observed` | O hash e caminho foram observados ou não encontrados no momento da varredura. **Não prova criação/exclusão exatamente naquele momento.** |
| Pessoa | `note`, `decision`, `todo`, `correction`, `declared` | Uma declaração humana foi registrada; **não constitui verificação automática**. |
| LLM | `note`, `decision`, `todo`, `correction`, `declared` | Uma declaração atribuída à LLM, identificada por `actor=llm` e referência `llm:mcp:`. **Não constitui confirmação humana.** |
| Pessoa | `relation`, `proposed/declared` | Uma associação foi proposta ou confirmada por alguém; **não demonstra causalidade**. |

O observador de arquivos do LAC não extrai conteúdo interno de PDFs/DOCX nem integra conversas privadas do ChatGPT. A busca FTS5 do histórico indexa **títulos, mensagens de commit, notas escritas e referências/caminhos**, não o texto de todos os documentos. A busca documental opcional consulta o índice do Recoll, que pode conter conteúdo de PDFs/DOCX conforme os extratores instalados. Resultados dessa consulta não entram automaticamente na busca FTS5 do histórico.

## Segurança e limites explícitos da v0.1

- Escuta no loopback IPv4 por padrão. `--bind 0.0.0.0` habilita a rede. Sessão institucional é obrigatória nas rotas de dados e administração, inclusive no loopback; login e saúde mínima são públicos. Valida `Host` e `Origin`, exige cabeçalho de escrita, rejeita leitura arbitrária de arquivos e não usa shell para executar Git ou Recoll.
- HTTP é destinado ao computador local ou à LAN confiável. Não exponha a porta à internet. O login por código valida o acesso à caixa @embrapa.br; todos os usuários verificados compartilham o laboratório, sem isolamento por usuário. O transporte HTTP não oferece criptografia.
- Os arquivos observados nunca são modificados. O diretório registrado de documentos pode incluir `.md`, `.tex`, `.pdf`, `.zip`, `.docx`, `.xlsx`, `.json` e outros tipos explícitos no código.
- Arquivos acima de **32 MiB** não são indexados. Limite de **5.000 arquivos elegíveis por raiz**. Diretórios `.git`, `build`, `output`, `node_modules` e outros técnicos são ignorados. Symlinks não são seguidos.
- Git: consulta até **1.000 commits por raiz e varredura**. Se houver mais, commits antigos além do limite não são importados.
- SQLite usa WAL, transações e **gatilhos append-only** para eventos; **projeções** (`file_snapshots`, `roots`) podem ser atualizadas. Alterações intencionais feitas por um administrador ao DB podem contornar gatilhos. A âncora externa detecta alterações na parte histórica por ela referenciada, desde que esteja protegida.
- SHA-256 **não é assinatura digital**, nem garante autoria, veracidade científica ou segurança contra quem altera tanto o banco quanto a âncora externa.
- Não há replicação, backup automático, classificação semântica, contas de usuário ou integração nativa com IDE. Não inclua documentos confidenciais sem avaliar seus caminhos e títulos; eles ficam pesquisáveis para o usuário local.
- `occurred_at` preserva a data fornecida pelo Git ou a data da observação; `recorded_at` marca o ingresso no banco. O diário pode incluir fatos históricos importados hoje.

## Operações de linha de comando

O serviço usa `~/.local/share/lac/lac.db`. Os comandos abaixo consultam o mesmo banco padrão:

```bash
~/.local/bin/lac stats
~/.local/bin/lac verify
~/.local/bin/lac report --from 2026-11-07 --to 2026-11-09 --out diario.md
~/.local/bin/lac anchor --out "$HOME/Documentos/LAC_ANCHOR_2026-11-09.txt"
~/.local/bin/lac verify --anchor "$HOME/Documentos/LAC_ANCHOR_2026-11-09.txt"
```

O diretório de destino precisa existir. O comando `anchor` não sobrescreve arquivos. Guarde a âncora fora do diretório do banco e em backup independente. O serviço observa as fontes cadastradas a cada 180 segundos; o painel permite observar imediatamente.

## Compilação manual e desenvolvimento

```bash
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release -DBUILD_TESTING=ON
cmake --build build --parallel 2
ctest --test-dir build --output-on-failure
```

Para um ambiente isolado de desenvolvimento, sem disputar a porta do serviço instalado:

```bash
./build/lac serve --db /tmp/lac-dev/lac.db --port 8766 --scan-every 0 --webroot ./web
```

Esse comando manual usa loopback e outro banco. O serviço persistente continua em 8765. Use `--db CAMINHO` nos demais comandos para operar um banco diferente do padrão.

## Estrutura do projeto

| Diretório | Conteúdo |
|---|---|
| `include/lac`, `src` | Núcleo C++, SQLite, observadores e API HTTP |
| `web` | Interface estática |
| `scripts` | Instalação, adaptadores e ponte MCP |
| `systemd` | Unidades de serviço |
| `tests` | Testes de integração |
| `docs` | Fundamentos, decisões e contratos |

Referências: [fundamentos](LAC-BASES-001_v0.1.0.md), [API/MCP e integrações](LAC-API-MCP-001_v0.1.3.md), [decisão sobre rede e integrações](ADR-002-INTEGRACOES-MCP-REDE.md).
