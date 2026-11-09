# Prévia visual — laboratório e assistente

T02 em avaliação. Todos os materiais, datas e respostas são fictícios.
Nenhum acesso ao banco, API operacional ou LLM. O adaptador real de inferência
fica em `scripts/lac_local_llm.py`, separado desta demonstração.

Abra `index.html` diretamente no navegador ou, a partir da raiz do repositório:

```bash
python3 -m http.server 8876 --bind 127.0.0.1 --directory prototypes/laboratorio
```

Abra `http://127.0.0.1:8876`. Esse servidor é apenas uma prévia estática local
com dados fictícios; não instala, reinicia nem substitui o LAC autenticado.

## Percurso para avaliar

1. Selecione o documento. Examine a conexão proposta no painel do assistente.
2. Compare origens na bancada; abra o registro de cada material.
3. Revise a associação e confirme ou descarte somente nesta prévia.
4. Alterne entre relações, trajetória e bancada; seleção permanece.
5. Mova um cartão pelo controle de arrastar ou pelas setas no painel.
6. Fixe posição e recarregue a página; arranjo e revisão são preservados.
7. Abra Memória, inspecione origem e desative preferência demonstrativa.
8. Use o seletor de estados para processamento, pausa, fonte/modelo ausente
   e laboratório vazio. Restaure o exemplo ao terminar.

Busca abre por botão ou `/`. Mapa pode ser movido pelas setas quando está com
foco. Zoom por botões ou Ctrl/Command + roda. Tab/Enter permitem operar cartões,
relações e ações. Posições e preferências ficam somente no localStorage deste
exemplo (`lac-visual-prototype-v1`); não há memória real do assistente nesta tela.

Critério humano pendente: reconhecer mudança, localizar origem e revisar
vínculo com pouco esforço. Testes de interação não substituem essa avaliação.

## Verificação de navegador

Com o servidor acima ativo e Playwright disponível no ambiente:

```bash
node tests/check_prototype.cjs
```

Execute a partir da raiz do repositório. `LAC_PLAYWRIGHT_MODULE` pode apontar
para instalação externa do pacote. O verificador usa Chromium headless,
exercita desktop/celular e salva capturas em `.cache/prototype`, fora do Git.
