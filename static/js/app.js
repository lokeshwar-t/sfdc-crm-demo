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
document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('table.datatable').forEach(t => {
    new DataTable(t, {pageLength: 15, lengthChange: false,
      language: {search: '', searchPlaceholder: 'Filter…'}});
  });
  // auto-dismiss flash toasts
  setTimeout(() => document.querySelectorAll('.toast-flash').forEach(el => {
    bootstrap.Alert.getOrCreateInstance(el).close();
  }), 3500);
});
