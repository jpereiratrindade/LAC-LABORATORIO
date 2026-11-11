# LAC — Laboratório de Continuidade

**Sempre pronto. Sempre incompleto.**

Memória local de trabalho para retomar projetos: acompanha commits e mudanças em documentos, preserva uma linha do tempo e organiza notas, decisões, pendências e relações. Núcleo C++26 com SQLite, interface web, API HTTP e administração opcional por LLM via MCP.

## Plano de evolução e continuidade

A evolução para laboratório visual com automação, assistente LLM local e memória
persistente está no [plano de execução](docs/PLANO-ASSISTENTE-LOCAL.md).
Para retomar o trabalho com outro assistente, comece pela
[passagem de contexto](docs/CONTINUIDADE.md). Essas capacidades estão planejadas;
os comandos abaixo descrevem a versão operacional atual.

Primeira entrega experimental: [prévia visual navegável](prototypes/laboratorio/README.md)
e adaptador de inferência local validado com Ollama. Interface da prévia usa
dados fictícios; automação contínua e memória real seguem nas próximas etapas.
Contratos e inventário: [assistente local](docs/LAC-ASSISTENTE-CONTRATOS-001.md).
Resultados dos testes reais: [avaliação inicial](docs/avaliacoes/2026-11-09-ollama.md).

## Rodar com um comando

Dentro da pasta do projeto:

```bash
./iniciar.sh
```

O comando **compila, testa, instala e inicia o LAC**. Também configura a inicialização no boot, mantém o serviço funcionando após logout e, quando executado novamente, instala a versão atual e reinicia o serviço. Preserva o banco, as fontes cadastradas e a configuração SMTP. O antigo token compartilhado de acesso é desativado.

Ao terminar, mostra os endereços de acesso. Neste computador:

