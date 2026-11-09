# LAC-IMPL-001 — Caderno de entrega Caveman Full

**Versão:** 0.1.0 · **Data:** 2026-11-09 · **Situação:** implementado e testado em bancada Linux

## Objetivo do patch

Permitir iniciar do zero um laboratório independente de continuidade operacional. O patch cria um repositório inteiro, não altera sistemas existentes.

## Entregáveis auditáveis

1. `CMakeLists.txt`: build C++26 e CTest.
2. `src/core.cpp`: SQLite/FTS5, event log append-only, observação de Git e documentos, hash em cadeia, âncora externa, exportação Markdown.
3. `src/server.cpp`: servidor HTTP local em 127.0.0.1, API JSON e formulários de registro.
4. `web/`: painel responsivo local para acompanhar fatos, pendências, relações e fontes.
5. `tests/test_lab.py`: testes de ponta a ponta sem dependências Python adicionais.
6. `systemd/lac.service`: integração de inicialização de usuário, opt-in.
7. `docs/`: fundamentos REA/RIT/MPRR e registros de decisão.

## Aplicação como patch Git em pasta vazia

```bash
mkdir -p ~/dev/cpp/lac-laboratorio
cd ~/dev/cpp/lac-laboratorio
git init
git apply --check ~/Downloads/LAC_v0.1.0_full.patch
git apply ~/Downloads/LAC_v0.1.0_full.patch
bash scripts/setup_fedora.sh
```

**Alternativa:** extrair `LAC_v0.1.0_sources.tar.gz` em `~/dev/cpp` e executar `bash lac-laboratorio/scripts/setup_fedora.sh`.

## Boot mínimo

```bash
./build/lac init
./build/lac register --project 'ELO/OS' --path "$HOME/dev/cpp/elo-os" --kind git
./build/lac scan
./build/lac serve --webroot ./web
```

Abra `http://127.0.0.1:8765`.

## Gate de aceitação F0

- [x] Compilação de C++ em modo `-std=c++26` com GCC 14.2.
- [x] Teste de idempotência documental.
- [x] Registro de modificação e ausência de arquivo.
- [x] Teste Git com commits reais em repositório temporário.
- [x] Teste HTTP de registros, pendências e relações.
- [x] Verificação da cadeia SHA-256 e detecção de alteração não autorizada.
- [x] Exportação Markdown e âncora externa.
- [x] Verificação sintática do frontend JavaScript com Node.js 22.
- [ ] Validação de funcionamento prolongado em Fedora 44.
- [ ] Teste de interface web em navegador real neste desktop.
- [ ] Definição de licença e configuração de backup periódico.

## Invariantes para F1

Aumentar observabilidade sem aumentar arbitrariedade interpretativa. Avaliar consumo real de memória/CPU e recuperação de sete dias de atividades; cadastrar caminhos de projetos reais apenas com consentimento, selecionar uma rotina de backup, e investigar integrações somente após medir lacunas. **Não introduzir LLM como requisito.**
