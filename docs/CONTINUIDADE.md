# Continuidade — entrada para qualquer assistente

Atualizado em 2026-11-09. Esta é a passagem de contexto do trabalho de evolução
visual e assistente local. Não depende de acesso ao histórico do chat.

## Pedido e limites desta entrega

O usuário pediu um plano executável e recuperável caso o Codex caia ou outro
assistente precise continuar.
Esta entrega é documentação. Não implementa telas, LLM, memória ou automação,
não instala modelos e não altera serviços locais/remotos.

Direção consolidada na conversa:

- Interface visual, pouco texto permanente, sem aparência de planilha.
- LAC representa trajetórias e conexões entre frentes, além de retomar projetos.
- Automação prepara contexto a partir de acontecimentos autorizados.
- Assistente com LLM local, memória persistente e feedback inspecionável.
- Pessoa explora, corrige e decide; interpretações da LLM têm autoria e fontes.
- Preservar acesso restrito, continuidade temporal e operação após logout.

## Leitura mínima e estado

1. [Plano e tarefas](PLANO-ASSISTENTE-LOCAL.md).
2. [Arquitetura proposta](ADR-004-ASSISTENTE-LOCAL.md).
3. [README operacional](../README.md), para comandos e autenticação atuais.

Base de código analisada: `7b3338e088aec0710646e35b5ad115de06302bf7`.
Árvore estava limpa no início desta entrega. Revalidar o Git na retomada.

- T00: concluída — plano, ADR, passagem de contexto e instruções no repositório.
- T01 a T12: pendentes.
- Próxima tarefa proposta: T01, contratos e inventário do host de inferência.
- Primeiro artefato visual: T02, protótipo navegável com dados ilustrativos.
- Nenhum protótipo, modelo instalado ou teste de inferência foi produzido aqui.

## Fatos importantes para evitar retrabalho

- O núcleo está na v0.1.4; há commits posteriores com captura rápida, cartão
  de continuidade, guia e briefing. Preservar esses trabalhos ao redesenhar.
- Briefing atual usa regras. Não confundir sua existência com LLM instalada.
- Relações existentes ligam projetos; relação documento/decisão é evolução.
- API de eventos retorna no máximo 200, ordenados por ocorrência; não é feed
  incremental seguro para automação. Commits antigos podem ser importados hoje.
- Autoria LLM atual reconhece MCP. Não deixar worker novo aparecer como pessoa.
- Há schema versão 1 e bloqueio a versão futura: projetar migração e rollback.
- OTP é obrigatório, até no loopback. Sessão humana expira em doze horas;
  projetar identidade limitada para worker que funcione sem login.
- Laboratório é compartilhado entre usuários autorizados; memória pessoal
  exige isolamento explícito e teste. Não presumir ACLs por projeto.
- Recoll/ActivityWatch são opcionais. Metadados não comprovam conteúdo,
  produtividade nem causalidade. Modelos e extratores reais não foram validados.

## Verificações desta entrega

Inspeção de Git, documentação, schema, rotas, briefing e instalação existentes.
Validação documental realizada: cinco documentos, 18 links locais e estados
das 13 tarefas conferidos; sem espaços finais ou referências quebradas.
`git diff --check` passou. Repetir a checagem do diff preparado antes do commit.
Não declarar validação de runtime por revisão de Markdown.

Não houve mudança de código; testes de compilação/runtime não são necessários
nesta entrega. Ao executar tarefa de código, usar testes pertinentes do plano.

## Retomar de forma concreta

```bash
git status --short --branch
git log -5 --oneline
```

Ler AGENTS e os documentos acima. Conferir instrução atual do usuário e estado
dos arquivos. Para T01, primeiro esclarecer por evidência qual host executará
inferência; inspecionar recursos apenas nos ambientes disponíveis/autorizados.
Não escolher modelo com base no hardware de outra máquina.

`./iniciar.sh` compila, testa, instala e reinicia o serviço: não executar só
para conferir se a documentação está correta. Comandos de build isolado e
testes estão no plano. Não registrar SMTP, sessões, bancos ou memória de usuários.

## Texto para entregar a outro assistente

> Continue o LAC neste repositório. Leia AGENTS.md, docs/CONTINUIDADE.md,
> docs/PLANO-ASSISTENTE-LOCAL.md e docs/ADR-004-ASSISTENTE-LOCAL.md.
> Confira o Git e o estado real antes de editar. A direção é laboratório
> visual com automação, LLM local e memória rastreável. T00 está concluída;
> a próxima tarefa proposta é T01. Execute o escopo que eu solicitar agora,
> preserve invariantes e atualize a passagem de contexto ao concluir ou parar.

## Registro da próxima execução

Ao continuar, substituir esta seção por data, tarefa em andamento, mudanças,
verificações com resultado, pendências e próximo passo. Se houver alterações
sem commit, identificá-las. Registrar commit da entrega anterior sem tentar
colocar o hash do próprio commit dentro dele.
