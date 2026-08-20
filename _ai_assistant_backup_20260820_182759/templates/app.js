/* ============================================================
   DataStream AI Chatbot — Frontend Application
   Connects to FastAPI backend at http://localhost:8000
   ============================================================ */

'use strict';

// ── Configuration ─────────────────────────────────────────────
const API_BASE = `${window.location.protocol}//${window.location.hostname}:8000`;

const PROVIDER_MODELS = {
  groq:      ['llama-3.1-8b-instant', 'llama-3.3-70b-versatile', 'gemma2-9b-it', 'llama-3.2-1b-preview'],
  openai:    ['gpt-4o', 'gpt-4o-mini', 'gpt-4-turbo', 'gpt-3.5-turbo'],
  anthropic: ['claude-opus-4-7', 'claude-sonnet-4-6', 'claude-haiku-4-5-20251001'],
};

const SCENARIO_LABELS = {
  1: 'LLM Only',
  2: 'LLM + Rules',
  3: 'Embedding',
  4: 'Database Q&A',
};

// ── State ──────────────────────────────────────────────────────
let token         = localStorage.getItem('ds_token') || null;
let currentUser   = null;
let currentSession = null;   // active session_id
let isWaiting     = false;
let sortState     = {};      // per-table sort tracking

// ── Helpers ────────────────────────────────────────────────────
const $ = id => document.getElementById(id);

