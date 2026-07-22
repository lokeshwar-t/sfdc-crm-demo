/* CloudVision CRM — shared JS */

// ---------- AI panel ----------
function openAI(prompt, accountId) {
  document.getElementById('aiAccountId').value = accountId || '';
  const panel = new bootstrap.Offcanvas(document.getElementById('aiPanel'));
  panel.show();
  if (prompt) askAI(prompt);
}

function askAI(prompt) {
  document.getElementById('aiPrompt').value = prompt;
  sendAI();
}

function submitAI(e) {
  e.preventDefault();
  sendAI();
  return false;
}

function sendAI() {
  const input = document.getElementById('aiPrompt');
  const prompt = input.value.trim();
  if (!prompt) return;
  const box = document.getElementById('aiMessages');
  box.insertAdjacentHTML('beforeend', `<div class="ai-msg user">${escapeHtml(prompt)}</div>`);
  const typing = document.createElement('div');
  typing.className = 'ai-msg ai typing';
  typing.textContent = 'Thinking';
  box.appendChild(typing);
  box.scrollTop = box.scrollHeight;
  input.value = '';

  fetch('/api/ai/chat', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({prompt: prompt, account_id: document.getElementById('aiAccountId').value})
  }).then(r => r.json()).then(d => {
    setTimeout(() => {           // small delay for realism
      typing.classList.remove('typing');
      typing.innerHTML = mdLite(d.response);
      box.scrollTop = box.scrollHeight;
    }, 500);
  }).catch(() => { typing.textContent = 'Something went wrong.'; });
}

function escapeHtml(s) {
  return s.replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
}

function mdLite(s) {
  return escapeHtml(s)
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\n/g, '<br>');
}

// ---------- Meeting-Prep agent ----------
let mpHours = 24;
const MP_STORE_KEY = 'mp:lastRun';   // sessionStorage — survives tab navigation, clears with the session
let mpRelTimer = null;

function mpSelectWindow(btn) {
  mpHours = parseInt(btn.dataset.hours, 10);
  mpSetActiveWindow(mpHours);
  mpLoadMeetings(mpHours);   // keep the "Next Xh" list in step with the selection
}

// Populate the upcoming-meetings panel from the SAME source the agent briefs.
function mpLoadMeetings(hours) {
  const list = document.getElementById('mpMeetingsList');
  if (!list) return;
  const title = document.getElementById('mpMeetingsTitle');
  if (title) title.textContent = `Next ${hours} Hours`;
  fetch(`/api/meetings/upcoming?hours=${hours}`)
    .then(r => r.json())
    .then(d => {
      const ms = d.meetings || [];
      if (!ms.length) { list.innerHTML = '<div class="text-muted small py-2">No meetings scheduled.</div>'; return; }
      list.innerHTML = ms.map(m => `<div class="py-2 border-bottom">
          <div class="small fw-semibold">${escapeHtml((m.title || '').slice(0, 44))}</div>
          <div class="text-muted" style="font-size:11.5px">${mpFmtMeetingTime(m.start_time)}${m.location ? ' · ' + escapeHtml(m.location) : ''}</div>
        </div>`).join('');
    })
    .catch(() => { list.innerHTML = '<div class="text-muted small py-2">Could not load meetings.</div>'; });
}

function mpFmtMeetingTime(iso) {
  if (!iso) return '';
  const d = new Date(iso);   // naive (UTC-seeded) time renders as-is, matching the server
  if (isNaN(d)) return escapeHtml(iso);
  const date = d.toLocaleDateString('en-US', {weekday: 'short', month: 'short', day: '2-digit'}).replace(',', '');
  const time = d.toLocaleTimeString('en-US', {hour: 'numeric', minute: '2-digit'});
  return `${date}, ${time}`;
}

function mpSetActiveWindow(hours) {
  document.querySelectorAll('#mpWindow .btn').forEach(b =>
    b.classList.toggle('active', parseInt(b.dataset.hours, 10) === hours));
}

// Persist / restore the last run so navigating away and back doesn't re-trigger it.
function mpSaveRun(exec, hours, ts) {
  try {
    sessionStorage.setItem(MP_STORE_KEY, JSON.stringify({exec: exec, hours: hours, generatedAt: ts}));
  } catch (e) { /* quota / serialization — non-fatal, just won't persist */ }
}

function mpRestore() {
  let saved = null;
  try { saved = JSON.parse(sessionStorage.getItem(MP_STORE_KEY) || 'null'); } catch (e) { saved = null; }
  if (!saved || !saved.exec) return;
  mpHours = saved.hours || mpHours;
  mpSetActiveWindow(mpHours);
  const box = document.getElementById('mpResult');
  box.classList.remove('d-none');
  box.innerHTML = renderMeetingPrep(saved.exec, mpHours, saved.generatedAt);
  mpStartRelTimer();
}

function mpFmtTime(ts) {
  return new Date(ts).toLocaleTimeString([], {hour: 'numeric', minute: '2-digit'});
}

function mpRelTime(ts) {
  const s = Math.max(0, Math.round((Date.now() - ts) / 1000));
  if (s < 45) return 'just now';
  const m = Math.round(s / 60);
  if (m < 60) return `${m} min ago`;
  const h = Math.floor(m / 60), rem = m % 60;
  return rem ? `${h} hr ${rem} min ago` : `${h} hr ago`;
}

// Keep every "X ago" label current without re-rendering the cards.
function mpStartRelTimer() {
  if (mpRelTimer) return;
  mpRelTimer = setInterval(() => {
    const els = document.querySelectorAll('.mp-rel');
    if (!els.length) { clearInterval(mpRelTimer); mpRelTimer = null; return; }
    els.forEach(el => { el.textContent = mpRelTime(+el.dataset.ts); });
  }, 30000);
}

const MP_POLL_INTERVAL = 3000;   // ms between status polls
const MP_MAX_MS = 150000;        // give up after 2.5 min
let mpPollTimer = null;

function runMeetingPrep() {
  const btn = document.getElementById('mpRunBtn');
  const box = document.getElementById('mpResult');
  const original = btn.innerHTML;
  const started = Date.now();

  btn.disabled = true;
  btn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>Preparing…';
  box.classList.remove('d-none');
  mpShowLoader(box, 0);

  const finish = (html) => {
    if (mpPollTimer) { clearTimeout(mpPollTimer); mpPollTimer = null; }
    box.innerHTML = html;
    btn.disabled = false;
    btn.innerHTML = original;
  };

  fetch('/api/meeting-prep/run', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({hours: mpHours})
  }).then(async r => ({ok: r.ok, data: await r.json()}))
    .then(({ok, data}) => {
      if (!ok || data.error || !data.execution_id) { finish(mpError(data)); return; }
      mpPoll(data.execution_id, started, finish, box);
    })
    .catch(() => finish(mpError({error: 'Could not reach the agent.'})));
}

