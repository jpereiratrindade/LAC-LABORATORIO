# ADR-003 — Login institucional e acesso restrito por padrão

- **Estado:** Accepted para v0.1.4
- **Data:** 2026-11-09
- **Substitui:** autenticação por token compartilhado da ADR-002.

O usuário deve provar acesso a uma caixa do domínio exato `embrapa.br` por código de uso único enviado por SMTP TLS. Loopback não é exceção. Dados e administração exigem sessão; somente assets de login, contratos de autenticação e saúde mínima são públicos.

Códigos têm seis dígitos, dez minutos de validade e até cinco tentativas. Reenvios e solicitações têm limites persistentes por e-mail/IP/instalação. Não existe modo que mostre códigos no HTTP ou nos logs. SMTP indisponível implica acesso bloqueado.

Um adaptador Python padrão trata SMTP, HMAC, sessões e rate limiting em banco separado, sem dependências pip nem alteração do histórico. A ponte C++ transmite credenciais via stdin em descritor anônimo, sem argv ou arquivos temporários. O núcleo de observação e a CLI permanecem determinísticos e independentes de LLM.

Sessões duram doze horas e são revogáveis; cookies são HttpOnly/SameSite=Strict. A API aceita o token de uma sessão para MCP, que pode salvar sua sessão em arquivo privado. Credenciais de serviço são uma exceção explícita e ficam desabilitadas por padrão.

A instalação reaproveita somente configuração SMTP existente do MORFO, quando disponível, sem executar `.env` e sem compartilhar usuários/sessões. Todos os usuários institucionais verificados compartilham os dados da instalação; uma allowlist opcional restringe endereços. Não se introduz ACL por projeto nesta entrega.

A rede permanece configurável. O HTTP existente continua limitado à LAN confiável; SMTP usa TLS com validação de certificado. Dados de login não tornam o serviço um provedor de identidade do ecossistema. O catálogo sister-synth apenas observa e redireciona para o LAC.

Contrato e limites: [LAC-AUTH-001](LAC-AUTH-001_v0.1.4.md).