function fmt(date) {
  if (!date) return '';
  const d = new Date(date);
  return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

function showToast(msg, duration = 3000) {
  const t = $('toast');
  t.textContent = msg;
  t.classList.add('visible');
  setTimeout(() => t.classList.remove('visible'), duration);
}

function setTheme(theme) {
  document.documentElement.dataset.theme = theme;
  localStorage.setItem('ds_theme', theme);
  $('theme-toggle').textContent = theme === 'dark' ? '🌙' : '☀️';
}

// Auto-grow textarea
function autoResize(el) {
  el.style.height = 'auto';
  el.style.height = Math.min(el.scrollHeight, 140) + 'px';
}

// ── API ────────────────────────────────────────────────────────
async function api(method, path, body = null, isForm = false) {
  const opts = {
    method,
    headers: { 'Content-Type': 'application/json' },
  };
  if (token) opts.headers['Authorization'] = `Bearer ${token}`;
  if (body)  opts.body = JSON.stringify(body);

  const res = await fetch(API_BASE + path, opts);

  if (res.status === 401) {
    logout();
    throw new Error('Session expired. Please log in again.');
  }
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  if (res.status === 204) return null;
  return res.json();
}

// ── Auth ───────────────────────────────────────────────────────
async function login(username, password) {
  const res = await fetch(`${API_BASE}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password, client_id: 'web' }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Login failed' }));
    throw new Error(err.detail || 'Invalid credentials');
  }
  const data = await res.json();
  return data.access_token;
}

function logout() {
  token = null;
  currentUser = null;
  currentSession = null;
  localStorage.removeItem('ds_token');
  showLogin();
}

// ── Login flow ─────────────────────────────────────────────────
function showLogin() {
  $('app').classList.remove('visible');
  $('login-page').classList.remove('hidden');
  $('login-username').focus();
}

function showApp() {
  $('login-page').classList.add('hidden');
  $('app').classList.add('visible');
}

$('login-form').addEventListener('submit', async (e) => {
  e.preventDefault();
  const username = $('login-username').value.trim();
  const password = $('login-password').value;
  const errEl    = $('login-error');
  const btn      = $('login-btn');

  errEl.classList.remove('visible');
  btn.disabled = true;
  $('login-btn-text').style.display = 'none';
  $('login-btn-spinner').style.display = '';

  try {
    token = await login(username, password);
    localStorage.setItem('ds_token', token);
    await initApp();
    showApp();
  } catch (err) {
    errEl.textContent = err.message;
    errEl.classList.add('visible');
  } finally {
    btn.disabled = false;
    $('login-btn-text').style.display = '';
    $('login-btn-spinner').style.display = 'none';
  }
});

// ── App init ───────────────────────────────────────────────────
async function initApp() {
  // Fetch user info
  currentUser = await api('GET', '/auth/me');
  $('user-name').textContent = currentUser.username;
  $('user-avatar').textContent = currentUser.username[0].toUpperCase();

  // Load model status into header + settings
  await loadModelStatus();

  // Load session history into sidebar
  await loadSessions();
}

// ── Model status ───────────────────────────────────────────────
async function loadModelStatus() {
  try {
    const status = await api('GET', '/model/status');
    const label = `Scenario ${status.active_scenario} · ${SCENARIO_LABELS[status.active_scenario] || ''} · ${status.active_provider.toUpperCase()} / ${status.active_model}`;
    $('badge-text').textContent = label;

    // Sync settings UI
    $('provider-select').value = status.active_provider;
    populateModelSelect(status.active_provider, status.active_model);
    $('temp-slider').value = status.temperature;
    $('temp-val').textContent = status.temperature.toFixed(2);
    $('mem-slider').value = status.memory_window_size;
    $('mem-val').textContent = status.memory_window_size;
    $('cosine-slider').value = status.cosine_similarity_threshold;
    $('cosine-val').textContent = status.cosine_similarity_threshold.toFixed(2);

    // Scenario cards
    document.querySelectorAll('.scenario-card').forEach(c => {
      c.classList.toggle('active', parseInt(c.dataset.scenario) === status.active_scenario);
    });

    return status;
  } catch {}
}

// ── Sessions ───────────────────────────────────────────────────
async function loadSessions() {
  try {
    const sessions = await api('GET', '/sessions?limit=50');
    renderSessions(sessions);
  } catch {}
}

function renderSessions(sessions) {
  const list = $('sessions-list');
  list.innerHTML = '';
  if (!sessions || sessions.length === 0) {
    list.innerHTML = '<div style="padding:16px;font-size:0.78rem;color:var(--text-muted);text-align:center;">No conversations yet</div>';
    return;
  }
  sessions.forEach(s => {
    const el = document.createElement('div');
    el.className = 'session-item' + (s.id === currentSession ? ' active' : '');
    el.dataset.sessionId = s.id;
    el.innerHTML = `
      <div class="session-icon">💬</div>
      <div class="session-info">
        <div class="session-title" title="${escHtml(s.title)}">${escHtml(s.title)}</div>
        <div class="session-meta">Sc.${s.scenario} · ${s.message_count} msgs</div>
      </div>
      <button class="session-delete-btn" data-sid="${s.id}" title="Delete conversation" aria-label="Delete conversation">🗑</button>
    `;
    el.addEventListener('click', (e) => {
      if (e.target.classList.contains('session-delete-btn')) return;
      resumeSession(s.id, s.title);
    });
    el.querySelector('.session-delete-btn').addEventListener('click', async (e) => {
      e.stopPropagation();
      if (!confirm(`Delete "${s.title}"?`)) return;
      try {
        await api('DELETE', `/sessions/${s.id}`);
        if (currentSession === s.id) { currentSession = null; }
        await loadSessions();
        showToast('Conversation deleted');
      } catch (err) { showToast('Error: ' + err.message); }
    });
    list.appendChild(el);
  });
}

async function resumeSession(sessionId, title) {
  currentSession = sessionId;
  // Load history
  try {
    const detail = await api('GET', `/sessions/${sessionId}`);
    clearMessages();
    detail.messages.forEach(m => {
      if (m.role === 'user') appendUserMessage(m.content, m.created_at);
      else if (m.role === 'assistant') appendBotMessage(m.content, {}, m.created_at);
    });
    // Update active state in sidebar
    document.querySelectorAll('.session-item').forEach(el => {
      el.classList.toggle('active', el.dataset.sessionId === sessionId);
    });
    showToast(`Resumed: ${title}`);
  } catch (err) { showToast('Error loading session: ' + err.message); }
}

// ── Chat ───────────────────────────────────────────────────────
async function sendMessage() {
  const input = $('msg-input');
  const text = input.value.trim();
  if (!text || isWaiting) return;

  isWaiting = true;
  input.value = '';
  autoResize(input);
  $('send-btn').disabled = true;
  $('empty-state').style.display = 'none';

  appendUserMessage(text, new Date().toISOString());
  const typingId = appendTypingIndicator();

  try {
    const body = { message: text };
    if (currentSession) body.session_id = currentSession;

    const res = await api('POST', '/chat', body);

    removeElement(typingId);
    currentSession = res.session_id;

    appendBotMessage(res.response, res, new Date().toISOString());
    await loadSessions();
    await loadModelStatus();
  } catch (err) {
    removeElement(typingId);
    appendErrorMessage(err.message);
  } finally {
    isWaiting = false;
    $('send-btn').disabled = false;
    input.focus();
  }
}

// ── Message rendering ──────────────────────────────────────────
function clearMessages() {
  const container = $('messages-container');
  container.innerHTML = '';
  // Re-add empty state (hidden)
  const es = document.createElement('div');
  es.className = 'empty-state';
  es.id = 'empty-state';
  es.style.display = 'none';
  es.innerHTML = `<div class="empty-state-icon">🌊</div><h3>Start a conversation</h3>`;
  container.appendChild(es);
}

function appendUserMessage(text, time) {
  const container = $('messages-container');
  $('empty-state').style.display = 'none';

  const el = document.createElement('div');
  el.className = 'message user';
  el.innerHTML = `
    <div class="msg-avatar">${currentUser ? currentUser.username[0].toUpperCase() : 'U'}</div>
    <div class="msg-content">
      <div class="msg-bubble">${escHtml(text)}</div>
      <div class="msg-time">${fmt(time)}</div>
    </div>
  `;
  container.appendChild(el);
  scrollBottom();
}

function appendBotMessage(text, meta, time) {
  const container = $('messages-container');
  const el = document.createElement('div');
  el.className = 'message bot';
  el.id = 'msg-' + Date.now();

  // Build badges
  let badges = '';
  if (meta.rule_matched)
    badges += `<span class="badge badge-rule">📋 Rule: ${escHtml(meta.rule_matched)}</span> `;
  if (meta.cached)
    badges += `<span class="badge badge-cached">⚡ Cached</span> `;
  if (meta.scenario)
    badges += `<span class="badge badge-scenario">Sc.${meta.scenario}</span> `;
  if (meta.metadata && meta.metadata.intent)
    badges += `<span class="badge badge-intent">🎯 ${escHtml(meta.metadata.intent)}</span>`;

  // Render markdown
  const htmlContent = renderMarkdown(text);

  // Build table HTML if rows present
  let tableHtml = '';
  if (meta.metadata && meta.metadata.rows && Array.isArray(meta.metadata.rows) && meta.metadata.rows.length > 0) {
    tableHtml = buildTable(meta.metadata.rows, meta.metadata.rows.length);
  }

  // Build chart HTML if chart present
  let chartHtml = '';
  const chartInfo = meta.metadata && meta.metadata.chart;
  if (chartInfo) {
    if (typeof chartInfo === 'object' && chartInfo.png_base64) {
      // Use embedded base64 directly — no separate fetch needed
      chartHtml = buildChartBase64(chartInfo);
    } else {
      // Fallback: fetch via /charts/ endpoint
      const rawChart = typeof chartInfo === 'string' ? chartInfo
        : String(chartInfo.path || chartInfo);
      const filename = rawChart.replace(/^.*[\\\/]/, '');
      chartHtml = buildChartFetch(filename, token);
    }
  }

  // Build metadata drawer
  let metaDrawerHtml = '';
  if (meta.metadata && Object.keys(meta.metadata).length > 0) {
    metaDrawerHtml = buildMetaDrawer(meta.metadata);
  }

  el.innerHTML = `
    <div class="msg-avatar">🤖</div>
    <div class="msg-content">
      ${badges ? `<div style="margin-bottom:8px;display:flex;gap:6px;flex-wrap:wrap;">${badges}</div>` : ''}
      <div class="msg-bubble">${htmlContent}</div>
      ${tableHtml}
      ${chartHtml}
      ${metaDrawerHtml}
      <div class="msg-time">${fmt(time)}</div>
    </div>
  `;

  container.appendChild(el);

  // Wire up meta drawer toggles
  const toggleBtn = el.querySelector('.meta-drawer-toggle');
  if (toggleBtn) {
    toggleBtn.addEventListener('click', () => {
      toggleBtn.classList.toggle('open');
      el.querySelector('.meta-drawer-content').classList.toggle('open');
    });
  }

  // Wire up copy button
  const copyBtn = el.querySelector('.btn-copy');
  if (copyBtn) {
    copyBtn.addEventListener('click', () => {
      const rows = meta.metadata && meta.metadata.rows;
      if (rows) copyTableCSV(rows, copyBtn);
    });
  }

  // Wire up table sorting
  el.querySelectorAll('.data-table th[data-col]').forEach(th => {
    th.addEventListener('click', () => sortTable(th, el));
  });

  // Apply syntax highlighting to code blocks
  el.querySelectorAll('pre code').forEach(block => {
    hljs.highlightElement(block);
  });

  scrollBottom();
}

function appendTypingIndicator() {
  const container = $('messages-container');
  const id = 'typing-' + Date.now();
  const el = document.createElement('div');
  el.className = 'message bot';
  el.id = id;
  el.innerHTML = `
    <div class="msg-avatar">🤖</div>
    <div class="msg-content">
      <div class="msg-bubble">
        <div class="typing-indicator">
          <div class="typing-dot"></div>
          <div class="typing-dot"></div>
          <div class="typing-dot"></div>
        </div>
      </div>
    </div>
  `;
  container.appendChild(el);
  scrollBottom();
  return id;
}

function appendErrorMessage(msg) {
  const container = $('messages-container');
  const el = document.createElement('div');
  el.className = 'message bot';
  el.innerHTML = `
    <div class="msg-avatar">⚠️</div>
    <div class="msg-content">
      <div class="msg-bubble" style="border-color:rgba(239,68,68,0.4);background:rgba(239,68,68,0.08);">
        <strong style="color:#fca5a5;">Error</strong><br/>
        <span style="color:var(--text-secondary);font-size:0.85rem;">${escHtml(msg)}</span>
      </div>
    </div>
  `;
  container.appendChild(el);
  scrollBottom();
}

// ── Rendering helpers ──────────────────────────────────────────
function renderMarkdown(text) {
  if (!text) return '';
  // Strip the markdown table lines (|...|) — we render them as a styled HTML table separately
  // Also strip the chart saved line and trailing metadata summary
  let cleaned = text
    .split('\n')
    .filter(line => {
      const t = line.trim();
      // remove markdown table rows
      if (t.startsWith('|')) return false;
      // remove "📊 Chart saved:" lines
      if (t.startsWith('📊')) return false;
      // remove "_… plus N more rows" lines
      if (t.startsWith('_…')) return false;
      return true;
    })
    .join('\n')
    .trim();
  marked.setOptions({ breaks: true, gfm: true });
  return marked.parse(cleaned);
}

function buildTable(rows, totalRows) {
  if (!rows || rows.length === 0) return '';
  const cols = Object.keys(rows[0]);
  const tableId = 'tbl-' + Date.now();

  const thead = `<tr>${cols.map(c =>
    `<th data-col="${escHtml(c)}" title="${escHtml(c)}">
      ${escHtml(c)} <span class="sort-icon">⇅</span>
    </th>`
  ).join('')}</tr>`;

  const tbody = rows.map(row =>
    `<tr>${cols.map(c => {
      const val = row[c];
      const display = val === null || val === undefined ? '' : String(val);
      return `<td title="${escHtml(display)}">${escHtml(display)}</td>`;
    }).join('')}</tr>`
  ).join('');

  return `
    <div class="data-table-wrapper">
      <div class="data-table-toolbar">
        <div class="data-table-title">
          📊 Results
          <span class="rows-badge">${totalRows} row${totalRows !== 1 ? 's' : ''}</span>
        </div>
        <button class="btn-copy" title="Copy as CSV">📋 Copy CSV</button>
      </div>
      <div class="data-table-scroll">
        <table class="data-table" id="${tableId}">
          <thead>${thead}</thead>
          <tbody>${tbody}</tbody>
        </table>
      </div>
    </div>`;
}

function buildChartBase64(chartInfo) {
  const title = chartInfo.title || 'Chart';
  return `
    <div class="chart-wrapper">
      <div class="chart-header">📈 ${escHtml(title)}</div>
      <img class="chart-img" src="data:image/png;base64,${chartInfo.png_base64}" alt="${escHtml(title)}" />
    </div>`;
}

function buildChartFetch(filename, jwt) {
  const imgId = 'chart-' + Date.now();
  setTimeout(() => loadChartImage(filename, jwt, imgId), 100);
  return `
    <div class="chart-wrapper">
      <div class="chart-header">📈 Chart</div>
      <img class="chart-img" id="${imgId}" src="" alt="Loading chart…" />
    </div>`;
}

async function loadChartImage(filename, jwt, imgId) {
  try {
    const res = await fetch(`${API_BASE}/charts/${filename}`, {
      headers: { Authorization: `Bearer ${jwt}` },
    });
    if (!res.ok) throw new Error('Chart not found');
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const img = document.getElementById(imgId);
    if (img) {
      img.src = url;
      img.alt = filename;
    }
  } catch {
    const img = document.getElementById(imgId);
    if (img) img.alt = 'Chart unavailable';
  }
}

function buildMetaDrawer(meta) {
  const lines = [];
  if (meta.intent)      lines.push({ k: 'Intent', v: String(meta.intent) });
  if (meta.description) lines.push({ k: 'Query',  v: String(meta.description) });
  if (meta.sql)         lines.push({ k: 'SQL',    v: String(meta.sql) });
  if (meta.row_count !== undefined)
                        lines.push({ k: 'Rows',   v: String(meta.row_count) + ' returned' });
  if (meta.chart && typeof meta.chart === 'object' && meta.chart.path)
                        lines.push({ k: 'Chart',  v: String(meta.chart.path) });
  if (!lines.length) return '';

  const rowsHtml = lines.map(l =>
    `<div class="meta-row">
      <span class="meta-key">${escHtml(l.k)}</span>
      <span class="meta-val">${escHtml(l.v)}</span>
    </div>`
  ).join('');

  return `
    <div class="meta-drawer">
      <button class="meta-drawer-toggle">
        <span class="toggle-icon">▶</span> Debug info
      </button>
      <div class="meta-drawer-content">
        ${rowsHtml}
      </div>
    </div>`;
}

// ── Table sorting ──────────────────────────────────────────────
function sortTable(th, msgEl) {
  const col = th.dataset.col;
  const table = th.closest('table');
  const tbody = table.querySelector('tbody');
  const rows = Array.from(tbody.querySelectorAll('tr'));
  const cols = Array.from(th.closest('thead').querySelectorAll('th')).map(h => h.dataset.col);
  const colIdx = cols.indexOf(col);

  const tableId = table.id;
  if (!sortState[tableId]) sortState[tableId] = {};
  const asc = sortState[tableId][col] !== 'asc';
  sortState[tableId][col] = asc ? 'asc' : 'desc';

  // Update sort icons
  th.closest('thead').querySelectorAll('th').forEach(h => {
    h.classList.remove('sorted-asc', 'sorted-desc');
    h.querySelector('.sort-icon').textContent = '⇅';
  });
  th.classList.add(asc ? 'sorted-asc' : 'sorted-desc');
  th.querySelector('.sort-icon').textContent = asc ? '↑' : '↓';

  rows.sort((a, b) => {
    const av = a.cells[colIdx]?.textContent || '';
    const bv = b.cells[colIdx]?.textContent || '';
    const an = parseFloat(av), bn = parseFloat(bv);
    if (!isNaN(an) && !isNaN(bn)) return asc ? an - bn : bn - an;
    return asc ? av.localeCompare(bv) : bv.localeCompare(av);
  });

  rows.forEach(r => tbody.appendChild(r));
}

// ── CSV copy ───────────────────────────────────────────────────
function copyTableCSV(rows, btn) {
  if (!rows || rows.length === 0) return;
  const cols = Object.keys(rows[0]);
  const csv = [
    cols.join(','),
    ...rows.map(r => cols.map(c => {
      const v = String(r[c] ?? '');
      return v.includes(',') || v.includes('"') ? `"${v.replace(/"/g, '""')}"` : v;
    }).join(',')),
  ].join('\n');

  navigator.clipboard.writeText(csv).then(() => {
    btn.textContent = '✅ Copied!';
    btn.classList.add('copied');
    setTimeout(() => {
      btn.textContent = '📋 Copy CSV';
      btn.classList.remove('copied');
    }, 2000);
  }).catch(() => showToast('Copy failed'));
}

