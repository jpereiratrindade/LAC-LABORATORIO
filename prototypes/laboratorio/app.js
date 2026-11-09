'use strict';

// Illustrative data only. This prototype never calls the LAC API or a model.
const $ = id => document.getElementById(id);
const icon = name => `<svg aria-hidden="true"><use href="#i-${name}"/></svg>`;
const STORAGE_KEY = 'lac-visual-prototype-v1';
const materials = [
  {id:'project',ref:'project:1',kind:'project',icon:'grid',label:'Frente de trabalho',title:'Coleta em campo',short:'Um protocolo, várias etapas.',x:62,y:68,w:206,h:128,nature:'Contexto de projeto',text:'Frente demonstrativa que reúne o protocolo, sua revisão e a validação em campo.'},
  {id:'doc',ref:'event:102',kind:'document',icon:'doc',label:'Documento · revisão observada',title:'Protocolo de coleta',short:'protocolo.md · revisão 3',x:395,y:156,w:246,h:216,nature:'Observação técnica',text:'O observador encontrou alteração no hash de protocolo.md. O conteúdo da alteração não foi recuperado. A miniatura nesta tela é ilustrativa.'},
  {id:'decision',ref:'event:101',kind:'decision',icon:'check',label:'Metodologia · declaração',title:'Revisar o protocolo',short:'Proposta registrada por uma pessoa.',x:772,y:85,w:238,h:155,nature:'Declaração humana',text:'Foi registrada a proposta de revisar o protocolo de coleta. A validação em campo ainda não foi realizada, segundo essa declaração.'},
  {id:'git',ref:'event:103',kind:'commit',icon:'git',label:'Git · observação',title:'Ajusta roteiro de coleta',short:'Commit encontrado na fonte cadastrada.',x:65,y:375,w:239,h:146,nature:'Observação técnica',text:'Um commit demonstrativo menciona protocolo.md. Sua presença não comprova validação do protocolo nem funcionamento de uma implementação.'},
  {id:'task',ref:'event:104',kind:'task',icon:'time',label:'Próximo passo · declarado',title:'Validar em campo',short:'Pendência registrada, ainda aberta.',x:769,y:389,w:238,h:142,nature:'Declaração humana',text:'Uma pessoa registrou a pendência de realizar a validação em campo após revisar o protocolo.'},
  {id:'gap',ref:'result:demo-1',kind:'question',icon:'search',label:'Lacuna de contexto',title:'O que mudou no texto?',short:'Conteúdo ainda não recuperado.',x:400,y:488,w:240,h:119,nature:'Interpretação demonstrativa',text:'Há observação de mudança no hash, mas não há conteúdo recuperado que permita descrever a alteração.'},
];
const edges = [
  {from:'project',to:'doc',label:'reúne',x:300,y:153},
  {from:'git',to:'doc',label:'menciona o arquivo',x:286,y:386},
  {from:'doc',to:'decision',label:'associação proposta',x:656,y:170,candidate:true},
  {from:'decision',to:'task',label:'pendência vinculada',x:803,y:306},
  {from:'doc',to:'gap',label:'conteúdo ausente',x:463,y:431,extended:true},
];
const defaults = () => ({view:'laboratory',selected:'doc',relation:'candidate',expanded:false,positions:{},pins:[],camera:null,scenario:'normal',memory:{concise:true,sources:true}});
let state = defaults();
try {
  const saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || 'null');
  if (saved && typeof saved === 'object') {
    for (const key of ['view','selected','relation','scenario']) if (typeof saved[key] === 'string') state[key] = saved[key];
    state.expanded = saved.expanded === true;
    state.pins = Array.isArray(saved.pins) ? saved.pins.filter(id => materials.some(m => m.id === id)) : [];
    for (const m of materials) {
      const p = saved.positions?.[m.id];
      if (p && Number.isFinite(p.x) && Number.isFinite(p.y)) state.positions[m.id] = {x:Math.max(0,Math.min(1080-m.w,p.x)),y:Math.max(20,Math.min(650-m.h,p.y))};
    }
    if (saved.memory && typeof saved.memory.concise === 'boolean' && typeof saved.memory.sources === 'boolean') state.memory = saved.memory;
    const c = saved.camera;
    if (c && [c.x,c.y,c.z].every(Number.isFinite) && c.z >= .25 && c.z <= 1.8 && Math.abs(c.x)<5000 && Math.abs(c.y)<5000) state.camera=c;
  }
} catch { /* Storage can be unavailable in a private browser. */ }
if (!['laboratory','connections','trajectory','bench'].includes(state.view)) state.view='laboratory';
if (!materials.some(m => m.id===state.selected) && state.selected!=='relation') state.selected='doc';
if (!['candidate','confirmed','rejected'].includes(state.relation)) state.relation='candidate';
if (!['normal','processing','paused','unavailable','missing','empty'].includes(state.scenario)) state.scenario='normal';
let draft = '';
let toastTimer;
const material = id => materials.find(m => m.id===id) || materials[1];
const position = m => state.positions[m.id] || {x:m.x,y:m.y};
const size = m => {const el=document.querySelector(`[data-node="${m.id}"]`);return {w:el?.offsetWidth||m.w,h:el?.offsetHeight||m.h};};
const save = () => { try { localStorage.setItem(STORAGE_KEY, JSON.stringify(state)); } catch {} };