function mpPoll(execId, started, finish, box) {
  mpShowLoader(box, Math.round((Date.now() - started) / 1000));
  fetch(`/api/meeting-prep/status/${encodeURIComponent(execId)}`)
    .then(async r => ({ok: r.ok, data: await r.json()}))
    .then(({ok, data}) => {
      if (!ok || data.error) { finish(mpError(data)); return; }
      if (data.state === 'success') {
        const ts = Date.now();
        mpSaveRun(data.result, mpHours, ts);
        finish(renderMeetingPrep(data.result, mpHours, ts));
        mpStartRelTimer();
        return;
      }
      if (data.state === 'error') {
        finish(mpError({error: 'The workflow reported a failure.',
                        detail: _short(data.result)}));
        return;
      }
      if (Date.now() - started > MP_MAX_MS) {
        finish(mpError({error: 'Timed out waiting for the workflow.',
                        detail: `Still ${data.status || 'running'} after ${Math.round(MP_MAX_MS / 1000)}s (execution ${execId}).`}));
        return;
      }
      mpPollTimer = setTimeout(() => mpPoll(execId, started, finish, box), MP_POLL_INTERVAL);
    })
    .catch(() => {
      if (Date.now() - started > MP_MAX_MS) { finish(mpError({error: 'Lost connection while polling the workflow.'})); return; }
      mpPollTimer = setTimeout(() => mpPoll(execId, started, finish, box), MP_POLL_INTERVAL);
    });
}

function mpShowLoader(box, elapsed) {
  box.innerHTML = `<div class="d-flex align-items-center text-muted small">
      <span class="spinner-border spinner-border-sm me-2 text-primary"></span>
      Refold is briefing you on the next ${mpHours} hours… <span class="ms-1">(${elapsed}s)</span>
    </div>`;
}

function mpError(data) {
  data = data || {};
  return `<div class="alert alert-warning mb-0 py-2 small">
    <i class="fa-solid fa-triangle-exclamation me-1"></i>${escapeHtml(data.error || 'Something went wrong.')}
    ${data.detail ? `<div class="text-muted mt-1" style="word-break:break-word">${escapeHtml(String(data.detail))}</div>` : ''}
    ${data.hint ? `<div class="text-muted mt-1">${escapeHtml(data.hint)}</div>` : ''}
  </div>`;
}

function _short(v, n) {
  n = n || 400;
  const s = (typeof v === 'object' && v !== null) ? JSON.stringify(v) : String(v);
  return s.length > n ? s.slice(0, n) + '…' : s;
}

// Dig the array of meeting briefs out of the Cobalt execution response.
// Shape: { nodes: [ { latest_output: { body: { briefs: [...] } } } ] }
function mpExtractBriefs(exec) {
  if (!exec || typeof exec !== 'object') return [];
  const looksLikeBrief = (x) => x && typeof x === 'object' && (x.brief || x.meeting_title);

  const bodies = [];
  if (Array.isArray(exec.nodes)) {
    exec.nodes.forEach(n => { if (n && n.latest_output) bodies.push(n.latest_output.body); });
  }
  bodies.push(exec.body, exec.result, exec.output, exec);  // fallbacks

  for (const body of bodies) {
    if (body && Array.isArray(body.briefs)) return body.briefs;
    if (Array.isArray(body) && body.some(looksLikeBrief)) return body.filter(looksLikeBrief);
  }
  return [];
}

function mpHealthClass(h) {
  h = (h || '').toLowerCase();
  if (h.includes('green')) return 'bg-success-subtle text-success';
  if (h.includes('yellow')) return 'bg-warning-subtle text-warning';
  if (h.includes('red')) return 'bg-danger-subtle text-danger';
  return 'bg-light text-dark border';
}

function mpList(items, cls) {
  return `<ul class="small mb-0 ps-3 ${cls || ''}">${items.map(i => `<li class="mb-1">${escapeHtml(String(i))}</li>`).join('')}</ul>`;
}

function mpGeneratedLabel(ts) {
  if (!ts) return '';
  return `<div class="small text-muted"><i class="fa-regular fa-clock me-1"></i>Generated ${mpFmtTime(ts)} · <span class="mp-rel" data-ts="${ts}">${mpRelTime(ts)}</span></div>`;
}

function renderMeetingPrep(exec, hours, ts) {
  const briefs = mpExtractBriefs(exec);
  if (!briefs.length) {
    return `<div class="text-center text-muted py-4">
        <i class="fa-regular fa-calendar-check fa-2x mb-2 d-block text-secondary"></i>
        <div class="fw-semibold">No meetings in the next ${hours} hours</div>
        <div class="small">Nothing to prep for this window — try a longer one.</div>
        ${ts ? `<div class="mt-2">${mpGeneratedLabel(ts)}</div>` : ''}
        <details class="mt-3 text-start"><summary class="small text-secondary" style="cursor:pointer">Raw workflow response</summary>
          <pre class="small bg-light p-2 rounded mt-2 mb-0" style="white-space:pre-wrap;max-height:240px;overflow:auto">${escapeHtml(JSON.stringify(exec, null, 2))}</pre>
        </details>
      </div>`;
  }

  let html = `<div class="d-flex justify-content-between align-items-center flex-wrap gap-2 mb-3">
      <div>
        <span class="badge bg-primary-subtle text-primary me-2">Next ${hours}h</span>
        <span class="small text-muted">${briefs.length} meeting${briefs.length === 1 ? '' : 's'} briefed by the agent</span>
      </div>
      <div class="d-flex align-items-center flex-wrap gap-3">
        ${mpGeneratedLabel(ts)}
        <div class="btn-group btn-group-sm">
          <button type="button" class="btn btn-outline-secondary" onclick="mpToggleAll(true)"><i class="fa-solid fa-angles-down me-1"></i>Expand all</button>
          <button type="button" class="btn btn-outline-secondary" onclick="mpToggleAll(false)"><i class="fa-solid fa-angles-up me-1"></i>Collapse all</button>
        </div>
      </div>
    </div><div class="row g-3">`;

  briefs.forEach((item, i) => {
    const b = agentUnwrapBrief(item.brief || item);
    const title = item.meeting_title || b.meeting_title || 'Meeting';
    const tps = b.talking_points || [];
    const risks = b.risks || [];
    const hasHealth = b.health && String(b.health).toLowerCase() !== 'not available';
    const hasRenewal = b.renewal && String(b.renewal).toLowerCase() !== 'not available';
    const bodyId = `mpBody${i}`;

    html += `<div class="col-12">
      <div class="card section-card">
        <div class="card-header bg-white border-0 py-2 mp-toggle" role="button" tabindex="0"
             data-bs-toggle="collapse" data-bs-target="#${bodyId}" aria-expanded="true" aria-controls="${bodyId}">
          <div class="d-flex justify-content-between align-items-center flex-wrap gap-2">
            <h6 class="fw-semibold mb-0">
              <i class="fa-solid fa-chevron-down me-2 mp-caret text-muted small"></i>
              <i class="fa-solid fa-calendar-check me-2 text-primary"></i>${escapeHtml(title)}
            </h6>
            <div class="d-flex gap-2 flex-wrap">
              ${hasHealth ? `<span class="badge ${mpHealthClass(b.health)}"><i class="fa-solid fa-heart-pulse me-1"></i>${escapeHtml(b.health)}</span>` : ''}
              ${hasRenewal ? `<span class="badge bg-light text-dark border"><i class="fa-solid fa-rotate me-1"></i>Renewal ${escapeHtml(b.renewal)}</span>` : ''}
            </div>
          </div>
        </div>
        <div id="${bodyId}" class="collapse show mp-collapse">
          <div class="card-body pt-2">
            ${b.situation ? `<p class="small text-muted mb-3">${escapeHtml(b.situation)}</p>` : ''}
            <div class="row g-3">
              ${tps.length ? `<div class="col-md-6">
                <div class="fw-semibold small mb-1"><i class="fa-solid fa-comment-dots me-1 text-info"></i>Talking points</div>
                ${mpList(tps)}
              </div>` : ''}
              ${risks.length ? `<div class="col-md-6">
                <div class="fw-semibold small mb-1"><i class="fa-solid fa-triangle-exclamation me-1 text-warning"></i>Risks</div>
                ${mpList(risks)}
              </div>` : ''}
            </div>
            ${b.recommended_ask ? `<div class="alert alert-primary py-2 px-3 small mt-3 mb-0"><i class="fa-solid fa-bullseye me-1"></i><strong>Recommended ask:</strong> ${escapeHtml(b.recommended_ask)}</div>` : ''}
          </div>
        </div>
      </div>
    </div>`;
  });

  html += '</div>';
  return html;
}

