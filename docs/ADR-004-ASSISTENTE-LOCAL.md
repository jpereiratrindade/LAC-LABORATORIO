# ADR-004 — Assistente local, memória e automação

- Data: 2026-11-09.
- Estado: proposta técnica para execução incremental.
- Direção solicitada: experiência visual, automação e assistente com LLM local
  e memória persistente. Implementação ainda não iniciada.
- Referências: [plano](PLANO-ASSISTENTE-LOCAL.md),
  [retomada](CONTINUIDADE.md), [governança](ADR-000-GOVERNANCA.md).

## Contexto

O LAC já observa fontes, preserva eventos e oferece API e MCP. A interface
continua concentrada em listas e formulários. A evolução deve preparar contexto
automaticamente e permitir explorar trajetórias e relações visualmente.

O assistente precisa lembrar preferências e feedback entre sessões, indicar
suas fontes e operar sem exigir uma nova conversa para cada acontecimento.
Memória persistente não implica treinamento automático dos pesos do modelo.

## Arquitetura proposta

1. O núcleo C++ mantém observação, autenticação, contratos, validação de escrita
   e histórico append-only. Não delega suas invariantes ao modelo.
2. Um serviço de automação local, inicialmente em Python, processa fila durável,
   recupera contexto autorizado e consulta um provedor local de inferência.
3. Ollama é o primeiro adaptador proposto. Modelo e limites serão escolhidos
   após inventário do servidor e avaliação com conteúdo em português.
4. O navegador acessa somente a API autenticada do LAC. O serviço de inferência
   fica no loopback do host de execução; nuvem e fallback remoto ficam
   desabilitados. Uma implantação em outro host exige contrato próprio.
5. Memória, trabalhos, arranjos visuais e sínteses são dados derivados com
   esquema versionado. Declarações e revisões relevantes geram eventos pela
   camada de escrita do núcleo; o worker não escreve diretamente em `events`.
6. A integração com o worker precisa de identidade técnica e permissões por
   ação/escopo. A sessão OTP humana de doze horas e a credencial administrativa
   atual não resolvem, sozinhas, a execução contínua com privilégios limitados.

## Contratos a fechar antes da implementação correspondente

- Eventos incrementais por cursor de ingestão, e não por data de ocorrência.
- Referências estáveis para projeto, evento, artefato e revisão de artefato.
- Relações tipadas, justificadas e vinculadas às referências utilizadas.
- Autoria explícita da automação; compatibilidade com registros `llm:mcp:`.
- Trabalho com chave idempotente, lease, tentativas limitadas e retomada.
- Resultado estruturado com versão, fontes, modelo, prompt e escopo.
- Revisões de memória com proprietário, validade e proveniência.
- Endpoint ou canal local autenticado de menor privilégio para o worker.

As rotas novas serão especificadas em T01. Não são APIs disponíveis hoje.

## Política de autonomia

Dentro das tarefas e fontes habilitadas, observação, recuperação, sínteses e
registro de propostas atribuídas à LLM podem executar automaticamente.
Confirmação humana de relações, adoção de compromissos e ampliação de fontes
exigem ações humanas explícitas. Conteúdo de documento não amplia permissões.

Aceitar ou rejeitar uma proposta informa a memória com seu contexto. Uma
rejeição não constitui regra universal; confirmação não demonstra causalidade.
Saídas estruturadas precisam de validação de schema e referências. Schema
válido não garante que uma interpretação seja verdadeira.

## Consequências e compatibilidade

- O produto ganha inferência local; o núcleo determinístico continua funcional
  quando o modelo está indisponível. Essa evolução amplia o produto descrito
  nas ADRs 000 e 002, sem retirar as garantias do núcleo.
- Migrações são aditivas e testadas sobre cópia de banco antigo. A versão
  atual aceita apenas `user_version <= 1`; rollback de binário após migração
  exige banco compatível, sem descartar registros posteriores.
- Retificações preservam o histórico. Desativar uma memória derivada impede
  uso em novos contextos e invalida caches; não apaga o evento de origem.
- A escolha do modelo depende do hardware disponível e de avaliação no host
  efetivo; funcionamento no servidor não deve ser inferido a partir da estação.

## Alternativas fora da primeira entrega

Treinamento contínuo de pesos, agentes com shell livre, coleta irrestrita,
colaboração simultânea no canvas e integração presumida com outros sistemas.
Busca vetorial será avaliada somente se a recuperação lexical/contextual
mostrar uma limitação mensurável.

## Referências técnicas

- [API local do Ollama](https://docs.ollama.com/api/introduction).
- [Saídas estruturadas](https://docs.ollama.com/capabilities/structured-outputs).
- [Modo local e configuração](https://docs.ollama.com/faq).

Revalidar documentação na implementação. Não fixar modelo ou tamanho de
contexto com base apenas nos exemplos dessas páginas.
