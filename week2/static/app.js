/* Ledger — front end.

   Four jobs: manage conversations, send questions, render answers with footnotes, and
   build the provenance rail. Conversations live in localStorage, so closing the tab does
   not lose them; nothing is sent anywhere except the question and recent history. */

const $ = (id) => document.getElementById(id);

const thread    = $("thread");
const rail      = $("rail");
const composer  = $("composer");
const input     = $("question");
const sendBtn   = $("send");
const sessionsEl = $("sessions");

const STORE_KEY = "ledger-sessions";
const THEME_KEY = "ledger-theme";
const MODEL_KEY = "ledger-model";
const MAX_TURNS = 6;        // exchanges of context sent with each question

let sessions = [];          // [{ id, title, created, turns: [{ q, ts, trace }] }]
let currentId = null;
let entryCount = 0;         // rail numbering within the open conversation
let busy = false;

/* ---------- storage ---------- */

function load() {
  try {
    sessions = JSON.parse(localStorage.getItem(STORE_KEY) || "[]");
  } catch (e) {
    sessions = [];
  }
}

function save() {
  try {
    localStorage.setItem(STORE_KEY, JSON.stringify(sessions));
  } catch (e) {
    // Quota exceeded or private mode. The app keeps working for this session.
    console.warn("Could not save conversations:", e);
  }
}

const current = () => sessions.find((s) => s.id === currentId);

function newSession() {
  const s = { id: Date.now().toString(36), title: "New conversation",
              created: Date.now(), turns: [] };
  sessions.unshift(s);
  currentId = s.id;
  save();
  renderSessions();
  renderThread();
  input.focus();
}

function deleteSession(id, ev) {
  ev.stopPropagation();
  sessions = sessions.filter((s) => s.id !== id);
  if (currentId === id) currentId = sessions[0]?.id ?? null;
  if (!currentId) newSession(); else { save(); renderSessions(); renderThread(); }
}

/* ---------- theme ---------- */

function applyTheme(name) {
  document.documentElement.setAttribute("data-theme", name);
  const next = name === "dark" ? "Light" : "Dark";
  $("theme-label").textContent = next;
  $("theme-toggle").setAttribute("aria-label", `Switch to ${next.toLowerCase()} mode`);
  try { localStorage.setItem(THEME_KEY, name); } catch (e) { /* ignore */ }
}

(function initTheme() {
  let saved = null;
  try { saved = localStorage.getItem(THEME_KEY); } catch (e) { /* ignore */ }
  if (!saved) {
    saved = window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  }
  applyTheme(saved);
})();

$("theme-toggle").addEventListener("click", () => {
  const now = document.documentElement.getAttribute("data-theme");
  applyTheme(now === "dark" ? "light" : "dark");
});

/* ---------- models ---------- */

fetch("/api/models")
  .then((r) => r.json())
  .then(({ models, default: fallback }) => {
    const sel = $("model");
    let saved = null;
    try { saved = localStorage.getItem(MODEL_KEY); } catch (e) { /* ignore */ }

    models.forEach((m) => {
      const o = document.createElement("option");
      o.value = m.id;
      o.textContent = m.label;
      o.title = m.note;
      sel.appendChild(o);
    });
    sel.value = models.some((m) => m.id === saved) ? saved : fallback;
    sel.addEventListener("change", () => {
      try { localStorage.setItem(MODEL_KEY, sel.value); } catch (e) { /* ignore */ }
    });
  })
  .catch(() => { /* the default model is used server side */ });

/* ---------- examples ---------- */

fetch("/api/examples")
  .then((r) => r.json())
  .then(({ examples }) => {
    const box = $("examples");
    if (!box) return;
    examples.forEach((ex) => {
      const b = document.createElement("button");
      b.className = "example" + (/Blocked/i.test(ex.label) ? " danger" : "");
      b.type = "button";
      b.textContent = ex.label;
      b.addEventListener("click", () => { input.value = ex.text; input.focus(); });
      box.appendChild(b);
    });
  })
  .catch(() => {});

/* ---------- helpers ---------- */

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) => (
    { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]
  ));
}

const clock = (ts) =>
  new Date(ts).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });

