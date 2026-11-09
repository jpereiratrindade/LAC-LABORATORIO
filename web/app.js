'use strict';
// LAC v0.1.4: every actionable control maps to a real local endpoint or browser preference.
const $ = id => document.getElementById(id);
const $create = (tag, css = '', value) => {
  const node = document.createElement(tag);
  if (css) node.className = css;
  if (value !== undefined) node.textContent = value;
  return node;
};
let activeView = 'overview';
let debounce;
const viewLabels = {overview:'Visão geral', timeline:'Linha do tempo', projects:'Projetos',
  events:'Eventos', relations:'Relações', sources:'Fontes', todos:'Pendências',
  guide:'Guia de Uso & Metodologia',
  observation:'Observação', integrity:'Integridade', reports:'Relatórios',
  settings:'Preferências', integrations:'Integrações', about:'Sobre o LAC'};
const eventIcons = {git_commit:'⌁',file_added:'+',file_changed:'↻',file_missing:'−',
  note:'✎',decision:'✓',todo:'□',todo_closed:'✓',relation:'◇',correction:'↶'};
let authenticated=false;
try { sessionStorage.removeItem('lac_api_token'); } catch {}
const authHeaders = () => ({});
const api = async (path, data) => {
  const opts = data === undefined ? {} : {
    method: 'POST', headers: {'Content-Type':'application/x-www-form-urlencoded','X-LAC-Local':'1'},
    body: new URLSearchParams(data).toString()
  };
  opts.headers={...opts.headers,...authHeaders()};
  const response = await fetch(path, opts);
  if(response.status===401&&!path.startsWith('/api/auth/'))showLogin();
  const parsed = await response.json();
  if (!response.ok) throw new Error(parsed.error || `HTTP ${response.status}`);
  return parsed;
};
function showNotice(message, error = false) {
  const n = $('notice'); n.hidden = false; n.textContent = message;
  n.classList.toggle('error', error);
}
const localDate = value => {
  if (!value) return '—';
  const d = new Date(value);
  return Number.isNaN(d.valueOf()) ? value : d.toLocaleString('pt-BR', {dateStyle:'short',timeStyle:'short'});
};
const empty = text => $create('p','empty',text);
function card(title, body, tags = [], ref = '', when = '', icon = '◦') {
  const root = $create('article','event');
  const left = $create('div','event-left');
  const symbol = $create('span','event-icon',icon);
  const inner = $create('div');
  inner.append($create('div','event-title',title));
  if (body) inner.append($create('p','event-body',body));
  if (ref) inner.append($create('div','event-ref',ref));
  const chips = $create('div','tags');
  for (const [text, style] of tags) chips.append($create('span',`tag ${style || ''}`,text));
  inner.append(chips); left.append(symbol,inner);
  root.append(left,$create('div','event-time',localDate(when)));
  return root;
}
const formatDate = d => `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`;
function setRecentDates() {
  const now = new Date(), ago = new Date(now); ago.setDate(now.getDate()-6);
  $('filterFrom').value = formatDate(ago); $('filterTo').value = formatDate(now);
}
function showView(view) {
  if (!viewLabels[view]||!authenticated) return;
  activeView = view;
  $('currentView').textContent = viewLabels[view];
  for (const b of document.querySelectorAll('[data-view]')) {
    b.classList.toggle('active',b.dataset.view===view);
    if (b.dataset.view===view) b.setAttribute('aria-current','page');
    else b.removeAttribute('aria-current');
  }
  const timeline = view === 'overview' || view === 'timeline';
  $('dashboardBody').hidden = !timeline;
  $('view-timeline').hidden = !timeline;
  $('dashboardIntro').hidden = view !== 'overview';
  $('dashboardStats').hidden = view !== 'overview';
  $('quickRail').hidden = view !== 'overview';
  $('dashboardBody').classList.toggle('full-width', view === 'timeline');
  for (const el of document.querySelectorAll('.page > section.view')) el.hidden = el.id !== `view-${view}`;
  // Hash navigation works locally without triggering a server request.
  if (window.location.hash !== `#${view}`) history.replaceState(null,'',`#${view}`);
  refresh().catch(e => showNotice(e.message,true));
}
async function refreshStats() {
  const [stats, check] = await Promise.all([api('/api/stats'),api('/api/verify')]);
  for (const [id,value] of [['statProjects',stats.projects],['statEvents',stats.events],
    ['statRoots',stats.roots],['statTodos',stats.open_todos]]) $(id).textContent=value;
  $('mastHealth').textContent = check.ok ? '● Cadeia íntegra' : '⚠ Divergência detectada';
  $('mastHealth').classList.toggle('unhealthy',!check.ok);
  return check;
}
async function refreshProjectsOptions() {
  const projects = await api('/api/projects');
  for (const [id,placeholder] of [['filterProject','Todos'],['reportProject','Todos os projetos'],['omniProject','lac-laboratorio']]) {
    const el=$(id); if (!el) continue;
    const before=el.value;
    el.replaceChildren(id==='omniProject' ? new Option('lac-laboratorio','lac-laboratorio') : new Option(placeholder,''));
    for (const p of projects) if (![...el.options].some(o => o.value === p.name)) el.add(new Option(p.name,p.name));
    if (before && [...el.options].some(o => o.value === before)) el.value=before;
  }
  return projects;
}
function renderEvent(target,e) {
  const element=card(e.title,e.body,[[e.project],[(e.kind||'').replaceAll('_',' ')],
    [e.evidence_state,e.evidence_state],[e.actor==='llm'?'Autoria: LLM':e.actor==='user'?'Autoria: pessoa':'Observação automática']],e.source_ref,e.occurred_at,eventIcons[e.kind]||'◦');
  element.querySelector('.event-time').append($create('span','',`Registrado: ${localDate(e.recorded_at)}`));
  if (e.source_ref && (e.kind==='file_added'||e.kind==='file_changed'||/\.(md|tex|pdf|txt)$/i.test(e.source_ref))) {
    const examBtn=$create('button','inline-button','Examinar texto');
    examBtn.type='button';
    examBtn.addEventListener('click',()=>inspectDocument(e.source_ref,e.project));
    element.querySelector('.event-left > div:last-child').append(examBtn);
  }
  target.append(element);
}
async function refreshEvents() {
  const q = new URLSearchParams({limit:'200'});
  for (const [id,key] of [['filterQ','q'],['filterProject','project'],['filterKind','kind'],
    ['filterFrom','from'],['filterTo','to']]) if ($(id).value.trim()) q.set(key,$(id).value.trim());
  const list=await api(`/api/events?${q}`), target=$('events');
  target.replaceChildren();
  if (!list.length) {
    const filtered=['filterQ','filterProject','filterKind','filterFrom','filterTo'].some(id=>$(id).value.trim());
    const c=$create('div','empty empty-timeline');
    const mark=$create('img','empty-mark'); mark.src='/assets/lac-symbol.svg';mark.alt='';
    c.append(mark,$create('strong','',filtered?'Nenhum registro encontrado.':'Nenhum registro encontrado.'));
    c.append($create('p','',filtered ? 'Amplie os filtros. Ausência de evidência não comprova ausência de atividade.' :
      'Registre um acontecimento, cadastre um projeto ou execute uma observação de diretórios e repositórios.'));
    const actions=$create('div','empty-actions');
    const primary=$create('button','primary',filtered?'Limpar filtros':'Observar agora');
    primary.type='button';primary.addEventListener('click',()=>filtered?$('btnClear').click():showView('sources'));
    const manual=$create('button','ghost','Registrar manualmente'); manual.type='button';
    manual.addEventListener('click',()=>openNote()); actions.append(primary,manual); c.append(actions);target.append(c);
    return;
  }
  for (const e of list) renderEvent(target,e);
  updatePulseCard(list);
}
async function refreshEventListing() {
  const list=await api('/api/events?limit=200'),target=$('eventsListing');target.replaceChildren();
  if (!list.length) {target.append(empty('Nenhum evento observado ou declarado ainda.'));return;}
  for (const e of list) renderEvent(target,e);
  updatePulseCard(list);
}
async function refreshProjects() {
  const [projects,roots]=await Promise.all([api('/api/projects'),api('/api/roots')]);
  const target=$('projects');target.replaceChildren();
  if (!projects.length) {target.append(empty('Nenhum projeto cadastrado. Registre uma fonte ou um acontecimento.'));return;}
  for (const p of projects) {
    const n=roots.filter(r=>r.project===p.name).length;
    const el=$create('article','project-card');
    el.append($create('h3','',p.name),$create('p','',`${p.events} evento(s) · ${n} fonte(s) autorizada(s)`));
    const button=$create('button','ghost compact','Examinar eventos');button.type='button';
    button.addEventListener('click',()=>{$('filterProject').value=p.name;showView('timeline');});
    el.append(button);target.append(el);
  }
}
async function refreshTodos() {
  const list=await api('/api/todos'),target=$('todos');target.replaceChildren();
  if (!list.length) {target.append(empty('Nenhuma pendência aberta registrada.'));return;}
  for (const t of list) {
    const el=card(t.title,t.body,[[t.project],['declarada','declared'],[t.actor==='llm'?'Autoria: LLM':'Autoria: pessoa']],`Evento #${t.id}`,t.occurred_at,'□');
    const btn=$create('button','inline-button','Registrar encerramento');btn.type='button';
    btn.addEventListener('click',async()=>{
      if (!confirm('Declarar a pendência concluída? O histórico será preservado.'))return;
      try{await api('/api/todos/close',{id:String(t.id)});showNotice('Encerramento registrado em novo evento.');await refresh();}
      catch(e){showNotice(e.message,true);}
    });
    el.querySelector('.event-left > div:last-child').append(btn);target.append(el);
  }
}
async function refreshRelations() {
  const list=await api('/api/relations'),target=$('relations');target.replaceChildren();
  if (!list.length) {target.append(empty('Nenhuma relação declarada.'));return;}
  for (const r of list) target.append(card(`${r.from} ↔ ${r.to}`,r.label,
    [[r.state==='candidate'?'Candidata':'Confirmada pelo usuário',r.state==='candidate'?'proposed':'declared'],[r.actor==='llm'?'Autoria: LLM':'Autoria: pessoa']],
    `Evento #${r.event_id}`,'','◇'));
}
async function refreshRoots(){
  const list=await api('/api/roots');
  for(const id of ['roots','observationRoots']){
    const target=$(id);target.replaceChildren();
    if(!list.length){target.append(empty('Nenhuma fonte cadastrada. Cadastre um caminho na seção Fontes.'));continue;}
    for(const r of list)target.append(card(r.project,r.path,[[r.kind]],'','','⌁'));
  }
}
let currentInsightIndex=0, currentInsightsList=[];
function displayInsight(idx){
  if(!currentInsightsList.length)return;
  idx=(idx+currentInsightsList.length)%currentInsightsList.length;
  currentInsightIndex=idx;
  const item=currentInsightsList[idx];
  $('insightCounter').textContent=`${idx+1}/${currentInsightsList.length}`;
  $('insightDocTitle').textContent=`${item.project} · ${item.document_path}`;
  $('insightSummary').textContent=item.summary;
  const gapsContainer=$('insightGapsList');
  gapsContainer.replaceChildren();
  const gaps=Array.isArray(item.gaps)?item.gaps:[];
  if(gaps.length){
    const ul=document.createElement('ul');
    for(const gap of gaps){const li=document.createElement('li');li.textContent=gap;ul.appendChild(li);}
    gapsContainer.appendChild(ul);
    $('insightOpportunity').textContent=gaps[0];
    $('btnAdoptGap').onclick=()=>{
      openNote('todo');
      const form=$('noteForm');
      form.elements.project.value=item.project;
      form.elements.title.value=gaps[0].slice(0,180);
      form.elements.reference.value=`lac:event:${item.event_id}`;
      form.elements.body.value=`Oportunidade identificada na análise autônoma de ${item.document_path}:\n\n${item.summary}`;
    };
  }else{
    $('insightOpportunity').textContent='Síntese concluída sem lacunas críticas aparentes.';
    $('btnAdoptGap').onclick=()=>openNote('note');
  }
  $('btnViewInsightDoc').onclick=()=>inspectDocument(item.document_path,item.project,item.summary);
  $('insightModelBadge').textContent=item.model||'qwen2.5:7b';
  $('insightTimeBadge').textContent=(item.created_at||'').slice(11,16);

  const relContainer=$('insightRelationsContainer');
  relContainer.replaceChildren();
  const relations=Array.isArray(item.relations)?item.relations:[];
  if(relations.length){
    for(const rel of relations){
      const row=$create('div','insight-rel-item');
      row.append($create('strong','',`⚡ Proposta relacional (MPRR): ${item.project} ↔ ${rel.target_project}`));
      row.append($create('span','',`— ${rel.label}`));
      const adoptRelBtn=$create('button','preset-pill','Adotar relação');
      adoptRelBtn.type='button';
      adoptRelBtn.onclick=async()=>{
        try{
          await api('/api/relations',{from:item.project,to:rel.target_project,label:rel.label,state:'candidate'});
          showNotice('Relação candidata registrada no histórico.');
          await refresh();
        }catch(e){showNotice(e.message,true);}
      };
      row.append(adoptRelBtn);
      relContainer.append(row);
    }
  }
}
async function inspectDocument(filePath, project, insightSummary){
  try{
    showNotice('Lendo documento nas fontes autorizadas...');
    const data=await api(`/api/documents/read?path=${encodeURIComponent(filePath)}`);
    if(!data.ok){throw new Error(data.error||'Falha ao ler documento');}
    $('docModalProject').textContent=project||'DOCUMENTO AUTORIZADO';
    $('docModalFilename').textContent=data.filename;
    $('docModalExt').textContent=data.ext;
    $('docModalSize').textContent=`${data.bytes} bytes (${data.chars} caracteres)`;
    $('docModalPath').textContent=data.path;
    $('docModalHash').textContent=data.sha256;
    $('docModalText').textContent=data.text;
    if(insightSummary){
      $('docModalInsightSection').hidden=false;
      $('docModalInsightSummary').textContent=insightSummary;
    }else{
      $('docModalInsightSection').hidden=true;
    }
    $('docDialog').showModal();
    $('notice').hidden=true;
  }catch(e){
    showNotice(e.message,true);
  }
}
async function refreshInsights(){
  try{
    const list=await api('/api/assistant/insights');
    const card=$('autonomousInsightCard');
    if(!card)return;
    if(!list||!list.length){card.hidden=true;currentInsightsList=[];return;}
    currentInsightsList=list;
    card.hidden=false;
    displayInsight(currentInsightIndex);
  }catch(e){}
}
async function refresh(){
  const projects=await refreshProjectsOptions();
  await refreshStats();
  if(activeView==='overview')await refreshInsights();
  switch(activeView){
    case 'overview':case 'timeline':await refreshEvents();break;
    case 'events':await refreshEventListing();break;
    case 'projects':await refreshProjects();break;
    case 'todos':await refreshTodos();break;
    case 'relations':await refreshRelations();break;
    case 'sources':case 'observation':await refreshRoots();break;
    case 'integrations':await refreshIntegrations();break;
    case 'integrity':await verify(false);break;
    default:break;
  }
  return projects;
}
function openNote(kind='note') {
  $('noteForm').reset();$('noteForm').elements.kind.value=kind;
  if($('filterProject').value)$('noteForm').elements.project.value=$('filterProject').value;
  $('noteDialog').showModal();
}
async function scan(button) {
  button.disabled=true;
  try{const r=await api('/api/scan',{});showNotice(`Observação concluída: ${r.new_events} novo(s) evento(s). Apenas fontes autorizadas.`);await refresh();}
  catch(e){showNotice(e.message,true);}finally{button.disabled=false;}
}
async function verify(notify=true) {
  const r=await api('/api/verify');
  const details=$('integrityDetails');
  details.replaceChildren($create('strong','',r.ok?'Cadeia interna íntegra':'Divergência detectada'),$create('p','',r.message));
  details.classList.toggle('danger',!r.ok);
  if(notify)showNotice(r.message,!r.ok);
  return r;
}
let lastBriefingMarkdown = '';

