## template.py
html_content = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>RCPT Compiler Nuitka</title>
<style>
:root {
  --bg: #0d1117;
  --panel: #161b22;
  --border: #30363d;
  --text: #c9d1d9;
  --text-muted: #8b949e;
  --accent: #58a6ff;
  --accent-glow: rgba(88,166,255,0.25);
  --success: #a5d6a7;
  --mono: 'JetBrains Mono', Menlo, Consolas, monospace;
}

* { box-sizing:border-box; margin:0; padding:0; }

body {
  background:var(--bg);
  color:var(--text);
  font-family: 'Inter', system-ui, sans-serif;
  min-height:100vh;
  display:grid;
  place-items:center;
  padding:20px;
}

.panel {
  width:100%;
  max-width:760px;
  background:var(--panel);
  border-radius:16px;
  border:1px solid var(--border);
  box-shadow:0 10px 30px -10px rgba(0,0,0,0.6), 0 4px 16px rgba(0,0,0,0.4);
  padding:32px;
  transition:transform .2s, box-shadow .2s;
}

.panel:hover { transform:translateY(-2px); box-shadow:0 20px 50px -15px rgba(88,166,255,0.18), 0 8px 24px rgba(0,0,0,0.5); }

.title {
  font-size:1.8rem;
  font-weight:700;
  color:#e6edf3;
  text-align:center;
  margin-bottom:1.8rem;
}

.field { margin-bottom:1.4rem; }
.field label {
  display:block;
  font-size:0.9rem;
  font-weight:500;
  color:var(--text-muted);
  margin-bottom:0.5rem;
}

input, select {
  width:100%;
  padding:0.8rem 1rem;
  border-radius:10px;
  border:1px solid var(--border);
  background:#0d1117;
  color:var(--text);
  font-size:0.95rem;
  transition:all .2s;
}

input:focus, select:focus {
  border-color:var(--accent);
  box-shadow:0 0 0 3px var(--accent-glow);
  outline:none;
}

.actions {
  display:flex;
  gap:12px;
  margin:1.8rem 0;
  flex-wrap:wrap;
}

button {
  flex:1 1 140px;
  padding:0.9rem 1.6rem;
  font-size:0.96rem;
  font-weight:600;
  border-radius:10px;
  cursor:pointer;
  transition:all .2s;
}