// Expand/collapse every card in a result container (carets + aria stay in sync via Bootstrap).
function mpToggleAll(show, sel) {
  document.querySelectorAll(`${sel || '#mpResult'} .mp-collapse`).forEach(el => {
    const c = bootstrap.Collapse.getOrCreateInstance(el, {toggle: false});
    show ? c.show() : c.hide();
  });
}


// ---------- Renewal agent (same trigger→poll→render pattern as Meeting-Prep) ----------
let rpDays = 90;
const RP_STORE_KEY = 'rp:lastRun';

function rpSelectWindow(btn) {
  rpDays = parseInt(btn.dataset.days, 10);
  rpSetActiveWindow(rpDays);
}

function rpSetActiveWindow(days) {
  document.querySelectorAll('#rpWindow .btn').forEach(b =>
    b.classList.toggle('active', parseInt(b.dataset.days, 10) === days));
}

function rpSaveRun(exec, days, ts) {
  try { sessionStorage.setItem(RP_STORE_KEY, JSON.stringify({exec: exec, days: days, generatedAt: ts})); } catch (e) {}
}

function rpRestore() {
  let saved = null;
  try { saved = JSON.parse(sessionStorage.getItem(RP_STORE_KEY) || 'null'); } catch (e) { saved = null; }
  if (!saved || !saved.exec) return;
  rpDays = saved.days || rpDays;
  rpSetActiveWindow(rpDays);
  const box = document.getElementById('rpResult');
  box.classList.remove('d-none');
  box.innerHTML = renderRenewalPrep(saved.exec, rpDays, saved.generatedAt);
  mpStartRelTimer();
}

function runRenewalPrep() {
  const btn = document.getElementById('rpRunBtn');
  const box = document.getElementById('rpResult');
  const original = btn.innerHTML;
  const started = Date.now();

  btn.disabled = true;
  btn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>Preparing…';
  box.classList.remove('d-none');
  rpShowLoader(box, 0);

  const finish = (html) => {
    if (rpPollTimer) { clearTimeout(rpPollTimer); rpPollTimer = null; }
    box.innerHTML = html;
    btn.disabled = false;
    btn.innerHTML = original;
  };

  fetch('/api/renewal-prep/run', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({days: rpDays})
  }).then(async r => ({ok: r.ok, data: await r.json()}))
    .then(({ok, data}) => {
      if (!ok || data.error || !data.execution_id) { finish(mpError(data)); return; }
      rpPoll(data.execution_id, started, finish, box);
    })
    .catch(() => finish(mpError({error: 'Could not reach the agent.'})));
}

let rpPollTimer = null;
function rpPoll(execId, started, finish, box) {
  rpShowLoader(box, Math.round((Date.now() - started) / 1000));
  fetch(`/api/renewal-prep/status/${encodeURIComponent(execId)}`)
    .then(async r => ({ok: r.ok, data: await r.json()}))
    .then(({ok, data}) => {
      if (!ok || data.error) { finish(mpError(data)); return; }
      if (data.state === 'success') {
        const ts = Date.now();
        rpSaveRun(data.result, rpDays, ts);
        finish(renderRenewalPrep(data.result, rpDays, ts));
        mpStartRelTimer();
        return;
      }
      if (data.state === 'error') {
        finish(mpError({error: 'The workflow reported a failure.', detail: _short(data.result)}));
        return;
      }
      if (Date.now() - started > MP_MAX_MS) {
        finish(mpError({error: 'Timed out waiting for the workflow.',
                        detail: `Still ${data.status || 'running'} after ${Math.round(MP_MAX_MS / 1000)}s (execution ${execId}).`}));
        return;
      }
      rpPollTimer = setTimeout(() => rpPoll(execId, started, finish, box), MP_POLL_INTERVAL);
    })
    .catch(() => {
      if (Date.now() - started > MP_MAX_MS) { finish(mpError({error: 'Lost connection while polling the workflow.'})); return; }
      rpPollTimer = setTimeout(() => rpPoll(execId, started, finish, box), MP_POLL_INTERVAL);
    });
}

function rpShowLoader(box, elapsed) {
  box.innerHTML = `<div class="d-flex align-items-center text-muted small">
      <span class="spinner-border spinner-border-sm me-2 text-primary"></span>
      Refold is briefing you on renewals in the next ${rpDays} days… <span class="ms-1">(${elapsed}s)</span>
    </div>`;
}