// ── DOM utilities ──────────────────────────────────────────────
function removeElement(id) {
  const el = document.getElementById(id);
  if (el) el.remove();
}

function scrollBottom() {
  const c = $('messages-container');
  requestAnimationFrame(() => { c.scrollTop = c.scrollHeight; });
}

function escHtml(str) {
  if (str === null || str === undefined) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

// ── Settings ───────────────────────────────────────────────────
function openSettings() {
  $('settings-overlay').classList.add('open');
  $('settings-drawer').classList.add('open');
}

function closeSettings() {
  $('settings-overlay').classList.remove('open');
  $('settings-drawer').classList.remove('open');
}

function populateModelSelect(provider, selectedModel) {
  const sel = $('model-select');
  sel.innerHTML = '';
  const models = PROVIDER_MODELS[provider] || [];
  models.forEach(m => {
    const opt = document.createElement('option');
    opt.value = m;
    opt.textContent = m;
    if (m === selectedModel) opt.selected = true;
    sel.appendChild(opt);
  });
}

$('provider-select').addEventListener('change', () => {
  populateModelSelect($('provider-select').value, null);
});

// Slider live display
['temp', 'mem', 'cosine'].forEach(id => {
  const slider = $(`${id}-slider`);
  const val    = $(`${id}-val`);
  slider.addEventListener('input', () => {
    val.textContent = parseFloat(slider.value).toFixed(id === 'mem' ? 0 : 2);
  });
});

// Scenario card selection (visual only — applied via "Apply")
let selectedScenario = 1;
document.querySelectorAll('.scenario-card').forEach(card => {
  card.addEventListener('click', () => {
    document.querySelectorAll('.scenario-card').forEach(c => c.classList.remove('active'));
    card.classList.add('active');
    selectedScenario = parseInt(card.dataset.scenario);
  });
});

$('apply-settings-btn').addEventListener('click', async () => {
  const btn = $('apply-settings-btn');
  const statusEl = $('settings-status');
  btn.disabled = true;
  statusEl.textContent = '';

  const body = {
    scenario:                   selectedScenario,
    provider:                   $('provider-select').value,
    model:                      $('model-select').value,
    temperature:                parseFloat($('temp-slider').value),
    memory_window_size:         parseInt($('mem-slider').value),
    cosine_similarity_threshold: parseFloat($('cosine-slider').value),
  };

  try {
    const res = await api('POST', '/model/switch', body);
    statusEl.textContent = '✅ ' + (res.message || 'Settings applied');
    await loadModelStatus();
    setTimeout(() => { statusEl.textContent = ''; }, 3000);
    showToast('Settings updated');
  } catch (err) {
    statusEl.style.color = 'var(--error)';
    statusEl.textContent = '❌ ' + err.message;
    setTimeout(() => { statusEl.style.color = ''; statusEl.textContent = ''; }, 4000);
  } finally {
    btn.disabled = false;
  }
});

// ── Event wiring ───────────────────────────────────────────────
$('send-btn').addEventListener('click', sendMessage);

$('msg-input').addEventListener('keydown', (e) => {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    sendMessage();
  }
});

