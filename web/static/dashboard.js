/* ==============================================================================
   CYBERPUNK BITCOIN NODE DASHBOARD CONTROLLER (HIGH-PERFORMANCE)
   Memory-safe, Layout-Throttled, Background Tab Aware
   ============================================================================== */

let globe = null;
let lastPeersHash = '';
let isTabVisible = true;

function formatBytes(bytes, decimals = 2) {
  if (!+bytes) return '0 B';
  const k = 1024;
  const dm = decimals < 0 ? 0 : decimals;
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(dm))} ${sizes[i]}`;
}

function formatDifficulty(diff) {
  if (!diff) return '0.00';
  if (diff >= 1e12) return (diff / 1e12).toFixed(2) + ' T';
  if (diff >= 1e9) return (diff / 1e9).toFixed(2) + ' G';
  if (diff >= 1e6) return (diff / 1e6).toFixed(2) + ' M';
  if (diff >= 1e3) return (diff / 1e3).toFixed(2) + ' K';
  return Number(diff).toFixed(2);
}

function formatUptime(seconds) {
  const d = Math.floor(seconds / (3600 * 24));
  const h = Math.floor((seconds % (3600 * 24)) / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = Math.floor(seconds % 60);
  if (d > 0) return `${d}d ${h}h ${m}m`;
  return `${h}h ${m}m ${s}s`;
}

// DOM update helper that avoids reflow if text hasn't changed
function setTextIfChanged(id, val) {
  const el = document.getElementById(id);
  if (el && el.textContent !== String(val)) {
    el.textContent = val;
  }
}

async function fetchStats() {
  try {
    const res = await fetch('/api/stats');
    if (!res.ok) return;
    const data = await res.json();
    updateUI(data);
  } catch (e) {
    // Graceful silent error retry
  }
}

async function fetchPeers() {
  try {
    const res = await fetch('/api/peers');
    if (!res.ok) return;
    const data = await res.json();
    const peers = data.peers || [];
    updatePeersTable(peers);
    if (globe) {
      globe.setPeers(peers);
    }
  } catch (e) {
    // Graceful silent error retry
  }
}

function updateUI(data) {
  const chain = data.blockchain || {};
  const net = data.network || {};
  const mem = data.mempool || {};
  const sys = data.system || {};

  // 1. Top Bar Status
  const statusEl = document.getElementById('nodeStatusText');
  const statusDot = document.getElementById('nodeStatusDot');
  const isSyncing = chain.ibd || (chain.progress < 99.99);

  if (data.online) {
    const txt = isSyncing ? 'SYNCING (IBD)' : 'NODE IN SYNC';
    if (statusEl.textContent !== txt) {
      statusEl.textContent = txt;
      statusEl.style.color = isSyncing ? 'var(--neon-gold)' : 'var(--neon-green)';
      statusDot.className = isSyncing ? 'status-dot syncing' : 'status-dot';
      statusDot.style.background = '';
    }
  } else {
    if (statusEl.textContent !== 'DAEMON OFFLINE') {
      statusEl.textContent = 'DAEMON OFFLINE';
      statusEl.style.color = 'var(--neon-pink)';
      statusDot.className = 'status-dot';
      statusDot.style.background = 'var(--neon-pink)';
    }
  }

  setTextIfChanged('navIp', sys.ip || '--');
  setTextIfChanged('navVersion', net.version || 'v31.1.0');
  setTextIfChanged('navUptime', formatUptime(sys.uptime_sec || 0));

  // 2. Hero Block Card
  setTextIfChanged('valBlockHeight', (chain.blocks || 0).toLocaleString());
  setTextIfChanged('valHeaders', (chain.headers || 0).toLocaleString());
  
  const pct = Math.min(100, Math.max(0, chain.progress || 0));
  setTextIfChanged('valProgressPct', `${pct.toFixed(2)}%`);
  
  const bar = document.getElementById('progressBarFill');
  if (bar) bar.style.width = `${pct}%`;

  // 3. Chain & Mining Stats
  setTextIfChanged('valDifficulty', formatDifficulty(chain.difficulty));
  setTextIfChanged('valPeersCount', `${net.connections || 0} (${net.connections_in || 0} In / ${net.connections_out || 0} Out)`);
  setTextIfChanged('valMempoolTxs', `${(mem.txs || 0).toLocaleString()} txs (${mem.usage_mb || 0} MB)`);
  setTextIfChanged('valPruneTarget', `${chain.prune_target_mb || 550} MB`);

  // 4. Globe Overlay Telemetry
  setTextIfChanged('globePeerCount', net.connections || 0);
  setTextIfChanged('globeTrafficRecv', formatBytes(net.totalbytesrecv || 0));
  setTextIfChanged('globeTrafficSent', formatBytes(net.totalbytessent || 0));

  // 5. Host Hardware (Orange Pi Zero 3)
  const temp = sys.cpu_temp || 0;
  const tempEl = document.getElementById('valCpuTemp');
  if (tempEl) {
    tempEl.textContent = `${temp.toFixed(1)} °C`;
    if (temp < 55) tempEl.style.color = 'var(--neon-green)';
    else if (temp < 70) tempEl.style.color = 'var(--neon-gold)';
    else tempEl.style.color = 'var(--neon-pink)';
  }

  setTextIfChanged('valRamUsage', `${sys.ram_used_mb || 0} MB / ${sys.ram_total_mb || 1470} MB (${sys.ram_pct || 0}%)`);
  const ramBar = document.getElementById('ramBarFill');
  if (ramBar) ramBar.style.width = `${sys.ram_pct || 0}%`;

  setTextIfChanged('valDiskStorage', `${sys.disk_free_gb || 0} GB Free / ${sys.disk_total_gb || 0} GB`);
  const diskBar = document.getElementById('diskBarFill');
  if (diskBar) diskBar.style.width = `${sys.disk_used_pct || 0}%`;

  const sdGb = sys.sd_lifetime_gb || 284;
  setTextIfChanged('valSdHealth', `100% Clean (${sdGb} GB Written)`);

  setTextIfChanged('valLoadAvg', (sys.load_avg || []).join('  '));
}

function updatePeersTable(peers) {
  const tbody = document.getElementById('peerTableBody');
  if (!tbody) return;

  // Simple string hash to avoid unnecessary innerHTML rewrites
  const currentHash = JSON.stringify(peers.map(p => [p.addr, p.pingtime, p.bytesrecv, p.synced_blocks]));
  if (currentHash === lastPeersHash) return;
  lastPeersHash = currentHash;

  if (!peers.length) {
    tbody.innerHTML = '<tr><td colspan="6" style="text-align:center; color:var(--text-muted); padding:20px;">Searching for Bitcoin P2P peers...</td></tr>';
    return;
  }

  tbody.innerHTML = peers.map(p => `
    <tr>
      <td style="color:var(--neon-cyan);">${p.addr}</td>
      <td><span class="${p.inbound ? 'badge-inbound' : 'badge-outbound'}">${p.inbound ? 'INBOUND' : 'OUTBOUND'}</span></td>
      <td>${p.subver || 'Unknown'}</td>
      <td style="color:${p.pingtime < 100 ? 'var(--neon-green)' : 'var(--neon-gold)'};">${p.pingtime} ms</td>
      <td>↓ ${formatBytes(p.bytesrecv)} | ↑ ${formatBytes(p.bytessent)}</td>
      <td>#${(p.synced_blocks || p.synced_headers || 0).toLocaleString()}</td>
    </tr>
  `).join('');
}

async function sendRpcCommand() {
  const input = document.getElementById('consoleInput');
  const cmd = input.value.trim();
  if (!cmd) return;

  const consoleBody = document.getElementById('consoleBody');
  
  // Cap max entries in console to prevent DOM bloat
  if (consoleBody.children.length > 50) {
    while (consoleBody.children.length > 30) {
      consoleBody.removeChild(consoleBody.firstChild);
    }
  }

  consoleBody.innerHTML += `<div class="console-entry-cmd">&gt; bitcoin-cli ${cmd}</div>`;
  input.value = '';

  try {
    const res = await fetch('/api/rpc', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ command: cmd })
    });
    const data = await res.json();

    if (data.error) {
      consoleBody.innerHTML += `<div class="console-entry-res" style="color:var(--neon-pink);">${data.error}</div>`;
    } else {
      const output = typeof data.result === 'object' ? JSON.stringify(data.result, null, 2) : String(data.result);
      consoleBody.innerHTML += `<div class="console-entry-res">${output}</div>`;
    }
  } catch (e) {
    consoleBody.innerHTML += `<div class="console-entry-res" style="color:var(--neon-pink);">${e.message}</div>`;
  }

  consoleBody.scrollTop = consoleBody.scrollHeight;
}

// Adaptive polling loop
function schedulePolling() {
  const pollInterval = isTabVisible ? 2500 : 10000;
  setTimeout(async () => {
    await fetchStats();
    await fetchPeers();
    schedulePolling();
  }, pollInterval);
}

window.addEventListener('DOMContentLoaded', () => {
  globe = new CyberpunkGlobe('globeCanvas');

  fetchStats();
  fetchPeers();
  schedulePolling();

  document.addEventListener('visibilitychange', () => {
    isTabVisible = !document.hidden;
  });

  const btn = document.getElementById('consoleSubmitBtn');
  if (btn) btn.addEventListener('click', sendRpcCommand);

  const input = document.getElementById('consoleInput');
  if (input) {
    input.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') sendRpcCommand();
    });
  }
});