function rpMoney(v) {
  if (v === null || v === undefined || v === '') return '';
  const n = Number(v);
  if (isNaN(n)) return escapeHtml(String(v));
  if (Math.abs(n) >= 1e6) return `$${(n / 1e6).toFixed(1)}M`;
  if (Math.abs(n) >= 1e3) return `$${Math.round(n / 1e3)}K`;
  return `$${Math.round(n)}`;
}

function rpFmtDate(iso) {
  if (!iso) return '';
  const d = new Date(iso);
  if (isNaN(d)) return escapeHtml(iso);
  return d.toLocaleDateString('en-US', {month: 'short', day: '2-digit', year: 'numeric'});
}

function rpLikelihoodClass(p) {
  const n = Number(p);
  if (isNaN(n)) return 'bg-light text-dark border';
  if (n >= 75) return 'bg-success-subtle text-success';
  if (n >= 55) return 'bg-warning-subtle text-warning';
  return 'bg-danger-subtle text-danger';
}

// LLM nodes sometimes return the brief unparsed — as {response:"```json…```"} or
// a fenced/plain JSON string. Normalize to the structured object either way.
function agentUnwrapBrief(raw) {
  let b = raw;
  if (b && typeof b === 'object' && typeof b.response === 'string') b = b.response;
  if (typeof b === 'string') {
    const s = b.trim().replace(/^```(?:json)?\s*/i, '').replace(/```\s*$/, '').trim();
    try { return JSON.parse(s); } catch (e) { return {situation: b}; }  // fallback: show raw text
  }
  return b || {};
}

function renderRenewalPrep(exec, days, ts) {
  const briefs = mpExtractBriefs(exec);   // same Cobalt envelope as Meeting-Prep
  if (!briefs.length) {
    return `<div class="text-center text-muted py-4">
        <i class="fa-regular fa-calendar-check fa-2x mb-2 d-block text-secondary"></i>
        <div class="fw-semibold">No renewals in the next ${days} days</div>
        <div class="small">Nothing due in this window — try a longer one.</div>
        ${ts ? `<div class="mt-2">${mpGeneratedLabel(ts)}</div>` : ''}
        <details class="mt-3 text-start"><summary class="small text-secondary" style="cursor:pointer">Raw workflow response</summary>
          <pre class="small bg-light p-2 rounded mt-2 mb-0" style="white-space:pre-wrap;max-height:240px;overflow:auto">${escapeHtml(JSON.stringify(exec, null, 2))}</pre>
        </details>
      </div>`;
  }

  let html = `<div class="d-flex justify-content-between align-items-center flex-wrap gap-2 mb-3">
      <div>
        <span class="badge bg-primary-subtle text-primary me-2">Next ${days}d</span>
        <span class="small text-muted">${briefs.length} renewal${briefs.length === 1 ? '' : 's'} briefed by the agent</span>
      </div>
      <div class="d-flex align-items-center flex-wrap gap-3">
        ${mpGeneratedLabel(ts)}
        <div class="btn-group btn-group-sm">
          <button type="button" class="btn btn-outline-secondary" onclick="mpToggleAll(true, '#rpResult')"><i class="fa-solid fa-angles-down me-1"></i>Expand all</button>
          <button type="button" class="btn btn-outline-secondary" onclick="mpToggleAll(false, '#rpResult')"><i class="fa-solid fa-angles-up me-1"></i>Collapse all</button>
        </div>
      </div>
    </div><div class="row g-3">`;

  briefs.forEach((item, i) => {
    const b = agentUnwrapBrief(item.brief || item);
    const account = item.account || b.account || 'Account';
    const amount = item.amount != null ? item.amount : b.amount;
    const likelihood = item.likelihood != null ? item.likelihood : b.likelihood;
    const status = item.status || b.status;
    const renewalDate = item.renewal_date || b.renewal_date;
    const tps = b.talking_points || [];
    const risks = b.risks || [];
    const play = b.recommended_play || b.recommended_ask || b.play;
    const hasHealth = b.health && String(b.health).toLowerCase() !== 'not available';
    const bodyId = `rpBody${i}`;

    html += `<div class="col-12">
      <div class="card section-card">
        <div class="card-header bg-white border-0 py-2 mp-toggle" role="button" tabindex="0"
             data-bs-toggle="collapse" data-bs-target="#${bodyId}" aria-expanded="true" aria-controls="${bodyId}">
          <div class="d-flex justify-content-between align-items-center flex-wrap gap-2">
            <h6 class="fw-semibold mb-0">
              <i class="fa-solid fa-chevron-down me-2 mp-caret text-muted small"></i>
              <i class="fa-solid fa-rotate me-2 text-primary"></i>${escapeHtml(account)}
            </h6>
            <div class="d-flex gap-2 flex-wrap align-items-center">
              ${amount != null ? `<span class="badge bg-dark-subtle text-dark border">${rpMoney(amount)}</span>` : ''}
              ${likelihood != null ? `<span class="badge ${rpLikelihoodClass(likelihood)}">${escapeHtml(String(likelihood))}% likely</span>` : ''}
              ${status ? `<span class="badge bg-light text-dark border">${escapeHtml(status)}</span>` : ''}
              ${renewalDate ? `<span class="badge bg-light text-dark border"><i class="fa-regular fa-calendar me-1"></i>${rpFmtDate(renewalDate)}</span>` : ''}
              ${hasHealth ? `<span class="badge ${mpHealthClass(b.health)}"><i class="fa-solid fa-heart-pulse me-1"></i>${escapeHtml(b.health)}</span>` : ''}
            </div>
          </div>
        </div>
        <div id="${bodyId}" class="collapse show mp-collapse">
          <div class="card-body pt-2">
            ${b.situation ? `<p class="small text-muted mb-3">${escapeHtml(b.situation)}</p>` : ''}
            <div class="row g-3">
              ${tps.length ? `<div class="col-md-6">
                <div class="fw-semibold small mb-1"><i class="fa-solid fa-comment-dots me-1 text-info"></i>Talking points</div>
                ${mpList(tps)}
              </div>` : ''}
              ${risks.length ? `<div class="col-md-6">
                <div class="fw-semibold small mb-1"><i class="fa-solid fa-triangle-exclamation me-1 text-warning"></i>Risks</div>
                ${mpList(risks)}
              </div>` : ''}
            </div>
            ${play ? `<div class="alert alert-primary py-2 px-3 small mt-3 mb-0"><i class="fa-solid fa-chess-knight me-1"></i><strong>Recommended play:</strong> ${escapeHtml(play)}</div>` : ''}
          </div>
        </div>
      </div>
    </div>`;
  });

  html += '</div>';
  return html;
}

// ---------- Churn Sentinel agent (read → reason → act; writes back to the CRM) ----------
let csLimit = 10;
const CS_STORE_KEY = 'cs:lastRun';
let csPollTimer = null;

