# LAC-BASES-001 — Bases do Laboratório de Continuidade

**Versão:** 0.1.0
**Data:** 2026-11-09
**Estado:** proposto e operacional em bancada
**Tipo:** documento constituinte, não comprovação empírica
**Lema:** Simples, leve. Sempre pronto. Sempre incompleto.

## 1. Problema de pesquisa e engenharia

Os rastros de trabalho estão dispersos: commits, diretórios, versões de documentos, discussões, decisões e tarefas. A reconstrução posterior depende de memória pessoal, da disponibilidade das conversas e de buscas manuais. O LAC visa reduzir o custo de **retomar uma trajetória** preservando seus acontecimentos recuperáveis, relações explícitas e indeterminações.

A questão não é criar uma IA onisciente. É construir **continuidade operacional verificável** dentro dos limites da evidência disponível.

## 2. Compromissos epistemológicos

### REA — Reflexividade Epistêmica e Adaptativa

A interpretação humana pode ser revista. O sistema preserva registros de correção como **novos acontecimentos**; não reescreve silenciosamente o registro passado. REA é uma orientação, **não um classificador computacional**.

### RIT — Reflexividade sob Integridade Temporal

Preservar a distinção entre tempo do acontecimento e tempo de observação/registro. A fila de eventos deve ser append-only, identificada e encadeada por hashes. A verificabilidade depende da conservação do banco e de âncoras independentes; não promete prova criptográfica de autoria.

### MPRR — Percepção Relacional da Realidade

O MPRR permanece um **referencial metodológico autônomo**. O LAC pode permitir que pessoas registrem relações e elaborem comparações, mas não concluir por algoritmo que uma associação é um mecanismo, uma causa ou uma oportunidade realizada. A relação possui natureza explícita: candidata ou confirmada por uma pessoa, sem equivaler a validação científica.

### Sempre pronto. Sempre incompleto.

Uma primeira versão deve ser útil com dois repositórios e uma pasta, sem exigir ontologia total, processamento distribuído, embeddings, vetorizações ou servidores de IA. A incompletude é modelada honestamente: evidência insuficiente permanece insuficiente.

## 3. Decisões técnicas

1. **Processo único:** C++26 + SQLite + OpenSSL Crypto, frontend HTML/CSS/JS estático.
2. **Sem integrações invasivas:** observação autorizada por raiz explicitamente registrada (`git` ou `docs`).
3. **Sem LLM no núcleo:** tarefas determinísticas de detecção, hashing, filtragem e recuperação.
4. **Modelo de evento:** `id`, `project_id`, `kind`, `title`, `body`, `source_type`, `source_ref`, `occurred_at`, `recorded_at`, `evidence_state`, `dedupe_key`, `prev_hash`, `event_hash`.
5. **Histórico imutável e projeções mutáveis:** `events` append-only; snapshots não pretendem ser história.
6. **Idempotência:** Git identificado por raiz+SHA; documentos versionados por raiz+caminho+revisão, revisões só incrementam após alteração; notas humanas são acontecimentos distintos.
7. **Busca:** FTS5 de títulos, corpo de registros e referências, sem fingir extração semântica de PDFs.
8. **Interface:** localhost, somente leitura ou mutações autorizadas, sem portas públicas.
9. **Diário:** exportação Markdown com data do acontecimento, data de registro e origem.
10. **Integridade:** SHA-256 encadeado calculado a partir de serialização canônica com campos de tamanho prefixado, somado a âncora externa opcional.

## 4. Fronteiras e membranas

| Fronteira | Responsabilidade do LAC | O que permanece fora |
|---|---|---|
| Git | Observar commits acessíveis ao usuário | Certificar que testes passaram ou que a funcionalidade foi implementada |
| Documentos | Observar metadados, caminhos e hashes | Inferir conteúdo ou intenção do autor |
| Pessoa | Armazenar decisões, notas, pendências e retificações | Transformar afirmações em fatos verificados automaticamente |
| TESSITURA | Registrar rastros de trabalho e links | Substituir seu domínio científico temporal-relacional |
| EVIDA | Vincular artefatos por proveniência | Substituir validação de evidências documentais |
| IdeaWalker | Complementar continuidade operacional | Substituir narrativa, ingestão interpretativa ou modelos próprios |
| MÉTIS | Preservar rastros de integração | Executar experimentos metodológicos |