async function generateExecutiveBriefing(days = 1) {
  const container = $('briefingOutput');
  container.innerHTML = '<p class="support">Processando eventos e compilando síntese inteligente...</p>';
  try {
    const cutoff = Date.now() - (days * 86400 * 1000);
    const [eventsList, todosList] = await Promise.all([
      api('/api/events?limit=300'),
      api('/api/todos')
    ]);
    
    const recent = eventsList.filter(e => {
      const t = Date.parse(e.occurred_at || e.recorded_at);
      return !Number.isNaN(t) ? t >= cutoff : true;
    });

    const commits = recent.filter(e => e.kind === 'git_commit');
    const files = recent.filter(e => ['file_added', 'file_changed', 'file_missing'].includes(e.kind));
    const decisions = recent.filter(e => e.kind === 'decision');
    const corrections = recent.filter(e => e.kind === 'correction');
    const closedTodos = recent.filter(e => e.kind === 'todo_closed');

    const periodText = days === 1 ? 'Hoje / Últimas 24 horas' : `Últimos ${days} dias`;
    
    container.replaceChildren();
    
    const header = $create('div', 'briefing-result-header');
    header.append(
      $create('strong', '', `Síntese do Período: ${periodText}`),
      $create('span', 'tag', `${recent.length} evento(s) analisado(s)`)
    );
    container.append(header);

    // 1. Avanços
    const sec1 = $create('div', 'briefing-section');
    sec1.append($create('h4', '', '🚀 1. Avanços Observados (Código e Arquivos)'));
    if (commits.length || files.length) {
      const ul = $create('ul', 'briefing-list');
      for (const c of commits) ul.append($create('li', '', `[Git] ${c.title}`));
      for (const f of files) ul.append($create('li', '', `[Arquivo] ${f.title} (${f.kind})`));
      sec1.append(ul);
    } else {
      sec1.append($create('p', 'support', 'Nenhum commit ou modificação de arquivo registrada no período.'));
    }
    container.append(sec1);

    // 2. Decisões
    const sec2 = $create('div', 'briefing-section');
    sec2.append($create('h4', '', '💡 2. Decisões e Hipóteses Firmadas'));
    if (decisions.length) {
      const ul = $create('ul', 'briefing-list');
      for (const d of decisions) {
        const li = $create('li');
        li.append($create('strong', '', d.title), $create('span', 'muted', ` (${d.actor === 'llm' ? 'LLM' : 'Pessoa'}): `), $create('span', '', d.body || ''));
        ul.append(li);
      }
      sec2.append(ul);
    } else {
      sec2.append($create('p', 'support', 'Nenhuma nova decisão declarada no intervalo.'));
    }
    container.append(sec2);

    // 3. Gestão Adaptativa / Correções
    const sec3 = $create('div', 'briefing-section');
    sec3.append($create('h4', '', '🔄 3. Gestão Adaptativa (Correções e Ajustes de Rota)'));
    if (corrections.length) {
      const ul = $create('ul', 'briefing-list');
      for (const corr of corrections) {
        const li = $create('li', 'correction-item');
        li.append($create('strong', '', `⚠ ${corr.title}: `), $create('span', '', corr.body || ''));
        ul.append(li);
      }
      sec3.append(ul);
    } else {
      sec3.append($create('p', 'support', 'Nenhum desvio ou hipótese refutada registrada. Rumo mantido.'));
    }
    container.append(sec3);

    // 4. Próximos Passos e Pendências
    const sec4 = $create('div', 'briefing-section');
    sec4.append($create('h4', '', '📌 4. Próximos Passos e Continuidade'));
    const ulTodos = $create('ul', 'briefing-list');
    if (closedTodos.length) {
      for (const ct of closedTodos) ulTodos.append($create('li', '', `✔ Concluído: ${ct.title}`));
    }
    if (todosList.length) {
      for (const t of todosList) ulTodos.append($create('li', 'todo-open', `⏳ [Em aberto] #${t.id} ${t.title}`));
    } else {
      ulTodos.append($create('li', '', '✔ Nenhuma pendência em aberto no momento.'));
    }
    sec4.append(ulTodos);
    container.append(sec4);

    let md = `# LAC — Síntese Executiva Automatizada (${periodText})\n\n`;
    md += `## 1. 🚀 Avanços Observados\n`;
    if (commits.length || files.length) {
      for (const c of commits) md += `- [Git] ${c.title}\n`;
      for (const f of files) md += `- [Arquivo] ${f.title}\n`;
    } else md += `- Nenhum commit no período.\n`;
    md += `\n## 2. 💡 Decisões & Hipóteses\n`;
    if (decisions.length) for (const d of decisions) md += `- **${d.title}**: ${d.body}\n`;
    else md += `- Nenhuma nova decisão declarada.\n`;
    md += `\n## 3. 🔄 Gestão Adaptativa (Correções)\n`;
    if (corrections.length) for (const c of corrections) md += `- ⚠ **${c.title}**: ${c.body}\n`;
    else md += `- Trajetória mantida.\n`;
    md += `\n## 4. 📌 Próximos Passos & Pendências\n`;
    for (const ct of closedTodos) md += `- ✔ Concluído: ${ct.title}\n`;
    if (todosList.length) for (const t of todosList) md += `- ⏳ Aberto: #${t.id} ${t.title}\n`;
    else md += `- Todas as pendências em dia!\n`;
    lastBriefingMarkdown = md;

    $('btnCopyBriefing').hidden = false;
  } catch (err) {
    container.innerHTML = `<p class="notice error">Erro ao compilar síntese: ${err.message}</p>`;
  }
}