function csSelectWindow(btn) {
  csLimit = parseInt(btn.dataset.limit, 10);
  csSetActiveWindow(csLimit);
}

function csSetActiveWindow(limit) {
  document.querySelectorAll('#csWindow .btn').forEach(b =>
    b.classList.toggle('active', parseInt(b.dataset.limit, 10) === limit));
}

function csSaveRun(exec, limit, ts) {
  try { sessionStorage.setItem(CS_STORE_KEY, JSON.stringify({exec: exec, limit: limit, generatedAt: ts})); } catch (e) {}
}

function csRestore() {
  let saved = null;
  try { saved = JSON.parse(sessionStorage.getItem(CS_STORE_KEY) || 'null'); } catch (e) { saved = null; }
  if (!saved || !saved.exec) return;
  csLimit = saved.limit || csLimit;
  csSetActiveWindow(csLimit);
  const box = document.getElementById('csResult');
  box.classList.remove('d-none');
  box.innerHTML = renderChurnSentinel(saved.exec, csLimit, saved.generatedAt);
  mpStartRelTimer();
}

function runChurnSentinel() {
  const btn = document.getElementById('csRunBtn');
  const box = document.getElementById('csResult');
  const original = btn.innerHTML;
  const started = Date.now();

  btn.disabled = true;
  btn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>Sweeping…';
  box.classList.remove('d-none');
  csShowLoader(box, 0);

  const finish = (html) => {
    if (csPollTimer) { clearTimeout(csPollTimer); csPollTimer = null; }
    box.innerHTML = html;
    btn.disabled = false;
    btn.innerHTML = original;
  };

  fetch('/api/churn-sentinel/run', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({limit: csLimit})
  }).then(async r => ({ok: r.ok, data: await r.json()}))
    .then(({ok, data}) => {
      if (!ok || data.error || !data.execution_id) { finish(mpError(data)); return; }
      csPoll(data.execution_id, started, finish, box);
    })
    .catch(() => finish(mpError({error: 'Could not reach the agent.'})));
}

function csPoll(execId, started, finish, box) {
  csShowLoader(box, Math.round((Date.now() - started) / 1000));
  fetch(`/api/churn-sentinel/status/${encodeURIComponent(execId)}`)
    .then(async r => ({ok: r.ok, data: await r.json()}))
    .then(({ok, data}) => {
      if (!ok || data.error) { finish(mpError(data)); return; }
      if (data.state === 'success') {
        const ts = Date.now();
        const n = mpExtractBriefs(data.result).length;
        csSaveRun(data.result, csLimit, ts);
        finish(renderChurnSentinel(data.result, csLimit, ts));
        mpStartRelTimer();
        // notify the current user so the bell lights up, then refresh it
        fetch('/api/churn-sentinel/notify', {method: 'POST', headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({count: n, limit: csLimit})}).then(() => refreshBell()).catch(() => {});
        return;
      }
      if (data.state === 'error') {
        finish(mpError({error: 'The workflow reported a failure.', detail: _short(data.result)}));
        return;
      }
      if (Date.now() - started > MP_MAX_MS) {
        finish(mpError({error: 'Timed out waiting for the workflow.',
                        detail: `Still ${data.status || 'running'} after ${Math.round(MP_MAX_MS / 1000)}s (execution ${execId}).`}));
        return;
      }
      csPollTimer = setTimeout(() => csPoll(execId, started, finish, box), MP_POLL_INTERVAL);
    })
    .catch(() => {
      if (Date.now() - started > MP_MAX_MS) { finish(mpError({error: 'Lost connection while polling the workflow.'})); return; }
      csPollTimer = setTimeout(() => csPoll(execId, started, finish, box), MP_POLL_INTERVAL);
    });
}

function csShowLoader(box, elapsed) {
  box.innerHTML = `<div class="d-flex align-items-center text-muted small">
      <span class="spinner-border spinner-border-sm me-2 text-primary"></span>
      Refold is sweeping the ${csLimit} riskiest accounts and filing save-plays… <span class="ms-1">(${elapsed}s)</span>
    </div>`;
}

// Render the actions the agent wrote back (notifications / tasks) as green pills.
function csActionsTaken(item, b) {
  return agentActionsTaken(item.actions_taken || item.actions || b.actions_taken || b.actions || []);
}

function agentActionsTaken(acts) {
  acts = acts || [];
  if (!acts.length) return '';
  const pill = (a) => {
    const label = typeof a === 'string' ? a
      : (a.title || a.message || a.label || a.summary || (a.type ? a.type : 'action'));
    const icon = /task/i.test(a.type || '') ? 'fa-list-check'
      : (/notif|alert/i.test(a.type || '') ? 'fa-bell' : 'fa-check');
    return `<span class="badge bg-success-subtle text-success border border-success-subtle me-1 mb-1"><i class="fa-solid ${icon} me-1"></i>${escapeHtml(String(label))}</span>`;
  };
  return `<div class="mt-3"><div class="fw-semibold small mb-1"><i class="fa-solid fa-bolt me-1 text-success"></i>Actions taken by the agent</div>
    <div class="d-flex flex-wrap">${acts.map(pill).join('')}</div></div>`;
}

