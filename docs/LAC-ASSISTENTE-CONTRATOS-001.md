# LAC — contratos do assistente local, versão 1

Data: 2026-11-09. T01 concluída como especificação; rotas desta seção ainda
não estão implementadas. Ver [plano](PLANO-ASSISTENTE-LOCAL.md).

## Host e primeiro provedor

O usuário confirmou a estação Fedora atual como host, junto ao LAC existente.
Inventário por `/proc`, `/sys/class/drm` e API local, em 2026-11-09:

- Ryzen 9 7950X, 32 threads, 61,9 GiB de RAM.
- GPU AMD dedicada, PCI 1002:744c, 24 GiB de VRAM; GPU integrada adicional.
- Aproximadamente 554 GiB disponíveis no home no momento da inspeção.
- Ollama 0.32.5 acessível em `127.0.0.1:11434`; nenhum modelo carregado naquele
  instante. `qwen2.5:7b` e `qwen2.5:14b` já instalados, ambos Q4_K_M, com
  capacidade de geração e sem destino remoto declarado em `/api/show`.

Ollama é o runtime inicial. `qwen2.5:7b` é candidato para primeira avaliação;
modelo definitivo depende de qualidade e latência medidas. VRAM disponível
não comprova que o runtime esteja acelerando na GPU: verificar `/api/ps` após
inferência. Nada neste inventário comprova capacidade do labeco-srv.

Adaptador só usa endereço loopback, modelo instalado com digest e tamanho
local, e rejeita modelos que declarem `remote_host`/`remote_model`. Não há
download ou fallback remoto. Configuração global `OLLAMA_NO_CLOUD=1` será
verificada na implantação T12; não foi alterada no Ollama compartilhado.

## Identificadores e proveniência

- `project:<id>`: ID estável do projeto, independente do nome.
- `event:<id>`: evento histórico imutável.
- `artifact:<id>`: artefato cadastrado, inicialmente por raiz e caminho relativo.
- `artifact:<id>:revision:<n>`: revisão observada, hash e fonte autorizada.
- `relation:<id>`: relação tipada; `result:<id>`: resultado derivado.
- `memory:<id>:revision:<n>`: revisão de memória derivada.

Renomear caminho não implica continuidade de identidade automaticamente.
Referências a conteúdo trazem hash da revisão efetivamente lida. Se o arquivo
mudou, recuperar a nova revisão ou informar indisponibilidade; não atribuir
conteúdo atual a hash antigo. IDs desconhecidos não são aceitos por escrita.

## Feed incremental — T03

`GET /api/assistant/feed?after_id=0&limit=100` devolve eventos em ordem crescente
de ID, independentemente de `occurred_at`. Limite de 1 a 200. Resposta:

```json
{
  "schema_version": "1",
  "items": [{"ref": "event:101", "project_ref": "project:1", "origin": "observer"}],
  "next_after_id": 101,
  "has_more": false
}
```

Para identidade limitada, o servidor percorre uma janela de IDs e filtra o
escopo. `next_after_id` aponta o último ID examinado, mesmo sem itens visíveis;
`has_more` indica IDs posteriores. Isso evita loop sobre janela sem permissão.
Cursor de cliente não representa autorização nem substitui checkpoint durável.
Trocar escopo exige reprocessamento explícito, sem retroagir o cursor por acaso.

Importação de commit antigo é um evento novo para o feed. A UI pode ordenar
por ocorrência; automação usa ingestão. Eventos produzidos pela automação são
identificados e não realimentam a mesma tarefa automaticamente.

## Identidade técnica — T03

Credencial própria para worker, aleatória com pelo menos 256 bits; só digest
persistido no banco de autorização. Arquivo privado 0600 entregue ao serviço,
fora do repositório e fora dos argumentos do processo. Validação distingue
`human`, `external_llm`, `automation` e o administrador técnico legado.

Credencial do worker aceita somente ações habilitadas e IDs de projetos/fontes
atribuídos pelo servidor: ler feed/contexto, reivindicar trabalho, publicar
resultado e consultar seu estado. Não permite cadastrar fontes, ampliar
escopo, confirmar relações, assumir compromissos ou acessar memória pessoal.
Rotas não permitidas retornam 403, inclusive rotas administrativas existentes.

Credencial pode ser rotacionada/revogada; revisão de política é verificada em
cada operação e antes de persistir resultado. Mudanças de política são ações
humanas autenticadas. O worker funciona no boot sem depender de OTP de uma
pessoa ou token administrativo irrestrito. Sem credencial válida, aguarda.

## Fila durável — T05

Trabalho identifica tarefa, projeto, fontes/revisões, versão da política,
prompt e modelo. Chave idempotente: SHA-256 de JSON canônico desses campos.
Defaults iniciais: uma inferência por vez, agregação por projeto por 15 segundos,
lease de 120 segundos com renovação e no máximo três tentativas transitórias.

