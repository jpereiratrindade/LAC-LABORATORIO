'use strict';
// LAC v0.1.3: every actionable control maps to a real local endpoint or browser preference.
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
  observation:'Observação', integrity:'Integridade', reports:'Relatórios',
  settings:'Preferências', integrations:'Integrações', about:'Sobre o LAC'};
const eventIcons = {git_commit:'⌁',file_added:'+',file_changed:'↻',file_missing:'−',
  note:'✎',decision:'✓',todo:'□',todo_closed:'✓',relation:'◇',correction:'↶'};
let apiToken='';
try { apiToken=sessionStorage.getItem('lac_api_token')||''; } catch {}
const authHeaders = () => apiToken ? {'Authorization':`Bearer ${apiToken}`} : {};
const api = async (path, data) => {
  const opts = data === undefined ? {} : {
    method: 'POST', headers: {'Content-Type':'application/x-www-form-urlencoded','X-LAC-Local':'1'},
    body: new URLSearchParams(data).toString()
  };
  opts.headers={...opts.headers,...authHeaders()};
  const response = await fetch(path, opts);
  if(response.status===403){$('accessPanel').hidden=false;}
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
  if (!viewLabels[view]) return;
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
  for (const [id,placeholder] of [['filterProject','Todos'],['reportProject','Todos os projetos']]) {
    const el=$(id), before=el.value;
    el.replaceChildren(new Option(placeholder,''));
    for (const p of projects) el.add(new Option(p.name,p.name));
    el.value=before;
  }
  return projects;
}
function renderEvent(target,e) {
  const element=card(e.title,e.body,[[e.project],[(e.kind||'').replaceAll('_',' ')],
    [e.evidence_state,e.evidence_state],[e.actor==='llm'?'Autoria: LLM':e.actor==='user'?'Autoria: pessoa':'Observação automática']],e.source_ref,e.occurred_at,eventIcons[e.kind]||'◦');
  element.querySelector('.event-time').append($create('span','',`Registrado: ${localDate(e.recorded_at)}`));
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
}
async function refreshEventListing() {
  const list=await api('/api/events?limit=200'),target=$('eventsListing');target.replaceChildren();
  if (!list.length) {target.append(empty('Nenhum evento observado ou declarado ainda.'));return;}
  for (const e of list) renderEvent(target,e);
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
async function refresh(){
  const projects=await refreshProjectsOptions();
  await refreshStats();
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
showView(viewLabels[initial]?initial:'overview');
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
$('btnAccess').addEventListener('click',()=>{$('accessPanel').hidden=false;$('apiToken').focus();});
$('accessForm').addEventListener('submit',async e=>{
  e.preventDefault();apiToken=$('apiToken').value.trim();$('apiToken').value='';
  try{sessionStorage.setItem('lac_api_token',apiToken);}catch{}
  try{await refresh();$('accessPanel').hidden=true;showNotice('Acesso à API conectado nesta sessão.');}catch(err){showNotice(err.message,true);}
});