function renderChurnSentinel(exec, limit, ts) {
  const briefs = mpExtractBriefs(exec);
  if (!briefs.length) {
    return `<div class="text-center text-muted py-4">
        <i class="fa-regular fa-face-smile fa-2x mb-2 d-block text-secondary"></i>
        <div class="fw-semibold">No at-risk accounts surfaced</div>
        ${ts ? `<div class="mt-2">${mpGeneratedLabel(ts)}</div>` : ''}
        <details class="mt-3 text-start"><summary class="small text-secondary" style="cursor:pointer">Raw workflow response</summary>
          <pre class="small bg-light p-2 rounded mt-2 mb-0" style="white-space:pre-wrap;max-height:240px;overflow:auto">${escapeHtml(JSON.stringify(exec, null, 2))}</pre>
        </details>
      </div>`;
  }

  let html = `<div class="d-flex justify-content-between align-items-center flex-wrap gap-2 mb-3">
      <div>
        <span class="badge bg-primary-subtle text-primary me-2">Top ${limit}</span>
        <span class="small text-muted">${briefs.length} account${briefs.length === 1 ? '' : 's'} swept &amp; actioned by the agent</span>
      </div>
      <div class="d-flex align-items-center flex-wrap gap-3">
        ${mpGeneratedLabel(ts)}
        <div class="btn-group btn-group-sm">
          <button type="button" class="btn btn-outline-secondary" onclick="mpToggleAll(true, '#csResult')"><i class="fa-solid fa-angles-down me-1"></i>Expand all</button>
          <button type="button" class="btn btn-outline-secondary" onclick="mpToggleAll(false, '#csResult')"><i class="fa-solid fa-angles-up me-1"></i>Collapse all</button>
        </div>
      </div>
    </div><div class="row g-3">`;

  briefs.forEach((item, i) => {
    const b = agentUnwrapBrief(item.brief || item);
    const account = item.account || b.account || 'Account';
    const csm = item.csm || b.csm;
    const risks = b.risks || b.signals || [];
    const play = b.recommended_play || b.save_play || b.recommended_ask || b.play;
    const hasHealth = b.health && String(b.health).toLowerCase() !== 'not available';
    const bodyId = `csBody${i}`;

    html += `<div class="col-12">
      <div class="card section-card">
        <div class="card-header bg-white border-0 py-2 mp-toggle" role="button" tabindex="0"
             data-bs-toggle="collapse" data-bs-target="#${bodyId}" aria-expanded="true" aria-controls="${bodyId}">
          <div class="d-flex justify-content-between align-items-center flex-wrap gap-2">
            <h6 class="fw-semibold mb-0">
              <i class="fa-solid fa-chevron-down me-2 mp-caret text-muted small"></i>
              <i class="fa-solid fa-heart-crack me-2 text-danger"></i>${escapeHtml(account)}
            </h6>
            <div class="d-flex gap-2 flex-wrap align-items-center">
              ${csm ? `<span class="badge bg-light text-dark border"><i class="fa-regular fa-user me-1"></i>${escapeHtml(csm)}</span>` : ''}
              ${hasHealth ? `<span class="badge ${mpHealthClass(b.health)}"><i class="fa-solid fa-heart-pulse me-1"></i>${escapeHtml(b.health)}</span>` : ''}
            </div>
          </div>
        </div>
        <div id="${bodyId}" class="collapse show mp-collapse">
          <div class="card-body pt-2">
            ${b.situation ? `<p class="small text-muted mb-3">${escapeHtml(b.situation)}</p>` : ''}
            ${risks.length ? `<div class="fw-semibold small mb-1"><i class="fa-solid fa-triangle-exclamation me-1 text-warning"></i>Risk signals</div>${mpList(risks)}` : ''}
            ${play ? `<div class="alert alert-primary py-2 px-3 small mt-3 mb-0"><i class="fa-solid fa-life-ring me-1"></i><strong>Save play:</strong> ${escapeHtml(play)}</div>` : ''}
            ${csActionsTaken(item, b)}
          </div>
        </div>
      </div>
    </div>`;
  });

  html += '</div>';
  return html;
}

// ---------- Briefing agent (business-wide exec summary; writes to the inbox) ----------
let bfDays = 7;
const BF_STORE_KEY = 'bf:lastRun';
let bfPollTimer = null;

function bfSelectWindow(btn) {
  bfDays = parseInt(btn.dataset.days, 10);
  bfSetActiveWindow(bfDays);
}

function bfSetActiveWindow(days) {
  document.querySelectorAll('#bfWindow .btn').forEach(b =>
    b.classList.toggle('active', parseInt(b.dataset.days, 10) === days));
}

function bfSaveRun(exec, days, ts) {
  try { sessionStorage.setItem(BF_STORE_KEY, JSON.stringify({exec: exec, days: days, generatedAt: ts})); } catch (e) {}
}

function bfRestore() {
  let saved = null;
  try { saved = JSON.parse(sessionStorage.getItem(BF_STORE_KEY) || 'null'); } catch (e) { saved = null; }
  if (!saved || !saved.exec) return;
  bfDays = saved.days || bfDays;
  bfSetActiveWindow(bfDays);
  const box = document.getElementById('bfResult');
  box.classList.remove('d-none');
  box.innerHTML = renderBriefing(saved.exec, bfDays, saved.generatedAt);
  mpStartRelTimer();
}

function runBriefing() {
  const btn = document.getElementById('bfRunBtn');
  const box = document.getElementById('bfResult');
  const original = btn.innerHTML;
  const started = Date.now();

  btn.disabled = true;
  btn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>Compiling…';
  box.classList.remove('d-none');
  bfShowLoader(box, 0);

  const finish = (html) => {
    if (bfPollTimer) { clearTimeout(bfPollTimer); bfPollTimer = null; }
    box.innerHTML = html;
    btn.disabled = false;
    btn.innerHTML = original;
  };

  fetch('/api/briefing/run', {
    method: 'POST', headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({days: bfDays})
  }).then(async r => ({ok: r.ok, data: await r.json()}))
    .then(({ok, data}) => {
      if (!ok || data.error || !data.execution_id) { finish(mpError(data)); return; }
      bfPoll(data.execution_id, started, finish, box);
    })
    .catch(() => finish(mpError({error: 'Could not reach the agent.'})));
}

function bfPoll(execId, started, finish, box) {
  bfShowLoader(box, Math.round((Date.now() - started) / 1000));
  fetch(`/api/briefing/status/${encodeURIComponent(execId)}`)
    .then(async r => ({ok: r.ok, data: await r.json()}))
    .then(({ok, data}) => {
      if (!ok || data.error) { finish(mpError(data)); return; }
      if (data.state === 'success') {
        const ts = Date.now();
        bfSaveRun(data.result, bfDays, ts);
        finish(renderBriefing(data.result, bfDays, ts));
        mpStartRelTimer();
        const bf = bfExtractBriefing(data.result);
        fetch('/api/briefing/notify', {method: 'POST', headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({headline: bf && bf.headline ? bf.headline : ''})}).then(() => refreshBell()).catch(() => {});
        return;
      }
      if (data.state === 'error') {
        finish(mpError({error: 'The workflow reported a failure.', detail: _short(data.result)}));
        return;
      }
      if (Date.now() - started > MP_MAX_MS) {
        finish(mpError({error: 'Timed out waiting for the workflow.',
                        detail: `Still ${data.status || 'running'} after ${Math.round(MP_MAX_MS / 1000)}s (execution ${execId}).`}));
        return;
      }
      bfPollTimer = setTimeout(() => bfPoll(execId, started, finish, box), MP_POLL_INTERVAL);
    })
    .catch(() => {
      if (Date.now() - started > MP_MAX_MS) { finish(mpError({error: 'Lost connection while polling the workflow.'})); return; }
      bfPollTimer = setTimeout(() => bfPoll(execId, started, finish, box), MP_POLL_INTERVAL);
    });
}

function bfShowLoader(box, elapsed) {
  box.innerHTML = `<div class="d-flex align-items-center text-muted small">
      <span class="spinner-border spinner-border-sm me-2 text-primary"></span>
      Refold is compiling your executive briefing (last ${bfDays} days)… <span class="ms-1">(${elapsed}s)</span>
    </div>`;
}

