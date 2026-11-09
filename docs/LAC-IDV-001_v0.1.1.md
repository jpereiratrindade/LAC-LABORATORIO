# LAC-IDV-001 — Identidade visual do Laboratório de Continuidade

**Versão:** 0.1.1 · **Estado:** Experimental · **Data:** 2026-11-09

## Intenção

O LAC integra visualmente o ecossistema SisTer sem reutilizar marcas de EVIDA ou TESSITURA e sem herdar seus contratos de domínio. A identidade deve servir ao laboratório, não determinar seu conteúdo científico.

## Símbolo

O **Laço de Continuidade** reúne duas trajetórias entrelaçadas em um traço aberto à leitura relacional. O símbolo é uma metáfora visual de permanência e transformação, **não** uma definição formal de REA, RIT ou MPRR, tampouco um emblema de inferência automática.

O desenho vetorial original é `web/assets/lac-symbol.svg`; `web/favicon.svg` é a sua variante compacta, sobre fundo azul-profundo. Ambos são independentes de fontes, frameworks e recursos remotos.

## Paleta de referência

| Token | Cor | Finalidade |
|---|---|---|
| navy | `#071c34` | Navegação e identidade |
| navy2 | `#0b2948` | Superfícies escuras |
| cyan | `#48cbe8` | Percursos, destaques e foco |
| amber | `#f4bf65` | Segunda trajetória / alteridade |
| ink | `#11283f` | Texto principal |
| background | `#f0f5fa` | Superfícies claras |
| green | `#159663` | Ações positivas e indicadores de integridade |

## Contrato de interface

1. Nenhum elemento decorativo deve sugerir uma funcionalidade inexistente.
2. A integridade real vem do endpoint `/api/verify`, nunca apenas da cor verde.
3. Recurso local apenas: sem CDN, Google Fonts, framework CSS, analytics ou telemetria.
4. Sem inferência de relações: elas permanecem explicitamente declaradas.
5. A atualização de identidade não deve migrar o banco SQLite.
6. A interface deve funcionar em desktop e largura móvel, com teclado e preferências de movimento reduzido.

## Continuidade da identidade

O novo ícone é proposto como marca do LAC v0.1.1; a equipe pode revisá-lo por meio de uma próxima versão documentada. Não alterar retroativamente a identidade da v0.1.0.
