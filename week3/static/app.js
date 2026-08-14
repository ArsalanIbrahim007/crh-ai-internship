const $ = s => document.querySelector(s);
const DEPTS = ['Legal','Trading','Risk','HR','Finance','Compliance','IT','General'];
const FMTS  = ['email','pdf','docx','html','csv'];

let session = null, roles = [], picked = { dept:new Set(), fmt:new Set() };

const esc = s => (s||'').replace(/[&<>"]/g, c =>
  ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));

// grounding score -> colour. lime = supported, amber = weak, rose = unsupported.
function gcol(g) {
  if (g === null || g === undefined) return 'var(--ink-faint)';
  if (g >= 0.7) return 'var(--lime)';
  if (g >= 0.4) return 'var(--amber)';
  return 'var(--rose)';
}

function markers(text) {
  return esc(text)
    .replace(/\*\*(.+?)\*\*/g, '<b>$1</b>')
    .replace(/^\s*\*\s+/gm, '• ')
    .replace(/\[(\d{1,2})\]/g,
      (_, n) => `<span class="cm" data-n="${n}">${n}</span>`);
}

// ---------- boot ----------
async function boot() {
  const [h, r] = await Promise.all([
    fetch('/api/health').then(x => x.json()),
    fetch('/api/roles').then(x => x.json()),
  ]);

  $('#cChunks').textContent = h.index.chunks.toLocaleString();
  $('#cParents').textContent = h.index.parents.toLocaleString();
  $('#model').innerHTML = h.models.map(m => `<option>${m}</option>`).join('');

  roles = r.roles;
  $('#role').innerHTML = roles.map(x =>
    `<option value="${x.name}"${x.name === r.default ? ' selected' : ''}>${x.label}</option>`).join('');
  showRole();

  $('#deptChips').innerHTML = DEPTS.map(d =>
    `<span class="chip" data-k="dept" data-v="${d}">${d}</span>`).join('');
  $('#fmtChips').innerHTML = FMTS.map(f =>
    `<span class="chip" data-k="fmt" data-v="${f}">${f}</span>`).join('');

  fetch('/api/corpus').then(x => x.json()).then(c => {
    $('#cDocs').textContent = (c.manifest.documents || 0).toLocaleString();
  });

  session = (await fetch('/api/sessions', { method:'POST' }).then(x => x.json())).session_id;
}

function showRole() {
  const r = roles.find(x => x.name === $('#role').value);
  $('#roleDesc').textContent = r ? r.description : '';
}

// ---------- events ----------
document.addEventListener('click', e => {
  const chip = e.target.closest('.chip');
  if (chip) {
    const set = picked[chip.dataset.k];
    set.has(chip.dataset.v) ? set.delete(chip.dataset.v) : set.add(chip.dataset.v);
    chip.classList.toggle('on');
  }
  const tab = e.target.closest('.tab');
  if (tab) {
    document.querySelectorAll('.tab').forEach(t => t.classList.remove('on'));
    document.querySelectorAll('.pane').forEach(p => p.classList.remove('on'));
    tab.classList.add('on');
    $('#pane-' + tab.dataset.pane).classList.add('on');
    if (tab.dataset.pane === 'analytics') loadAnalytics();
  }
  const cm = e.target.closest('.cm');
  if (cm) {
    const el = document.getElementById('src-' + cm.dataset.n);
    if (el) { el.classList.add('open'); el.scrollIntoView({ behavior:'smooth', block:'center' }); }
  }
  const src = e.target.closest('.src');
  if (src && !e.target.closest('.cm')) src.classList.toggle('open');
});

$('#role').addEventListener('change', showRole);
$('#btnAsk').addEventListener('click', ask);
$('#btnSearch').addEventListener('click', search);
$('#btnNew').addEventListener('click', async () => {
  session = (await fetch('/api/sessions', { method:'POST' }).then(x => x.json())).session_id;
  $('#askOut').innerHTML = '<div class="empty">New conversation started.</div>';
});
$('#q').addEventListener('keydown', e => {
  if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); ask(); }
});
$('#sq').addEventListener('keydown', e => {
  if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); search(); }
});