async function exportReport(params){
  const response=await fetch(`/api/report?${params}`,{headers:authHeaders()});
  if(!response.ok)throw new Error('Falha ao gerar diário');
  const blob=await response.blob(),url=URL.createObjectURL(blob);
  const a=document.createElement('a');a.href=url;
  a.download=`LAC_Diario_${params.get('from')||'inicio'}_${params.get('to')||'atual'}.md`;
  document.body.append(a);a.click();a.remove();
  // Defer revocation until the browser has had time to schedule the download.
  setTimeout(()=>URL.revokeObjectURL(url),30000);
}
for(const btn of document.querySelectorAll('[data-view]'))btn.addEventListener('click',()=>showView(btn.dataset.view));
for(const btn of document.querySelectorAll('[data-go]'))btn.addEventListener('click',e=>{e.preventDefault();showView(btn.dataset.go);});
for(const btn of document.querySelectorAll('[data-open-note]'))btn.addEventListener('click',()=>openNote(btn.dataset.openNote));
$('btnNewNote').addEventListener('click',()=>openNote());
$('closeNote').addEventListener('click',()=>$('noteDialog').close());
$('cancelNote').addEventListener('click',()=>$('noteDialog').close());
for(const id of ['btnScan','btnScanFull'])$(id).addEventListener('click',()=>scan($(id)));
for(const id of ['btnVerify','btnVerifyFull'])$(id).addEventListener('click',()=>verify().catch(e=>showNotice(e.message,true)));
for(const id of ['filterProject','filterKind','filterFrom','filterTo','filterQ'])
  $(id).addEventListener('input',()=>{clearTimeout(debounce);debounce=setTimeout(()=>refreshEvents().catch(e=>showNotice(e.message,true)),200);});