$('msg-input').addEventListener('input', () => autoResize($('msg-input')));

$('new-chat-btn').addEventListener('click', () => {
  currentSession = null;
  clearMessages();
  $('empty-state').style.display = '';
  document.querySelectorAll('.session-item').forEach(el => el.classList.remove('active'));
  $('msg-input').focus();
});

$('settings-btn').addEventListener('click', openSettings);
$('sidebar-settings-btn').addEventListener('click', openSettings);
$('close-settings-btn').addEventListener('click', closeSettings);
$('settings-overlay').addEventListener('click', closeSettings);

$('logout-btn').addEventListener('click', () => {
  if (confirm('Log out?')) logout();
});

$('theme-toggle').addEventListener('click', () => {
  const current = document.documentElement.dataset.theme;
  setTheme(current === 'dark' ? 'light' : 'dark');
});

// ── Bootstrap ──────────────────────────────────────────────────
(async function bootstrap() {
  // Restore theme
  const savedTheme = localStorage.getItem('ds_theme') || 'dark';
  setTheme(savedTheme);

  // If token exists, try to go straight to app
  if (token) {
    try {
      await initApp();
      showApp();
    } catch {
      // Token may be expired
      token = null;
      localStorage.removeItem('ds_token');
      showLogin();
    }
  } else {
    showLogin();
  }
})();