function relativeDay(ts) {
  const d = new Date(ts), now = new Date();
  const sameDay = d.toDateString() === now.toDateString();
  if (sameDay) return clock(ts);
  return d.toLocaleDateString([], { month: "short", day: "numeric" });
}

/* Minimal markdown. The model writes **bold**, `code` and fenced blocks, and showing the
   raw asterisks looks broken. Deliberately small: escaping happens first, so this only
   ever promotes already-safe text into tags, and there is no link or image handling to
   turn model output into a clickable surface. */
function markdown(safe) {
  return mdTables(safe)
    .replace(/```([\s\S]*?)```/g, (_, code) => `<pre class="md-block">${code.trim()}</pre>`)
    .replace(/`([^`\n]+)`/g, "<code class=\"md-code\">$1</code>")
    .replace(/\*\*([^*\n]+)\*\*/g, "<strong>$1</strong>")
    .replace(/(^|[\s(])\*([^*\n]+)\*(?=[\s.,;:)]|$)/g, "$1<em>$2</em>")
    .replace(/^#{2,4}\s+(.+)$/gm, "<span class=\"md-h\">$1</span>")
    // the model sometimes emits literal <br>, which escaping turned into visible text
    .replace(/&lt;br\s*\/?&gt;/gi, "<br>")
    .replace(/^\s*[-*]\s+(.+)$/gm, "<span class=\"md-li\">$1</span>");
}

/* Pipe tables. The model reaches for these constantly on ranked results, and raw pipes
   are the single ugliest thing in the output. Deliberately forgiving: a header row, an
   optional divider, then rows - no alignment syntax, no nesting. */
function mdTables(text) {
  const lines = text.split("\n");
  const out = [];
  let i = 0;

  const isRow = (l) => l.trim().startsWith("|") && l.includes("|", 1);
  const isDivider = (l) => /^\s*\|[\s|:-]+\|?\s*$/.test(l) && l.includes("-");
  const cells = (l) => l.trim().replace(/^\|/, "").replace(/\|$/, "").split("|")
                        .map((c) => c.trim());

  while (i < lines.length) {
    if (!isRow(lines[i])) { out.push(lines[i]); i += 1; continue; }

    const block = [];
    while (i < lines.length && isRow(lines[i])) { block.push(lines[i]); i += 1; }

    if (block.length < 2) { out.push(...block); continue; }

    const header = cells(block[0]);
    const body = block.slice(isDivider(block[1]) ? 2 : 1)
                      .filter((l) => !isDivider(l))
                      .map(cells);

    const th = header.map((h) => `<th>${h}</th>`).join("");
    const tr = body.map((row) =>
      `<tr>${header.map((_, n) => `<td>${row[n] ?? ""}</td>`).join("")}</tr>`).join("");

    out.push(`<table class="md-table"><thead><tr>${th}</tr></thead><tbody>${tr}</tbody></table>`);
  }
  return out.join("\n");
}

/* Mark every retrieved figure with a footnote pointing into the record.

   Only currency, thousands-separated numbers, decimals and percentages qualify. A bare
   "region 4" needs no provenance, and the lookarounds keep the pattern out of dates - an
   earlier version footnoted the year inside 2024-02-10. */
function withFootnotes(text, entryIds) {
  const safe = escapeHtml(text);
  if (!entryIds.length) return markdown(safe);

  let i = 0;
  const FIGURE = /(?<![\w\-/.])(\$\s?\d[\d,]*(?:\.\d+)?|\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+\.\d+%?|\d+%)(?![\w\-/])/g;

  return markdown(safe.replace(FIGURE, (match) => {
    const id = entryIds[Math.min(i, entryIds.length - 1)];
    i += 1;
    return `${match}<sup class="fn" data-entry="${id}">${id}</sup>`;
  }));
}

function lightEntry(id, on) {
  document.querySelector(`.entry[data-n="${id}"]`)?.classList.toggle("lit", on);
  document.querySelectorAll(`.fn[data-entry="${id}"]`)
          .forEach((f) => f.classList.toggle("lit", on));
}

/* ---------- rendering ---------- */

function renderSessions() {
  sessionsEl.innerHTML = "";
  sessions.forEach((s) => {
    const li = document.createElement("li");
    li.className = "session" + (s.id === currentId ? " active" : "");
    li.innerHTML = `
      <div class="session-body">
        <span class="session-title">${escapeHtml(s.title)}</span>
        <span class="session-time">${relativeDay(s.created)}</span>
      </div>
      <button class="session-del" title="Delete conversation" aria-label="Delete">&times;</button>`;
    li.addEventListener("click", () => {
      if (s.id === currentId) return;
      currentId = s.id;
      renderSessions();
      renderThread();
    });
    li.querySelector(".session-del")
      .addEventListener("click", (e) => deleteSession(s.id, e));
    sessionsEl.appendChild(li);
  });
}

function resetRail() {
  entryCount = 0;
  rail.innerHTML = `<p class="rail-empty">Each tool the copilot runs is logged here with
    its arguments, duration and result size. Hover a footnote in an answer to find the
    entry behind it.</p>`;
  $("record-count").textContent = "no entries";
}

function addEntry(step) {
  entryCount += 1;
  const id = entryCount;

  const el = document.createElement("div");
  el.className = "entry" + (step.error ? " errored" : "");
  el.dataset.n = id;

  const args = JSON.stringify(step.arguments, null, 1);
  const preview = (step.result_preview || "").split("\n").slice(0, 3).join("\n");

  el.innerHTML = `
    <p class="entry-tool">${escapeHtml(step.tool)}</p>
    <pre class="entry-args">${escapeHtml(args)}</pre>
    <div class="entry-meta"><span>${step.seconds}s</span><span>${step.error ? "failed" : "ok"}</span></div>
    <p class="entry-result">${escapeHtml(preview)}</p>`;

  el.addEventListener("mouseenter", () => lightEntry(id, true));
  el.addEventListener("mouseleave", () => lightEntry(id, false));

  rail.querySelector(".rail-empty")?.remove();
  rail.appendChild(el);
  rail.scrollTop = rail.scrollHeight;
  $("record-count").textContent = `${entryCount} ${entryCount === 1 ? "entry" : "entries"}`;
  return id;
}

function addExchange(question, trace, ts) {
  $("opening")?.remove();

  const toolSteps = (trace.steps || []).filter((s) => s.kind === "tool_call");
  const ids = toolSteps.map(addEntry);

  const wrap = document.createElement("article");
  wrap.className = "exchange";

  const refused = trace.blocked;
  const answerHtml = refused
    ? `${escapeHtml(trace.answer)}<span class="refusal-reason">${escapeHtml(trace.block_reason)}</span>`
    : withFootnotes(trace.answer, ids);

  const tokens = (trace.prompt_tokens || 0) + (trace.completion_tokens || 0);

  wrap.innerHTML = `
    <div class="msg-user">
      <p class="asked">${escapeHtml(question)}</p>
      <span class="stamp">${clock(ts)}</span>
    </div>
    <div class="msg-bot">
      <div class="answered${refused ? " refused" : ""}">${answerHtml}</div>
      <div class="exchange-foot">
        <span>${clock(ts)}</span>
        <span>${toolSteps.length} tool ${toolSteps.length === 1 ? "call" : "calls"}</span>
        <span>${trace.total_seconds}s</span>
        <span>${tokens} tokens</span>
        ${trace.model ? `<span>${escapeHtml(trace.model)}</span>` : ""}
        ${trace.hit_step_limit ? "<span>step limit reached</span>" : ""}
      </div>
    </div>`;

  wrap.querySelectorAll(".fn").forEach((f) => {
    const id = Number(f.dataset.entry);
    f.addEventListener("mouseenter", () => lightEntry(id, true));
    f.addEventListener("mouseleave", () => lightEntry(id, false));
    f.addEventListener("click", () => {
      document.querySelector(`.entry[data-n="${id}"]`)
              ?.scrollIntoView({ behavior: "smooth", block: "center" });
    });
  });

  thread.appendChild(wrap);
  thread.scrollTop = thread.scrollHeight;
}

function addNotice(question, ts, html) {
  $("opening")?.remove();
  const wrap = document.createElement("article");
  wrap.className = "exchange";
  wrap.innerHTML = `
    <div class="msg-user">
      <p class="asked">${escapeHtml(question)}</p>
      <span class="stamp">${clock(ts)}</span>
    </div>
    <div class="msg-bot">${html}</div>`;
  thread.appendChild(wrap);
  thread.scrollTop = thread.scrollHeight;
  return wrap;
}

function renderThread() {
  thread.innerHTML = "";
  resetRail();
  const s = current();
  if (!s || !s.turns.length) {
    thread.innerHTML = `
      <div class="opening" id="opening">
        <p class="opening-eyebrow">Read-only access to the company database</p>
        <h2 class="opening-head">Ask about revenue, customers,<br>products or staff.</h2>
        <p class="opening-body">Answers are written from query results, never from memory.
          Each figure carries a footnote to the exact SQL that produced it, shown in the
          record on the right.</p>
        <div class="examples" id="examples"></div>
      </div>`;
    fetch("/api/examples").then((r) => r.json()).then(({ examples }) => {
      const box = $("examples");
      if (!box) return;
      examples.forEach((ex) => {
        const b = document.createElement("button");
        b.className = "example" + (/Blocked/i.test(ex.label) ? " danger" : "");
        b.type = "button";
        b.textContent = ex.label;
        b.addEventListener("click", () => { input.value = ex.text; input.focus(); });
        box.appendChild(b);
      });
    }).catch(() => {});
    return;
  }
  s.turns.forEach((t) => addExchange(t.q, t.trace, t.ts));
}

/* ---------- asking ---------- */

function historyFor(session) {
  const msgs = [];
  session.turns.forEach((t) => {
    if (t.trace.blocked) return;      // a refused turn is not context
    msgs.push({ role: "user", content: t.q });
    msgs.push({ role: "assistant", content: t.trace.answer });
  });
  return msgs.slice(-MAX_TURNS * 2);
}

composer.addEventListener("submit", async (e) => {
  e.preventDefault();
  const question = input.value.trim();
  if (!question || busy) return;

  const session = current();
  if (!session) return;

  busy = true;
  sendBtn.classList.add("busy");
  sendBtn.disabled = true;
  input.value = "";

  const ts = Date.now();

  try {
    const res = await fetch("/api/ask", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        question,
        history: historyFor(session),
        model: $("model").value || undefined,
      }),
    });

    if (res.status === 429) {
      const info = await res.json();
      const alts = (info.alternatives || [])
        .map((m) => `<button data-model="${m.id}">Switch to ${escapeHtml(m.label)}</button>`)
        .join("");
      const node = addNotice(question, ts, `
        <div class="limit-notice">
          <strong>Quota reached.</strong> ${escapeHtml(info.message)}
          <div class="limit-actions">${alts}</div>
        </div>`);
      node.querySelectorAll(".limit-actions button").forEach((b) => {
        b.addEventListener("click", () => {
          $("model").value = b.dataset.model;
          try { localStorage.setItem(MODEL_KEY, b.dataset.model); } catch (e) {}
          input.value = question;
          input.focus();
        });
      });

    } else if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      addNotice(question, ts, `
        <div class="limit-notice"><strong>The request did not complete.</strong>
          ${escapeHtml(body.detail || `Server returned ${res.status}`)}</div>`);

    } else {
      const trace = await res.json();
      addExchange(question, trace, ts);

      session.turns.push({ q: question, ts, trace });
      if (session.turns.length === 1) {
        session.title = question.length > 42 ? question.slice(0, 42) + "…" : question;
      }
      save();
      renderSessions();

      if (trace.usage) {
        $("token-count").textContent = trace.usage.total_tokens.toLocaleString();
      }
    }
  } catch (err) {
    addNotice(question, ts, `
      <div class="limit-notice"><strong>Could not reach the server.</strong>
        Is uvicorn still running?</div>`);
  } finally {
    busy = false;
    sendBtn.classList.remove("busy");
    sendBtn.disabled = false;
    input.focus();
  }
});

$("new-chat").addEventListener("click", newSession);

/* ---------- start ---------- */

load();
if (!sessions.length) {
  newSession();
} else {
  currentId = sessions[0].id;
  renderSessions();
  renderThread();
}
input.focus();
