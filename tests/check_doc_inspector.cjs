const { chromium } = require(process.env.LAC_PLAYWRIGHT_MODULE || 'playwright');

const token = process.argv[2];
if (!token) {
  console.error("Uso: node check_doc_inspector.cjs <token>");
  process.exit(1);
}

(async () => {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  await context.addCookies([{ name: 'lac_session', value: token, domain: '127.0.0.1', path: '/' }]);
  const page = await context.newPage();
  
  const consoleErrors = [];
  page.on('console', msg => {
    if (msg.type() === 'error') consoleErrors.push(msg.text());
  });

  console.log("=== 1. Carregando a Visão Geral ===");
  await page.goto('http://127.0.0.1:8765/#overview', { waitUntil: 'networkidle' });

  // Check autonomousInsightCard
  const cardVisible = await page.$eval('#autonomousInsightCard', el => !el.hidden);
  console.log("Card de Descoberta Preparada visível:", cardVisible);
  if (cardVisible) {
    const title = await page.$eval('#insightDocTitle', el => el.textContent);
    console.log("Insight Doc:", title);
    
    // Click on [Examinar texto] in the insight card
    console.log("Clicando em 'Examinar texto' no card de insight...");
    await page.click('#btnViewInsightDoc');
    await page.waitForTimeout(600);
    
    const modalOpen = await page.$eval('#docDialog', el => el.open);
    console.log("Modal #docDialog aberto:", modalOpen);
    
    const docTitle = await page.$eval('#docModalFilename', el => el.textContent);
    const docText = await page.$eval('#docModalText', el => el.textContent.slice(0, 100));
    console.log("Documento no modal:", docTitle);
    console.log("Amostra do texto no modal:", docText.replace(/\n/g, ' '));
    
    // Close modal
    await page.click('#closeDoc');
    await page.waitForTimeout(200);
    const modalClosed = await page.$eval('#docDialog', el => !el.open);
    console.log("Modal fechado com sucesso:", modalClosed);
  }

  console.log("=== 2. Testando botão 'Examinar texto' na Linha do Tempo ===");
  const examButtons = await page.$$('.event .inline-button');
  console.log("Total de botões 'Examinar texto' na timeline:", examButtons.length);
  if (examButtons.length > 0) {
    await examButtons[0].click();
    await page.waitForTimeout(600);
    const modalOpen = await page.$eval('#docDialog', el => el.open);
    const filename = await page.$eval('#docModalFilename', el => el.textContent);
    console.log(`Modal aberto a partir da timeline para '${filename}':`, modalOpen);
    await page.click('#btnCloseDocBtn');
  }

  console.log("=== 3. Verificando se houve erros de CSP ou console ===");
  if (consoleErrors.length > 0) {
    console.error("Erros no console:", consoleErrors);
    process.exit(1);
  } else {
    console.log("Nenhum erro de CSP ou JavaScript detectado no navegador!");
  }

  await browser.close();
  console.log("=== TESTE CONCLUÍDO COM SUCESSO ===");
})();