**Não reivindicar integração real** com os projetos externos até que haja contratos e testes correspondentes.

## 5. Invariantes verificáveis

- **INV-001:** um evento inserido não admite `UPDATE` ou `DELETE` via banco operacional.
- **INV-002:** importação repetida, sem alteração na origem, não cria novo evento.
- **INV-003:** cada evento encadeia hash do evento anterior; `verify` detecta alteração não acompanhada de recálculo completo.
- **INV-004:** o compromisso temporal distingue o momento atribuído ao acontecimento e o de registro.
- **INV-005:** declaração humana e observação técnica recebem rótulos diferentes.
- **INV-006:** associação humana não gera causalidade nem promove automaticamente sua confirmação.
- **INV-007:** a aplicação não executa Git através de shell com interpolação do caminho.
- **INV-008:** a interface não serve arquivos arbitrários do sistema de arquivos.
- **INV-009:** nenhuma raiz é observada sem cadastro explícito.
- **INV-010:** o histórico retificado é preservado; a retificação é novo evento.

## 6. Modelo temporal

O Git fornece data do committer, com offset original. Na varredura de documentos, o tempo da observação é o tempo de ocorrência que o sistema **consegue atestar**, não necessariamente a data original de criação. Notas humanas usam momento de declaração. Toda entrada traz `recorded_at` em UTC para evitar retroatividade sem registro.

As consultas temporais filtram a data civil correspondente ao campo `occurred_at` armazenado. Estudos que exijam timezone único deverão introduzir tratamento explícito e documentado, sem reescrever valores anteriores.

## 7. Segurança e privacidade

Processo local com HTTP em `127.0.0.1`. Checagem de Host, Origin e cabeçalho de ações de escrita; CSP, limites de cabeçalhos/corpo, sem CORS. A aplicação não tem modelo de ameaça para exposição em rede ou múltiplos usuários. O banco pertence à conta que executa o serviço. A trilha registra **nomes e caminhos**, que podem ser sensíveis: não cadastrar fontes confidenciais sem avaliação.

Eventos encadeados são evidência de integridade **relativa ao banco**; âncoras externas preservadas fora dele elevam a capacidade de detectar adulteração. Não há assinatura assimétrica, backup automático ou garantia anticorrupção por falha de hardware.

## 8. Testes de aceitação F0

| Caso | Critério |
|---|---|
| Registrar diretório e fazer scan | Adicionar um evento por documento elegível |
| Reexecutar scan | Zero eventos novos, se não houve alteração |
| Alterar documento | Registrar `file_changed`, com hash anterior e novo |
| Desaparecimento observado | Registrar `file_missing`, sem declarar a causa |
| Importar Git | Registrar SHA, mensagem e data do committer |
| Repetir Git | Não duplicar SHA da mesma raiz |
| Registrar decisão | Evento `declared` preservado |
| Registrar relação | Estado explícito `candidate` ou `user_confirmed` |
| Encerrar pendência | Novo evento; evento aberto permanece no histórico |
| Verificar trilha | Cadeia íntegra em estado não adulterado |
| Corromper dado | Detectar divergência (sem recálculo completo dos hashes) |
| API remota/cross-origin | Rejeitar origem/Host não local |
| Exportar diário | Markdown com fonte, datas e hash |

## 9. Limites e programa de pesquisa F1

A integração com exportações do ChatGPT, ferramentas de busca textual completa em documentos, sincronização entre dispositivos, visualização de genealogias de decisões, mecanismos de backup e interfaces com IdeaWalker/TESSITURA/MÉTIS/EVIDA são **possibilidades**, não funcionalidades implementadas.

A primeira pesquisa empírica sugerida consiste em registrar um ciclo semanal de trabalho (incluindo seus silêncios documentais) e comparar: (a) quantidade de acontecimentos recuperáveis; (b) tempo para localizar documentos; (c) quantidade de decisões sem evidência explícita; (d) falsos vínculos sugeridos por busca textual. Só depois avaliar se modelos locais trazem ganho suficiente para justificar custo e risco.

**Critério de evolução:** introduzir uma capacidade somente diante de limitação observável e teste replicável. A ausência de completude não deve gerar um projeto ilimitado.