function payload(query) {
  return {
    query,
    departments: [...picked.dept],
    formats: [...picked.fmt],
    use_reranker: $('#tRerank').checked,
    use_compression: $('#tCompress').checked,
    use_selfquery: $('#tSelfquery').checked,
    model: $('#model').value,
    session_id: session,
  };
}

// ---------- ask ----------
async function ask() {
  const q = $('#q').value.trim();
  if (!q) return;
  $('#btnAsk').disabled = true;
  $('#askOut').innerHTML = '<div class="empty"><span class="spinner"></span> retrieving, reranking, generating, verifying…</div>';

  try {
    const res = await fetch('/api/ask', {
      method:'POST',
      headers:{ 'Content-Type':'application/json', 'X-Role': $('#role').value },
      body: JSON.stringify(payload(q)),
    });
    if (!res.ok) throw new Error((await res.json()).detail || res.statusText);
    renderAnswer(await res.json());
    $('#q').value = '';
  } catch (err) {
    $('#askOut').innerHTML = `<div class="empty">Request failed: ${esc(String(err))}</div>`;
  } finally {
    $('#btnAsk').disabled = false;
  }
}

function renderAnswer(d) {
  const s = d.stats;
  const vclass = s.verdict.startsWith('high') ? 'v-high'
    : s.verdict.startsWith('moderate') ? 'v-mod' : 'v-low';

  const spine = d.sentences.map(x => `
    <div class="spine-row">
      <div class="spine" style="--g-col:${gcol(x.grounding)};background:${gcol(x.grounding)}"></div>
      <div class="sentence${x.flagged ? ' flag' : ''}">${markers(x.text)}<span class="gscore">${
        x.grounding === null ? 'uncited' : x.grounding.toFixed(2)}</span></div>
    </div>`).join('');

  const t = s.timings_ms || {};
  const total = Object.values(t).reduce((a,b) => a+b, 0) || 1;
  const bar = [
    ['retrieval_ms','var(--violet)'], ['compression_ms','var(--violet-lo)'],
    ['generation_ms','var(--lime)'],  ['verification_ms','var(--amber)'],
  ].map(([k,c]) => `<i style="width:${(t[k]||0)/total*100}%;background:${c}" title="${k} ${t[k]||0}ms"></i>`).join('');

  const sq = Object.keys(d.selfquery || {}).length
    ? `<span>self-query → ${esc(JSON.stringify(d.selfquery))}</span>` : '';

  const srcs = d.sources.map(x => `
    <div class="src" id="src-${x.n}">
      <div class="src-head">
        <span class="src-n">${x.n}</span>
        <span class="src-title">${esc(x.title)}</span>
        <span class="tag">${esc(x.department)}</span>
        <span class="tag">${esc(x.fmt)}</span>
        ${x.page ? `<span class="tag">p.${x.page}</span>` : ''}
        <span class="tag">score ${x.retrieval_score}</span>
      </div>
      <div class="src-body">${esc(x.text)}</div>
    </div>`).join('');

  $('#askOut').innerHTML = `
    <div class="answer-card">
      ${spine}
      <div class="verdict-bar">
        <span class="verdict ${vclass}">${esc(s.verdict)}</span>
        <span>confidence <b>${s.confidence}</b></span>
        <span>coverage <b>${(s.citation_coverage*100).toFixed(0)}%</b></span>
        <span>sources <b>${s.sources_used}/${s.sources_offered}</b></span>
        <span>dense ${s.retrieval.dense_hits} · sparse ${s.retrieval.sparse_hits} · overlap ${s.retrieval.overlap}</span>
        <span>${esc(d.model || '')}${d.fell_back ? ' (fallback)' : ''}</span>
        <span>${s.total_ms} ms</span>
        ${sq}
      </div>
      <div class="timings">${bar}</div>
    </div>
    ${srcs || '<div class="empty">No sources cited.</div>'}`;
}

