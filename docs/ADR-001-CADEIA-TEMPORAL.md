# ADR-001 — Histórico append-only e âncoras externas

- **Estado:** Accepted para a implementação experimental v0.1.0
- **Data:** 2026-11-09
- **Decisão:** eventos append-only com `prev_hash` e `event_hash`, SHA-256 sobre representação canônica, dupla temporalidade e âncora externa opcional.

## Motivação

Um relatório reconstruído precisa distinguir quando algo ocorreu e quando foi conhecido. Sob revisão, a retificação não deve apagar a versão anterior.

## Trade-off

SQLite facilita consultas e projeções, mas não é WORM nem mecanismo de assinatura. Uma pessoa com acesso ao banco pode substituir gatilhos e recalcular todo o histórico. Por isso `lac anchor` grava o hash e ID de um ponto do histórico em arquivo independente, que `lac verify --anchor` compara com o registro encadeado.

## Não objetivos

Não garantir autoria de commits, verdade de declarações, ordenação causal ou segurança contra adulteração simultânea do banco e da âncora. Não substituir backups.