function toast(text) {
  $('toast').textContent=text; $('toast').hidden=false;
  clearTimeout(toastTimer); toastTimer=setTimeout(() => { $('toast').hidden=true; },3200);
}

function renderEdges() {
  $('edges').innerHTML=edges.filter(e => !e.extended || state.expanded).map(e => {
    const a=material(e.from), b=material(e.to), pa=position(a), pb=position(b), sa=size(a), sb=size(b);
    let ax=pa.x+sa.w/2, ay=pa.y+sa.h/2, bx=pb.x+sb.w/2, by=pb.y+sb.h/2;
    if (Math.abs(ax-bx)>100) {const right=ax<bx;ax+=right?sa.w/2:-sa.w/2;bx+=right?-sb.w/2:sb.w/2;}
    else {const down=ay<by;ay+=down?sa.h/2:-sa.h/2;by+=down?-sb.h/2:sb.h/2;}
    const path=`M${ax},${ay} C${ax+(bx-ax)*.5},${ay} ${ax+(bx-ax)*.5},${by} ${bx},${by}`;
    const status=e.candidate ? state.relation : '';
    const label=e.candidate ? ({candidate:'associação proposta',confirmed:'confirmada nesta prévia',rejected:'proposta descartada'})[state.relation] : e.label;
    return `<g class="${e.candidate?'edge-target':''}" ${e.candidate?'role="button" tabindex="0" aria-label="Revisar conexão proposta entre protocolo e decisão" data-edge="relation"':''}><path class="edge ${status}" d="${path}"/>${e.candidate?`<path class="edge-hit" d="${path}"/>`:''}<text class="edge-label" text-anchor="middle" x="${(ax+bx)/2}" y="${(ay+by)/2-13}">${label}</text></g>`;
  }).join('');
}

function renderNodes() {
  $('nodes').innerHTML=materials.filter(m => m.id!=='gap'||state.expanded).map(m => {
    const p=position(m);
    return `<article class="node ${m.kind} ${state.selected===m.id?'selected':''}" data-node="${m.id}" style="left:${p.x}px;top:${p.y}px;width:${m.w}px;min-height:${m.h}px">${state.pins.includes(m.id)?`<span class="pin-indicator" title="Posição fixada">${icon('pin')}</span>`:''}<div class="node-header">${icon(m.icon)}<span>${m.label}</span><button class="move-handle" data-drag="${m.id}" aria-label="Arrastar ${m.title}; alternativa disponível no painel de seleção">${icon('move')}</button></div><button class="node-select" data-select="${m.id}" aria-pressed="${state.selected===m.id}"><h3>${m.title}</h3>${m.id==='doc'?'<div class="document-preview"><div class="paper" aria-hidden="true"><i></i><i></i><i></i><i></i><i></i></div><span>Uma nova revisão.<br>Conteúdo ainda não recuperado.</span></div>':`<p>${m.short}</p>`}<span class="node-bottom">${icon(m.id==='doc'?'git':m.icon)}${m.id==='doc'?'Hash alterado · fonte cadastrada':m.nature}</span></button></article>`;
  }).join('');
  renderEdges();
}