// ---------- search ----------
async function search() {
  const q = $('#sq').value.trim();
  if (!q) return;
  $('#btnSearch').disabled = true;
  $('#searchOut').innerHTML = '<div class="empty"><span class="spinner"></span> searching…</div>';

  try {
    const d = await fetch('/api/search', {
      method:'POST',
      headers:{ 'Content-Type':'application/json', 'X-Role': $('#role').value },
      body: JSON.stringify(payload(q)),
    }).then(x => x.json());

    const rows = d.results.map((r,i) => {
      const delta = r.rank_delta > 0 ? `<span style="color:var(--lime)">▲${r.rank_delta}</span>`
        : r.rank_delta < 0 ? `<span style="color:var(--rose)">▼${-r.rank_delta}</span>`
        : '<span style="color:var(--ink-faint)">—</span>';
      return `<div class="src">
        <div class="src-head">
          <span class="src-n">${i+1}</span>
          <span class="src-title">${esc(r.title || 'untitled')}</span>
          <span class="tag">${esc(r.department)}</span>
          <span class="tag">${esc(r.fmt)}</span>
          <span class="tag">${esc(r.retriever || '')}</span>
          <span class="tag">${r.score}</span>
          <span class="tag">${delta}</span>
        </div>
        <div class="src-body">${esc(r.text)}</div>
      </div>`;
    }).join('');

    $('#searchOut').innerHTML = `
      <div class="answer-card" style="padding:15px 20px">
        <div class="verdict-bar" style="border:0;margin:0;padding:0">
          <span>dense <b>${d.stats.dense_hits}</b></span>
          <span>sparse <b>${d.stats.sparse_hits}</b></span>
          <span>overlap <b>${d.stats.overlap}</b></span>
          <span>deduped <b>${d.stats.deduped ?? 0}</b></span>
          <span>rerank <b>${(d.stats.rerank||{}).latency_ms ?? 0} ms</b></span>
          <span>total <b>${d.stats.total_latency_ms} ms</b></span>
          <span>role <b>${esc(d.role)}</b></span>
        </div>
      </div>${rows}`;
  } catch (err) {
    $('#searchOut').innerHTML = `<div class="empty">Failed: ${esc(String(err))}</div>`;
  } finally {
    $('#btnSearch').disabled = false;
  }
}

// ---------- analytics ----------
async function loadAnalytics() {
  const a = await fetch('/api/analytics').then(x => x.json());
  if (!a.total_queries) {
    $('#anOut').innerHTML = '<div class="empty">No queries recorded yet.</div>';
    return;
  }
  const m = (k, v, lime) => `<div class="metric"><div class="k">${k}</div><div class="v${lime?' lime':''}">${v}</div></div>`;

  $('#anOut').innerHTML = `
    <div class="grid">
      ${m('queries', a.total_queries)}
      ${m('avg confidence', a.avg_confidence, true)}
      ${m('avg coverage', (a.avg_coverage*100).toFixed(0) + '%')}
      ${m('p50 latency', a.p50_ms + 'ms')}
      ${m('p95 latency', a.p95_ms + 'ms')}
      ${m('flagged claims', a.flagged_sentences)}
      ${m('model fallbacks', a.model_fallbacks)}
    </div>
    <div class="group-label">By role</div>
    <table><thead><tr><th>Role</th><th>Queries</th><th>Avg confidence</th></tr></thead><tbody>
      ${a.by_role.map(r => `<tr><td>${esc(r.role||'—')}</td><td>${r.queries}</td><td>${r.confidence}</td></tr>`).join('')}
    </tbody></table>
    <div class="group-label" style="margin-top:24px">Recent queries</div>
    <table><thead><tr><th>Question</th><th>Role</th><th>Conf.</th><th>ms</th><th>Model</th></tr></thead><tbody>
      ${a.recent.map(r => `<tr><td>${esc((r.question||'').slice(0,64))}</td><td>${esc(r.role||'')}</td>
        <td>${(r.confidence||0).toFixed(2)}</td><td>${Math.round(r.total_ms||0)}</td>
        <td>${esc((r.model||'').split('/').pop())}</td></tr>`).join('')}
    </tbody></table>`;
}

boot();