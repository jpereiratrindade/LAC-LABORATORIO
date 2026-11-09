# LAC v0.1.4 — Acesso institucional restrito

## Fluxo de acesso

A autenticação é obrigatória em loopback e LAN. O usuário informa um endereço do domínio **exato `embrapa.br`**, recebe por SMTP um código numérico de seis dígitos e o confirma no painel. Não são aceitos subdomínios, outros provedores ou sufixos como `embrapa.br.example.com`.

O fluxo segue os parâmetros do MORFO: dez minutos de validade, uso único, até cinco tentativas e intervalo mínimo de sessenta segundos entre solicitações. Há limites persistentes de quinze minutos por endereço, IP e instalação. Reenvio invalida o código anterior. A geração usa aleatoriedade criptográfica sem viés; o banco guarda HMAC do código, nunca seu valor original.

A sessão dura doze horas. O navegador recebe cookie `lac_session` com `HttpOnly`, `SameSite=Strict` e `Path=/`. A API também devolve `session_token` no sucesso para clientes não navegadores. O painel não grava tokens em localStorage/sessionStorage. O banco guarda apenas hashes SHA-256 das sessões; logout revoga a sessão. A sessão persiste após reinício do serviço até expirar.

Não existe login por token compartilhado, senha fixa, bypass local ou modo de desenvolvimento que devolva OTP. `LAC_API_TOKEN` deixou de autenticar o servidor. Sem configuração SMTP ou se o envio falhar, o login permanece bloqueado.

## Configuração privada

Execute `./iniciar.sh`. O instalador prepara `~/.config/lac/server.env` com permissão 0600. Quando o LAC ainda não tem um campo SMTP e existe `../MORFO/.env`, copia somente os campos correspondentes de SMTP, sem executar esse arquivo, sem copiar usuários ou sessões e sem imprimir credenciais. Para outra localização, use `LAC_SMTP_SOURCE=/caminho/MORFO/.env ./iniciar.sh`.

Para configuração manual, siga [`config/server.env.example`](../config/server.env.example):

- `LAC_SMTP_HOST`, `LAC_SMTP_PORT` (padrão 587).
- `LAC_SMTP_USER`, `LAC_SMTP_PASS`, `LAC_SMTP_FROM`.
- `LAC_SMTP_SECURITY=starttls` ou `ssl`; SMTP sem TLS é recusado.
- `LAC_SMTP_CA_FILE`, opcional para uma autoridade certificadora privada.
- `LAC_AUTH_ALLOWED_EMAILS`, opcional: lista separada por vírgulas para restringir ainda mais os endereços institucionais.

Reinicie o serviço após editar. O remetente SMTP pode ser o já usado pelo MORFO; o domínio obrigatório aplica-se ao destinatário de autenticação. Nenhum conteúdo de projetos é enviado nos e-mails de login.

Todos os usuários institucionais verificados compartilham o mesmo laboratório e os mesmos poderes administrativos. A autenticação não implementa isolamento por usuário ou papéis. Use a allowlist para restringir quem pode entrar em uma instalação pessoal.

## API de autenticação

POST usa `application/x-www-form-urlencoded`, `X-LAC-Local: 1` e validação de Host/Origin. O IP de limitação vem da conexão, nunca de um header encaminhado pelo cliente.

| Método/rota | Entrada | Comportamento |
|---|---|---|
| GET `/api/health` | — | Saúde mínima pública: `service=lac`, versão e `auth_required=true`; não expõe contagens ou eventos |
| GET `/api/auth/status` | Cookie ou Bearer opcional | Estado da própria sessão, domínio permitido e disponibilidade da configuração SMTP |
| POST `/api/auth/request-code` | `email` | Solicita o código; 403 para domínio inválido, 429 para limite, 503 para SMTP indisponível |
| POST `/api/auth/verify-code` | `email`, `code` | Consome o código e retorna sessão/cookie; 401 para falha, expiração ou bloqueio |
| POST `/api/auth/logout` | Cookie ou Bearer | Revoga a sessão e limpa o cookie |

As demais rotas `/api/*` exigem sessão e retornam 401 quando ausente/inválida. Falhas no componente de autenticação retornam 503 e nunca liberam dados. Arquivos estáticos são públicos para apresentar a tela de login; não contêm dados do banco.

## MCP

Primeiro autentique pelo terminal:

```bash
python3 ~/.local/share/lac/scripts/lac_mcp.py --login nome@embrapa.br
```

O código é digitado sem eco. A sessão fica em `~/.config/lac/mcp-sessions.json`, permissão 0600, associada ao endereço exato do servidor e com validade de doze horas. Para outro servidor, acrescente `--url http://IP_PRIVADO:8765` tanto no login quanto na configuração do cliente.

Depois configure o cliente para iniciar a ponte por stdio normalmente; acrescente `--allow-write` somente se desejar administração. `LAC_SESSION_TOKEN` pode fornecer uma sessão obtida pela API. O logout/revogação e a expiração continuam sendo verificados pelo servidor em cada chamada.

`LAC_SERVICE_TOKEN` permite automação serviço a serviço, mas **não é criado nem habilitado por padrão**. Se definido explicitamente no servidor, deve ter pelo menos 32 caracteres e concede administração completa; nesse caso configure o mesmo valor no processo MCP. É uma opção operacional do administrador, não um login institucional do painel. O nome legado `LAC_API_TOKEN` no cliente só transporta uma credencial já válida; o servidor não aceita o antigo token compartilhado.

## Persistência e auditoria

O histórico científico permanece no banco original e mantém seus hashes. Autenticação usa `CAMINHO_DO_DB.auth.sqlite3`, permissão 0600, com:

- HMAC de desafios e segredo local privado;
- hashes de sessões e expiração;
- limites de requisição persistentes por quinze minutos;
- auditoria de pedidos, falhas e logins, com e-mail/IP e retenção de trinta dias.

Cookies e códigos não são passados em argumentos de processos: o C++ fornece os parâmetros ao adaptador Python por stdin usando um descritor de memória anônimo. Não há dependências pip. Python é obrigatório para a autenticação do servidor HTTP; a CLI C++ continua independente.

## Rede e integração com SisTer/SYNTH

O serviço permanece em `0.0.0.0:8765`, com login obrigatório. HTTP não cifra códigos ou sessões entre navegador e LAC; mantenha a LAN confiável. Para um gateway HTTPS que preserve o Host validado, `LAC_COOKIE_SECURE=1` marca cookies Secure e permite Origin HTTPS correspondente. O gateway precisa encaminhar para um Host IPv4/localhost aceito; o servidor não confia em headers de proxy para identificar o cliente.

O sister-synth inclui o LAC em **Outros sistemas**, usa a saúde pública mínima para observá-lo e só redireciona para um provedor observado cujo destino pertença à allowlist. Esse redirecionamento não compartilha sessões nem autentica o usuário; o LAC mantém seu próprio login. Sem manifesto assinado, a identidade permanece `UNVERIFIED`.

## Validação

Testes cobrem domínio exato, tentativas, expiração, reenvio, concorrência de uso único, persistência/revogação de sessão, rejeição do token legado e SMTP indisponível. O fluxo HTTP real é exercitado contra um servidor SMTP TLS local com certificado de teste; nenhuma mensagem é enviada a caixas externas durante os testes.

Referências técnicas: [smtplib](https://docs.python.org/3/library/smtplib.html), [orientações de autenticação OWASP](https://cheatsheetseries.owasp.org/cheatsheets/Authentication_Cheat_Sheet.html). O código local do MORFO foi consultado como referência funcional; seu backend e seus dados não são alterados.