function camera() {
  if (!state.camera) fitAll(false);
  const c=state.camera;
  $('world').style.transform=`translate(${c.x}px,${c.y}px) scale(${c.z})`;
  $('world').classList.toggle('overview',c.z<.85);
  renderEdges();
  $('zoomValue').textContent=`${Math.round(c.z*100)}%`;
}

function fitAll(persist=true) {
  const r=$('mapViewport').getBoundingClientRect();
  if (!r.width || !r.height) return;
  const z=Math.min((r.width-24)/1080,(r.height-36)/650,1.1);
  state.camera={x:(r.width-1080*z)/2,y:(r.height-650*z)/2+10,z:Math.max(.25,z)};
  if (r.width<500) { fitSelection(false); return; }
  camera(); if(persist) save();
}

function fitSelection(persist=true) {
  const r=$('mapViewport').getBoundingClientRect(), m=material(state.selected), p=position(m);
  if (!r.width || !r.height) return;
  const z=r.width<500?.85:Math.min(1.1,(r.height-50)/(m.h+80));
  state.camera={x:r.width/2-(p.x+m.w/2)*z,y:r.height/2-(p.y+m.h/2)*z,z};
  camera(); if(persist) save();
}

function zoom(factor) {
  const r=$('mapViewport').getBoundingClientRect(), c=state.camera;
  const z=Math.min(1.8,Math.max(.25,c.z*factor)), f=z/c.z;
  state.camera={x:r.width/2-(r.width/2-c.x)*f,y:r.height/2-(r.height/2-c.y)*f,z};
  camera(); save();
}

function sourceCard(id) {
  const m=material(id);
  return `<button class="source-card" data-source="${id}">${icon(m.icon)}<span><strong>${m.title}</strong><small>${m.ref} · ${m.nature}</small></span>${icon('arrow')}</button>`;
}

function renderInspector() {
  const m=material(state.selected), reviewed=state.relation!=='candidate';
  let content;
  if (state.selected==='relation') {
    const label={candidate:'Conexão candidata',confirmed:'Confirmação demonstrativa',rejected:'Proposta descartada'}[state.relation];
    content=`<p class="eyebrow">UMA RELAÇÃO PARA EXAMINAR</p><span class="badge ${state.relation==='confirmed'?'accepted':''}">${icon(state.relation==='confirmed'?'check':'link')}${label}</span><h2>Do protocolo<br>à decisão.</h2><p>As duas fontes tratam da revisão do protocolo. Isso permite propor uma associação; não comprova que a alteração no arquivo decorra desta decisão.</p><div class="insight-callout"><p>O conteúdo alterado ainda não foi recuperado. Compare as origens antes de confirmar o vínculo.</p></div><div class="inspector-buttons"><button class="button secondary" data-action="compare">Comparar fontes</button>${reviewed?'': '<button class="button primary" data-action="confirm">Confirmar vínculo</button><button class="text-button" data-action="reject">Descartar</button>'}</div>${reviewed?'<p>Revisão feita apenas nesta prévia. Autoria: pessoa demonstrativa. Nenhum registro enviado ao LAC.</p>':''}<div class="source-label"><span>BASE DA PROPOSTA</span><span>2 referências</span></div>${sourceCard('doc')}${sourceCard('decision')}`;
  } else {
    content=`<p class="eyebrow">${m.nature.toUpperCase()}</p><h2>${m.title}</h2><p>${m.text}</p>${m.id==='doc'?`<div class="insight-callout"><p>Encontrei uma possível conexão com a proposta de revisão em Metodologia.</p></div><div class="inspector-buttons"><button class="button primary" data-action="review">${reviewed?'Ver revisão':'Examinar conexão'} ${icon('arrow')}</button><button class="button secondary" data-action="compare">Comparar</button></div>`:`<div class="inspector-buttons"><button class="button secondary" data-action="neighbors">Explorar relações ${icon('arrow')}</button></div>`}<div class="source-label"><span>ORIGEM DA SELEÇÃO</span><span>Exemplo fictício</span></div>${sourceCard(m.id)}<div class="selection-tools"><button data-action="pin">${icon('pin')}${state.pins.includes(m.id)?'Desafixar':'Fixar posição'}</button><span class="move-tools" aria-label="Mover seleção por clique"><button data-move="-24,0" aria-label="Mover cartão para esquerda">←</button><button data-move="0,-24" aria-label="Mover cartão para cima">↑</button><button data-move="0,24" aria-label="Mover cartão para baixo">↓</button><button data-move="24,0" aria-label="Mover cartão para direita">→</button></span></div>`;
  }
  $('inspectorContent').innerHTML=content;
}

