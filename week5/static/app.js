/* ================================================================
   AutonomOps — Dashboard Application Logic
   ================================================================ */

const AGENT_ICONS = {
    ceo: '👔', pm: '📋', researcher: '🔬',
    swe: '💻', qa: '🧪', tech_writer: '📝',
    hitl: '✋',
};

const AGENT_ORDER = ['ceo', 'hitl', 'pm', 'researcher', 'swe', 'qa', 'tech_writer'];

let currentThreadId = null;
let pollInterval = null;

// ── Workflow Launcher ──────────────────────────────────────────

async function startWorkflow() {
    const input = document.getElementById('initiative-input');
    const initiative = input.value.trim();
    if (!initiative) return;

    const runBtn = document.getElementById('run-btn');
    runBtn.disabled = true;
    runBtn.innerHTML = '<span class="btn-icon">⏳</span> Running...';

    setSystemStatus('running', 'Running');
    clearStreamLog();
    resetWorkflowGraph();

    try {
        const res = await fetch('/api/run', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ initiative }),
        });
        const data = await res.json();

        if (data.error) {
            addStreamEntry('system', `Error: ${data.error}`, 0, '');
            setSystemStatus('error', 'Error');
            runBtn.disabled = false;
            runBtn.innerHTML = '<span class="btn-icon">▶</span> Launch Agents';
            return;
        }

        currentThreadId = data.thread_id;
        addStreamEntry('system', `Workflow started. Thread: ${data.thread_id.slice(0, 8)}...`, 0, '');

        // Start polling for state updates
        startPolling(data.thread_id);

    } catch (err) {
        addStreamEntry('system', `Network error: ${err.message}`, 0, '');
        setSystemStatus('error', 'Error');
        runBtn.disabled = false;
        runBtn.innerHTML = '<span class="btn-icon">▶</span> Launch Agents';
    }
}


// ── State Polling ──────────────────────────────────────────────

function startPolling(threadId) {
    if (pollInterval) clearInterval(pollInterval);

    let lastPhase = '';
    let lastMsgCount = 0;

    pollInterval = setInterval(async () => {
        try {
            const res = await fetch(`/api/state/${threadId}`);
            if (!res.ok) return;

            const state = await res.json();
            const phase = state.current_phase || '';
            const messages = state.messages || [];

            // Update workflow graph
            updateWorkflowGraph(phase, state);

            // Add new messages to stream
            if (messages.length > lastMsgCount) {
                for (let i = lastMsgCount; i < messages.length; i++) {
                    const msg = messages[i];
                    addStreamEntry(
                        msg.agent,
                        msg.content,
                        msg.turns,
                        msg.model_used,
                        msg.tool_calls_count,
                    );
                }
                lastMsgCount = messages.length;
            }

            // Update reflection badge
            if (state.reflection_count > 0) {
                document.getElementById('reflection-badge').style.display = 'block';
                document.getElementById('reflection-count').textContent = state.reflection_count;
            }

            // Update workspace
            updateWorkspaceFiles();

            // Check if complete
            if (phase === 'complete') {
                clearInterval(pollInterval);
                pollInterval = null;
                setSystemStatus('success', 'Complete');

                const runBtn = document.getElementById('run-btn');
                runBtn.disabled = false;
                runBtn.innerHTML = '<span class="btn-icon">▶</span> Launch Agents';

                addStreamEntry('system', '✅ Workflow complete! All agents finished.', 0, '');
            }

            // Check if error
            if (phase === 'error' || state.workflow_status === 'error') {
                clearInterval(pollInterval);
                pollInterval = null;
                setSystemStatus('error', 'Error');

                const runBtn = document.getElementById('run-btn');
                runBtn.disabled = false;
                runBtn.innerHTML = '<span class="btn-icon">▶</span> Launch Agents';

                const errMsg = state.workflow_error || 'Unknown error';
                addStreamEntry('system', `❌ Workflow failed: ${errMsg}`, 0, '');
            }

            lastPhase = phase;

        } catch (err) {
            // Silently retry on network errors
        }
    }, 2000);
}


// ── Workflow Graph Updates ──────────────────────────────────────

const PHASE_MAP = {
    'started':          { active: 'ceo' },
    'ceo_complete':     { complete: ['ceo'], active: 'hitl' },
    'awaiting_approval':{ complete: ['ceo'], active: 'hitl' },
    'approved':         { complete: ['ceo', 'hitl'], active: 'pm' },
    'pm_complete':      { complete: ['ceo', 'hitl', 'pm'], active: 'research' },
    'research_complete':{ complete: ['ceo', 'hitl', 'pm', 'research'], active: 'swe' },
    'swe_complete':     { complete: ['ceo', 'hitl', 'pm', 'research', 'swe'], active: 'qa' },
    'qa_complete':      { complete: ['ceo', 'hitl', 'pm', 'research', 'swe', 'qa'], active: 'tech_writer' },
    'docs_complete':    { complete: ['ceo', 'hitl', 'pm', 'research', 'swe', 'qa', 'tech_writer'] },
    'complete':         { complete: ['ceo', 'hitl', 'pm', 'research', 'swe', 'qa', 'tech_writer'] },
};

