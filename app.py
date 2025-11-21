# app.py
import os
import uuid
from collections import defaultdict
from flask import Flask, request, Response, jsonify, render_template_string

app = Flask(__name__)

# -----------------------
# CONFIG
# -----------------------
CHUNK_SIZE = 64         # bytes per chunk for simulation
REPLICATION = 3         # number of replicas per chunk
NODES = ["node1", "node2", "node3"]  # virtual nodes
# -----------------------

def chunk_file_bytes(file_bytes, chunk_size=CHUNK_SIZE):
    """Return list of byte chunks."""
    return [file_bytes[i:i+chunk_size] for i in range(0, len(file_bytes), chunk_size)]

def assign_chunks_greedy(num_chunks, nodes=NODES, replication=REPLICATION):
    """
    Greedy fill: each time choose the node with least assigned chunks so far.
    Returns dict node -> list of chunk_ids.
    """
    node_map = {n: [] for n in nodes}
    for cidx in range(num_chunks):
        for _ in range(replication):
            target = min(node_map.keys(), key=lambda n: len(node_map[n]))
            node_map[target].append(f"chunk_{cidx}")
    return node_map

INDEX_HTML = """
<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <title>MiniDFS — Upload visualizer</title>
  <style>
    body { font-family: system-ui, -apple-system, "Segoe UI", Roboto, 14px; padding: 20px; max-width: 900px; }
    table { border-collapse: collapse; width: 100%; margin-top: 10px; }
    th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
    th { background: #f2f2f2; }
    .node { padding: 8px; border-radius: 6px; background: #fafafa; margin-bottom: 6px; }
    .chunk-percent { font-weight: 600; }
    .small { font-size: 0.9em; color: #555; }
    .center { text-align: center; }
    #out { white-space: pre-wrap; background:#fff; border:1px solid #eee; padding:10px; margin-top:8px; }
    button { margin-left: 8px; padding: 6px 10px; }
  </style>
</head>
<body>
  <h2>MiniDFS — Upload visualizer</h2>
  <p class="small">Chunk size: <span id="cfg_chunk">{{ chunk_size }}</span> bytes • Replication: <span id="cfg_rep">{{ replication }}</span></p>

  <form id="uploadForm">
    <input type="file" id="fileInput" name="file" required />
    <button type="submit">Upload & Analyze</button>
  </form>

  <div id="summary" style="display:none;">
    <h3>File summary</h3>
    <p><strong>Name:</strong> <span id="fname"></span> · <strong>Size:</strong> <span id="fsize"></span> bytes</p>
    <p><strong>Total chunks:</strong> <span id="tot_chunks"></span></p>

    <h3>Per-chunk breakdown</h3>
    <table id="chunkTable">
      <thead>
        <tr><th class="center">Chunk ID</th><th>Size (bytes)</th><th>% of file</th><th>Replicated on</th></tr>
      </thead>
      <tbody></tbody>
    </table>

    <h3>Node distribution</h3>
    <div id="nodes"></div>
  </div>

  <div id="out"></div>

<script>
const form = document.getElementById('uploadForm');
form.addEventListener('submit', async (e) => {
  e.preventDefault();
  const f = document.getElementById('fileInput').files[0];
  if (!f) return alert('pick a file first');

  const fd = new FormData();
  fd.append('file', f);

  document.getElementById('out').textContent = 'Uploading...';

  try {
    const resp = await fetch('/upload_json', { method: 'POST', body: fd });
    if (!resp.ok) {
      const text = await resp.text();
      document.getElementById('out').textContent = 'Error: ' + text;
      return;
    }
    const data = await resp.json();
    renderResult(data);
  } catch (err) {
    document.getElementById('out').textContent = 'Upload failed: ' + err;
  }
});

function renderResult(data) {
  document.getElementById('out').textContent = '';
  document.getElementById('summary').style.display = 'block';
  document.getElementById('fname').textContent = data.filename;
  document.getElementById('fsize').textContent = data.file_size;
  document.getElementById('tot_chunks').textContent = data.total_chunks;

  // build chunk table
  const tbody = document.querySelector('#chunkTable tbody');
  tbody.innerHTML = '';
  data.chunks.forEach(ch => {
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td class="center">${ch.id}</td>
      <td>${ch.size}</td>
      <td>${ch.percent.toFixed(2)}%</td>
      <td>${ch.nodes.join(', ')}</td>
    `;
    tbody.appendChild(tr);
  });

  // build node distribution
  const nodesDiv = document.getElementById('nodes');
  nodesDiv.innerHTML = '';
  const nodeMap = data.node_map;
  for (const [node, chs] of Object.entries(nodeMap)) {
    const div = document.createElement('div');
    div.className = 'node';
    const unique = Array.from(new Set(chs));
    div.innerHTML = `<strong>${node}</strong> <span class="small">(${unique.length} chunk refs)</span><br><span>${unique.join(', ') || 'no chunks'}</span>`;
    nodesDiv.appendChild(div);
  }
}
</script>
</body>
</html>
"""

@app.route("/", methods=["GET"])
def index():
    return render_template_string(INDEX_HTML, chunk_size=CHUNK_SIZE, replication=REPLICATION)

@app.route("/health", methods=["GET"])
def health():
    return {"status": "ok"}

@app.route("/upload_json", methods=["POST"])
def upload_json():
    """
    Accepts multipart/form-data with key 'file'.
    Returns JSON describing chunking: per-chunk sizes, percent of file,
    and which nodes hold replicas.
    """
    if 'file' not in request.files:
        return Response("No file provided (use form field 'file').", status=400, mimetype="text/plain")

    f = request.files['file']
    filename = f.filename or f"uploaded_{uuid.uuid4().hex}"
    data = f.read()
    filesize = len(data)

    # 1) chunk
    chunks = chunk_file_bytes(data, CHUNK_SIZE)
    num_chunks = len(chunks)

    # 2) assign replicas (greedy)
    node_map = assign_chunks_greedy(num_chunks)

    # 3) build chunk objects with size and percent
    chunk_to_nodes = defaultdict(list)
    for node, chs in node_map.items():
        for c in chs:
            chunk_to_nodes[c].append(node)

    chunk_list = []
    for idx, ch_bytes in enumerate(chunks):
        cid = f"chunk_{idx}"
        size = len(ch_bytes)
        percent = (size / filesize * 100) if filesize > 0 else 0.0
        nodes_for_chunk = chunk_to_nodes.get(cid, [])
        chunk_list.append({
            "id": cid,
            "index": idx,
            "size": size,
            "percent": percent,
            "nodes": nodes_for_chunk
        })

    # build response
    resp = {
        "filename": filename,
        "file_size": filesize,
        "chunk_size": CHUNK_SIZE,
        "replication": REPLICATION,
        "total_chunks": num_chunks,
        "chunks": chunk_list,
        "node_map": node_map
    }
    return jsonify(resp)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    # debug=False for production-like run
    app.run(host="0.0.0.0", port=port, debug=False)
