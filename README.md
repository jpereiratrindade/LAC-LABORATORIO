# LAC — Laboratório de Continuidade

**Interface v0.1.2:** painel integrado com navegação completa, ações reais, marca filamentada em SVG e preferências locais. Nenhuma migração do banco. Consulte [`docs/LAC-IDV-002_v0.1.2.md`](docs/LAC-IDV-002_v0.1.2.md).

> **Simples, leve. Sempre pronto. Sempre incompleto.**
>
> `LAC-BASES-001` · v0.1.0 · 2026-11-09

Sistema **local e independente** de memória de trabalho: observa mudanças no Git e em diretórios documentais autorizados, preserva eventos temporalizados e permite retomar projetos por uma interface web. **Não utiliza LLM, Codex, Gemini, APIs externas, nuvem ou telemetria.**

## Requisitos

- Linux / Fedora, Git, CMake >= 3.25 e Ninja (ou Make)
- Compilador com suporte ao modo **C++26** (`-std=c++2c` / `-std=c++26`)
- `sqlite-devel` com extensão **FTS5** e `openssl-devel` para SHA-256
- Python 3 para os testes; **não é requerido na execução do binário**

No Fedora:

```bash
sudo dnf install -y gcc-c++ cmake ninja-build sqlite-devel openssl-devel git python3
```

## Compilar e testar

```bash
cd lac-laboratorio
cmake -S . -B build -G Ninja -DCMAKE_BUILD_TYPE=Release
cmake --build build -j"$(nproc)"
ctest --test-dir build --output-on-failure
```

Instalar opcionalmente no usuário, **sem sudo**:

```bash
cmake --install build --prefix "$HOME/.local"
```

Para uso no diretório do projeto, preceda os comandos com `./build/lac`; após instalar, use `~/.local/bin/lac` ou adicione `~/.local/bin` ao PATH.

## Primeiros passos

```bash
./build/lac init
./build/lac register --project "ELO/OS" --path "$HOME/dev/cpp/elo-os" --kind git
./build/lac register --project "TESSITURA" --path "$HOME/dev/cpp/tessitura/docs" --kind docs
./build/lac scan
./build/lac verify
./build/lac serve --webroot ./web --port 8765 --scan-every 180
```

Abra **http://127.0.0.1:8765** no navegador. Os caminhos acima são **exemplos**: registre apenas diretórios existentes. É possível registrar novas fontes pela aba **Fontes** na interface web, sem CLI.

A execução de `serve` observa fontes a cada 180 segundos por padrão e oferece um botão **Observar agora**. Não abre portas externas: só `127.0.0.1`.

## Consultas e continuidade

Na interface web:

- **Visão geral:** hero, indicadores, linha do tempo e ações rápidas, conforme o painel de referência.
- **Linha do tempo:** filtrar por projeto, tipo, palavra e data; botão para os sete dias recentes.
- **Projetos e Eventos:** cartões e registros reais, consultados no banco local.
- **Gestão:** Observação, Integridade, Relatórios e preferências persistidas somente no navegador.
- **Continuidade:** registrar pendências e encerrá-las mediante novo evento (sem apagar o anterior).
- **Relações:** cadastrar associação **candidata** ou **confirmada pelo usuário**, nunca gerar causalidade implícita.
- **Fontes:** cadastrar projetos/repositórios Git e pastas de documentos.
- **Registros manuais:** declaração, decisão, retificação ou pendência. São marcados como `declared`.
- **Exportar diário:** baixar Markdown com ocorrências, origem, data de registro e SHA-256 por evento.

Pelo terminal:

```bash
./build/lac report --from 2026-11-07 --to 2026-11-08 --out fim_de_semana.md
./build/lac anchor --out "$HOME/Documentos/LAC_ANCHOR_2026-11-09.txt"
./build/lac verify --anchor "$HOME/Documentos/LAC_ANCHOR_2026-11-09.txt"
./build/lac stats
```

**Guarde o arquivo âncora fora do diretório do banco e preferencialmente em backup independente.** O comando `anchor` não sobrescreve uma âncora existente.

## Inicialização ao entrar no desktop (opcional)

Depois de `cmake --install build --prefix "$HOME/.local"`:

```bash
mkdir -p "$HOME/.config/systemd/user"
cp systemd/lac.service "$HOME/.config/systemd/user/lac.service"
systemctl --user daemon-reload
systemctl --user enable --now lac.service
systemctl --user status lac.service
```