function renderTrajectory() {
  const entries=[['decision','06 nov · 09:20'],['git','08 nov · 16:05'],['doc','09 nov · 08:40'],['task','09 nov · 09:10']];
  $('trajectory').innerHTML=`<div class="section-heading"><div><p class="eyebrow">MESMO CONTEXTO, OUTRA PERSPECTIVA</p><h2>Como chegamos até aqui</h2><p>Datas demonstrativas. A sequência indica tempo, sem atribuir causa.</p></div>${icon('time')}</div><div class="timeline">${entries.map(([id,date])=>{const m=material(id);return `<article class="time-item"><time>${date}</time><span class="time-dot"></span><button class="${state.selected===id?'selected':''}" data-select="${id}">${icon(m.icon)}<h3>${m.title}</h3><p>${m.short}</p><small>${m.nature}</small></button></article>`;}).join('')}</div>`;
}

function renderBench() {
  $('bench').innerHTML=`<div class="section-heading"><div><p class="eyebrow">MATERIAIS APROXIMADOS, ORIGENS PRESERVADAS</p><h2>Compare antes de relacionar</h2><p>Seleção atual: ${state.selected==='relation'?'conexão candidata':material(state.selected).title}.</p></div>${icon('doc')}</div><div class="comparison">${['doc','decision'].map(id=>{const m=material(id);return `<article class="compare-card ${state.selected===id?'selected':''}">${icon(m.icon)}<p class="eyebrow">${m.nature}</p><h3>${m.title}</h3><blockquote>${m.text}</blockquote><small>${m.ref} · dados fictícios<br>${id==='doc'?'Sem conteúdo extraído.':'Declaração de pessoa demonstrativa.'}</small><button class="text-button" data-source="${id}">Examinar origem</button></article>`;}).join('')}</div><div class="compare-actions"><span>Organizar materiais não cria vínculo automaticamente.</span><button class="button primary" data-action="review">${icon('link')} ${state.relation==='candidate'?'Revisar associação':'Ver revisão registrada na prévia'}</button></div>`;
}

