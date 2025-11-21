<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width,initial-scale=1" />
  <title>Static Site — Ports & File Sizes</title>
  <style>
    :root{font-family:Inter,system-ui,Segoe UI,Roboto,14px;--muted:#666;--accent:#0366d6}
    body{max-width:980px;margin:28px auto;padding:18px;border-radius:10px}
    h1{margin:0 0 6px;font-size:20px}
    p.lead{color:var(--muted);margin-top:0}
    .meta {display:flex;gap:12px;flex-wrap:wrap;margin:12px 0}
    .card{padding:10px;border:1px solid #e6e6e6;border-radius:8px;background:#fafafa}
    table{width:100%;border-collapse:collapse;margin-top:12px}
    th,td{padding:8px 10px;border-bottom:1px solid #efefef;text-align:left}
    th{background:#f7f7f7;font-weight:600}
    td.size{width:160px;font-family:monospace;text-align:right}
    .small{font-size:0.9em;color:var(--muted)}
    .ok{color:green}
    .err{color:#bb0000}
    footer{margin-top:18px;color:var(--muted);font-size:0.9em}
    button{background:var(--accent);color:#fff;border:0;padding:8px 10px;border-radius:6px;cursor:pointer}
  </style>
</head>
<body>
<a href="present.txt" style="display:none;"></a>

<a href="abstractpre.txt" style="display:none;"></a>
  <h1>Static Diagnostics — Ports & File Sizes</h1>
  <p class="lead">This static page inspects the current origin (host:port) and attempts to fetch file sizes for common files and assets found on the page.</p>

  <div class="meta">
    <div class="card">
      <div><strong>Origin</strong></div>
      <div id="origin" class="small"></div>
    </div>

    <div class="card">
      <div><strong>Detected port</strong></div>
      <div id="port" class="small"></div>
    </div>

    <div class="card">
      <div><strong>Protocol</strong></div>
      <div id="proto" class="small"></div>
    </div>

    <div class="card">
      <div><strong>Auto-scan status</strong></div>
      <div id="status" class="small ok">idle</div>
    </div>
  </div>

  <div>
    <button id="btnScan">Run Scan Now</button>
    <button id="btnRefresh" title="Reload the page">Refresh Page</button>
  </div>

  <table id="filesTable" aria-live="polite">
    <thead>
      <tr>
        <th>File / Resource</th>
        <th>URL</th>
        <th class="size">Size</th>
        <th class="small">Notes</th>
      </tr>
    </thead>
    <tbody></tbody>
    <tfoot>
      <tr>
        <th colspan="2">Total</th>
        <th id="totalSize" class="size">—</th>
        <th class="small"></th>
      </tr>
    </tfoot>
  </table>

  <footer>
    <div class="small">Deploy to any static host. If a server disallows HEAD or cross-origin access, the page will try GET as fallback. Some hosts may block size retrieval for remote or third-party resources.</div>
  </footer>

<script>
(function () {
  const originEl = document.getElementById('origin');
  const portEl = document.getElementById('port');
  const protoEl = document.getElementById('proto');
  const statusEl = document.getElementById('status');
  const tbody = document.querySelector('#filesTable tbody');
  const totalSizeEl = document.getElementById('totalSize');
  const btnScan = document.getElementById('btnScan');
  const btnRefresh = document.getElementById('btnRefresh');

  function human(bytes) {
    if (bytes === null || bytes === undefined) return '—';
    if (bytes === 0) return '0 B';
    const units = ['B','KB','MB','GB','TB'];
    let i = 0;
    let n = bytes;
    while (n >= 1024 && i < units.length-1) { n /= 1024; i++; }
    return `${n.toFixed(n < 10 && i>0 ? 2 : 1)} ${units[i]}`;
  }

  // Show origin & port
  const loc = window.location;
  originEl.textContent = loc.hostname + (loc.port ? ':' + loc.port : '');
  protoEl.textContent = loc.protocol.replace(':','');
  // If port omitted show default
  const portDetected = loc.port || (loc.protocol === 'https:' ? '443' : '80');
  portEl.textContent = portDetected;

  btnRefresh.addEventListener('click', () => location.reload());

  // Candidate files to probe (common static files)
  function gatherCandidatePaths() {
    const candidates = new Set([
      'index.html',
      'favicon.ico',
      'robots.txt',
      'sitemap.xml',
      'styles.css',
      'main.css',
      'app.js',
      'main.js',
      'bundle.js',
      'logo.png',
      'logo.svg'
    ]);

    // also gather assets referenced in the HTML (same-origin relative or absolute)
    // <link>, <script>, <img>, <a rel="preload">, <source>
    const selectors = [
      'link[href]',
      'script[src]',
      'img[src]',
      'source[src]',
      'audio[src]',
      'video[src]'
    ];
    selectors.forEach(sel => {
      document.querySelectorAll(sel).forEach(el => {
        const url = el.getAttribute('href') || el.getAttribute('src');
        if (!url) return;
        // convert to same-origin relative path if it points to same origin
        try {
          const u = new URL(url, window.location.href);
          if (u.origin === window.location.origin) {
            const path = u.pathname + (u.search || '');
            // remove leading slash to probe relative, but keep absolute form too
            candidates.add(path.replace(/^\//,''));
            candidates.add(path);
            candidates.add(u.href);
          } else {
            // add cross-origin URL too (may fail due to CORS)
            candidates.add(u.href);
          }
        } catch(e) {
          // in case URL parsing fails just add raw
          candidates.add(url);
        }
      });
    });

    // always include the current page href
    candidates.add(window.location.pathname.replace(/^\//,'') || 'index.html');
    candidates.add(window.location.href);

    return Array.from(candidates);
  }

  // Try HEAD, fallback to GET and read blob size; returns {size, note}
  async function probeSize(url) {
    // normalize relative urls: if url starts without scheme and without leading slash, prefix with './'
    let probeUrl = url;
    try {
      // convert non-absolute to absolute
      const u = new URL(url, window.location.href);
      probeUrl = u.href;
    } catch (e) {
      // leave as-is
    }

    // Try HEAD
    try {
      const head = await fetch(probeUrl, { method: 'HEAD' });
      if (head.ok) {
        const cl = head.headers.get('content-length');
        if (cl !== null) {
          return { size: Number(cl), note: 'HEAD: content-length' };
        }
        // HEAD OK but no content-length -> try GET
      } else {
        // Not OK (404/403). return error note
        return { size: null, note: `HEAD ${head.status} ${head.statusText}` };
      }
    } catch (err) {
      // HEAD failed (maybe not allowed); fall through to GET attempt
      // (no-op)
    }

    // Try GET and measure blob size
    try {
      const get = await fetch(probeUrl, { method: 'GET' });
      if (!get.ok) {
        return { size: null, note: `GET ${get.status} ${get.statusText}` };
      }
      const blob = await get.blob();
      return { size: blob.size, note: 'GET: measured blob' };
    } catch (err) {
      return { size: null, note: 'fetch error (CORS or network)' };
    }
  }

  async function runScan() {
    statusEl.textContent = 'scanning...';
    statusEl.className = 'small';
    tbody.innerHTML = '';
    totalSizeEl.textContent = '—';

    const candidates = gatherCandidatePaths();
    // de-duplicate while preserving order
    const seen = new Set();
    const list = [];
    for (const p of candidates) {
      if (!p) continue;
      if (seen.has(p)) continue;
      seen.add(p);
      list.push(p);
    }

    let total = 0;
    for (const p of list) {
      // create row placeholder
      const tr = document.createElement('tr');
      const fileCell = document.createElement('td');
      fileCell.textContent = p;
      const urlCell = document.createElement('td');
      const displayUrl = (() => {
        try { return new URL(p, window.location.href).href; } catch(e){ return p; }
      })();
      urlCell.textContent = displayUrl;
      const sizeCell = document.createElement('td');
      sizeCell.className = 'size';
      sizeCell.textContent = '…';
      const noteCell = document.createElement('td');
      noteCell.className = 'small';
      noteCell.textContent = '';

      tr.appendChild(fileCell);
      tr.appendChild(urlCell);
      tr.appendChild(sizeCell);
      tr.appendChild(noteCell);
      tbody.appendChild(tr);

      // probe
      // small delay to avoid hammering servers when many files
      await new Promise(r => setTimeout(r, 80));
      const result = await probeSize(p);
      if (result.size !== null) {
        sizeCell.textContent = result.size + ' B (' + human(result.size) + ')';
        noteCell.textContent = result.note;
        total += result.size;
      } else {
        sizeCell.textContent = '—';
        noteCell.textContent = result.note;
      }
    }

    totalSizeEl.textContent = total ? `${total} B (${human(total)})` : '—';
    statusEl.textContent = 'done';
    statusEl.className = 'small ok';
  }

  // Run automatically after small delay
  setTimeout(runScan, 400);

  btnScan.addEventListener('click', () => {
    runScan();
  });
})();
</script>
</body>
</html>

