/* Session-only, bounded charts and lazy anonymous person histories. */
let personDetailCache=new Map();
let detailRequest=0;
const examTypes=['LOOKING_LEFT','LOOKING_RIGHT','LOOKING_DOWN','LOOKING_UP','TURNED_BACK','HAND_RAISED','STANDING','READING','WRITING'];
window.NazarPerf={liveRenders:0,liveRenderMs:0,personDomUpdates:0};
function setHtmlChanged(node,html){if(node.innerHTML!==html)node.innerHTML=html}
function renderLivePeople(state){
  const started=performance.now(),list=$('#people-list'),tracks=state.tracks||[];
  for(const node of [...list.querySelectorAll('[data-live-track]')])if(!tracks.some(t=>String(t.track_id)===node.dataset.liveTrack))node.remove();
  if(!tracks.length){setHtmlChanged(list,`<div class="empty-state">${escapeHtml(t('live.noPeople'))}</div>`);return}
  list.querySelector('.empty-state')?.remove();
  for(const person of tracks){
    let node=list.querySelector(`[data-live-track="${Number(person.track_id)}"]`);
    if(!node){node=document.createElement('div');node.className='person-row';node.dataset.liveTrack=person.track_id;list.appendChild(node)}
    const exam=state.session?.mode==='EXAM',observations=state.exam_observations?.[person.track_id]||{count:0,counts:{},recent:[]};
    const signature=JSON.stringify([getLanguage(),person.role,person.attributes.map(a=>[a.name,a.source]),exam,exam?observations:null]);
    if(node.dataset.signature===signature)continue;
    node.dataset.signature=signature;window.NazarPerf.personDomUpdates++;
    const role=person.role||'UNKNOWN',roles={en:{STUDENT:'Student',TEACHER:'Teacher',UNKNOWN:'Unknown'},ru:{STUDENT:'Ученик',TEACHER:'Учитель',UNKNOWN:'Неизвестно'},kk:{STUDENT:'Оқушы',TEACHER:'Мұғалім',UNKNOWN:'Белгісіз'}}[getLanguage()]||{};
    const examContent=role==='TEACHER'?`<div class="exam-observations"><small>${escapeHtml(t('person.teacherExcluded'))}</small></div>`:role==='UNKNOWN'?`<div class="exam-observations"><h4>${escapeHtml(t('person.unknownExam'))} · ${observations.count}</h4><small>${escapeHtml(t('person.unknownNote'))}</small></div>`:`<div class="exam-observations"><h4>${escapeHtml(t('person.exam'))} · ${observations.count}</h4><div class="exam-counts">${examTypes.map(name=>`<span>${escapeHtml(label(name))}<b>${observations.counts[name]||0}</b></span>`).join('')}</div>${observations.recent.slice(-5).map(e=>`<div class="exam-entry"><time>${relativeTime(e.session_offset_s)}</time> ${escapeHtml(label(e.event_type))}</div>`).join('')}<small>${escapeHtml(t('person.recentNote'))}</small></div>`;
    node.innerHTML=`<span class="avatar">#${person.track_id}</span><div class="live-person-content"><strong>${escapeHtml(role==='UNKNOWN'?(getLanguage()==='ru'?'Человек':getLanguage()==='kk'?'Адам':'Person')+' #'+person.track_id:(roles[role]||role)+' #'+person.track_id)}</strong><label class="role-control">${escapeHtml(t('person.role'))}: <select aria-label="${escapeHtml(t('person.role'))}" data-role-person="${person.track_id}">${Object.entries(roles).map(([value,text])=>`<option value="${value}" ${value===role?'selected':''}>${text}</option>`).join('')}</select></label><div class="chips">${person.attributes.length?person.attributes.map(a=>`<span class="chip ${escapeHtml(a.source)}">${escapeHtml(label(a.name))}</span>`).join(''):`<span class="chip geometry">${escapeHtml(t('live.noConfirmedState'))}</span>`}</div>${exam?examContent:''}</div>`;
  }
  window.NazarPerf.liveRenders++;window.NazarPerf.liveRenderMs+=performance.now()-started;
}
document.addEventListener('change',async event=>{const select=event.target.closest('[data-role-person]');if(!select)return;const response=await fetch(nazarUrl(`/api/session/people/${select.dataset.rolePerson}/role`),{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify({role:select.value})});if(!response.ok)select.value='UNKNOWN';});
function relativeTime(value){if(value==null)return '—';const s=Math.max(0,Math.floor(value));return [Math.floor(s/3600),Math.floor(s/60)%60,s%60].map(x=>String(x).padStart(2,'0')).join(':')}
function eventOptions(){return `<option value="">${escapeHtml(t('events.allTypes'))}</option>`+detailData.event_distribution.map(x=>`<option value="${escapeHtml(x.event_type)}">${escapeHtml(label(x.event_type))}</option>`).join('')}
function sessionEventsMarkup(){return `<div class="filter-row"><label>${escapeHtml(t('events.allTypes'))}<select id="detail-event-type">${eventOptions()}</select></label><label>${escapeHtml(t('person.student'))}<select id="detail-event-track"><option value="">${escapeHtml(t('detail.allTracks'))}</option>${detailData.track_ids.map(id=>`<option value="${id}">#${id}</option>`).join('')}</select></label></div><div id="detail-event-list"></div>`}
function activityChart(rows,key,caption,line=false){
  if(!rows.length)return `<p class="empty-state">${escapeHtml(t('detail.noSamples'))}</p>`;
  const w=640,h=180,left=32,bottom=145,max=Math.max(1,...rows.map(r=>r[key]||0));
  const x=i=>left+i*(w-left-12)/Math.max(1,rows.length-1),y=v=>bottom-v/max*115;
  let marks='';
  if(line){
    let run=[];const flush=()=>{if(run.length)marks+=`<polyline points="${run.join(' ')}" fill="none" stroke="var(--accent)" stroke-width="2.5"/>`;run=[]};
    rows.forEach((r,i)=>{if(r[key]==null){flush();return}run.push(`${x(i)},${y(r[key])}`);marks+=`<circle cx="${x(i)}" cy="${y(r[key])}" r="2.5" fill="var(--accent)"><title>${relativeTime(r.offset_s)}: ${r[key]}</title></circle>`});flush();
  } else marks=rows.map((r,i)=>`<rect x="${x(i)}" y="${y(r[key])}" width="${Math.max(2,(w-left)/rows.length-4)}" height="${bottom-y(r[key])}" rx="2" fill="var(--accent)"><title>${relativeTime(r.offset_s)}: ${r[key]}</title></rect>`).join('');
  const indices=[...new Set([0,1,2,3,4,5].map(i=>Math.round(i*(rows.length-1)/5)))];
  return `<svg class="activity-chart" viewBox="0 0 ${w+16} ${h}" role="img" aria-label="${escapeHtml(caption)}"><line x1="${left}" y1="${bottom}" x2="${w}" y2="${bottom}" stroke="currentColor" opacity=".2"/><text x="0" y="30">${max}</text><text x="10" y="145">0</text>${marks}${indices.map(i=>`<text x="${x(i)}" y="170" text-anchor="${i===0?'start':i===rows.length-1?'end':'middle'}">${relativeTime(rows[i].offset_s)}</text>`).join('')}</svg>`;
}
function renderPersonAnalytics(){
  const a=detailData,s=a.session;
  return `<div class="session-summary">${[[t('sessions.duration'),relativeTime(a.duration_s)],[t('sessions.people'),a.people_observed],[t('person.confirmed'),s.event_count],[t('sessions.timelapse'),s.timelapse_available?t('sessions.available'):'—']].map(([k,v])=>`<div><span>${escapeHtml(k)}</span><strong>${escapeHtml(v)}</strong></div>`).join('')}</div><h3>${escapeHtml(t('person.activity'))}</h3><div class="content-grid analytics-grid"><div><h3>${escapeHtml(t('analytics.overTime'))}</h3>${activityChart(a.events_over_time,'count',t('analytics.overTime'))}</div><div><h3>${escapeHtml(t('detail.peopleOverTime'))}</h3>${activityChart(a.people_over_time,'people_count',t('detail.peopleOverTime'),true)}</div></div><h3>${escapeHtml(t('person.title'))}</h3><div class="filter-row"><label>${escapeHtml(t('events.allTypes'))}<select id="people-event-filter">${eventOptions()}</select></label><label>${escapeHtml(t('person.find'))}<input id="people-track-filter" type="search" inputmode="numeric" placeholder="#1"></label></div><div id="session-person-cards"></div><p class="notice">${escapeHtml(t('detail.occurrences'))} ${escapeHtml(t('detail.noDurations'))}</p>`;
}
function renderPersonCards(){
  const type=$('#people-event-filter').value,search=$('#people-track-filter').value.trim().replace(/^#/,'');
  const people=detailData.people.filter(p=>(!type||p.event_counts[type])&&(!search||String(p.track_id).includes(search)));
  $('#session-person-cards').innerHTML=people.length?people.map(p=>`<details class="session-person" data-person-track="${p.track_id}"><summary><span class="avatar">#${p.track_id}</span><span><strong>${escapeHtml(t('person.name',{id:p.track_id}))}</strong><small>${escapeHtml(t('person.span'))}: ${relativeTime(p.first_seen_s)}–${relativeTime(p.last_seen_s)}</small></span><span class="person-count">${p.event_count} ${escapeHtml(t('sessions.events'))}</span></summary><div class="person-body"></div></details>`).join(''):`<p class="empty-state">${escapeHtml(t('person.noMatches'))}</p>`;
}
async function expandPerson(card){
  const sid=openSessionId,tid=Number(card.dataset.personTrack),body=card.querySelector('.person-body');
  if(!card.open)return;
  const filter=$('#people-event-filter')?.value||'',key=`${sid}:${tid}:${filter}`;
  body.innerHTML=`<p>${escapeHtml(t('sessions.loading'))}</p>`;
  try{
    if(!personDetailCache.has(key))personDetailCache.set(key,(async()=>{
      const person=await api(`/api/sessions/${sid}/people/${tid}`);
      if(filter)person.events=await api(`/api/sessions/${sid}/events?page=1&track=${tid}&type=${encodeURIComponent(filter)}`);
      return person;
    })());
    const p=await personDetailCache.get(key);if(sid!==openSessionId||!card.isConnected)return;
    const exam=detailData.session.mode==='EXAM';
    const distribution=exam?examTypes.map(event_type=>({event_type,count:p.event_counts[event_type]||0})):Object.entries(p.event_counts).map(([event_type,count])=>({event_type,count}));
    body.innerHTML=`<div class="person-facts">${[[t('person.first'),relativeTime(p.first_seen_s)],[t('person.last'),relativeTime(p.last_seen_s)],[t('person.span'),relativeTime(p.observed_span_s)],[t('person.confirmed'),p.event_count]].map(([k,v])=>`<span>${escapeHtml(k)}<strong>${escapeHtml(v)}</strong></span>`).join('')}</div>${p.first_seen_s==null?`<p class="subheading">${escapeHtml(t('person.noBounds'))}</p>`:''}<h3>${escapeHtml(t(exam?'person.exam':'analytics.distribution'))}</h3>${bars(distribution)}<h3>${escapeHtml(t('sessions.eventTimeline'))}</h3><div class="person-timeline">${eventRows(p.events.items)}</div><div class="person-pagination">${pageButtons(p.events,tid,filter)}</div>`;
  }catch(error){personDetailCache.delete(key);body.textContent=error.message}
}
function pageButtons(page,track='',type=''){
  return `<span>${page.total} ${escapeHtml(t('sessions.events'))}</span> `+(page.offset?`<button class="row-button" data-event-page="${Math.max(0,page.offset-page.limit)}" data-track="${track}" data-type="${escapeHtml(type)}">${escapeHtml(t('person.previous'))}</button>`:'')+(page.next_offset!=null?`<button class="row-button" data-event-page="${page.next_offset}" data-track="${track}" data-type="${escapeHtml(type)}">${escapeHtml(t('person.next'))}</button>`:'');
}
async function renderDetailEvents(offset=0){
  const target=$('#detail-event-list');if(!target)return;
  const sid=openSessionId,requestId=++detailRequest,type=$('#detail-event-type').value,track=$('#detail-event-track').value;
  try{const page=await api(`/api/sessions/${sid}/events?page=1&offset=${offset}&track=${track}&type=${encodeURIComponent(type)}`);
    if(requestId!==detailRequest||sid!==openSessionId||!target.isConnected)return;
    target.innerHTML=eventRows(page.items)+pageButtons(page);
  }catch(error){if(target.isConnected)target.textContent=error.message}
}
document.addEventListener('toggle',event=>{if(event.target.matches('details[data-person-track]'))expandPerson(event.target)},true);
document.addEventListener('change',event=>{if(event.target.id==='people-event-filter')renderPersonCards()});
let peopleSearchTimer;
document.addEventListener('input',event=>{if(event.target.id==='people-track-filter'){clearTimeout(peopleSearchTimer);peopleSearchTimer=setTimeout(()=>{if($('#people-track-filter'))renderPersonCards()},150)}});
document.addEventListener('click',async event=>{
  const button=event.target.closest('[data-event-page]');if(!button)return;
  const card=button.closest('[data-person-track]');
  if(!card){renderDetailEvents(Number(button.dataset.eventPage));return}
  const sid=openSessionId;button.disabled=true;
  try{const page=await api(`/api/sessions/${sid}/events?page=1&offset=${button.dataset.eventPage}&track=${button.dataset.track}&type=${encodeURIComponent(button.dataset.type)}`);
    if(sid!==openSessionId||!card.isConnected)return;
    card.querySelector('.person-timeline').innerHTML=eventRows(page.items);card.querySelector('.person-pagination').innerHTML=pageButtons(page,button.dataset.track,button.dataset.type);
  }catch(error){toast(error.message,true);button.disabled=false}
});