$('btnWeekend').addEventListener('click',()=>{setRecentDates();refreshEvents().catch(e=>showNotice(e.message,true));});
$('btnClear').addEventListener('click',()=>{for(const id of ['filterQ','filterProject','filterKind','filterFrom','filterTo'])$(id).value='';refreshEvents().catch(e=>showNotice(e.message,true));});
$('btnExport').addEventListener('click',async()=>{
  const q=new URLSearchParams();for(const [id,key] of [['filterFrom','from'],['filterTo','to'],['filterProject','project']])if($(id).value)q.set(key,$(id).value);
  try{await exportReport(q);}catch(e){showNotice(e.message,true);}
});
$('btnReportQuick').addEventListener('click',async()=>{
  const q=new URLSearchParams();
  for(const [id,key] of [['filterFrom','from'],['filterTo','to'],['filterProject','project']]) if($(id).value)q.set(key,$(id).value);
  try{await exportReport(q);}catch(e){showNotice(e.message,true);}
});
$('reportForm').addEventListener('submit',async e=>{
  e.preventDefault();const values=new FormData(e.currentTarget),q=new URLSearchParams();
  for(const k of ['from','to','project'])if(values.get(k))q.set(k,String(values.get(k)));
  try{await exportReport(q);}catch(err){showNotice(err.message,true);}
});
$('btnBriefingToday').addEventListener('click',()=>generateExecutiveBriefing(1));
$('btnBriefingWeek').addEventListener('click',()=>generateExecutiveBriefing(7));
$('btnCopyBriefing').addEventListener('click',async()=>{
  if(!lastBriefingMarkdown)return;
  try{
    await navigator.clipboard.writeText(lastBriefingMarkdown);
    showNotice('Síntese copiada para a área de transferência em formato Markdown!');
  }catch(e){showNotice('Erro ao copiar: '+e.message,true);}
});
$('closeDoc')?.addEventListener('click',()=>$('docDialog').close());
$('btnCloseDocBtn')?.addEventListener('click',()=>$('docDialog').close());
$('btnCopyDocText')?.addEventListener('click',async()=>{
  try{
    await navigator.clipboard.writeText($('docModalText').textContent);
    showNotice('Texto do documento copiado!');
  }catch(e){showNotice('Erro ao copiar: '+e.message,true);}
});
$('btnPrevInsight')?.addEventListener('click',()=>displayInsight(currentInsightIndex-1));
$('btnNextInsight')?.addEventListener('click',()=>displayInsight(currentInsightIndex+1));
for(const [id,path] of [['noteForm','/api/notes'],['relationForm','/api/relations'],['rootForm','/api/roots']]){
  $(id).addEventListener('submit',async e=>{
    e.preventDefault();const form=e.currentTarget,values=Object.fromEntries(new FormData(form));
    const button=form.querySelector('[type=submit]');button.disabled=true;
    try{const r=await api(path,values);showNotice(`Registro ${r.id} criado, preservando o histórico.`);
      if(id==='noteForm')$('noteDialog').close();else form.reset();await refresh();
    }catch(err){showNotice(err.message,true);}finally{button.disabled=false;}
  });
}
// User interface preferences are browser-only; no network calls or event mutation.
function loadPreference(key){try{return localStorage.getItem(key)==='true';}catch{return false;}}
function savePreference(key,value){try{localStorage.setItem(key,String(value));}catch{showNotice('O navegador não permitiu salvar esta preferência.',true);}}
$('preferCompact').checked=loadPreference('lac_compact');
$('preferRecent').checked=loadPreference('lac_recent');
document.body.classList.toggle('compact-display',$('preferCompact').checked);
$('preferCompact').addEventListener('change',e=>{document.body.classList.toggle('compact-display',e.target.checked);savePreference('lac_compact',e.target.checked);});
$('preferRecent').addEventListener('change',e=>savePreference('lac_recent',e.target.checked));
if($('preferRecent').checked)setRecentDates();
const initial=location.hash.replace(/^#/,'');
initializeAuth();
window.addEventListener('hashchange',()=>{const view=location.hash.replace(/^#/,'');if(viewLabels[view]&&view!==activeView)showView(view);});

async function refreshIntegrations() {
  const data=await api('/api/integrations'),target=$('integrationStatus');target.replaceChildren();
  for(const [name,conf] of Object.entries(data)){
    const label={disabled:'Desabilitado',configured:'Configurado; índice ainda não consultado',missing:'Ferramenta não instalada',reachable:'API acessível; coleta não verificada',unavailable:'API indisponível'}[conf.state]||conf.state;
    target.append(card(name==='recoll'?'Recoll':'ActivityWatch',label,[],conf.last_query_at?`Última consulta: ${localDate(conf.last_query_at)}`:'Nenhuma consulta registrada'));
    const form=$(name==='recoll'?'recollConfig':'activityConfig');
    form.elements.enabled.checked=conf.enabled;
    for(const key of name==='recoll'?['config_dir','roots']:['url','buckets'])form.elements[key].value=conf[key]||'';
  }
  const aw=data.activitywatch,select=$('activityBucket'),before=select.value;select.replaceChildren();
  for(const bucket of (aw.buckets||'').split('\n').filter(Boolean))select.add(new Option(bucket,bucket));
  if([...select.options].some(option=>option.value===before))select.value=before;
  const available=(aw.available_buckets||[]).map(bucket=>bucket.id).join('\n');
  if(available)target.append(card('Buckets disponíveis',available));
}
for(const id of ['recollConfig','activityConfig'])$(id).addEventListener('submit',async e=>{
  e.preventDefault();const form=e.currentTarget,data=Object.fromEntries(new FormData(form));data.enabled=String(form.elements.enabled.checked);
  const button=form.querySelector('[type=submit]');button.disabled=true;
  try{await api('/api/integrations/configure',data);showNotice('Escopo da integração atualizado.');await refreshIntegrations();}
  catch(err){showNotice(err.message,true);}finally{button.disabled=false;}
});
$('btnIntegrationsRefresh').addEventListener('click',()=>refreshIntegrations().catch(e=>showNotice(e.message,true)));
$('recollSearch').addEventListener('submit',async e=>{
  e.preventDefault();const button=e.currentTarget.querySelector('button');button.disabled=true;
  try{
    const q=new URLSearchParams(new FormData(e.currentTarget)),data=await api(`/api/integrations/recoll/search?${q}`),target=$('documentResults');target.replaceChildren();
    if(!data.results.length)target.append(empty('Nenhum resultado na fatia consultada do índice e nas pastas autorizadas.'));
    for(const item of data.results){
      const element=card(item.title||item.path,item.abstract,[[item.mimetype]],item.path,item.mtime&&/^\d+$/.test(item.mtime)?new Date(Number(item.mtime)*1000).toISOString():'');
      const save=$create('button','secondary','Preparar nota com referência');save.type='button';
      save.addEventListener('click',()=>{openNote();const form=$('noteForm');form.elements.title.value=(item.title||item.path).slice(0,200);form.elements.body.value='Resultado consultado no Recoll; relevância e conteúdo ainda não verificados.\n'+item.abstract;form.elements.reference.value=item.path.slice(0,3000);});
      element.append(save);target.append(element);
    }
  }catch(err){showNotice(err.message,true);}finally{button.disabled=false;}
});
$('activityQuery').addEventListener('submit',async e=>{
  e.preventDefault();const button=e.currentTarget.querySelector('button');button.disabled=true;
  try{
    const q=new URLSearchParams(new FormData(e.currentTarget)),data=await api(`/api/integrations/activitywatch/activity?${q}`),target=$('activityResults');target.replaceChildren();
    target.append($create('p','support',`${data.events_returned} evento(s) consultado(s)${data.possibly_truncated?' · limite atingido; resumo parcial':''}. Nenhum evento importado.`));
    for(const item of data.applications)target.append(card(item.app,`${Math.round(item.seconds/60)} min em intervalos reportados`));
    if(!data.applications.length)target.append(empty('Nenhum intervalo retornado; isso não comprova ausência de atividade.'));
  }catch(err){showNotice(err.message,true);}finally{button.disabled=false;}
});

function showLogin() {
  authenticated=false;document.body.classList.add('auth-pending');$('loginScreen').hidden=false;
  if($('noteDialog').open)$('noteDialog').close();
  $('authEmailForm').hidden=false;$('authCodeForm').hidden=true;$('authCode').value='';
  for(const id of ['events','eventsListing','todos','relations','roots','projects','documentResults','activityResults','integrationStatus'])$(id).replaceChildren();
}
function enterWorkspace(identity) {
  authenticated=true;$('loginScreen').hidden=true;document.body.classList.remove('auth-pending');
  $('sessionEmail').textContent=identity.email||'Sessão autenticada';
  $('authCode').value='';$('authMessage').textContent='';
  showView(viewLabels[initial]?initial:'overview');
}
async function initializeAuth() {
  try{
    const identity=await api('/api/auth/status');
    if(identity.authenticated)enterWorkspace(identity);
    else {showLogin();if(!identity.smtp_configured)$('authMessage').textContent='O envio de códigos precisa ser configurado pelo administrador.';}
  }catch(error){showLogin();$('authMessage').textContent='Autenticação indisponível. Contate o administrador.';}
}
$('authEmailForm').addEventListener('submit',async event=>{
  event.preventDefault();const button=event.currentTarget.querySelector('button');button.disabled=true;$('authMessage').textContent='';
  const email=$('authEmail').value.trim().toLowerCase();
  try{
    const result=await api('/api/auth/request-code',{email});
    $('authEmail').value=email;$('authEmailForm').hidden=true;$('authCodeForm').hidden=false;
    $('authTarget').textContent=`Verifique a caixa de entrada de ${email}.`;
    $('authMessage').textContent=result.message;$('authCode').focus();
  }catch(error){$('authMessage').textContent=error.message;}finally{button.disabled=false;}
});
$('authCodeForm').addEventListener('submit',async event=>{
  event.preventDefault();const button=event.currentTarget.querySelector('[type=submit]');button.disabled=true;
  try{const identity=await api('/api/auth/verify-code',{email:$('authEmail').value,code:$('authCode').value});enterWorkspace(identity);}
  catch(error){$('authMessage').textContent=error.message;}finally{button.disabled=false;}
});
$('authBack').addEventListener('click',()=>{$('authEmailForm').hidden=false;$('authCodeForm').hidden=true;$('authCode').value='';$('authMessage').textContent='Aguarde pelo menos 60 segundos entre solicitações.';});
async function logout() {
  try{await api('/api/auth/logout',{});showLogin();$('sessionEmail').textContent='';$('authMessage').textContent='Sessão encerrada.';}
  catch(error){showNotice('Não foi possível encerrar a sessão: '+error.message,true);}
}
$('btnLogout').addEventListener('click',logout);
$('btnAccess').addEventListener('click',logout);

/* -------------------------------------------------------------
 * EXPERIÊNCIA CONTEMPORÂNEA: Omni-Bar, Pulse Card & Presets Táteis
 * ------------------------------------------------------------- */
let currentPortal = 'system';
let cachedLastEvent = null;

const PRESET_TEMPLATES = {
  where: {
    title: 'Onde parei: ',
    body: 'Parei na etapa ___. O próximo passo imediato é ___.\nArquivos/módulos em aberto: ___.'
  },
  decision: {
    title: 'Decisão de Sistema: ',
    body: 'Decidimos que ___ em vez de ___.\nMotivo principal: ___.'
  },
  block: {
    title: 'Bloqueio / Gargalo: ',
    body: 'Travado em ___.\nO que falta para destravar: ___.'
  },
  next: {
    title: 'Próximo passo prioritário: ',
    body: 'Ao retomar o trabalho, a primeira ação obrigatória é: ___.'
  },
  git_last: {
    from_last: true
  }
};

function updatePulseCard(events) {
  if (!events || !events.length) return;
  cachedLastEvent = events[0];
  
  const focus = $('pulseFocusTitle');
  if (focus) focus.textContent = `${events[0].project} · Em Construção`;
  
  const lastAction = $('pulseLastAction');
  if (lastAction) {
    const kindLabel = (events[0].kind || '').replace('_', ' ');
    lastAction.textContent = `Último marco [${kindLabel}]: ${events[0].title}`;
  }

  api('/api/todos').then(todos => {
    const nextEl = $('pulseNextStep');
    if (!nextEl) return;
    if (todos && todos.length) {
      nextEl.textContent = `Pendência #${todos[0].id}: ${todos[0].title}`;
    } else {
      nextEl.textContent = 'Tudo em dia! Defina a próxima etapa ou continue construindo.';
    }
  }).catch(() => {});

  const barsContainer = $('pulseWeekBars');
  if (barsContainer) {
    barsContainer.replaceChildren();
    const dayCounts = [0, 0, 0, 0, 0, 0, 0];
    const now = new Date();
    for (const e of events) {
      const d = new Date(e.occurred_at || e.recorded_at);
      const diffDays = Math.floor((now - d) / (86400 * 1000));
      if (diffDays >= 0 && diffDays < 7) {
        dayCounts[6 - diffDays]++;
      }
    }
    const max = Math.max(...dayCounts, 1);
    for (let i = 0; i < 7; i++) {
      const count = dayCounts[i];
      const bar = $create('div', 'pulse-bar');
      bar.style.height = `${Math.max(16, Math.round((count / max) * 100))}%`;
      bar.title = `${count} evento(s) há ${6 - i} dia(s)`;
      if (count > 0) bar.classList.add('has-activity');
      barsContainer.append(bar);
    }
  }
}

function applyPreset(key, isModal = false) {
  const p = PRESET_TEMPLATES[key];
  if (!p) return;

  if (p.from_last && cachedLastEvent) {
    if (isModal) {
      $('noteForm').elements.title.value = `Continuidade: ${cachedLastEvent.title}`.slice(0, 200);
      $('noteForm').elements.body.value = `Desdobramento do marco [${cachedLastEvent.kind}]:\n${cachedLastEvent.body || ''}`;
      $('noteForm').elements.reference.value = cachedLastEvent.source_ref || '';
    } else {
      $('omniInput').value = `Continuidade de [${cachedLastEvent.title}]: `;
      $('omniInput').focus();
    }
    return;
  }

  if (isModal) {
    $('noteForm').elements.title.value = p.title;
    $('noteForm').elements.body.value = p.body;
    $('noteForm').elements.title.focus();
  } else {
    $('omniInput').value = `${p.title} `;
    $('omniInput').focus();
  }
}

async function handleOmniSubmit() {
  const input = $('omniInput');
  const text = input.value.trim();
  if (!text) return;

  const project = $('omniProject') && $('omniProject').value ? $('omniProject').value : 'lac-laboratorio';
  let kind = 'note';
  let refPrefix = 'omni';

  if (currentPortal === 'system') {
    kind = 'decision';
    refPrefix = 'system:arch';
  } else if (currentPortal === 'ai') {
    kind = 'note';
    refPrefix = 'dialog:ai';
  } else if (currentPortal === 'doc') {
    kind = 'note';
    refPrefix = 'doc:concept';
  } else if (currentPortal === 'git') {
    kind = 'decision';
    refPrefix = 'code:git';
  }

  if (/^onde parei|próxim/i.test(text)) kind = 'todo';
  else if (/^bloqueio|travado|gargalo/i.test(text)) kind = 'todo';
  else if (/^decid|adot/i.test(text)) kind = 'decision';

  const button = $('btnOmniSend');
  button.disabled = true;
  try {
    const payload = {
      project: project,
      kind: kind,
      title: text.slice(0, 200),
      body: text.length > 200 ? text : `Captura rápida via Omni-Bar [${currentPortal}]`,
      reference: refPrefix
    };
    const res = await api('/api/notes', payload);
    input.value = '';
    showNotice(`Gravado instantaneamente (Evento #${res.id}).`);
    await refresh();
  } catch (err) {
    showNotice('Erro ao gravar: ' + err.message, true);
  } finally {
    button.disabled = false;
  }
}

// Event Listeners dos Portais Dimensionais
for (const btn of document.querySelectorAll('.portal-chip')) {
  btn.addEventListener('click', () => {
    for (const b of document.querySelectorAll('.portal-chip')) b.classList.remove('active');
    btn.classList.add('active');
    currentPortal = btn.dataset.portal;
  });
}

// Event Listeners das Pílulas de Presets na Omni-Bar
for (const pill of document.querySelectorAll('.omni-presets .preset-pill')) {
  pill.addEventListener('click', () => applyPreset(pill.dataset.preset, false));
}

// Event Listeners das Pílulas de Presets no Modal
for (const pill of document.querySelectorAll('.modal-presets .modal-preset')) {
  pill.addEventListener('click', () => applyPreset(pill.dataset.preset, true));
}

if ($('btnOmniSend')) $('btnOmniSend').addEventListener('click', handleOmniSubmit);
if ($('omniInput')) {
  $('omniInput').addEventListener('keydown', e => {
    if (e.key === 'Enter') {
      e.preventDefault();
      handleOmniSubmit();
    }
  });
}