function render() {
  const titles={laboratory:['O protocolo mudou.<br>O contexto está aqui.','Uma alteração observada. Uma decisão próxima. Uma conexão para examinar.'],connections:['Conexões que você<br>pode examinar.','Explore uma vizinhança por vez. Cada ligação mantém motivo e origem.'],trajectory:['Uma trajetória,<br>com suas revisões.','Acontecimentos e declarações preservam sua posição no tempo.'],bench:['Materiais próximos.<br>Decisões com contexto.','Compare fontes, examine lacunas e registre relações explicitamente.']};
  $('viewTitle').innerHTML=titles[state.view][0]; $('viewNote').textContent=titles[state.view][1];
  document.querySelectorAll('[data-view]').forEach(b=>{const active=b.dataset.view===state.view;b.classList.toggle('active',active);b.setAttribute('aria-pressed',String(active));});
  $('projectSwitcher').hidden=state.view!=='laboratory';
  const empty=state.scenario==='empty';
  $('mapSurface').hidden=empty||!['laboratory','connections'].includes(state.view);
  $('trajectory').hidden=empty||state.view!=='trajectory'; $('bench').hidden=empty||state.view!=='bench';
  $('emptyState').hidden=!empty;
  $('depthButton').hidden=empty||!['laboratory','connections'].includes(state.view);
  $('depthButton').setAttribute('aria-pressed',String(state.expanded));
  $('depthButton').textContent=state.expanded?'Recolher vizinhança −':'Expandir vizinhança +';
  $('scenario').value=state.scenario;
  const banners={processing:'Novas mudanças em processamento. O contexto já preparado continua disponível.',paused:'Automação pausada neste exemplo. Você pode explorar e revisar o contexto existente.',unavailable:'Modelo indisponível. O trabalho aguardaria na fila; os registros existentes continuam acessíveis.',missing:'Fonte indisponível. Há metadados registrados, mas o conteúdo não pode ser recuperado agora.'};
  $('stateBanner').hidden=!banners[state.scenario]; $('stateBanner').textContent=banners[state.scenario]||'';
  $('stateBanner').className=`state-banner ${state.scenario}`;
  renderNodes(); renderTrajectory(); renderBench(); renderInspector();
  requestAnimationFrame(()=>{if(!state.camera)fitAll();else camera();});
  save();
}

function select(id) {
  state.selected=id;
  if(id==='gap')state.expanded=true;
  render();
}

function openDialog(eyebrow,html) {
  $('dialogEyebrow').textContent=eyebrow; $('dialogContent').innerHTML=html;
  if(!$('detailDialog').open)$('detailDialog').showModal();
}

function openSource(id) {
  const m=material(id);
  if(state.scenario==='missing'&&id==='doc') {
    openDialog('FONTE INDISPONÍVEL','<h2>Conteúdo não acessível.</h2><p>O histórico preserva a observação do hash. A prévia não apresenta texto do arquivo como se tivesse sido recuperado.</p>'); return;
  }
  openDialog('ORIGEM · DADOS FICTÍCIOS',`<h2>${m.title}</h2><span class="badge">${m.nature}</span><blockquote>${m.text}</blockquote><div class="detail-meta">Referência: ${m.ref}<br>Ocorrência demonstrativa: 09/11/2026, 08:40<br>Registro demonstrativo: 09/11/2026, 08:41<br>Autoria: ${m.nature==='Observação técnica'?'observador demonstrativo':'declarante demonstrativo'}<br>Este material não vem do banco operacional.</div>`);
}

function memoryDialog() {
  openDialog('MEMÓRIA INSPECIONÁVEL · EXEMPLO',`<h2>O que o assistente lembra.</h2><p>Preferências demonstrativas, guardadas somente neste navegador. Você pode desativar seu uso nesta prévia.</p><label class="memory-item"><span>Preferir sínteses curtas<small>Origem: escolha explícita demonstrativa.<br>Escopo: pessoal · revisão 1.</small></span><input type="checkbox" data-memory="concise" ${state.memory.concise?'checked':''}></label><label class="memory-item"><span>Mostrar fontes junto das propostas<small>Origem: escolha explícita demonstrativa.<br>Escopo: pessoal · revisão 1.</small></span><input type="checkbox" data-memory="sources" ${state.memory.sources?'checked':''}></label><div class="detail-meta">Feedback nesta prévia: ${state.relation==='candidate'?'nenhuma revisão':state.relation==='confirmed'?'uma confirmação humana demonstrativa':'um descarte contextual'}.<br>Guardar feedback não treina os pesos do modelo.<br>Não há acesso à memória de outros usuários.</div>`);
}