**[Abrir o LAC](http://127.0.0.1:8765)**

O acesso é **restrito por padrão**, inclusive em localhost. Informe seu e-mail **@embrapa.br**, receba o código de seis dígitos e digite-o no painel. O código expira em dez minutos, permite até cinco tentativas e só pode ser usado uma vez. A sessão dura doze horas; use **Sair** para encerrá-la.

O comando reaproveita somente as configurações SMTP do MORFO local, quando disponíveis e ainda não configuradas no LAC, sem executar o arquivo `.env`. Se necessário, ajuste `~/.config/lac/server.env` conforme [config/server.env.example](config/server.env.example) e reinicie o serviço. Sem SMTP configurado, o acesso permanece bloqueado. Códigos nunca são exibidos na interface ou no log.

### Primeiro uso

1. Abra o painel, informe seu e-mail @embrapa.br e confirme o código recebido.
2. Entre em **Fontes** e cadastre um repositório Git ou uma pasta de documentos existente.
3. Execute **Observar agora** e consulte a **Linha do tempo**.
4. Registre notas, decisões e pendências conforme necessário.

Nenhuma pasta é observada antes de ser cadastrada. O serviço observa as fontes a cada 180 segundos. A instalação fica em `~/.local`; depois de instalado, o LAC não depende da pasta do repositório nem do disco de desenvolvimento.

## Requisitos

- Linux com systemd e sessão de usuário acessível para a instalação.
- Git, CMake >= 3.25, Ninja ou Make e compilador com suporte a C++26.
- Bibliotecas de desenvolvimento SQLite3 com FTS5 e OpenSSL.
- Python >= 3.9 para instalação, autenticação do servidor, testes, integrações e MCP. A CLI C++ funciona sem Python.
- Um remetente SMTP com autenticação e TLS para entregar os códigos institucionais. Os testes usam um servidor SMTP TLS local, sem envio real de e-mails.

Os requisitos precisam estar disponíveis antes de executar `./iniciar.sh`. Em Fedora com `dnf`:

```bash
sudo dnf install gcc-c++ cmake ninja-build sqlite-devel openssl-devel git python3
```

Em edições imutáveis, como Silverblue, use o método de instalação de pacotes do sistema; o comando `dnf` acima é destinado às edições tradicionais. Não é necessário executar `iniciar.sh` com sudo. A ativação de **linger**, quando ainda desabilitada, pode solicitar autenticação administrativa. O home precisa estar disponível no boot para funcionar antes do login.

## Rede local e serviço automático

O instalador usa `0.0.0.0:8765`, disponibilizando o painel e a API nas interfaces IPv4. Em outro computador, abra `http://IP_DO_SERVIDOR:8765`, usando um dos endereços exibidos pelo comando de instalação. O login continua exigindo o código enviado ao e-mail institucional.

Todas as rotas de dados e administração exigem sessão autenticada. Apenas a saúde mínima do serviço, os endpoints de login e os arquivos estáticos são públicos. HTTP não cifra o tráfego; use uma rede confiável. O instalador não altera o firewall.

| Ação | Comando |
|---|---|
| Instalar, atualizar e iniciar | `./iniciar.sh` |
| Consultar estado | `systemctl --user status lac-lan.service` |
| Reiniciar a versão instalada | `systemctl --user restart lac-lan.service` |
| Parar agora | `systemctl --user stop lac-lan.service` |
| Consultar logs | `journalctl --user -u lac-lan.service -n 50` |
| Confirmar funcionamento sem login | `loginctl show-user "$USER" -p Linger` — deve mostrar `yes` |
| Desabilitar no boot e parar | `systemctl --user disable --now lac-lan.service` |

O serviço usa o systemd do usuário com **linger**: o gerenciador inicia no boot e continua após logout. Não execute outra instância manual na porta 8765. O instalador substitui o serviço alternativo `lac.service`; uma execução manual precisa ser encerrada antes.

## Integrações opcionais

O comando único inicia o **núcleo, painel e API**, instala os adaptadores e prepara o serviço. As ferramentas externas mantêm sua própria instalação e configuração:

| Integração | Para que serve | Como habilitar |
|---|---|---|
| **Recoll** | Buscar conteúdo em documentos indexados | Instale e prepare o índice no Recoll; em **Integrações**, informe o diretório de configuração e as pastas autorizadas. |
| **ActivityWatch** | Consultar intervalos reportados por aplicativo | Inicie o ActivityWatch no servidor; em **Integrações**, autorize os buckets desejados. |
| **MCP / LLM** | Consultar e administrar o LAC por um cliente compatível | Configure o cliente para iniciar a ponte abaixo. |

Recoll e ActivityWatch não são instalados nem iniciados automaticamente. Dados consultados não entram automaticamente no histórico. Coletores da sessão e fontes em discos removíveis podem ficar indisponíveis antes do login.

### Administração por LLM

Autentique a ponte uma vez no terminal, usando seu próprio e-mail:

```bash
python3 ~/.local/share/lac/scripts/lac_mcp.py --login nome@embrapa.br
```

Digite o código recebido quando solicitado. A sessão é salva com permissão 0600 e expira após doze horas.

O cliente MCP inicia este processo quando precisar usar o LAC; não é um daemon adicional a deixar aberto no terminal:

```bash
python3 ~/.local/share/lac/scripts/lac_mcp.py --allow-write
```

A ponte usa a sessão salva para o endereço do servidor. Também aceita `LAC_SESSION_TOKEN` para uma sessão obtida pela API. Credenciais de serviço via `LAC_SERVICE_TOKEN` são opcionais, administrativas e desabilitadas por padrão; não são o login do painel. Sem `--allow-write`, a ponte oferece apenas consultas. O transporte MCP é **stdio**; a porta 8765 é a API HTTP.

Registros gerados pela LLM indicam essa autoria, e suas relações permanecem candidatas. O núcleo não chama modelos nem envia telemetria. O cliente LLM escolhido pode enviar os dados consultados ao provedor do modelo.

Login e contratos atuais: [acesso institucional](docs/LAC-AUTH-001_v0.1.4.md). Rotas funcionais e integrações: [API/MCP](docs/LAC-API-MCP-001_v0.1.3.md), com autenticação substituída na v0.1.4.

## Dados e limites

- Banco: `~/.local/share/lac/lac.db`.
- SMTP e opções de autenticação: `~/.config/lac/server.env`, com permissão 0600.
- Códigos protegidos por HMAC, hashes de sessões e auditoria de login: `~/.local/share/lac/lac.db.auth.sqlite3`, separados do histórico.
- Todos os e-mails @embrapa.br verificados acessam o mesmo laboratório; não há isolamento de dados por usuário. Uma lista restritiva opcional pode ser definida em `LAC_AUTH_ALLOWED_EMAILS`.
- Configuração de integrações: `~/.local/share/lac/lac.db.integrations.json`.
- Eventos são preservados; correções e encerramentos geram novos registros.
- Observações demonstram registros e mudanças. Não comprovam autoria, produtividade, causalidade ou validade científica.
- A busca do histórico pesquisa títulos, notas e referências. A busca no conteúdo documental depende da integração opcional com Recoll.

Detalhes técnicos, limites de varredura, âncoras de integridade e execução para desenvolvimento: [operação e limites](docs/OPERACAO-E-LIMITES.md). Fundamentos metodológicos: [LAC-BASES-001](docs/LAC-BASES-001_v0.1.0.md).

## Estado e licença

**v0.1.4**, em Fedora 44 / GCC 16: testes de CLI/API/MCP, autenticação institucional, SMTP TLS simulado e verificações do painel. O LAC também possui entrada opcional em **Outros sistemas** no sister-synth, condicionada à observação e ao destino autorizado. Adaptadores Recoll/ActivityWatch foram testados com serviços simulados; índices, extratores e coletores reais precisam de validação no ambiente de uso. Veja o [changelog](CHANGELOG.md).

Copyright (C) 2026 José Pedro Trindade. Licenciado sob **GNU GPL v3.0 (GPL-3.0-only)**. Texto completo em [LICENSE](LICENSE).

## Premissas de desenvolvimento

**Simples, leve. Sempre pronto. Sempre incompleto!**

[Significado e símbolos das premissas](docs/sister-principles/README.md).