function updateWorkflowGraph(phase, state) {
    const mapping = PHASE_MAP[phase];
    if (!mapping) return;

    // Reset all nodes
    document.querySelectorAll('.wf-node').forEach(node => {
        node.classList.remove('active', 'complete', 'failed');
        node.querySelector('.node-status').textContent = 'Pending';
    });

    // Mark completed
    (mapping.complete || []).forEach(agent => {
        const node = document.querySelector(`.wf-node[data-agent="${agent}"]`);
        if (node) {
            node.classList.add('complete');
            node.querySelector('.node-status').textContent = 'Done';
        }
    });

    // Mark active
    if (mapping.active) {
        const node = document.querySelector(`.wf-node[data-agent="${mapping.active}"]`);
        if (node) {
            node.classList.add('active');
            node.querySelector('.node-status').textContent = 'Running...';
        }
    }

    // Handle reflection: if QA failed, mark SWE as active again
    if (state && !state.test_passed && state.reflection_count > 0 && phase === 'swe_complete') {
        const qaNode = document.querySelector('.wf-node[data-agent="qa"]');
        if (qaNode) {
            qaNode.classList.remove('complete');
            qaNode.classList.add('active');
            qaNode.querySelector('.node-status').textContent = 'Re-testing...';
        }
    }
}

function resetWorkflowGraph() {
    document.querySelectorAll('.wf-node').forEach(node => {
        node.classList.remove('active', 'complete', 'failed');
        node.querySelector('.node-status').textContent = 'Pending';
    });
    document.getElementById('reflection-badge').style.display = 'none';
}


// ── Stream Log ─────────────────────────────────────────────────

function addStreamEntry(agent, content, turns, model, toolCalls) {
    const log = document.getElementById('stream-log');

    // Remove placeholder
    const ph = log.querySelector('.stream-placeholder');
    if (ph) ph.remove();

    const entry = document.createElement('div');
    entry.className = `stream-entry ${agent}`;

    const icon = AGENT_ICONS[agent] || '🤖';
    const truncated = content.length > 800 ? content.slice(0, 800) + '...' : content;

    entry.innerHTML = `
        <div class="agent-name">${icon} ${agent.toUpperCase()}</div>
        <div class="agent-content">${escapeHtml(truncated)}</div>
        <div class="meta">
            ${turns ? `<span>🔄 ${turns} turns</span>` : ''}
            ${model ? `<span>🧠 ${model}</span>` : ''}
            ${toolCalls ? `<span>🛠️ ${toolCalls} tool calls</span>` : ''}
        </div>
    `;

    log.appendChild(entry);
    log.scrollTop = log.scrollHeight;
}

function clearStreamLog() {
    const log = document.getElementById('stream-log');
    log.innerHTML = '';
}


// ── Workspace Explorer ─────────────────────────────────────────

async function updateWorkspaceFiles() {
    try {
        const res = await fetch('/api/workspace');
        const data = await res.json();
        const container = document.getElementById('workspace-files');

        if (!data.files || data.files.length === 0) {
            container.innerHTML = '<div class="stream-placeholder">No files yet.</div>';
            return;
        }

        container.innerHTML = data.files.map(f => `
            <div class="file-item" onclick="previewFile('${f.path}')">
                <span class="file-name">📄 ${f.path}</span>
                <span class="file-size">${formatBytes(f.size)}</span>
            </div>
        `).join('');

    } catch (err) {
        // silently skip
    }
}

async function previewFile(path) {
    try {
        const res = await fetch(`/api/workspace/${path}`);
        const data = await res.json();

        document.getElementById('preview-filename').textContent = path;
        document.getElementById('preview-content').textContent = data.content;
        document.getElementById('file-preview').style.display = 'block';
    } catch (err) {
        // skip
    }
}

function closePreview() {
    document.getElementById('file-preview').style.display = 'none';
}


// ── Utility ────────────────────────────────────────────────────

function setSystemStatus(type, text) {
    const indicator = document.getElementById('system-status');
    const dot = indicator.querySelector('.status-dot');
    const label = indicator.querySelector('.status-text');

    dot.className = `status-dot ${type}`;
    label.textContent = text;
}

function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}

function formatBytes(bytes) {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
}

function clearAll() {
    document.getElementById('initiative-input').value = '';
    clearStreamLog();
    resetWorkflowGraph();
    document.getElementById('workspace-files').innerHTML =
        '<div class="stream-placeholder">No files yet.</div>';
    closePreview();
    setSystemStatus('idle', 'Idle');

    if (pollInterval) {
        clearInterval(pollInterval);
        pollInterval = null;
    }

    const runBtn = document.getElementById('run-btn');
    runBtn.disabled = false;
    runBtn.innerHTML = '<span class="btn-icon">▶</span> Launch Agents';
}