function action(name) {
  if(name==='review'){state.selected='relation';render();}
  if(name==='compare'){state.view='bench';render();}
  if(name==='neighbors'){state.view='connections';render();requestAnimationFrame(()=>fitSelection());}
  if(name==='confirm'||name==='reject') {
    state.relation=name==='confirm'?'confirmed':'rejected';render();
    toast(name==='confirm'?'Vínculo confirmado somente nesta prévia.':'Proposta descartada neste contexto demonstrativo.');
  }
  if(name==='pin') {
    const id=material(state.selected).id;
    state.pins=state.pins.includes(id)?state.pins.filter(x=>x!==id):[...state.pins,id]; render();
    toast(state.pins.includes(id)?'Posição fixada nesta prévia.':'Posição desafixada.');
  }
}

function move(id,dx,dy) {
  const m=material(id),p=position(m);
  state.positions[id]={x:Math.max(0,Math.min(1080-m.w,p.x+dx)),y:Math.max(20,Math.min(650-m.h,p.y+dy))};
  const el=document.querySelector(`[data-node="${id}"]`);
  if(el){el.style.left=`${state.positions[id].x}px`;el.style.top=`${state.positions[id].y}px`;}
  renderEdges(); save();
}

document.addEventListener('click',event=>{
  const b=event.target.closest('button'); if(!b)return;
  if(b.dataset.view){state.view=b.dataset.view;render();}
  if(b.dataset.select)select(b.dataset.select);
  if(b.dataset.source)openSource(b.dataset.source);
  if(b.dataset.action)action(b.dataset.action);
  if(b.dataset.move){const [dx,dy]=b.dataset.move.split(',').map(Number);move(material(state.selected).id,dx,dy);}
});
$('edges').addEventListener('click',e=>{if(e.target.closest('[data-edge]'))select('relation');});
$('edges').addEventListener('keydown',e=>{if(e.target.closest('[data-edge]')&&['Enter',' '].includes(e.key)){e.preventDefault();select('relation');}});
$('depthButton').onclick=()=>{state.expanded=!state.expanded;render();};
$('zoomIn').onclick=()=>zoom(1.2);$('zoomOut').onclick=()=>zoom(1/1.2);
$('fitSelection').onclick=()=>fitSelection();$('fitAll').onclick=()=>fitAll();
$('scenario').onchange=e=>{state.scenario=e.target.value;render();};
$('closeDialog').onclick=()=>$('detailDialog').close();
$('detailDialog').addEventListener('click',e=>{if(e.target===$('detailDialog'))$('detailDialog').close();});
$('openMemory').onclick=memoryDialog;
$('focusProject').onclick=()=>{state.selected='project';state.view='connections';render();requestAnimationFrame(()=>fitAll());};
$('relatedProject').onclick=()=>{state.selected='decision';state.view='connections';render();requestAnimationFrame(()=>fitSelection());};
document.querySelector('.brand').onclick=e=>{e.preventDefault();state.view='laboratory';render();};
function reset(){state=defaults();draft='';$('answer').hidden=true;render();toast('Exemplo restaurado.');}
$('resetDemo').onclick=reset;$('restoreFromEmpty').onclick=reset;
$('openCapture').onclick=()=>{
  openDialog('REGISTRO DEMONSTRATIVO','<h2>Capture sem perder contexto.</h2><p>Rascunho restrito a esta aba. Nenhum evento será gravado no LAC.</p><form id="captureForm"><label class="capture-field" for="captureText">Observação sobre Coleta em campo</label><textarea id="captureText" rows="5" required maxlength="2000" placeholder="O que vale preservar deste momento?"></textarea><button class="button primary">Manter rascunho nesta aba</button></form>');
  $('captureText').value=draft;$('captureText').focus();
};
$('dialogContent').addEventListener('submit',e=>{if(e.target.id==='captureForm'){e.preventDefault();draft=$('captureText').value;$('detailDialog').close();toast('Rascunho mantido nesta aba. Nenhum evento gravado.');}});
$('dialogContent').addEventListener('change',e=>{if(e.target.dataset.memory){state.memory[e.target.dataset.memory]=e.target.checked;save();toast('Preferência demonstrativa atualizada.');}});