// Pull the single briefing object out of the Cobalt envelope.
function bfExtractBriefing(exec) {
  if (!exec || typeof exec !== 'object') return null;
  const bodies = [];
  if (Array.isArray(exec.nodes)) exec.nodes.forEach(n => { if (n && n.latest_output) bodies.push(n.latest_output.body); });
  bodies.push(exec.body, exec.result, exec.output, exec);
  for (const body of bodies) {
    if (!body) continue;
    const cand = agentUnwrapBrief(body.briefing || body.brief || body);
    if (cand && (cand.headline || cand.summary || cand.sections)) return cand;
  }
  return null;
}

function renderBriefing(exec, days, ts) {
  const bf = bfExtractBriefing(exec);
  if (!bf) {
    return `<div class="small text-muted mb-2">The workflow finished but returned no briefing.</div>
      <pre class="small bg-light p-2 rounded mb-0" style="white-space:pre-wrap;max-height:240px;overflow:auto">${escapeHtml(JSON.stringify(exec, null, 2))}</pre>`;
  }
  const sections = bf.sections || [];
  const recommended = bf.recommended_actions || [];

  let html = `<div class="d-flex justify-content-between align-items-center flex-wrap gap-2 mb-2">
      <span class="badge bg-primary-subtle text-primary">Last ${days}d</span>
      ${mpGeneratedLabel(ts)}
    </div>`;
  if (bf.headline) html += `<h5 class="fw-semibold mb-1">${escapeHtml(bf.headline)}</h5>`;
  if (bf.summary) html += `<p class="text-muted small mb-3">${escapeHtml(bf.summary)}</p>`;

  if (sections.length) {
    html += '<div class="row g-3">';
    sections.forEach(s => {
      const items = s.items || s.points || [];
      html += `<div class="col-md-6"><div class="card section-card h-100"><div class="card-body py-2">
          <div class="fw-semibold small mb-1"><i class="fa-solid fa-angle-right me-1 text-primary"></i>${escapeHtml(s.title || 'Section')}</div>
          ${items.length ? mpList(items) : '<div class="text-muted small mb-0">—</div>'}
        </div></div></div>`;
    });
    html += '</div>';
  }

  if (recommended.length) {
    html += `<div class="alert alert-primary py-2 px-3 small mt-3 mb-0">
        <div class="fw-semibold mb-1"><i class="fa-solid fa-list-check me-1"></i>Recommended actions</div>${mpList(recommended)}</div>`;
  }
  html += agentActionsTaken(bf.actions_taken || []);
  return html;
}

// Restore the last briefing on load so tab navigation doesn't force a re-run.
function mpInit() {
  if (document.getElementById('mpResult')) {
    mpRestore();                 // may set mpHours from the saved run
    mpLoadMeetings(mpHours);     // reflect the restored/default window in the list
  }
  if (document.getElementById('rpResult')) {
    rpRestore();
  }
  if (document.getElementById('csResult')) {
    csRestore();
  }
  if (document.getElementById('bfResult')) {
    bfRestore();
  }
}
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', mpInit);
} else {
  mpInit();
}

// ---------- Charts ----------
const CV = {
  colors: ['#6366f1', '#8b5cf6', '#ec4899', '#f59e0b', '#10b981', '#3b82f6', '#ef4444', '#14b8a6'],
  grid: {color: '#eef0f5'},
};
Chart.defaults.font.family = "'Inter', -apple-system, sans-serif";
Chart.defaults.font.size = 11.5;
Chart.defaults.color = '#64748b';
Chart.defaults.plugins.legend.labels.boxWidth = 12;

function lineChart(id, url, label, fill = true, money = true) {
  const el = document.getElementById(id);
  if (!el) return;
  fetch(url).then(r => r.json()).then(d => {
    new Chart(el, {
      type: 'line',
      data: {labels: d.labels, datasets: [{
        label: label, data: d.values, borderColor: '#6366f1', borderWidth: 2.5,
        pointRadius: 0, pointHoverRadius: 4, tension: 0.4, fill: fill,
        backgroundColor: (ctx) => {
          const g = ctx.chart.ctx.createLinearGradient(0, 0, 0, ctx.chart.height);
          g.addColorStop(0, 'rgba(99,102,241,.25)'); g.addColorStop(1, 'rgba(99,102,241,0)');
          return g;
        }
      }]},
      options: {maintainAspectRatio: false, plugins: {legend: {display: false}},
        scales: {x: {grid: {display: false}}, y: {grid: CV.grid, ticks: money ? {callback: v => '$' + v + 'M'} : {}}}}
    });
  });
}

function barChart(id, url, label, horizontal = false, money = true) {
  const el = document.getElementById(id);
  if (!el) return;
  fetch(url).then(r => r.json()).then(d => {
    new Chart(el, {
      type: 'bar',
      data: {labels: d.labels, datasets: [{label: label, data: d.values,
        backgroundColor: d.labels.map((_, i) => CV.colors[i % CV.colors.length] + 'cc'),
        borderRadius: 8, maxBarThickness: 42}]},
      options: {indexAxis: horizontal ? 'y' : 'x', maintainAspectRatio: false,
        plugins: {legend: {display: false}},
        scales: {
          x: {grid: horizontal ? CV.grid : {display: false}, ticks: horizontal && money ? {callback: v => '$' + v + 'M'} : {}},
          y: {grid: horizontal ? {display: false} : CV.grid, ticks: !horizontal && money ? {callback: v => '$' + v + 'M'} : {}}
        }}
    });
  });
}

function funnelChart(id, url) {
  const el = document.getElementById(id);
  if (!el) return;
  fetch(url).then(r => r.json()).then(d => {
    new Chart(el, {
      type: 'bar',
      data: {labels: d.labels, datasets: [{data: d.values,
        backgroundColor: ['#c7d2fe', '#a5b4fc', '#818cf8', '#6366f1', '#4f46e5'],
        borderRadius: 8, maxBarThickness: 30}]},
      options: {indexAxis: 'y', maintainAspectRatio: false, plugins: {legend: {display: false}},
        scales: {x: {grid: CV.grid, ticks: {callback: v => '$' + v + 'M'}}, y: {grid: {display: false}}}}
    });
  });
}

function doughnutChart(id, url, colorMap) {
  const el = document.getElementById(id);
  if (!el) return;
  fetch(url).then(r => r.json()).then(d => {
    new Chart(el, {
      type: 'doughnut',
      data: {labels: d.labels, datasets: [{data: d.values,
        backgroundColor: colorMap || CV.colors, borderWidth: 2, borderColor: '#fff'}]},
      options: {maintainAspectRatio: false, cutout: '68%',
        plugins: {legend: {position: 'bottom'}}}
    });
  });
}

