const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => [...document.querySelectorAll(selector)];
let liveState = null;
let activePage = 'live';
let toastTimer = null;
let openSessionId = null;
let detailData = null;
let detailTab = 'overview';
let selectedMode = null;
const {t, stateLabel, locale, getLanguage, setLanguage, applyI18n, getTheme, setTheme} = window.NazarI18n;

const escapeHtml = (value) => String(value ?? '').replace(/[&<>"']/g, (c) => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const label = (value) => stateLabel(value);
const modeLabel = (value) => value === 'LESSON' ? t('analytics.lesson') : value === 'EXAM' ? t('analytics.exam') : label(value);
const fmtDate = (value) => value ? new Intl.DateTimeFormat(locale(), {dateStyle:'medium',timeStyle:'short'}).format(new Date(value)) : '—';
const fmtTime = (value) => value ? new Intl.DateTimeFormat(locale(), {hour:'2-digit',minute:'2-digit',second:'2-digit'}).format(new Date(value)) : '—';
const duration = (start,end) => {
  if (!start) return '—';
  const seconds=Math.max(0,Math.floor((new Date(end || Date.now())-new Date(start))/1000));
  return `${String(Math.floor(seconds/3600)).padStart(2,'0')}:${String(Math.floor(seconds%3600/60)).padStart(2,'0')}:${String(seconds%60).padStart(2,'0')}`;
};
const durationSeconds = (value) => {
  if (value == null || !Number.isFinite(Number(value))) return '—';
  const seconds=Math.max(0,Math.round(Number(value)));
  return `${String(Math.floor(seconds/3600)).padStart(2,'0')}:${String(Math.floor(seconds%3600/60)).padStart(2,'0')}:${String(seconds%60).padStart(2,'0')}`;
};

async function api(path,options={}) {
  const response=await fetch(nazarUrl(path),{headers:{'Content-Type':'application/json'},...options});
  const data=await response.json();
  if (!response.ok) throw new Error(data.error || t('common.requestFailed',{status:response.status}));
  return data;
}

function toast(message,error=false) {
  const node=$('#toast');node.textContent=message;node.style.background=error?'#ad5250':'#153b4a';node.hidden=false;
  clearTimeout(toastTimer);toastTimer=setTimeout(()=>node.hidden=true,3500);
}

function showPage(page) {
  activePage=page;
  $$('.page').forEach(node=>node.classList.toggle('active',node.id===`page-${page}`));
  $$('.nav-item').forEach(node=>node.classList.toggle('active',node.dataset.page===(page==='session-detail'?'sessions':page)));
  location.hash=page;
  if (page==='sessions') loadSessions();
  if (page==='events') loadEvents();
  if (page==='system') loadSystem();
  if (page==='settings') loadSettings();
}

function renderLive(state) {
  liveState=state;
  setSourceLock(!!state.session);
  const camera=state.camera || {};
  $('#metric-people').textContent=state.visible_people ?? 0;
  $('#metric-fps').textContent=state.ai?.fps ?? '—';
  $('#metric-mode').textContent=state.session ? modeLabel(state.session.mode) : t('live.inactive');
  $('#metric-timer').textContent=state.session ? duration(state.session.started_at) : t('live.startLessonExam');
  $('#session-context').textContent=state.session ? [state.session.subject,state.session.class_name,state.session.teacher].filter(Boolean).join(' · ') : '';
  $('#metric-recording').textContent=state.timelapse?.recording ? t('live.onAir') : t('live.off');
  $('#metric-frames').textContent=state.timelapse?.recording ? t('live.framesCaptured',{count:state.timelapse.frames}) : state.timelapse?.error || t('live.timelapseInactive');
  $('#start-button').hidden=!!state.session;$('#stop-button').hidden=!state.session;
  $('#camera-detail').textContent=camera.source==='VIDEO' ? `${camera.filename || t('settings.video')} · ${Number(camera.position_s||0).toFixed(1)} / ${camera.duration_s == null ? '—' : Number(camera.duration_s).toFixed(1)} s` : camera.connected ? `${camera.resolution?.join(' × ') || t('common.resolutionUnknown')} · ${t('common.cameraFps',{value:camera.actual_fps ?? '—'})}` : camera.error || t('common.cameraDisconnected');
  const pill=$('#camera-pill');pill.textContent=camera.ended?t('status.videoEnded'):camera.connected?t('status.connected'):t('status.disconnected');pill.className=`pill ${camera.connected?'good':camera.ended?'muted':'bad'}`;
  const dot=$('#top-status-dot');dot.classList.toggle('online',!!camera.connected);
  $('#top-status-text').textContent=camera.source==='VIDEO'?(camera.ended?t('status.videoEnded'):camera.connected?t('status.videoPlaying'):t('status.videoUnavailable')):(camera.connected?t('status.cameraConnected'):t('status.cameraOffline'));
  $('#people-counter').textContent=state.visible_people ?? 0;
  renderLivePeople(state);
  renderActionsAB(state);
  setHtmlChanged($('#recent-events'),state.recent_events?.length ? state.recent_events.slice(0,5).map(e=>`<div class="event-row"><span class="event-dot"></span><div><strong>${escapeHtml(label(e.event_type))}${e.review_priority&&e.review_priority!=='NORMAL'?` · ${escapeHtml(e.review_priority)}`:''}</strong><small>${escapeHtml(t('events.personId',{id:e.track_id}))}${e.reason?` · ${escapeHtml(e.reason)}`:''}</small></div><span class="event-time">${e.source_offset_s == null ? fmtTime(e.occurred_at) : t('events.inVideo',{time:Number(e.source_offset_s).toFixed(2)})}</span></div>`).join('') : `<div class="empty-state">${escapeHtml(t('live.noEvents'))}</div>`);
  setHtmlChanged($('#system-glance'),`<div class="status-row"><span>${escapeHtml(t('system.inputSource'))}</span><strong>${camera.ended?t('status.videoEnded'):camera.connected?t('status.connected'):t('status.unavailable')}</strong></div><div class="status-row"><span>${escapeHtml(t('system.aiPipeline'))}</span><strong>${state.ai?.error ? escapeHtml(state.ai.error) : camera.ended?t('status.videoFinished'):state.ai?.last_frame_at ? t('status.processing'):t('status.waiting')}</strong></div><div class="status-row"><span>${escapeHtml(t('live.peopleInView'))}</span><strong>${state.visible_people ?? 0}</strong></div><div class="status-row"><span>${escapeHtml(t('sessions.timelapse'))}</span><strong>${state.timelapse?.recording?t('common.timelapseRecording'):t('system.inactive')}</strong></div>`);
}

function renderActionsAB(state){
  const panel=$('#actions-ab-panel'), enabled=!!state.actions_ab?.enabled;
  panel.hidden=!enabled;
  if(!enabled)return;
  const s=state.actions_ab?.summary||{};
  $('#actions-ab-metrics').innerHTML=`<span>${escapeHtml(s.rows||0)} rows · ${escapeHtml(s.unique_tracks||0)} tracks</span><strong>${escapeHtml(s.disagreement||0)} disagreements</strong>`;
  const tracks=(state.tracks||[]).filter(t=>t.actions_ab);
  $('#actions-ab-list').innerHTML=tracks.length?tracks.map(t=>{const a=t.actions_ab,yes=(m,n)=>Number(a[m][n])>=Number(a[m].thresholds[n])?'YES':'NO';return `<div class="ab-row"><strong>#${t.track_id}</strong><span>READING<br>V1 ${Number(a.v1.READING).toFixed(2)} ${yes('v1','READING')} → V2 ${Number(a.v2.READING).toFixed(2)} ${yes('v2','READING')}<br>Δ ${Number(a.delta.READING)>=0?'+':''}${Number(a.delta.READING).toFixed(2)}</span><span>WRITING<br>V1 ${Number(a.v1.WRITING).toFixed(2)} ${yes('v1','WRITING')} → V2 ${Number(a.v2.WRITING).toFixed(2)} ${yes('v2','WRITING')}<br>Δ ${Number(a.delta.WRITING)>=0?'+':''}${Number(a.delta.WRITING).toFixed(2)}</span></div>`}).join(''):`<div class="empty-state">Waiting for shadow model output.</div>`;
}

async function loadSessions() {
  try {
    const rows=await api('/api/sessions');
    $('#sessions-counter').textContent=rows.length;
    $('#sessions-table').innerHTML=rows.length ? rows.map(s=>`<tr><td><span class="pill ${s.mode==='EXAM'?'bad':'good'}">${escapeHtml(modeLabel(s.mode))}</span> <strong>#${s.id}</strong><small> · ${escapeHtml(s.source_type)}</small></td><td>${fmtDate(s.started_at)}</td><td>${escapeHtml(s.subject||'—')}</td><td>${escapeHtml(s.class_name||'—')}</td><td>${escapeHtml(s.teacher||'—')}</td><td>${duration(s.started_at,s.ended_at)}</td><td>${s.track_count}</td><td>${s.event_count}</td><td>${s.timelapse_available?t('sessions.available'):'—'}</td><td><button class="row-button" data-session-id="${s.id}">${escapeHtml(t('sessions.open'))}</button></td></tr>`).join('') : `<tr><td colspan="10" class="empty-cell">${escapeHtml(t('sessions.noData'))}</td></tr>`;
    const selector=$('#event-session');const old=selector.value;
    selector.innerHTML=`<option value="">${escapeHtml(t('events.allSessions'))}</option>`+rows.map(s=>`<option value="${s.id}">#${s.id} · ${escapeHtml(modeLabel(s.mode))}</option>`).join('');selector.value=old;
  } catch(error) { toast(error.message,true); }
}

async function openSession(id) {
  try {
    const requestId=++detailRequest;
    const data=await api(`/api/sessions/${id}/analytics`);
    if(requestId!==detailRequest)return;
    detailData=data;personDetailCache.clear();
    openSessionId=id;detailTab='overview';showPage('session-detail');renderDetail();
  } catch(error) {toast(error.message,true)}
}

function bars(rows) {
  const max=Math.max(1,...rows.map(x=>x.count));
  return rows.length ? rows.map(x=>`<div class="bar-row"><span class="bar-label">${escapeHtml(label(x.event_type))}</span><div class="bar-track"><div class="bar-fill" style="width:${100*x.count/max}%"></div></div><strong>${x.count}</strong></div>`).join('') : `<p class="empty-state">${escapeHtml(t('analytics.noEvents'))}</p>`;
}
function renderDetail() {
  if(!detailData)return;
  const a=detailData,s=a.session;
  ensurePhase2Tabs();
  $('[data-detail-tab="evidence"]').hidden=s.mode!=='EXAM';
  $('#detail-title').textContent=s.subject||`${t('events.session')} #${s.id}`;
  $('#detail-subtitle').textContent=[s.class_name,modeLabel(s.mode),s.teacher ? `${t('metadata.teacher')}: ${s.teacher}` : null,fmtDate(s.started_at),duration(s.started_at,s.ended_at),`${s.source_type} ${s.source_name||''}`].filter(Boolean).join(' · ');
  $$('[data-detail-tab]').forEach(x=>{x.classList.toggle('active',x.dataset.detailTab===detailTab);x.setAttribute('aria-selected',x.dataset.detailTab===detailTab?'true':'false')});
  const panel=$('#session-detail');
  if(detailTab==='overview') {
    panel.innerHTML=`<div class="detail-facts">${[[t('events.session'),`#${s.id}`],[t('events.allModes'),modeLabel(s.mode)],[t('sessions.date'),fmtDate(s.started_at)],[t('sessions.duration'),duration(s.started_at,s.ended_at)],[t('metadata.teacher'),s.teacher],[t('metadata.className'),s.class_name],[t('metadata.subject'),s.subject],[t('metadata.notes'),s.notes],[t('sessions.people'),s.track_count],[t('sessions.events'),s.event_count],[t('sessions.timelapse'),s.timelapse_available?t('sessions.available'):t('sessions.noTimelapse')]].filter(([,value])=>value!==null&&value!==undefined&&value!=='').map(([key,value])=>`<div class="status-row"><span>${escapeHtml(key)}</span><strong>${escapeHtml(value)}</strong></div>`).join('')}</div><div class="detail-actions"><button class="button primary" data-detail-tab="evidence">${t('detail.reviewEvidence')}</button><button class="button ghost" data-detail-tab="people">${t('detail.people')}</button><button class="button ghost" id="export-session">${t('detail.export')}</button><button class="button subtle danger" id="delete-session">${t('detail.delete')}</button></div>`;
  } else if(detailTab==='people') {
    panel.innerHTML=`<h2>${t('detail.people')}</h2><div id="session-people-cards"></div>`;
    $('#session-people-cards').innerHTML=a.people.length?a.people.map(p=>{const counts=p.event_counts||{},review=counts.REVIEW||0,high=counts.HIGH_REVIEW||0;return `<article class="event-row"><div><strong>${escapeHtml((p.role||'UNKNOWN')+' #'+p.track_id)}</strong><small>${t('detail.first')} ${relativeTime(p.first_seen_s)} · ${t('detail.last')} ${relativeTime(p.last_seen_s)} · ${t('detail.observed')} ${relativeTime(p.observed_span_s)} · ${t('detail.events')} ${p.event_count}</small></div><span>${t('detail.review')} ${review} · ${t('detail.highReview')} ${high}<br><button class="row-button" data-person-timeline="${p.track_id}">${t('detail.timeline')}</button><button class="row-button" data-person-evidence="${p.track_id}">${t('detail.evidence')}</button></span></article>`}).join(''):`<p class="empty-state">${t('detail.noPeople')}</p>`;
  } else if(detailTab==='events') {
    panel.innerHTML=sessionEventsMarkup();renderDetailEvents();
  } else if(detailTab==='analytics') {
    panel.innerHTML=renderPersonAnalytics();renderPersonCards();
  } else if(detailTab==='evidence') {
    panel.innerHTML=`<h2>${t('detail.videoEvidence')}</h2><p>${t('detail.reviewMoments')}</p><div class="filter-row"><label>${t('events.person')}<input id="evidence-person" type="number" min="1"></label><label>${t('person.role')}<select id="evidence-role"><option value="">${t('events.allTypes')}</option><option value="STUDENT" selected>${t('person.student')}</option><option value="TEACHER">${t('metadata.teacher')}</option><option value="UNKNOWN">${t('person.unknownExam')}</option></select></label><label>${t('detail.event')}<select id="evidence-type"><option value="">${t('events.allTypes')}</option>${examTypes.map(n=>`<option value="${n}">${escapeHtml(label(n))}</option>`).join('')}</select></label><label>${t('detail.review')}<select id="evidence-priority"><option value="">${t('events.allTypes')}</option><option selected>REVIEW</option><option>HIGH_REVIEW</option></select></label></div><div id="evidence-player"></div><div id="evidence-items"></div>`;
    loadEvidence();
  } else if(detailTab==='recording') {
    const m=s.source_metadata, meta=m?[[t('detail.source'),s.source_type==='VIDEO'?t('detail.originalSource'):t('settings.camera')],[t('detail.filename'),m.filename],[t('detail.duration'),durationSeconds(m.duration_s)],[t('detail.resolution'),m.resolution?.join('×')],[t('detail.fps'),m.fps],[t('detail.status'),t('detail.ready')]]:[];
    panel.innerHTML=`<div class="detail-facts"><h2>${t('detail.originalSource')}</h2>${meta.map(([key,value])=>`<div class="status-row"><span>${escapeHtml(key)}</span><strong>${escapeHtml(String(value))}</strong></div>`).join('')}</div>${s.timelapse_available ? `<h2>${t('detail.timelapse')}</h2><video id="detail-video" controls preload="metadata" src="${nazarUrl(`/api/timelapse/${s.id}`)}"></video><p class="subheading">${escapeHtml(t('person.seekNote'))}</p>` : `<p class="empty-state">${escapeHtml(t('detail.noRecording'))}</p>`}${sessionEventsMarkup()}`;
    renderDetailEvents();
  }
}
function eventRows(events) {
  return events.length ? `<div class="event-list">${events.map(e=>`<div class="event-row"><span class="event-dot"></span><div><strong>${escapeHtml(label(e.event_type))}${e.review_priority&&e.review_priority!=='NORMAL'?` · ${escapeHtml(e.review_priority)}`:''}</strong><small>${escapeHtml(t('person.name',{id:e.track_id}))}${e.duration_s==null?'':` · ${Number(e.duration_s).toFixed(1)} s`}${e.reason?` · ${escapeHtml(e.reason)}`:''}</small></div><time class="event-time">${relativeTime(e.offset_s??e.session_offset_s)}</time></div>`).join('')}</div>` : `<p class="empty-state">${escapeHtml(t('sessions.noSessionEvents'))}</p>`;
}
function renderMetadataMode(){
  if(!selectedMode)return;
  const exam=selectedMode==='EXAM';
  $('#metadata-mode-heading').textContent=t('metadata.forMode',{mode:modeLabel(selectedMode)});
  $('#metadata-teacher-label').textContent=t(exam?'metadata.proctor':'metadata.teacher');
  $('#metadata-class-label').textContent=t(exam?'metadata.classGroup':'metadata.className');
  $('#metadata-subject-label').textContent=t(exam?'metadata.subjectExam':'metadata.subject');
  $('#session-form button[type="submit"]').textContent=t(exam?'metadata.startExam':'metadata.startLesson');
}

async function loadEvents() {
  try {
    const query=new URLSearchParams();
    [['session','#event-session'],['mode','#event-mode'],['type','#event-type'],['date','#event-date']].forEach(([key,id])=>{if ($(id).value) query.set(key,$(id).value)});
    const rows=await api(`/api/events?${query}`);
    $('#events-table').innerHTML=rows.length ? rows.map(e=>`<tr><td>${e.source_offset_s == null ? fmtDate(e.occurred_at) : escapeHtml(t('events.inVideo',{time:Number(e.source_offset_s).toFixed(2)}))}</td><td>#${e.session_id} · ${escapeHtml(modeLabel(e.mode))}<small>${escapeHtml([e.subject,e.class_name].filter(Boolean).join(' · '))}</small></td><td>#${e.track_id}</td><td><span class="chip ${e.event_type.startsWith('LOOKING')?'head_model':e.event_type==='READING'||e.event_type==='WRITING'?'action_model':'geometry'}">${escapeHtml(label(e.event_type))}</span></td><td>${e.confidence==null?'—':Number(e.confidence).toFixed(2)}</td></tr>`).join('') : `<tr><td colspan="5" class="empty-cell">${escapeHtml(t('events.noData'))}</td></tr>`;
    const selected=$('#event-type').value;
    const allEvents=await api('/api/events?limit=2000');
    $('#event-type').innerHTML=`<option value="">${escapeHtml(t('events.allTypes'))}</option>`+[...new Set(allEvents.map(e=>e.event_type))].sort().map(type=>`<option value="${escapeHtml(type)}">${escapeHtml(label(type))}</option>`).join('');
    $('#event-type').value=selected;
  } catch(error) {toast(error.message,true)}
}


function statusRows(rows) { return rows.map(([key,value])=>`<div class="status-row"><span>${escapeHtml(key)}</span><strong>${escapeHtml(value ?? '—')}</strong></div>`).join(''); }
async function loadSystem() {
  if(loadSystem.busy)return;loadSystem.busy=true;
  try {
    const data=await api('/api/status');const cam=data.camera,pipe=data.pipeline,hardware=data.hardware,models=pipe.models;
    const cards=[
      [t('system.inputSource'),[[t('system.type'),cam.source],[t('system.status'),cam.ended?t('status.videoEnded'):cam.connected?t('status.connected'):t('status.disconnected')],[t('system.file'),cam.filename||'—'],[t('system.videoPosition'),cam.position_s == null ? '—' : `${cam.position_s} s`],[t('system.resolution'),cam.resolution?.join(' × ')||'—'],[t('system.requestedFps'),cam.requested_fps],[t('system.actualFps'),cam.actual_fps],[t('system.error'),cam.error||'—']]],
      [t('system.aiPipeline'),[[t('system.aiFps'),data.ai.fps],[t('system.poseFps'),pipe.model_fps.pose],[t('system.actionsFps'),pipe.model_fps.actions],[t('system.headFps'),pipe.model_fps.head],[t('system.poseLatency'),`${pipe.latency_ms.pose_ms} ms`],[t('system.actionsLatency'),`${pipe.latency_ms.actions_ms} ms`],[t('system.headLatency'),`${pipe.latency_ms.head_ms} ms`],[t('system.totalLatency'),`${pipe.latency_ms.total_ms} ms`],[t('system.poseCalls'),pipe.pose_calls]]],
      [t('system.models'),[['Pose',`${models.pose.loaded?t('system.loaded'):t('system.unavailable')} · ${models.pose.name} · ${models.pose.device}`],['Actions',`${models.actions.loaded?t('system.loaded'):t('system.unavailable')} · ${models.actions.name} · ${models.actions.device}`],['Head',`${models.head.loaded?t('system.loaded'):t('system.unavailable')} · ${models.head.name} · ${models.head.device}`],[t('system.thresholds'),t('system.thresholds')]]],
      [t('system.hardware'),[[t('system.cpu'),`${hardware.cpu_percent}%`],[t('system.ram'),`${hardware.ram_percent}%`],[t('system.processRam'),`${hardware.process_ram_mb} MB`],[t('system.cuda'),hardware.cuda_available?'Available':t('system.unavailable')],[t('system.gpu'),hardware.gpu?.name||'—'],[t('system.gpuUtilization'),hardware.gpu?.utilization_percent == null ? '—' : `${hardware.gpu.utilization_percent}%`],[t('system.vramInUse'),hardware.gpu?.vram_system_used_mb == null ? '—' : `${hardware.gpu.vram_system_used_mb} MB`],[t('system.vramTotal'),hardware.gpu?`${hardware.gpu.vram_total_mb} MB`:'—']]],
      [t('system.trackingRecording'),[[t('system.visibleTracks'),pipe.visible_tracks],[t('system.activeTracks'),pipe.active_tracks],[t('sessions.timelapse'),data.timelapse.recording?t('common.timelapseRecording'):t('system.inactive')],[t('system.framesRecorded'),data.timelapse.frames],[t('system.output'),data.timelapse.output||'—']]]
    ];
    setHtmlChanged($('#system-panels'),cards.map(([title,rows])=>`<section class="card"><div class="card-heading"><h2>${title}</h2></div>${statusRows(rows)}</section>`).join(''));
    $('#metric-latency').textContent=pipe.frames?t('common.perFrame',{value:pipe.latency_ms.total_ms}):t('live.waitingFrame');
  } catch(error){toast(error.message,true)} finally{loadSystem.busy=false}
}

async function loadSettings() {
  try {
    const data=await api('/api/settings');
    ensureSourceManager();
    $$('[data-setting]').forEach(node=>{const value=data.values[node.dataset.setting];if(node.type==='checkbox')node.checked=!!value;else node.value=value});
    ['boxes','skeleton','attributes'].forEach(name=>{$(`#overlay-${name}`).checked=!!data.values[`${name==='boxes'?'boxes':name==='skeleton'?'skeleton':'attributes'}_overlay`]});
    setSourcePanel(data.values.input_source); await loadCameras(data.values.camera_device_id);
  } catch(error){toast(error.message,true)}
}
function ensurePhase2Tabs(){
  const nav=$('#page-session-detail .detail-tabs');if(!nav)return;
  if(nav.dataset.phase2)return;nav.dataset.phase2='1';
  nav.insertAdjacentHTML('beforeend','<button data-detail-tab="people" role="tab">People</button><button data-detail-tab="recording" role="tab">Recording</button>');
}

function ensureSourceManager(){
  if($('#source-manager'))return;
  const grid=$('#page-settings .settings-grid'); if(!grid)return;
  const section=document.createElement('section');section.id='source-manager';section.className='card setting-section source-manager';
  section.innerHTML=`<h2 data-i18n="settings.sourceManager">Input source manager</h2><div class="source-switch"><label><input type="radio" name="source-choice" value="CAMERA"> <span data-i18n="settings.camera">Camera</span></label><label><input type="radio" name="source-choice" value="VIDEO"> <span data-i18n="settings.video">Video file</span></label></div><div id="source-camera-panel"><div class="field-grid"><label><span data-i18n="settings.cameraDevice">Camera</span><select id="camera-selector"><option value="" data-i18n="settings.noCameras">No cameras discovered</option></select></label></div><div class="source-actions"><button type="button" class="button subtle" id="camera-rescan" data-i18n="settings.rescanCameras">Rescan cameras</button><button type="button" class="button ghost" id="camera-preview-button" data-i18n="settings.preview">Preview</button></div><img id="camera-preview" class="camera-preview" hidden alt="Camera preview"></div><div id="source-video-panel" hidden><label><span data-i18n="settings.chooseVideo">Choose video file</span><input id="video-file" type="file" accept="video/*"></label><div id="video-dropzone" class="dropzone" data-i18n="settings.dropVideo">Drop a video here</div><div id="video-info" class="source-info" hidden></div><video id="video-preview" class="file-preview" controls muted hidden></video></div>`;
  grid.prepend(section);applyI18n();
  $$('input[name="source-choice"]').forEach(node=>node.addEventListener('change',()=>setSourcePanel(node.value)));
  $('#camera-selector').addEventListener('change',async event=>{try{await api('/api/camera/select',{method:'POST',body:JSON.stringify({device_id:event.target.value})});toast(t('common.saved'));await loadSettings()}catch(error){toast(error.message,true)}});
  $('#camera-rescan').addEventListener('click',()=>loadCameras($('#camera-selector').value,true));
  $('#camera-preview-button').addEventListener('click',()=>{const id=$('#camera-selector').value;if(id)$('#camera-preview').src=NAZAR_API+`/api/camera/preview?device_id=${encodeURIComponent(id)}&t=${Date.now()}`;else toast(t('settings.noCameras'),true)});
  $('#video-file').addEventListener('change',event=>{const file=event.target.files[0];if(file)uploadVideo(file)});
  const drop=$('#video-dropzone');['dragenter','dragover'].forEach(name=>drop.addEventListener(name,event=>{event.preventDefault();drop.classList.add('dragging')}));['dragleave','drop'].forEach(name=>drop.addEventListener(name,event=>{event.preventDefault();drop.classList.remove('dragging')}));drop.addEventListener('drop',event=>{const file=event.dataTransfer.files[0];if(file)uploadVideo(file)});
}
function setSourcePanel(source){
  const value=source==='VIDEO'?'VIDEO':'CAMERA';$$('input[name="source-choice"]').forEach(node=>node.checked=node.value===value);
  $('#source-camera-panel').hidden=value!=='CAMERA';$('#source-video-panel').hidden=value!=='VIDEO';
  const legacy=$('[data-setting="input_source"]');if(legacy)legacy.value=value;
}
async function loadCameras(selected='',rescan=false){
  try{const rows=await api(rescan?'/api/cameras/rescan':'/api/cameras',{method:rescan?'POST':'GET'}),selector=$('#camera-selector');selector.innerHTML=rows.length?rows.map(camera=>`<option value="${escapeHtml(camera.device_id)}">${escapeHtml(camera.name)} · ${escapeHtml(camera.resolution?.join(' × ')||'—')}</option>`).join(''):`<option value="">${escapeHtml(t('settings.noCameras'))}</option>`;selector.value=rows.some(row=>row.device_id===selected)?selected:(rows[0]?.device_id||'');}catch(error){toast(error.message,true)}}
function uploadVideo(file){
  const info=$('#video-info');info.hidden=false;info.textContent=`${t('settings.uploading')} ${file.name}`;
  const form=new FormData();form.append('video',file);
  const xhr=new XMLHttpRequest();xhr.open('POST',nazarUrl('/api/videos/import'));xhr.upload.onprogress=event=>{if(event.lengthComputable)info.textContent=`${t('settings.uploading')} ${Math.round(event.loaded/event.total*100)}%`};
  xhr.onload=()=>{let data={};try{data=JSON.parse(xhr.responseText)}catch(error){}if(xhr.status<200||xhr.status>=300){info.textContent=data.error||t('settings.videoImportFailed');toast(info.textContent,true);return}const m=data;info.innerHTML=`<strong>${escapeHtml(t('settings.videoReady'))}</strong> · ${escapeHtml(m.filename)}<br>${escapeHtml(t('settings.duration'))}: ${m.duration_s==null?'—':m.duration_s+' s'} · ${escapeHtml(t('settings.resolution'))}: ${m.resolution.join(' × ')} · ${escapeHtml(t('settings.frameRate'))}: ${m.fps||'—'} · ${escapeHtml(t('settings.fileSize'))}: ${(m.size_bytes/1048576).toFixed(1)} MB`;const preview=$('#video-preview');preview.src=nazarUrl(data.url);preview.hidden=false;setSourcePanel('VIDEO');toast(t('settings.videoReady'));loadSettings()};xhr.onerror=()=>{info.textContent=t('settings.videoImportFailed');toast(info.textContent,true)};xhr.send(form);
}
function setSourceLock(locked){['#camera-selector','#camera-rescan','#camera-preview-button','#video-file'].forEach(selector=>{const node=$(selector);if(node)node.disabled=locked});$$('input[name="source-choice"]').forEach(node=>node.disabled=locked)}

async function saveSettings() {
  const changes={};
  $$('[data-setting]').forEach(node=>{const name=node.dataset.setting;changes[name]=node.type==='checkbox'?node.checked:node.type==='number'?node.step==='1'||!node.step?Number.parseInt(node.value,10):Number(node.value):node.value});
  try {await api('/api/settings',{method:'POST',body:JSON.stringify(changes)});const note=$('#settings-message');note.textContent=t('common.saved');note.className='notice';note.hidden=false;toast(t('common.saved'))} catch(error){const note=$('#settings-message');note.textContent=error.message;note.className='notice error';note.hidden=false;toast(error.message,true)}
}

async function saveOverlay(name,checked) {
  const key=`${name}_overlay`;
  try {await api('/api/settings',{method:'POST',body:JSON.stringify({[key]:checked})})} catch(error){toast(error.message,true)}
}

function connectLive() {
  const source=new EventSource(nazarUrl('/api/live'));
  source.onmessage=(event)=>{try{renderLive(JSON.parse(event.data))}catch(error){console.error(error)}};
  source.onerror=()=>{$('#top-status-text').textContent=t('status.connecting')};
}

document.addEventListener('click',async(event)=>{
  const nav=event.target.closest('[data-page],[data-go]');if(nav){showPage(nav.dataset.page||nav.dataset.go);return}
  const refresh=event.target.closest('[data-refresh]');if(refresh){({sessions:loadSessions,events:loadEvents,system:loadSystem}[refresh.dataset.refresh])();return}
  const session=event.target.closest('[data-session-id]');if(session){openSession(session.dataset.sessionId);return}
  if(event.target.id==='close-detail'){openSessionId=null;detailData=null;showPage('sessions');return}
  const tab=event.target.closest('[data-detail-tab]');if(tab){detailTab=tab.dataset.detailTab;renderDetail();return}
  const timeline=event.target.closest('[data-person-timeline]');if(timeline){detailTab='analytics';renderDetail();setTimeout(()=>{const card=document.querySelector(`[data-person-track="${timeline.dataset.personTimeline}"]`);if(card){card.open=true;card.scrollIntoView({block:'center'})}},0);return}
  const personEvidence=event.target.closest('[data-person-evidence]');if(personEvidence){detailTab='evidence';renderDetail();setTimeout(()=>{$('#evidence-person').value=personEvidence.dataset.personEvidence;loadEvidence()},0);return}
  if(event.target.id==='export-session'){const b=event.target;b.disabled=true;b.textContent=t('detail.exporting');try{const res=await fetch(nazarUrl(`/api/sessions/${openSessionId}/export`));if(!res.ok)throw Error(t('detail.exportFailed'));const blob=await res.blob(),url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download=`nazar-session-${openSessionId}.zip`;a.click();URL.revokeObjectURL(url);b.textContent=t('detail.exportReady')}catch(e){b.disabled=false;b.textContent=t('detail.exportFailed');toast(e.message,true)}return}
  if(event.target.id==='delete-session'){if(!confirm(t('detail.deleteConfirm')))return;event.target.disabled=true;try{await api(`/api/sessions/${openSessionId}?confirm=1`,{method:'DELETE'});openSessionId=null;detailData=null;showPage('sessions');loadSessions()}catch(e){event.target.disabled=false;toast(e.message,true)}return}
  if(event.target.closest('#start-button')){$('#session-modal').hidden=false;selectedMode=null;$('#session-form').hidden=true;$$('[data-mode]').forEach(x=>x.classList.remove('selected'));fillRecent();return}
  if(event.target.id==='close-modal'||event.target.id==='session-modal'){$('#session-modal').hidden=true;return}
  const mode=event.target.closest('[data-mode]');if(mode){selectedMode=mode.dataset.mode;$$('[data-mode]').forEach(x=>x.classList.toggle('selected',x===mode));$('#session-form').hidden=false;renderMetadataMode();return}
  if(event.target.closest('#stop-button')){try{await api('/api/session/stop',{method:'POST'});toast(t('common.sessionSaved'));loadSessions()}catch(error){toast(error.message,true)}return}
  if(event.target.id==='save-settings'){saveSettings();return}
  if(event.target.id==='clear-filters'){$$('#page-events select,#page-events input').forEach(node=>node.value='');loadEvents()}
});

function fillRecent() {
  const recent=JSON.parse(localStorage.getItem('nazar-recent-metadata')||'{}');
  for(const [field,listId] of [['teacher','recent-teachers'],['class_name','recent-classes'],['subject','recent-subjects']]) {
    $(`[name="${field}"]`).value=recent[field]?.[0]||'';
    $(`#${listId}`).innerHTML=(recent[field]||[]).map(x=>`<option value="${escapeHtml(x)}"></option>`).join('');
  }
  $('[name="notes"]').value='';
}
$('#session-form').addEventListener('submit',async(event)=>{
  event.preventDefault();if(!selectedMode)return;
  const submit=$('#session-form button[type="submit"]');submit.disabled=true;
  try {
    const metadata=Object.fromEntries(new FormData(event.target).entries());
    await api('/api/session/start',{method:'POST',body:JSON.stringify({mode:selectedMode,...metadata})});
    const recent=JSON.parse(localStorage.getItem('nazar-recent-metadata')||'{}');
    for(const key of ['teacher','class_name','subject']) if(metadata[key].trim())recent[key]=[metadata[key].trim(),...(recent[key]||[]).filter(x=>x!==metadata[key].trim())].slice(0,5);
    localStorage.setItem('nazar-recent-metadata',JSON.stringify(recent));
    $('#session-modal').hidden=true;toast(t('common.sessionStarted',{mode:modeLabel(selectedMode)}));
  } catch(error){toast(error.message,true)} finally{submit.disabled=false}
});
$('#page-session-detail').addEventListener('change',event=>{
  if(event.target.id==='detail-event-type'||event.target.id==='detail-event-track')renderDetailEvents();
});

$$('#page-events select,#page-events input').forEach(node=>node.addEventListener('change',loadEvents));
['boxes','skeleton','attributes'].forEach(name=>$(`#overlay-${name}`).addEventListener('change',(event)=>saveOverlay(name,event.target.checked)));
$('#language-select').addEventListener('change',(event)=>setLanguage(event.target.value));
$('#theme-toggle').addEventListener('click',()=>setTheme(getTheme()==='dark'?'light':'dark'));
document.addEventListener('nazar:languagechange',()=>{
  $('#camera-image').src=nazarUrl('/stream')+'?lang='+encodeURIComponent(getLanguage());
  applyI18n();
  if(liveState) renderLive(liveState);
  if(activePage==='sessions') loadSessions();
  if(openSessionId) renderDetail();
  if(activePage==='events') loadEvents();
  renderMetadataMode();
  if(activePage==='system') loadSystem();
  if(activePage==='settings') loadSettings();
});
window.addEventListener('hashchange',()=>{const page=location.hash.slice(1);if(['live','sessions','events','system','settings'].includes(page)&&page!==activePage)showPage(page)});
setInterval(()=>{if(liveState?.session)$('#metric-timer').textContent=duration(liveState.session.started_at)},1000);
setInterval(()=>{if(activePage==='system')loadSystem()},1000);

$('#camera-image').src=nazarUrl('/stream')+'?lang='+encodeURIComponent(getLanguage());
applyI18n();
setTheme(getTheme());
showPage(['live','sessions','events','system','settings'].includes(location.hash.slice(1))?location.hash.slice(1):'live');
api('/api/state').then(renderLive).catch(error=>toast(error.message,true));
connectLive();loadSessions();loadSystem();

let evidenceRequest=0;
let evidencePage=[];
async function loadEvidence(offset=0){
  const target=$('#evidence-items');if(!target)return;
  const sid=openSessionId,seq=++evidenceRequest;
  const query=new URLSearchParams({person:$('#evidence-person').value,role:$('#evidence-role').value,type:$('#evidence-type').value,priority:$('#evidence-priority').value,offset:String(offset)});
  try{
    const data=await api(`/api/sessions/${sid}/evidence?${query}`);
    if(seq!==evidenceRequest||sid!==openSessionId||!target.isConnected)return;
    evidencePage=data.items;
    target.innerHTML=data.items.map(e=>`<article class="event-row evidence-card ${e.review_priority==='HIGH_REVIEW'?'high-review':''}"><div><strong>${relativeTime(e.session_offset_s)} · ${escapeHtml((e.role||'UNKNOWN')+' #'+e.track_id)}</strong><p><span class="chip">${escapeHtml(e.role||'UNKNOWN')}</span> · ${escapeHtml(label(e.event_type))} · ${escapeHtml(e.review_priority.replaceAll('_',' '))}</p><small>${escapeHtml(e.reason||'')} · ${e.duration_s==null?'—':Number(e.duration_s).toFixed(1)+' s'}<br>${t('detail.evidenceWindow')} ${relativeTime(e.evidence_start_s)} – ${relativeTime(e.evidence_end_s)}</small><p>${e.available?'':escapeHtml(e.unavailable_reason)}${e.recording_kind==='timelapse'?' · '+t('detail.sampledTimelapse'):''}</p></div>${e.available?`<button class="row-button" data-evidence-view="${Number(e.id)}">${t('detail.viewVideo')}</button>`:''}</article>`).join('')||`<p>${t('detail.noEvidence')}</p>`;
    target.innerHTML+=`<div>${data.total} review moments ${offset?`<button class="row-button" data-evidence-page="${Math.max(0,offset-data.limit)}">Previous</button>`:''}${offset+data.items.length<data.total?`<button class="row-button" data-evidence-page="${offset+data.limit}">Next</button>`:''}</div>`;
  }catch(error){if(target.isConnected)target.textContent=error.message}
}
document.addEventListener('change',event=>{if(['evidence-person','evidence-role','evidence-type','evidence-priority'].includes(event.target.id))loadEvidence()});
document.addEventListener('click',event=>{
  const nav=event.target.closest('[data-evidence-index]');if(nav&&!nav.disabled){const item=evidencePage[Number(nav.dataset.evidenceIndex)];if(item)document.querySelector(`[data-evidence-view="${item.id}"]`)?.click();return}
  const page=event.target.closest('[data-evidence-page]');if(page){loadEvidence(Number(page.dataset.evidencePage));return}
  const button=event.target.closest('[data-evidence-view]');if(!button)return;
  const item=evidencePage.find(e=>e.id===Number(button.dataset.evidenceView));if(!item)return;
  const target=$('#evidence-player');
  const idx=evidencePage.findIndex(e=>e.id===item.id),clipStart=item.recording_start_s||0,clipEnd=item.recording_end_s||0,eventStart=Math.max(0,(item.event_start_s||item.session_offset_s||0)-clipStart),eventEnd=Math.max(eventStart,(item.event_end_s||item.session_offset_s||0)-clipStart),clipLength=Math.max(clipEnd-clipStart,eventEnd,0.1),left=Math.max(0,Math.min(100,eventStart/clipLength*100)),width=Math.max(2,Math.min(100-left,(eventEnd-eventStart)/clipLength*100));
  target.innerHTML=`<div class="evidence-viewer-head"><strong>${escapeHtml((item.role||'UNKNOWN')+' #'+item.track_id)}</strong><br>${escapeHtml(label(item.event_type))} · ${escapeHtml(item.review_priority||'REVIEW')}</div><p>${t('detail.event')}: ${relativeTime(item.event_start_s||item.session_offset_s)} – ${relativeTime(item.event_end_s||item.session_offset_s)} · ${t('detail.evidence')}: ${relativeTime(item.evidence_start_s)} – ${relativeTime(item.evidence_end_s)} · ${t('detail.duration')}: ${item.duration_s==null?'—':Number(item.duration_s).toFixed(1)+' s'}<br>${escapeHtml(item.reason||t('detail.reviewMoments'))}</p>${item.status==='PROCESSING'?`<p class="notice">${t('status.processing')}</p>`:item.status==='UNAVAILABLE'?`<p class="notice">${escapeHtml(item.unavailable_reason||t('detail.noRecording'))}</p>`:`<video id="evidence-video" controls preload="metadata"></video><div class="evidence-marker"><small>0:00</small><span><i style="left:${left}%;width:${width}%">${t('detail.event')}</i></span><small>${relativeTime(clipLength)}</small></div><p>${t('detail.eventBegins')} ${relativeTime(eventStart)}.</p>`}<div class="evidence-nav"><button class="row-button" data-evidence-index="${idx-1}" ${idx<=0?'disabled':''}>${t('detail.previous')}</button><button class="row-button" data-evidence-index="${idx+1}" ${idx<0||idx>=evidencePage.length-1?'disabled':''}>${t('detail.next')}</button></div>`;
  if(item.status==='PROCESSING'||item.status==='UNAVAILABLE')return;
  const video=$('#evidence-video');video.src=nazarUrl(item.clip_available?item.clip_url:item.recording_url);
  const start=item.clip_available?0:item.recording_start_s,end=item.clip_available?null:item.recording_end_s;
  video.addEventListener('loadedmetadata',()=>{video.currentTime=Math.min(start,video.duration);video.play().catch(()=>{})},{once:true});
  if(end!=null)video.addEventListener('timeupdate',()=>{if(video.currentTime>=end)video.pause()});
  target.scrollIntoView({block:'nearest'});
});
