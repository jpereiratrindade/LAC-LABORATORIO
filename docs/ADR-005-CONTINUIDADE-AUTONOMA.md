# ADR-005 — Autonomia Operacional, Continuidade Documental e Investigação Relacional

- **Estado:** Accepted
- **Data:** 2026-11-09
- **Decisão:** Inversão fundamental do desenvolvimento do LAC. O LAC deixa de ser projetado a partir de ferramentas (Git, Recoll, Ollama, SQLite, formulários web) e passa a ser construído a partir do trabalho intelectual que deve acompanhar e ampliar de forma contínua e autônoma.
- **Referências:** [ADR-000](ADR-000-GOVERNANCA.md), [ADR-001](ADR-001-CADEIA-TEMPORAL.md), [ADR-004](ADR-004-ASSISTENTE-LOCAL.md), [CONTINUIDADE.md](CONTINUIDADE.md).

---

## 1. Contexto e Diagnóstico Crítico

A avaliação do LAC vinha incorrendo em uma inversão de foco: media-se o sucesso pelo número de commits observados, documentos indexados, rotas de API, integridade de hashes e telas construídas. Isso transformou temporariamente o sistema em uma ferramenta de alimentação manual (um visualizador de Git ou um formulário burocrático semelhante a planilhas).

A pergunta fundamental do LAC é:
> **Quanto do trabalho de organizar, relacionar, contextualizar e desenvolver nosso conhecimento o LAC consegue realizar autonomamente?**

O LAC não deve esperar que o pesquisador entre para registrar o que aconteceu, preencher formulários ou descrever decisões que já estão documentadas. O sistema deve trabalhar em segundo plano sobre os registros que a pesquisa já produz.

A intervenção humana não é dispensada: ela é reservada para a reflexão, a crítica, a deliberação ética e as decisões que exigem responsabilidade institucional e científica.

---

## 2. A Arquitetura da Continuidade Autônoma

O sistema organiza-se em quatro camadas integradas:

```
┌────────────────────────────────────────────────────────────────────────┐
│ 1. Produção Intelectual Existente                                      │
│    Documentos Markdown, LaTeX (.tex), relatórios em PDF, cadernos de   │
│    hipóteses, códigos e dados autorizados de múltiplos laboratórios.   │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ (observação de fontes autorizadas)
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│ 2. Motor de Continuidade Automatizado                                  │
│    Fila durável → Extração delimitada de texto → Comparação contextual │
│    → Inferência local (Ollama/Qwen 2.5) → Proposição de relações       │
│    → Identificação de lacunas epistemológicas (gaps) e oportunidades.   │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ (persistência idempotente)
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│ 3. Memória Histórica e Interpretações Evolutivas                       │
│    - RIT: Registro imutável de eventos, hashes, momento e fontes.      │
│    - REA: Interpretações e memórias derivadas que evoluem e são        │
│      revistas com feedback contextual, sem apagar o passado.           │
│    - MPRR: Grafo de relações candidatas, distinguindo hipóteses        │
│      relacionais de relações demonstradas.                             │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ (apresentação por exceção)
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│ 4. Laboratório de Investigação (A Janela Humana)                       │
│    O pesquisador encontra contextos preparados, lacunas expostas,      │
│    conexões sugeridas e próximos passos — nunca uma tela em branco.    │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Diretrizes Epistêmicas Operacionais (REA · RIT · MPRR)

| Fundamento | Exigência Operacional |
| :--- | :--- |
| **REA (Reflexividade Epistêmica e Adaptativa)** | Interpretações podem ser corrigidas, rejeitadas e reformuladas. Quando uma formulação conceitual é revista, a memória derivada incorpora a revisão e impede que a versão superada seja utilizada como vigente. |
| **RIT (Reflexividade sob Integridade Temporal)** | Responsabilidade histórica estrita. A automação preserva o documento original, a versão examinada, a data de observação e o momento da inferência. Uma síntese de hoje jamais é confundida com uma formulação de ontem. |
| **MPRR (Percepção Relacional da Realidade)** | Exploração de proximidades, contrastes e oportunidades de convergência entre laboratórios (ex: EVIDA, TESSITURA, MÉTIS), sem converter automaticamente hipóteses em causalidade ou validação científica. |

---

## 4. Prioridade Imediata de Desenvolvimento

Fica pausada qualquer priorização de novos widgets visuais isolados. A prioridade central passa a ser o **Primeiro Ciclo Autônomo de Continuidade Documental e Relacional**:

1. **Fila durável de tarefas no SQLite (`continuity_jobs`)**:
   Uma alteração em documento autorizado (`.md`, `.tex`, `.pdf`, `.txt`) gera automaticamente uma tarefa de análise recuperável e idempotente.
2. **Worker de continuidade em background (`scripts/lac_continuity_worker.py`)**:
   Consome jobs pendentes, extrai conteúdo com `lac_doc_reader.py`, recupera contexto histórico da frente e consulta o adaptador local Ollama (`qwen2.5:7b`).
3. **Memória derivada com rastreabilidade (`continuity_insights`)**:
   Persiste a síntese, as lacunas conceituais abertas e as conexões sugeridas, sem duplicação e com referências auditáveis.
4. **Critério de Aceite ("O Teste de Verdade")**:
   Modificar um documento autorizado (ex: em `TESSITURA/docs/`) e comprovar que o LAC, em background e sem nova entrada manual, reconhece a mudança, recupera o contexto anterior, sintetiza o impacto, aponta as lacunas conceituais e deixa o insight preparado para o pesquisador. Se não houver elementos suficientes, declara honestamente a insuficiência.

---

## 5. Consequências

- **Autonomia com revisão por exceção**: O LAC processa, resume e relaciona autonomamente; o ser humano revisa, corrige e delibera.
- **Continuidade assíncrona**: O LAC trabalha enquanto a equipe produz em outros lugares. Ao retornar ao sistema, o trabalho de contextualização já está adiantado.
- **Sempre pronto. Sempre incompleto**: Pronto para contribuir continuamente; incompleto porque o conhecimento, as relações e as possibilidades permanecem permanentemente abertos à investigação.