Estados: `pending`, `running`, `waiting_provider`, `completed`, `failed`,
`cancelled`. Pausa impede reivindicações; revogação cancela trabalho sem escopo.
Falha de saída/validação não é reexecutada indefinidamente.

Reivindicação devolve lease opaco e revisão. Publicar resultado exige lease
ativo, chave idempotente e escopo ainda válido. Resultado, evento atribuído,
conclusão e checkpoint são gravados em transação do núcleo. Repetição da mesma
entrega retorna resultado anterior; mesma chave com payload diferente gera 409.
Lease expirado não pode publicar, mesmo se nenhuma nova execução começou.

API futura: `POST /api/assistant/jobs/claim`, `/renew`, `/complete`, `/fail`.
Essas rotas não fazem parte da versão operacional atual.

## Contexto e saída de síntese — T04/T06/T07

Entrada inicial do adaptador, já recuperada pela camada autorizada:

```json
{
  "project_ref": "project:1",
  "sources": [{
    "ref": "event:101",
    "title": "Revisão do protocolo",
    "text": "Foi registrada uma revisão do protocolo. A validação segue pendente.",
    "nature": "declared"
  }]
}
```

O adaptador não lê arquivos nem busca fontes por conta própria. Começa com
até oito fontes e 6.144 bytes de JSON de contexto; exceder limite é erro
explícito, sem truncamento silencioso. Contexto vazio não gera inferência.

Saída do modelo segue [schema de síntese](../contracts/assistant-summary.schema.json):
`schema_version`, `summary`, `source_refs`, `gaps`. Referências precisam estar
na entrada; identificador inventado torna saída inválida. O texto deve preservar
diferença entre observação e declaração. Validação estrutural não garante
fidelidade semântica, que deve ser avaliada separadamente.

Envelope produzido pelo adaptador inclui projeto, modelo/digest, versão do
prompt, hash do contexto, duração e resultado validado. T07 persiste por API
do núcleo, nunca por inserção direta do worker no histórico.

Erros estáveis: `invalid_context`, `unavailable`, `model_missing`,
`remote_model`, `invalid_response`, `invalid_output`, `model_changed`,
`cancelled`, `timeout`. Sem corpo de documentos ou credenciais nas mensagens.

## Relações e revisão — T09

Novas relações usam referências de entidades, tipo, direção quando aplicável,
justificativa e fontes. Vocabulário inicial: `related_to`, `version_of`,
`cited_by`, `rectifies`. `version_of` e `rectifies` exigem vínculo explícito no
registro; sem apoio, a LLM só pode propor `related_to`.

Proposta da LLM permanece `candidate`. Ação humana de confirmar, descartar ou
retificar produz evento novo ligado à proposta. Projeção mostra estado atual;
histórico preserva estados anteriores. Confirmação não demonstra causalidade.
Relações antigas entre projetos continuam legíveis, com seus IDs e eventos.

## Memória e apresentação — T08/T10/T11

Memória tem ID, revisão, escopo `laboratory`/`personal`, proprietário autenticado,
tipo, conteúdo, proveniência, validade e estado `active`/`superseded`/`disabled`.
Proprietário vem da sessão, nunca de campo livre. Worker inicial só usa memória
compartilhada autorizada. Memória pessoal entra apenas em pedido da pessoa.

Revisar memória invalida cache pela versão; desativar impede uso futuro em
contexto. Preferência é declaração explícita ou proposta revisável identificada.
Ausência de feedback não é aceitação. Feedback contextual não vira regra global.

Seleção, filtros e arranjos visuais pertencem à pessoa. Dados simulados do
protótipo ficam fora da aplicação operacional, identificados; não indicam
inferência real nem escrevem no banco. Ações de revisão no protótipo apenas
demonstram estados.

## Migração e formato HTTP

T03 introduzirá migração versionada a partir do schema 1, de forma transacional,
com backup consistente. Não alterar serialização, campos ou hashes de eventos
antigos para inserir autoria nova. Atribuição nova deve ser reconhecível na
referência e nas projeções, mantendo compatibilidade com `llm:mcp:`.

Novos endpoints preservam HTTP atual: respostas JSON; POST form-urlencoded,
`X-LAC-Local: 1`, autenticação e limite de 16 KiB. Objetos estruturados via
campo JSON validado. Resultado inicial é pequeno; conteúdo de contexto é
recuperado em partes limitadas. Payload maior exige contrato novo, não ampliar
limites globais sem avaliar servidor. Endpoints com memória pessoal devem
derivar dono da sessão autenticada e rejeitar identidades técnicas.

Rollback de binário exige banco compatível; preservar novos registros antes
de restaurar backup. Não usar um binário antigo sobre schema futuro.

## Referências consultadas

- [Ollama: chat](https://docs.ollama.com/api/chat).
- [Ollama: modelos instalados](https://docs.ollama.com/api/tags).
- [Ollama: JSON schema](https://docs.ollama.com/capabilities/structured-outputs).

Documentação conferida nesta etapa; testes no runtime local têm registro próprio.
