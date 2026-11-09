# Continuidade — entrada para qualquer assistente

Atualizado em 2026-11-09. Passagem de contexto para evolução visual e assistente
local; não depende de acesso ao histórico do chat.

## Pedido atual e direção

Depois de registrar o plano, o usuário pediu começar sua execução. Confirmou
que a primeira LLM deve rodar nesta estação, junto ao LAC atual. Não reabrir
essa escolha sem motivo técnico ou nova orientação do usuário.

- Interface visual, pouco texto permanente, sem aparência de planilha.
- Trajetórias e conexões entre frentes, além de retomar projetos.
- Automação prepara contexto a partir de acontecimentos autorizados.
- Assistente local com memória persistente e feedback inspecionável.
- Interpretações têm autoria e fontes; pessoa explora, corrige e decide.
- Preservar acesso restrito, integridade temporal e operação após logout.

## Leitura mínima

1. [Plano e estados das tarefas](PLANO-ASSISTENTE-LOCAL.md).
2. [Contratos e inventário T01](LAC-ASSISTENTE-CONTRATOS-001.md).
3. [Arquitetura](ADR-004-ASSISTENTE-LOCAL.md).
4. [Prévia T02](../prototypes/laboratorio/README.md) e
   [avaliação do modelo T04](avaliacoes/2026-11-09-ollama.md).

## Estado real

Execução começou sobre `7807085`, com árvore limpa. Verificar Git na retomada.

- T00: concluída — plano e instruções de continuidade no repositório.
- T01: concluída — host, inventário e contratos especificados.
- T02: em andamento — protótipo navegável pronto e verificado em navegador;
  falta avaliação com pessoa usuária. Não marcar concluída só por testes.
- T03: pendente — próximo trabalho de backend, sem depender do aceite visual.
- T04: concluída — adaptador isolado com testes simulados e reais iniciais.
- T05 a T12: pendentes.

O LAC operacional não recebeu a nova UI, migração ou worker. O serviço
`lac-lan.service` não foi reiniciado nesta entrega. Nenhum modelo foi baixado.
Ollama existente executou inferências com dados sintéticos. Memória e fila
reais não estão implementadas; a prévia usa localStorage demonstrativo.

## Host confirmado e inferência

Estação: Ryzen 9 7950X, 32 threads, 61,9 GiB de RAM, GPU AMD com 24 GiB de
VRAM dedicada. Ollama 0.32.5 no loopback. Modelo inicial: `qwen2.5:7b` Q4_K_M,
já instalado. Inferência real e alocação em VRAM foram verificadas; ver relatório.

Adaptador: `scripts/lac_local_llm.py`. Recebe contexto JSON no stdin, não lê
fontes por conta própria, não escreve no LAC e não baixa modelos. Aceita
somente loopback e modelo local instalado. Limite de contexto: 6.144 bytes.
Schema: `contracts/assistant-summary.schema.json`. Prompt: `lac-summary-1.1`.

Configuração global `OLLAMA_NO_CLOUD` não foi alterada no runtime compartilhado.
O adaptador rejeita destinos/modelos remotos; confirmar configuração global na
implantação T12. Não anunciar daemon globalmente configurado se não verificado.

## Prévia visual

`prototypes/laboratorio/` contém HTML/CSS/JS independentes, com dados fictícios.
Inclui mapa, comparação, trajetória, revisão, busca, arranjo persistente e
preferências demonstrativas. Não conecta à API nem ao modelo real.

Servidor temporário usado para revisão:

```bash
python3 -m http.server 8876 --bind 127.0.0.1 --directory prototypes/laboratorio
```

Endereço: `http://127.0.0.1:8876`. Se não estiver disponível, iniciar esse
comando. Também é possível abrir o HTML diretamente. Não substituir o painel
autenticado por essa prévia. Capturas locais estão em `.cache/prototype` e
podem ser recriadas; não são necessárias para retomar código.

## Verificações e evidências

- Build isolado configurado e compilado; CTest com CLI/API/autenticação e
  adaptador local passou. Adaptador tem 16 testes simulados, sem modelo real.
- Playwright/Chromium: desktop 1500×1020 e celular 390×844, comparação/origem,
  confirmação, seleção entre vistas, posição/fixação após reload, movimento
  por clique e arraste, mapa por teclado, memória, busca, estados e rascunho.
- Nenhum erro JS ou chamada externa apareceu na verificação do protótipo.
- Três casos reais sintéticos em português, com JSON/referências válidos;
  limites semânticos e tempos constam no relatório de avaliação.
- Instalação em diretório temporário incluiu script/schema e passou em uma
  inferência real. Nenhuma instalação no prefixo operacional nesta etapa.

Comandos reproduzíveis estão no plano. Verificação visual usa
`tests/check_prototype.cjs` e pacote Playwright opcional; nesta estação há uma
instalação em cache que pode ser indicada por `LAC_PLAYWRIGHT_MODULE`.
Reavaliar dependência no próximo ambiente, sem presumir esse caminho.

## Atenção para T03

- `/api/events` retorna até 200 e ordena por ocorrência. Implementar feed por
  ID de ingestão; commits antigos podem chegar hoje. Não usar esse GET como fila.
- Relações atuais ligam projetos. Referências genéricas exigem esquema novo.
- Autoria atual reconhece `llm:mcp:`. Worker novo não pode aparecer como pessoa.
- Schema atual é versão 1 e binário rejeita versões futuras. Migração deve
  preservar IDs, hashes, serialização histórica e capacidade de verificação.
- OTP humano expira em doze horas. Projetar credencial técnica limitada por
  ação/escopo; token administrativo legado não atende esse contrato.
- Laboratório atual é compartilhado. Memória pessoal futura exige isolamento
  explícito; não presumir ACLs por projeto já disponíveis.
- Alguns textos do briefing atual inferem sucesso pela ausência de registros;
  corrigir na integração T07, preservando linguagem metodológica honesta.

## Retomar

```bash
git status --short --branch
git log -5 --oneline
```

Próximo passo: ler contrato T01 e implementar T03 em cópia/banco de teste,
começando por migração aditiva, feed incremental e testes com mais de 200
eventos e ocorrência antiga. Depois implementar identidade limitada e autoria.
Não marcar T03 concluída antes de seus contratos e testes passarem.

`./iniciar.sh` instala e reinicia serviço; não usar como simples teste.
Atualizar este arquivo e estados do plano a cada entrega/interrupção, incluindo
falhas e trabalho parcial. Registrar commit anterior pelo Git, sem tentar
inserir o hash do próprio commit dentro dele.

> Continue o LAC. Leia AGENTS.md, docs/CONTINUIDADE.md e os contratos da T01.
> Confira Git e estado real. Próximo backend: T03. A prévia T02 aguarda
> avaliação visual humana. Preserve histórico e autenticação; atualize a
> passagem de contexto antes de concluir ou interromper.