// ---------- Edit modals ----------
function openEdit(modalId, btn) {
  const rec = JSON.parse(btn.dataset.record);
  const modal = document.getElementById(modalId);
  const form = modal.querySelector('form');
  form.action = form.dataset.actionBase + rec.id;
  Object.entries(rec).forEach(([k, v]) => {
    const field = form.querySelector(`[name="${k}"]`);
    if (!field) return;
    if (field.type === 'checkbox') field.checked = !!v;
    else field.value = v === null || v === undefined ? '' : v;
  });
  new bootstrap.Modal(modal).show();
}

// ---------- Kanban drag & drop ----------
let draggedCard = null;

function dragDeal(ev) {
  draggedCard = ev.target.closest('.deal-card');
  ev.dataTransfer.effectAllowed = 'move';
  setTimeout(() => draggedCard.classList.add('dragging'), 0);
}

function dragEndDeal() {
  if (draggedCard) draggedCard.classList.remove('dragging');
  document.querySelectorAll('.kanban-body.drop-hover').forEach(el => el.classList.remove('drop-hover'));
}

function allowDrop(ev) {
  ev.preventDefault();
  ev.currentTarget.classList.add('drop-hover');
}

function leaveDrop(ev) {
  ev.currentTarget.classList.remove('drop-hover');
}

function dropDeal(ev) {
  ev.preventDefault();
  const zone = ev.currentTarget;
  zone.classList.remove('drop-hover');
  if (!draggedCard) return;
  const newStage = zone.dataset.stage;
  const oldZone = draggedCard.closest('.kanban-body');
  if (zone === oldZone) return;
  const id = draggedCard.dataset.id;
  zone.prepend(draggedCard);
  fetch(`/edit/api/opportunity/${id}/stage`, {
    method: 'POST', headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({stage: newStage})
  }).then(r => r.json()).then(d => {
    if (!d.ok) { oldZone.prepend(draggedCard); showToast('Could not move deal.', 'danger'); return; }
    const badge = draggedCard.querySelector('.ai-score');
    if (badge) {
      badge.textContent = d.ai_score;
      badge.className = 'ai-score ' + (d.ai_score >= 70 ? 'hi' : d.ai_score >= 40 ? 'mid' : 'lo');
    }
    updateKanbanTotals();
    showToast(`Deal moved to ${newStage}.`, 'success');
  }).catch(() => { oldZone.prepend(draggedCard); showToast('Could not move deal.', 'danger'); });
}

function updateKanbanTotals() {
  document.querySelectorAll('.kanban-col').forEach(col => {
    const totalEl = col.querySelector('.kanban-total');
    if (!totalEl) return;
    let sum = 0;
    col.querySelectorAll('.deal-card').forEach(c => sum += parseFloat(c.dataset.amount || 0));
    totalEl.textContent = sum >= 1e6 ? '$' + (sum / 1e6).toFixed(1) + 'M' : '$' + Math.round(sum / 1e3) + 'K';
  });
}

function showToast(msg, type) {
  const el = document.createElement('div');
  el.className = `toast-flash alert alert-${type} shadow-sm`;
  el.textContent = msg;
  document.body.appendChild(el);
  setTimeout(() => el.remove(), 2500);
}

// ---------- DataTables ----------
const agentDT = {};   // id -> DataTable instance (for programmatic filtering)
document.addEventListener('DOMContentLoaded', () => {
  const _dtInstances = [];
  document.querySelectorAll('table.datatable').forEach(t => {
    const opts = {pageLength: parseInt(t.dataset.pageLength, 10) || 15, lengthChange: false,
      autoWidth: false,   // let CSS width:100% fill the container (fixes narrow cols in tabs)
      language: {search: '', searchPlaceholder: 'Filter…'}};
    if (t.dataset.orderCol !== undefined) {
      opts.order = [[parseInt(t.dataset.orderCol, 10), t.dataset.orderDir || 'asc']];
    }
    const inst = new DataTable(t, opts);
    _dtInstances.push(inst);
    if (t.id) agentDT[t.id] = inst;
  });
  // DataTables initialized inside a hidden tab mis-sizes columns — recalc on show.
  document.querySelectorAll('button[data-bs-toggle="tab"]').forEach(btn => {
    btn.addEventListener('shown.bs.tab', () => _dtInstances.forEach(dt => dt.columns.adjust()));
  });
  // auto-dismiss flash toasts
  setTimeout(() => document.querySelectorAll('.toast-flash').forEach(el => {
    bootstrap.Alert.getOrCreateInstance(el).close();
  }), 3500);
  // poll the notification bell so agent write-backs appear without a reload
  if (document.getElementById('notifDot')) setInterval(refreshBell, 15000);
});

// Customer Health KPI boxes act as status filters on the health table.
function csFilterHealth(status, el) {
  const dt = agentDT['healthTable'];
  if (!dt) return;
  const wasActive = el.classList.contains('active');
  document.querySelectorAll('#healthKpis .kpi-filter').forEach(k => k.classList.remove('active'));
  // toggle off if the active box is clicked again, else filter to that status
  dt.column(3).search(wasActive ? '' : status).draw();
  if (!wasActive) el.classList.add('active');
}

// ---------- Notification bell (poll so agent write-backs surface without a reload) ----------
const NOTIF_ICONS = {Renewal: 'rotate', Contract: 'file-contract', Health: 'heart-pulse',
  Deal: 'bullseye', Task: 'list-check', Meeting: 'calendar-days', Activity: 'bolt'};

function refreshBell() {
  const dot = document.getElementById('notifDot');
  const list = document.getElementById('notifList');
  if (!dot || !list) return;
  fetch('/api/notifications/summary').then(r => r.ok ? r.json() : null).then(d => {
    if (!d) return;
    if (d.unread > 0) { dot.textContent = d.unread; dot.style.display = ''; }
    else { dot.textContent = ''; dot.style.display = 'none'; }
    if (!d.items.length) { list.innerHTML = '<div class="p-3 text-muted small">No notifications</div>'; return; }
    list.innerHTML = d.items.map(n => {
      const icon = NOTIF_ICONS[n.category] || 'bell';
      return `<a href="${n.link || '#'}" class="dropdown-item notif-item ${n.is_read ? '' : 'unread'}">
        <span class="notif-cat cat-${(n.category || '').toLowerCase()}"><i class="fa-solid fa-${icon}"></i></span>
        <span class="small">${escapeHtml(n.message)}</span></a>`;
    }).join('');
  }).catch(() => {});
}