function searchDialog() {
  openDialog('BUSCA NO CONTEXTO DEMONSTRATIVO','<h2>Encontre um ponto de partida.</h2><label class="capture-field" for="searchInput">Título do material</label><input class="search-field" id="searchInput" placeholder="Documento, decisão, próxima ação…" autocomplete="off"><div id="searchResults"></div>');
  function results(){const q=$('searchInput').value.toLocaleLowerCase('pt-BR');const list=materials.filter(m=>m.title.toLocaleLowerCase('pt-BR').includes(q));$('searchResults').innerHTML=list.map(m=>`<button class="source-card" data-search-select="${m.id}">${icon(m.icon)}<span><strong>${m.title}</strong><small>${m.nature}</small></span>${icon('arrow')}</button>`).join('');if(!list.length)$('searchResults').textContent='Nenhum material demonstrativo encontrado.';}
  $('searchInput').oninput=results;results();$('searchInput').focus();
}
$('openSearch').onclick=searchDialog;
$('dialogContent').addEventListener('click',e=>{const b=e.target.closest('[data-search-select]');if(b){$('detailDialog').close();state.view='connections';select(b.dataset.searchSelect);requestAnimationFrame(()=>fitSelection());}});
document.addEventListener('keydown',e=>{if(e.key==='/'&&!e.ctrlKey&&!e.metaKey&&!$('detailDialog').open&&!['INPUT','TEXTAREA','SELECT'].includes(document.activeElement.tagName)){e.preventDefault();searchDialog();}});
$('questionForm').onsubmit=e=>{
  e.preventDefault(); const q=$('question').value.trim().toLocaleLowerCase('pt-BR');if(!q)return;
  const response=q.includes('mud')?'Resposta demonstrativa: o hash de protocolo.md mudou (event:102). A proposta de revisão está registrada em event:101. O conteúdo alterado não foi recuperado.':q.includes('lembr')||q.includes('memór')?'Resposta demonstrativa: você pode inspecionar as preferências no botão Memória. Elas ficam neste navegador e não treinam o modelo.':'Esta prévia mostra ações e respostas demonstrativas. Use “Comparar” para examinar as duas fontes; conversa real com o modelo será integrada na T11.';
  $('answer').textContent=response;$('answer').hidden=false;$('question').value='';
};

let drag=null;
$('mapViewport').addEventListener('pointerdown',e=>{
  if(e.button!==0)return;
  const handle=e.target.closest('[data-drag]');
  if(handle){e.preventDefault();const id=handle.dataset.drag;drag={type:'node',id,x:e.clientX,y:e.clientY,target:handle};state.selected=id;renderInspector();document.querySelectorAll('[data-node]').forEach(el=>{const selected=el.dataset.node===id;el.classList.toggle('selected',selected);el.querySelector('.node-select').setAttribute('aria-pressed',String(selected));});handle.setPointerCapture(e.pointerId);}
  else if(!e.target.closest('.node,[data-edge]')){drag={type:'pan',x:e.clientX,y:e.clientY,target:$('mapViewport')};$('mapViewport').setPointerCapture(e.pointerId);}
});
$('mapViewport').addEventListener('pointermove',e=>{
  if(!drag)return;
  const dx=e.clientX-drag.x,dy=e.clientY-drag.y;drag.x=e.clientX;drag.y=e.clientY;
  if(drag.type==='node')move(drag.id,dx/state.camera.z,dy/state.camera.z);
  else {state.camera.x+=dx;state.camera.y+=dy;camera();}
});
for(const event of ['pointerup','pointercancel'])$('mapViewport').addEventListener(event,()=>{if(drag){drag=null;save();}});
$('mapViewport').addEventListener('keydown',e=>{
  if(e.target!==$('mapViewport'))return;
  const delta={ArrowLeft:[32,0],ArrowRight:[-32,0],ArrowUp:[0,32],ArrowDown:[0,-32]}[e.key];
  if(delta){e.preventDefault();state.camera.x+=delta[0];state.camera.y+=delta[1];camera();save();}
});
$('mapViewport').addEventListener('wheel',e=>{if(e.ctrlKey||e.metaKey){e.preventDefault();zoom(e.deltaY<0?1.1:1/1.1);}},{passive:false});
render();
