const { chromium } = require(process.env.LAC_PLAYWRIGHT_MODULE || 'playwright');
const fs = require('fs');
const path = require('path');

const token = process.argv[2];
if (!token) {
  console.error("Uso: node user_journey_test.cjs <token>");
  process.exit(1);
}

const outDir = path.resolve('.cache/user-journey');
fs.mkdirSync(outDir, { recursive: true });

(async () => {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    viewport: { width: 1440, height: 900 }
  });

  // Set auth cookie
  await context.addCookies([{
    name: 'lac_session',
    value: token,
    domain: '127.0.0.1',
    path: '/'
  }]);

  const page = await context.newPage();
  const logs = [];
  page.on('console', msg => logs.push(`[CONSOLE ${msg.type()}] ${msg.text()}`));
  page.on('pageerror', err => logs.push(`[PAGE ERROR] ${err.message}`));

  console.log("=== 1. ACESSANDO A VISÃO GERAL (OVERVIEW) ===");
  await page.goto('http://127.0.0.1:8765/#overview', { waitUntil: 'networkidle' });

  // Wait for overview to load
  await page.waitForSelector('#dashboardIntro');
  await page.screenshot({ path: path.join(outDir, '01_overview.png') });

  const mastHealth = await page.textContent('#mastHealth');
  const sessionEmail = await page.textContent('#sessionEmail');
  console.log(`[Masthead] Email: ${sessionEmail.trim()} | Cadeia: ${mastHealth.trim()}`);

  const statProjects = await page.textContent('#statProjects');
  const statEvents = await page.textContent('#statEvents');
  const statRoots = await page.textContent('#statRoots');
  const statTodos = await page.textContent('#statTodos');
  console.log(`[Indicadores] Projetos: ${statProjects} | Eventos: ${statEvents} | Fontes: ${statRoots} | Pendências: ${statTodos}`);

  const pulseTitle = await page.textContent('#pulseFocusTitle');
  const pulseLastAction = await page.textContent('#pulseLastAction');
  const pulseNextStep = await page.textContent('#pulseNextStep');
  console.log(`[Card de Pulso] Foco: ${pulseTitle.trim()} | Último marco: ${pulseLastAction.trim()} | Próximo passo: ${pulseNextStep.trim()}`);

  console.log("\n=== 2. TESTANDO OMNI-BAR: REGISTRO DE PENSAMENTO RÁPIDO ===");
  // Click on "Onde parei" preset
  await page.click('button[data-preset="where"]');
  const inputValue = await page.inputValue('#omniInput');
  console.log(`[Omni-Bar] Preset preenchido: "${inputValue}"`);

  // Customize input for TESSITURA
  await page.selectOption('#omniProject', 'TESSITURA');
  await page.fill('#omniInput', 'Investigação EXP-002: Confrontar indicadores INMET com série histórica de estiagem.');
  
  // Click on Diálogo IA portal chip
  await page.click('button[data-portal="ai"]');
  console.log(`[Omni-Bar] Portal selecionado: Diálogo IA`);

  // Submit note
  await page.click('#btnOmniSend');
  await page.waitForTimeout(1000);
  await page.screenshot({ path: path.join(outDir, '02_omni_submitted.png') });

  // Verify pulse updated
  const updatedPulse = await page.textContent('#pulseLastAction');
  console.log(`[Card de Pulso Atualizado]: ${updatedPulse.trim()}`);

  console.log("\n=== 3. EXPLORANDO E FILTRANDO A LINHA DO TEMPO ===");
  const eventsCount = await page.locator('#events .event').count();
  console.log(`[Linha do Tempo] Total de eventos renderizados inicialmente: ${eventsCount}`);

  // Filter by kind: decision
  await page.selectOption('#filterKind', 'decision');
  await page.waitForTimeout(500);
  const decisionEventsCount = await page.locator('#events .event').count();
  console.log(`[Filtro: Decisões] Eventos filtrados: ${decisionEventsCount}`);
  if (decisionEventsCount > 0) {
    const firstDecision = await page.locator('#events .event .event-title').first().textContent();
    console.log(`  -> Primeira decisão na lista: "${firstDecision.trim()}"`);
  }

  // Filter by project: EVIDA
  await page.selectOption('#filterKind', '');
  await page.selectOption('#filterProject', 'EVIDA');
  await page.waitForTimeout(500);
  const evidaEventsCount = await page.locator('#events .event').count();
  console.log(`[Filtro: Projeto EVIDA] Eventos filtrados: ${evidaEventsCount}`);

  console.log("\n=== 4. TESTANDO VIEW DE RELATÓRIOS E SÍNTESE EXECUTIVA ===");
  await page.click('button[data-view="reports"]');
  await page.waitForTimeout(500);
  await page.screenshot({ path: path.join(outDir, '03_reports.png') });

  // Click on "Gerar síntese de hoje"
  console.log("[Relatórios] Clicando em 'Gerar síntese de hoje'...");
  await page.click('#btnBriefingToday');
  await page.waitForTimeout(1500);
  const briefingText = await page.textContent('#briefingOutput');
  console.log(`[Síntese Executiva Gerada]:\n---\n${briefingText.trim().slice(0, 500)}...\n---`);
  await page.screenshot({ path: path.join(outDir, '04_briefing_generated.png') });

  console.log("\n=== 5. NAVEGANDO POR PENDÊNCIAS, RELAÇÕES E GUIA ===");
  // Todos view
  await page.click('button[data-view="todos"]');
  await page.waitForTimeout(500);
  const todosCount = await page.locator('#todos .event').count();
  console.log(`[Pendências] Total de pendências abertas: ${todosCount}`);

  // Relations view
  await page.click('button[data-view="relations"]');
  await page.waitForTimeout(500);
  const relationsCount = await page.locator('#relations .event').count();
  console.log(`[Relações] Total de relações registradas: ${relationsCount}`);

  // Guide view
  await page.click('button[data-view="guide"]');
  await page.waitForTimeout(500);
  const guideTitle = await page.textContent('#view-guide h2');
  console.log(`[Guia de Uso] Acessado com sucesso: "${guideTitle.trim()}"`);

  console.log("\n=== 6. VERIFICAÇÃO DE INTEGRIDADE PELA UI ===");
  await page.click('button[data-view="integrity"]');
  await page.waitForTimeout(500);
  await page.click('#btnVerifyFull');
  await page.waitForTimeout(1000);
  const integrityStatus = await page.textContent('#integrityDetails');
  console.log(`[Integridade] Resultado da auditoria: ${integrityStatus.trim()}`);
  await page.screenshot({ path: path.join(outDir, '05_integrity.png') });

  if (logs.length > 0) {
    console.log("\n[LOGS DO NAVEGADOR]");
    logs.forEach(l => console.log(l));
  } else {
    console.log("\n[LOGS DO NAVEGADOR] Nenhum erro no console!");
  }

  await browser.close();
  console.log("\n=== TESTE DE JORNADA DO USUÁRIO CONCLUÍDO ===");
})();