button.primary {
  background:linear-gradient(145deg,#5e60ce,#5390d9);
  color:#fff;
  border:none;
}

button.primary:hover { background:linear-gradient(145deg,#6c74ff,#63a0ff); }

button.outline {
  background:transparent;
  color:var(--text-muted);
  border:1px solid var(--border);
}

button.outline:hover {
  background:rgba(48,54,61,0.4);
  color:var(--text);
}

.terminal {
  margin-top:1.8rem;
  background:#0a0d14;
  border:1px solid #21262d;
  border-radius:12px;
  padding:1.2rem 1.4rem;
  min-height:260px;
  max-height:400px;
  overflow-y:auto;
  font-family:var(--mono);
  font-size:0.86rem;
  line-height:1.6;
  color:var(--success);
  white-space:pre-wrap;
  word-break:break-all;
  box-shadow:inset 0 0 16px rgba(88,166,255,0.05);
}

.terminal::-webkit-scrollbar { width:7px; }
.terminal::-webkit-scrollbar-track { background:#0d1117; }
.terminal::-webkit-scrollbar-thumb { background:#30363d; border-radius:4px; }
.terminal::-webkit-scrollbar-thumb:hover { background:#444d56; }

/* ── Modal ── */
.modal {
  position:fixed;
  inset:0;
  background:rgba(0,0,0,0.78);
  display:flex;
  align-items:center;
  justify-content:center;
  z-index:2000;
}

.modal-content {
  background:var(--panel);
  padding:28px;
  border-radius:16px;
  border:1px solid var(--border);
  width:92%;
  max-width:540px;
  max-height:82vh;
  overflow-y:auto;
}

.modal-title {
  font-size:1.45rem;
  margin-bottom:1rem;
  color:#e6edf3;
}

.modal-subtitle {
  color:var(--text-muted);
  font-size:0.92rem;
  margin-bottom:1.4rem;
}

.toggle-all {
  color:var(--accent);
  font-size:0.9rem;
  cursor:pointer;
  margin-bottom:1.2rem;
  display:inline-block;
}

.auth-item {
  margin:12px 0;
  display:flex;
  align-items:center;
  gap:14px;
}

.auth-item input {
  width:18px;
  height:18px;
  accent-color:var(--accent);
}

.auth-item label {
  cursor:pointer;
  color:var(--text);
  font-size:0.98rem;
  word-break:break-all;
}

.modal-buttons {
  margin-top:24px;
  display:flex;
  gap:14px;
  justify-content:flex-end;
}

.modal-buttons button {
  min-width:110px;
  padding:10px 20px;
}
</style>
</head>
<body>

<div class="panel">
  <div class="title">RCPT Compiler Nuitka</div>

  <div class="field"><label>Bot Token</label><input id="token" placeholder="Enter bot token"></div>
  <div class="field"><label>Owner Chat ID</label><input id="chatid" placeholder="e.g. 123456789"></div>
  <div class="field"><label>Ngrok Token</label><input id="ngrok" placeholder="Optional"></div>
  <div class="field">
    <label>Tunnel Provider</label>
    <select id="provider">
      <option>Ngrok</option>
      <option>LocalTunnel</option>
      <option>Cloudflare Tunnel</option>
    </select>
  </div>

  <div class="actions">
    <button class="primary" onclick="runCompile()">Compile Single</button>
    <button class="outline" onclick="openAuthSelector()">Select & Compile Multiple…</button>
    <button class="outline" onclick="clearLog()">Clear Log</button>
  </div>

  <div id="terminal" class="terminal"></div>
</div>

<div id="authModal" class="modal" style="display:none;">
  <div class="modal-content">
    <div class="modal-title">Compile multiple bots</div>
    <div class="modal-subtitle">Select which auth files from <code>auths/</code> to compile:</div>
    <div class="toggle-all" onclick="toggleSelectAll()">Select all / Deselect all</div>
    <div id="authList"></div>
    <div class="modal-buttons">
      <button class="outline" onclick="hideAuthModal()">Cancel</button>
      <button class="primary" onclick="confirmSelected()">Compile Selected</button>
    </div>
  </div>
</div>

<script>
function writeOut(text) {
  const t = document.getElementById('terminal');
  t.innerHTML += text.replace(/</g,'&lt;').replace(/>/g,'&gt;') + '<br>';
  t.scrollTop = t.scrollHeight;
}

function clearLog() {
  document.getElementById('terminal').innerHTML = '';
}

let authFilesCache = [];

function showAuthModal(files) {
  authFilesCache = files;
  const container = document.getElementById('authList');
  container.innerHTML = '';
  if (files.length === 0) {
    container.innerHTML = '<div style="color:var(--text-muted);padding:20px;text-align:center;">No .json files found in auths/</div>';
    return;
  }
  files.forEach(f => {
    const item = document.createElement('div');
    item.className = 'auth-item';
    item.innerHTML = `
      <input type="checkbox" id="a-${f}" value="${f}" checked>
      <label for="a-${f}">${f}</label>
    `;
    container.appendChild(item);
  });
  document.getElementById('authModal').style.display = 'flex';
}

function hideAuthModal() {
  document.getElementById('authModal').style.display = 'none';
}

function toggleSelectAll() {
  const boxes = document.querySelectorAll('#authList input');
  const allChecked = boxes.length === [...boxes].filter(b => b.checked).length;
  boxes.forEach(b => b.checked = !allChecked);
}

async function confirmSelected() {
  const checked = [...document.querySelectorAll('#authList input:checked')];
  const selected = checked.map(el => el.value);
  hideAuthModal();
  if (selected.length === 0) {
    writeOut("[INFO] No auth files selected");
    return;
  }
  writeOut(`→ Starting compilation of ${selected.length} bot(s)`);
  await window.pywebview.api.mass_compile(selected);
}

async function openAuthSelector() {
  const info = await window.pywebview.api.check_auths();
  if (!info.exists || info.files.length === 0) {
    writeOut("[INFO] No .json auth files found in auths/ folder");
    return;
  }
  showAuthModal(info.files);
}

async function runCompile() {
  const t = document.getElementById('token').value.trim();
  const c = document.getElementById('chatid').value.trim();
  const n = document.getElementById('ngrok').value.trim();
  const p = document.getElementById('provider').value;

  const lines = await window.pywebview.api.run_compile(t, c, n, p);
  lines.forEach(l => writeOut(l));
}

async function init() {
  const def = await window.pywebview.api.get_default_auth();
  if (def.token)          document.getElementById('token').value = def.token;
  if (def.chatid)         document.getElementById('chatid').value = def.chatid;
  if (def.ngrok_token)    document.getElementById('ngrok').value = def.ngrok_token;
  if (def.tunnel_provider) document.getElementById('provider').value = def.tunnel_provider;

  document.getElementById('token').addEventListener('input', e =>
    window.pywebview.api.check_token(e.target.value)
  );
}

window.addEventListener('load', init);
</script>
</body>
</html>
"""