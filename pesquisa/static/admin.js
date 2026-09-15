'use strict';
const filters = document.querySelector('#filters');
const errorBox = document.querySelector('#dashboard-error');
let page = 1, pageCount = 1, activeQuery = '', labels = {}, generation = 0;
const number = n => Number(n).toLocaleString('pt-BR');
const element = (tag, text, className) => { const e = document.createElement(tag); if (text !== undefined) e.textContent = text; if (className) e.className = className; return e; };
const date = value => new Date(value).toLocaleString('pt-BR', {timeZone:'America/Sao_Paulo', dateStyle:'short', timeStyle:'short'});
const dayLabel = value => value.split('-').reverse().join('/');
async function get(url) {
  const response = await fetch(url, {cache:'no-store'});
  if (response.status === 401) { window.location.assign('/login'); throw new Error('Sua sessão expirou. Entre novamente.'); }
  if (!response.ok) throw new Error('Não foi possível carregar. Confira o período dos filtros e tente novamente.');
  return response.json();
}
function bars(id, rows) {
  const container = document.querySelector(`#chart-${id}`); container.replaceChildren();
  [...rows].sort((a,b) => b.count-a.count).forEach(row => {
    const wrapper = element('div', undefined, 'bar-row');
    const label = element('div', undefined, 'bar-label');
    label.append(element('span',row.label),element('strong',`${number(row.count)} · ${number(row.percent)}%`));
    const bar = element('progress'); bar.max=100; bar.value=row.percent; bar.setAttribute('aria-label',`${row.label}: ${row.count} respostas, ${row.percent}%`);
    wrapper.append(label,bar); container.append(wrapper);
  });
}
function history(days) {
  const table = document.querySelector('#history-table'); table.replaceChildren();
  const container = document.querySelector('#history-chart'); container.replaceChildren();
  days.forEach(day => { const tr = element('tr'); [dayLabel(day.day),number(day.count),number(day.cumulative)].forEach(v => tr.append(element('td',v))); table.append(tr); });
  if (!days.length) {container.append(element('p','O histórico aparece a partir da primeira resposta.','empty'));return;}
  const ns='http://www.w3.org/2000/svg';
  const svg = document.createElementNS(ns,'svg'); svg.setAttribute('viewBox','0 0 900 190');svg.setAttribute('role','img');svg.setAttribute('aria-label',`Evolução acumulada: ${days.at(-1).cumulative} respostas de ${dayLabel(days[0].day)} a ${dayLabel(days.at(-1).day)}.`);
  const start = new Date(days[0].day+'T12:00:00Z').valueOf(), end = new Date(days.at(-1).day+'T12:00:00Z').valueOf();
  const max=days.at(-1).cumulative;
  const points=days.map(d => [50+(new Date(d.day+'T12:00:00Z').valueOf()-start)/Math.max(86400000,end-start)*810,145-d.cumulative/max*115]);
  function add(tag,attrs,text){const e=document.createElementNS(ns,tag);Object.entries(attrs).forEach(([k,v])=>e.setAttribute(k,String(v)));if(text)e.textContent=text;svg.append(e);return e;}
  [0,max].forEach(v=>{const y=145-v/max*115;add('line',{x1:50,x2:860,y1:y,y2:y,class:'gridline'});add('text',{x:35,y:y+4,'text-anchor':'end'},String(v));});
  let line=`M ${points[0][0]} ${points[0][1]}`;
  for(let i=1;i<points.length;i++)line+=` H ${points[i][0]} V ${points[i][1]}`;
  add('path',{d:`${line} L ${points.at(-1)[0]} 145 L 50 145 Z`,class:'trend-area'});
  add('path',{d:line,class:'trend-line'});
  if(points.length<=100)points.forEach(([x,y])=>add('circle',{cx:x,cy:y,r:3,class:'trend-dot'}));
  add('text',{x:50,y:177},dayLabel(days[0].day));
  if(days.length>1)add('text',{x:860,y:177,'text-anchor':'end'},dayLabel(days.at(-1).day));
  container.append(svg);
}
function cross(rows) {
  const table = document.querySelector('#cross-table'); table.replaceChildren();
  const head=element('thead'),hr=element('tr');hr.append(element('th','Formação'));
  Object.values(labels.format).forEach(label=>hr.append(element('th',label)));head.append(hr);
  const body=element('tbody');
  Object.entries(labels.stage).forEach(([stage,label])=>{const tr=element('tr');tr.append(element('th',label));Object.keys(labels.format).forEach(format=>{const count=rows.find(r=>r.stage===stage&&r.format===format)?.count||0;tr.append(element('td',number(count),count?'has-value':''));});body.append(tr);});
  table.append(head,body);
}
function renderAnalytics(data) {
  document.querySelector('#total').textContent=number(data.total);
  document.querySelector('#total-all').textContent=number(data.total_all);
  document.querySelector('#contacts').textContent=number(data.contact_consent);
  document.querySelector('#contact-percent').textContent=`${data.total?number(Math.round(data.contact_consent/data.total*1000)/10):0}% das respostas do recorte`;
  const ranked=[...data.groups.gaps].sort((a,b)=>b.count-a.count),top=ranked[0];
  const tied=ranked.filter(r=>r.count===top.count);
  document.querySelector('#top-gap').textContent=data.total?(tied.length>1?'Prioridades empatadas':top.label):'Aguardando respostas';
  document.querySelector('#gap-percent').textContent=data.total?`${number(top.percent)}% · ${number(top.count)} participantes${tied.length>1?' por opção':''}`:'Os resultados aparecerão aqui';
  labels={};Object.entries(data.groups).forEach(([id,rows])=>{labels[id]=Object.fromEntries(rows.map(r=>[r.code,r.label]));bars(id,rows);});
  const insights=document.querySelector('#insights');insights.replaceChildren();
  data.insights.forEach(item=>{const card=element('article',undefined,'insight');card.append(element('h3',item.title),element('p',item.text));insights.append(card);});
  if(!data.insights.length) insights.append(element('p','Ainda não há respostas neste recorte. Compartilhe a pesquisa ou ajuste os filtros.','empty'));
  history(data.days);cross(data.cross);
}
function renderRecords(data) {
  pageCount=data.pages;
  const target=document.querySelector('#records');target.replaceChildren();
  for(const r of data.rows){
    const tr=element('tr');tr.append(element('td',date(r.created_at)));
    const who=element('td',r.name||'Não informado');who.append(element('small',r.contact_consent?'Contato autorizado':'Sem autorização para contato'));tr.append(who);
    tr.append(element('td',labels.stage[r.stage]),element('td',labels.area[r.area]));
    const cell=element('td'),details=element('details');details.append(element('summary','Ler resposta e detalhes'));
    details.append(element('p',r.wish));
    const dl=element('dl');
    [['Formato',labels.format[r.format]],['Preparação',r.gaps.map(g=>labels.gaps[g]).join('; ')],['E-mail',r.email||'Não informado'],['Telefone',r.phone||'Não informado'],['Contato',r.contact_consent?'Autorizado':'Não autorizado']].forEach(([k,v])=>dl.append(element('dt',k),element('dd',v)));
    details.append(dl,element('small','Protocolo'),element('code',r.id));cell.append(details);tr.append(cell);target.append(tr);
  }
  if(!data.rows.length){const tr=element('tr'),td=element('td','Nenhuma resposta encontrada.','empty');td.colSpan=5;tr.append(td);target.append(tr);}
  document.querySelector('#record-count').textContent=`${number(data.total)} RESPOSTAS`;
  document.querySelector('#page-label').textContent=`Página ${data.page} de ${data.pages}`;
  document.querySelector('#page-prev').disabled=page<=1;document.querySelector('#page-next').disabled=page>=pageCount;
}
async function load(all=true) {
  const current=++generation;
  errorBox.hidden=true;document.querySelector('#updated').textContent='Atualizando dados…';
  try {
    if(all){const data=await get(`/api/admin/analytics?${activeQuery}`);if(current!==generation)return;renderAnalytics(data);}
    const records=await get(`/api/admin/responses?${activeQuery}&page=${page}`);if(current!==generation)return;renderRecords(records);
    document.querySelector('#updated').textContent=`Atualizado às ${new Date().toLocaleTimeString('pt-BR',{timeZone:'America/Sao_Paulo'})}`;
    document.querySelector('#export').href=`/api/admin/export.csv?${activeQuery}`;
  }catch(error){if(current!==generation)return;errorBox.textContent=error.message;errorBox.hidden=false;document.querySelector('#updated').textContent='Dados não atualizados';}
}
filters.addEventListener('submit',event=>{event.preventDefault();activeQuery=new URLSearchParams(new FormData(filters)).toString();page=1;load();});
document.querySelector('#clear').addEventListener('click',()=>{filters.reset();activeQuery='';page=1;load();});
document.querySelector('#refresh').addEventListener('click',()=>load());
document.querySelector('#page-prev').addEventListener('click',()=>{if(page>1){page--;load(false);}});
document.querySelector('#page-next').addEventListener('click',()=>{if(page<pageCount){page++;load(false);}});
load();