O serviço funciona na sessão do usuário; não exige root. O serviço não observa qualquer pasta até que suas fontes sejam registradas explicitamente.

Para desativá-lo: `systemctl --user disable --now lac.service`. Para remover as fontes, basta deixar de observar; **a versão 0.1 não fornece exclusão da trilha histórica**.

## O que é evidência e o que não é

| Origem | Tipo de registro | O que pode afirmar |
|---|---|---|
| Git | `git_commit`, `observed` | O commit e sua mensagem foram encontrados em um repositório registrado. **Não comprova funcionalidade validada.** |
| Diretório | `file_added`, `file_changed`, `file_missing`, `observed` | O hash e caminho foram observados ou não encontrados no momento da varredura. **Não prova criação/exclusão exatamente naquele momento.** |
| Pessoa | `note`, `decision`, `todo`, `correction`, `declared` | Uma declaração humana foi registrada; **não constitui verificação automática**. |
| Pessoa | `relation`, `proposed/declared` | Uma associação foi proposta ou confirmada por alguém; **não demonstra causalidade**. |

O LAC não lê conteúdo interno de PDFs/DOCX nem integra conversas privadas do ChatGPT. A busca FTS5 indexa **títulos, mensagens de commit, notas escritas e referências/caminhos**, não o texto de todos os documentos. Futuras integrações devem respeitar autorização, proveniência e isolamento dos projetos.

## Segurança e limites explícitos da v0.1

- Escuta **apenas no loopback IPv4**, valida `Host` e `Origin`, exige cabeçalho local para ações de escrita, rejeita leitura arbitrária de arquivos, impõe limites de tamanho e não usa shell para executar Git.
- HTTP **não deve ser exposto por proxy reverso, `--network host`, encaminhamento de portas, túnel ou rede pública**. Não há autenticação multiusuário.
- Os arquivos observados nunca são modificados. O diretório registrado de documentos pode incluir `.md`, `.tex`, `.pdf`, `.zip`, `.docx`, `.xlsx`, `.json` e outros tipos explícitos no código.
- Arquivos acima de **32 MiB** não são indexados. Limite de **5.000 arquivos elegíveis por raiz**. Diretórios `.git`, `build`, `output`, `node_modules` e outros técnicos são ignorados. Symlinks não são seguidos.
- Git: consulta até **1.000 commits por raiz e varredura**. Se houver mais, commits antigos além do limite não são importados.
- SQLite usa WAL, transações e **gatilhos append-only** para eventos; **projeções** (`file_snapshots`, `roots`) podem ser atualizadas. Alterações intencionais feitas por um administrador ao DB podem contornar gatilhos. A âncora externa detecta alterações na parte histórica por ela referenciada, desde que esteja protegida.
- SHA-256 **não é assinatura digital**, nem garante autoria, veracidade científica ou segurança contra quem altera tanto o banco quanto a âncora externa.
- Não há replicação, backup automático, classificação semântica, autenticação de rede ou integração nativa com IDE. Não inclua documentos confidenciais sem avaliar seus caminhos e títulos; eles ficam pesquisáveis para o usuário local.
- `occurred_at` preserva a data fornecida pelo Git ou a data da observação; `recorded_at` marca o ingresso no banco. O diário pode incluir fatos históricos importados hoje.

## Diretórios e documentos

```
include/lac/          contratos C++
src/                  ingestão, SQLite, integridade e servidor web
web/                  frontend HTML, CSS e JavaScript estáticos
tests/                testes de integração
systemd/              serviço de usuário opcional
scripts/              script de instalação auxiliada
docs/                 fundamentos, ADRs, limitações
```

Documentação constituinte: [`docs/LAC-BASES-001_v0.1.0.md`](docs/LAC-BASES-001_v0.1.0.md).

## Estado da entrega

**Implementado e testado em ambiente Linux com GCC 14.2, CMake 3.31, SQLite 3.46 + FTS5 e OpenSSL 3.5, em modo `-std=c++26`.** A validação final em Fedora 44 / GCC 16 e a execução prolongada permanecem atividades de integração local.

## Licença

Copyright (C) 2026 José Pedro Trindade.

Este projeto é licenciado sob a **GNU General Public License v3.0 (GPL-3.0-only)**.
Consulte o texto completo em [`LICENSE`](LICENSE).
